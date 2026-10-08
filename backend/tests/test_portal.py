import os
from datetime import datetime, timedelta, timezone

os.environ.update(APP_ENV="test", DATABASE_URL=os.getenv("TEST_DATABASE_URL", "sqlite://"), COOKIE_SECURE="false", RUN_REMINDER_WORKER="false")

import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.db import Base, engine, SessionLocal
from app.seed import seed_demo
from app.models import Reminder
from app.services import dispatch_reminders


@pytest.fixture()
def clients():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_demo(db)
    with TestClient(create_app()) as owner, TestClient(create_app()) as other, TestClient(create_app()) as agent:
        for client, account in ((owner, "ayse"), (other, "deniz"), (agent, "admin")):
            response = client.post("/api/v1/auth/demo", json={"account": account})
            assert response.status_code == 200
            client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        yield owner, other, agent


def create(client, key="test-unique-1"):
    response = client.post("/api/v1/tickets", headers={"Idempotency-Key": key}, json={"subject": "Bordro raporu açılmıyor", "body": "Ekim ayı bordro raporunu indirirken hata alıyorum.", "category": "payroll", "priority": "normal"})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_idempotency_and_persistence(clients):
    owner, _, _ = clients
    first = create(owner)
    assert create(owner)["id"] == first["id"]
    assert owner.get(f'/api/v1/tickets/{first["id"]}').json()["subject"] == first["subject"]


def test_tenant_cannot_read_write_or_remind_another_ticket(clients):
    owner, other, _ = clients
    ticket = create(owner)
    path = f'/api/v1/tickets/{ticket["id"]}'
    assert ticket["id"] not in [t["id"] for t in other.get("/api/v1/tickets").json()["items"]]
    assert other.get(path).status_code == 404
    assert other.post(path + "/messages", json={"body": "Başka firma mesajı", "version": 1}).status_code == 404
    assert other.post(path + "/reminders", json={"due_at": "2030-01-01T10:00:00Z", "note": "Takip"}).status_code == 404


def test_same_tenant_customer_scope_and_manager(clients):
    owner, _, _ = clients
    ticket = create(owner)
    for account, expected in (("emre", 404), ("manager", 200)):
        with TestClient(create_app()) as client:
            client.post("/api/v1/auth/demo", json={"account": account})
            assert client.get(f'/api/v1/tickets/{ticket["id"]}').status_code == expected


def test_staff_reply_private_note_close_and_reopen(clients):
    owner, _, agent = clients
    ticket = create(owner)
    path = f'/api/v1/tickets/{ticket["id"]}'
    note = agent.post(f'/api/v1/admin/tickets/{ticket["id"]}/notes', json={"body": "Gizli ekip notu", "version": ticket["version"]})
    assert note.status_code == 200, note.text
    reply = agent.post(path + "/messages", json={"body": "Raporu tekrar deneyebilirsiniz.", "version": note.json()["version"]})
    assert reply.json()["status"] == "waiting_customer"
    detail = owner.get(path).json()
    assert "Gizli ekip notu" not in str(detail)
    assert any(m["body"] == "Raporu tekrar deneyebilirsiniz." for m in detail["messages"])
    closed = owner.post(path + "/close", json={"version": detail["version"]})
    assert closed.json()["status"] == "closed"
    assert owner.post(path + "/messages", json={"body": "Yeni mesaj", "version": closed.json()["version"]}).status_code == 409
    assert owner.post(path + "/reopen", json={"version": closed.json()["version"]}).json()["status"] == "open"


def test_stale_version_and_customer_admin_rejected(clients):
    owner, _, _ = clients
    ticket = create(owner)
    path = f'/api/v1/tickets/{ticket["id"]}'
    assert owner.post(path + "/messages", json={"body": "İlk yeni mesaj", "version": 1}).status_code == 200
    assert owner.post(path + "/close", json={"version": 1}).status_code == 409
    assert owner.get("/api/v1/admin/tenants").status_code == 403


def test_followup_throttle(clients):
    owner, _, _ = clients
    ticket = create(owner)
    path = f'/api/v1/tickets/{ticket["id"]}/follow-up'
    assert owner.post(path, json={"version": 1}).status_code == 200
    assert owner.post(path, json={"version": 2}).status_code == 429


