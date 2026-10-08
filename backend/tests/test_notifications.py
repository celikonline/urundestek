import os
from datetime import datetime, timedelta, timezone

os.environ.update(APP_ENV="test", DATABASE_URL=os.getenv("TEST_DATABASE_URL", "sqlite://"), COOKIE_SECURE="false", RUN_REMINDER_WORKER="false")

import pytest
from fastapi.testclient import TestClient
from app import mailer
from app.config import settings
from app.db import Base, engine, SessionLocal
from app.main import create_app
from app.models import OutboundEmail, Reminder, User
from app.seed import seed_demo
from app.services import dispatch_reminders


@pytest.fixture()
def clients(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    monkeypatch.setattr(settings, "mail_from", "destek@example.test")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_demo(db)
    with TestClient(create_app()) as owner, TestClient(create_app()) as admin:
        for client, account in ((owner, "ayse"), (admin, "admin")):
            client.headers["X-CSRF-Token"] = client.post("/api/v1/auth/demo", json={"account": account}).json()["csrf_token"]
        yield owner, admin


def create(client):
    response = client.post("/api/v1/tickets", headers={"Idempotency-Key": "mail-test-1"}, json={"subject": "Bordro raporu açılmıyor", "body": "Ekim ayı bordro raporunu indirirken hata alıyorum.", "category": "payroll", "priority": "normal"})
    assert response.status_code == 201, response.text
    return response.json()


def queued():
    with SessionLocal() as db:
        return [(db.get(User, row.user_id).account, row.kind, row.subject, row.body) for row in db.query(OutboundEmail).order_by(OutboundEmail.created_at)]


def test_staff_reply_queues_short_customer_email_with_link(clients):
    owner, admin = clients
    ticket = create(owner)
    assert any(kind == "ticket" and account in {"admin", "agent"} for account, kind, _, _ in queued())
    admin.post(f'/api/v1/tickets/{ticket["id"]}/messages', json={"body": "Raporu düzelttik, tekrar deneyebilirsiniz.", "version": ticket["version"]})
    rows = [row for row in queued() if row[0] == "ayse"]
    assert len(rows) == 1
    account, kind, subject, body = rows[0]
    assert subject.startswith(f'[SenseİK Destek] #{ticket["number"]}')
    assert f'/?talep={ticket["id"]}' in body
    assert "Raporu düzelttik" not in body  # message bodies stay inside the portal


def test_preference_off_and_disabled_mail_skip_queue(clients, monkeypatch):
    owner, admin = clients
    ticket = create(owner)
    assert owner.patch("/api/v1/me/preferences", json={"email_notifications": False}).json()["email_notifications"] is False
    admin.post(f'/api/v1/tickets/{ticket["id"]}/messages', json={"body": "İlk yanıt", "version": ticket["version"]})
    assert not [row for row in queued() if row[0] == "ayse"]
    owner.patch("/api/v1/me/preferences", json={"email_notifications": True})
    monkeypatch.setattr(settings, "smtp_host", "")
    detail = owner.get(f'/api/v1/tickets/{ticket["id"]}').json()
    admin.post(f'/api/v1/tickets/{ticket["id"]}/messages', json={"body": "İkinci yanıt", "version": detail["version"]})
    assert not [row for row in queued() if row[0] == "ayse"]


def test_delivery_marks_sent_and_retries_failures(clients, monkeypatch):
    owner, admin = clients
    ticket = create(owner)
    admin.post(f'/api/v1/tickets/{ticket["id"]}/messages', json={"body": "Yanıt", "version": ticket["version"]})
    delivered = []
    monkeypatch.setattr(mailer, "deliver", lambda recipient, subject, body: delivered.append(recipient))
    with SessionLocal() as db:
        assert mailer.send_pending(db) == len(delivered) > 0
        assert all(row.status == "sent" and row.sent_at for row in db.query(OutboundEmail))

    def broken(recipient, subject, body):
        raise ConnectionRefusedError("smtp down")
    monkeypatch.setattr(mailer, "deliver", broken)
    with SessionLocal() as db:
        row = OutboundEmail(tenant_id=ticket["tenant_id"], ticket_id=ticket["id"], user_id=db.query(User).filter_by(account="ayse").one().id, kind="message", subject="Deneme", body="Deneme")
        db.add(row)
        db.commit()
        for _ in range(3):
            mailer.send_pending(db)
        db.refresh(row)
        assert row.status == "failed" and row.attempts == 3 and "ConnectionRefusedError" in row.last_error
        failed_id = row.id
    queue = admin.get("/api/v1/admin/mail-queue").json()
    assert queue["counts"]["failed"] == 1 and queue["items"][0]["id"] == failed_id
    assert admin.post(f"/api/v1/admin/mail-queue/{failed_id}/retry").status_code == 204
    assert admin.get("/api/v1/admin/mail-queue").json()["counts"]["pending"] == 1
    assert owner.get("/api/v1/admin/mail-queue").status_code == 403


def test_due_reminder_queues_email_once(clients):
    owner, _ = clients
    ticket = create(owner)
    rid = owner.post(f'/api/v1/tickets/{ticket["id"]}/reminders', json={"due_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), "note": "Bordro kontrolü"}).json()["id"]
    with SessionLocal() as db:
        db.get(Reminder, rid).due_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        dispatch_reminders(db)
        dispatch_reminders(db)
    assert len([row for row in queued() if row[1] == "reminder"]) == 1


def test_assignment_notifies_assignee(clients):
    owner, admin = clients
    ticket = create(owner)
    with SessionLocal() as db:
        agent_id = db.query(User).filter_by(account="agent").one().id
    assert admin.patch(f'/api/v1/admin/tickets/{ticket["id"]}', json={"version": ticket["version"], "assigned_to": agent_id}).status_code == 200
    assert any(account == "agent" and kind == "assignment" for account, kind, _, _ in queued())