def test_due_reminder_once_and_personal_visibility(clients):
    owner, other, agent = clients
    ticket = create(owner)
    reminder = owner.post(f'/api/v1/tickets/{ticket["id"]}/reminders', json={"due_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), "note": "Bordro kontrolü"})
    assert reminder.status_code == 201, reminder.text
    rid = reminder.json()["id"]
    assert rid not in [r["id"] for r in agent.get("/api/v1/reminders").json()]
    assert other.delete(f"/api/v1/reminders/{rid}").status_code == 404
    with SessionLocal() as db:
        db.get(Reminder, rid).due_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        dispatch_reminders(db)
        dispatch_reminders(db)
    notifications = owner.get("/api/v1/notifications").json()
    assert len([n for n in notifications if n["kind"] == "reminder"]) == 1


def test_closed_ticket_cancels_pending_reminder(clients):
    owner, _, _ = clients
    ticket = create(owner)
    reminder = owner.post(f'/api/v1/tickets/{ticket["id"]}/reminders', json={"due_at": "2030-01-01T00:00:00Z", "note": "Kontrol"}).json()
    owner.post(f'/api/v1/tickets/{ticket["id"]}/close', json={"version": 1})
    assert next(r for r in owner.get("/api/v1/reminders").json() if r["id"] == reminder["id"])["status"] == "cancelled"


def test_validation_csrf_and_logout(clients):
    owner, _, _ = clients
    assert owner.post("/api/v1/tickets", json={"subject": " ", "body": "short", "category": "general", "priority": "normal"}).status_code == 422
    del owner.headers["X-CSRF-Token"]
    assert owner.post("/api/v1/auth/logout").status_code == 403
    owner.headers["X-CSRF-Token"] = owner.get("/api/v1/me").json()["csrf_token"]
    assert owner.post("/api/v1/auth/logout").status_code == 204
    assert owner.get("/api/v1/me").status_code == 401


def test_one_time_launch_exchange(clients):
    from app.auth import create_launch_code
    from app.models import User
    owner, _, _ = clients
    with SessionLocal() as db:
        user = db.query(User).filter_by(account="ayse").one()
        code = create_launch_code(db, user)
    with TestClient(create_app()) as fresh:
        assert fresh.post("/api/v1/auth/exchange", json={"code": code}).status_code == 200
        assert fresh.post("/api/v1/auth/exchange", json={"code": code}).status_code == 401


def test_filters_and_staff_management(clients):
    owner, _, agent = clients
    ticket = create(owner)
    assert agent.get("/api/v1/admin/tickets", params={"q": "Bordro", "tenant_id": ticket["tenant_id"]}).json()["total"] >= 1
    tenants = agent.get("/api/v1/admin/tenants").json()
    assert len(tenants) == 2
    assert len(agent.get("/api/v1/admin/staff").json()) >= 1


def test_development_login_disabled_in_production(clients, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "app_env", "production")
    assert clients[0].post("/api/v1/auth/demo", json={"account": "admin"}).status_code == 404


def test_downgraded_manager_loses_reminder_and_notification_metadata(clients):
    from app.models import User, Notification
    owner, _, _ = clients
    ticket = create(owner)
    with TestClient(create_app()) as manager:
        session = manager.post("/api/v1/auth/demo", json={"account": "manager"}).json()
        manager.headers["X-CSRF-Token"] = session["csrf_token"]
        manager.post(f'/api/v1/tickets/{ticket["id"]}/reminders', json={"due_at":"2030-01-01T00:00:00Z", "note":"Başka kullanıcının talebi"})
        with SessionLocal() as db:
            user = db.query(User).filter_by(account="manager").one()
            db.add(Notification(tenant_id=ticket["tenant_id"],ticket_id=ticket["id"],user_id=user.id,kind="message",text="Gizli başlık"))
            user.role = "customer"
            db.commit()
        assert manager.get(f'/api/v1/tickets/{ticket["id"]}').status_code == 404
        assert manager.get("/api/v1/reminders").json() == []
        assert manager.get("/api/v1/notifications").json() == []


def test_reply_to_disabled_assignee_notifies_active_team(clients):
    from app.models import User, Ticket, Notification
    owner, _, _ = clients
    ticket = create(owner)
    with SessionLocal() as db:
        agent = db.query(User).filter_by(account="agent").one()
        agent.active = False
        db.get(Ticket, ticket["id"]).assigned_to = agent.id
        db.commit()
    owner.post(f'/api/v1/tickets/{ticket["id"]}/messages',json={"version":1,"body":"Talebimi tekrar kontrol eder misiniz?"})
    with SessionLocal() as db:
        admin = db.query(User).filter_by(account="admin").one()
        assert db.query(Notification).filter_by(ticket_id=ticket["id"],user_id=admin.id,kind="message").count() == 1
