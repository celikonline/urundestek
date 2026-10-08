import os
from datetime import timedelta

os.environ.update(APP_ENV="test", DATABASE_URL=os.getenv("TEST_DATABASE_URL", "sqlite://"), COOKIE_SECURE="false", RUN_REMINDER_WORKER="false", ANTHROPIC_API_KEY="test-key")

import pytest
from fastapi.testclient import TestClient
from app import ai
from app.config import settings
from app.db import Base, engine, SessionLocal
from app.main import create_app
from app.models import AiJob, AuditLog, Notification, Tenant, Ticket, TicketEvent, now
from app.seed import seed_demo


def verdict(**overrides):
    base = dict(reply="Merhaba, raporu şu adımlarla deneyin:\n\n1. Dönemi seçin.\n2. Beş dakika bekleyin.", confidence=0.9, needs_human=False, reason="Bilgi bankasında adımlar var.", category="payroll", priority="normal", customer_confirms_resolved=False)
    base.update(overrides)
    return ai.Verdict(**base)


@pytest.fixture()
def clients(monkeypatch):
    monkeypatch.setattr(settings, "ai_mode", "auto")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_demo(db)
    with TestClient(create_app()) as owner, TestClient(create_app()) as admin:
        for client, account in ((owner, "ayse"), (admin, "admin")):
            client.headers["X-CSRF-Token"] = client.post("/api/v1/auth/demo", json={"account": account}).json()["csrf_token"]
        yield owner, admin


def create(client, key="ai-test-1", category="general"):
    response = client.post("/api/v1/tickets", headers={"Idempotency-Key": key}, json={"subject": "Bordro raporu açılmıyor", "body": "Ekim ayı bordro raporunu indirirken hata alıyorum.", "category": category, "priority": "normal"})
    assert response.status_code == 201, response.text
    return response.json()


def run_jobs(monkeypatch, result):
    calls = []

    def fake(system_text, user_text):
        calls.append((system_text, user_text))
        return result
    monkeypatch.setattr(ai, "analyze", fake)
    with SessionLocal() as db:
        ai.process_ai_jobs(db)
    return calls


def test_auto_mode_replies_triages_and_notifies_customer(clients, monkeypatch):
    owner, admin = clients
    ticket = create(owner)
    calls = run_jobs(monkeypatch, verdict(priority="high"))
    assert len(calls) == 1 and "Bilgi bankası" in calls[0][0] and "bordro raporunu" in calls[0][1]
    detail = owner.get(f'/api/v1/tickets/{ticket["id"]}').json()
    assert detail["status"] == "waiting_customer" and detail["category"] == "payroll" and detail["priority"] == "high"
    reply = detail["messages"][-1]
    assert reply["author_role"] == "assistant" and reply["kind"] == "support" and "<p>" in reply["body_html"]
    assert any(n["kind"] == "message" for n in owner.get("/api/v1/notifications").json())
    with SessionLocal() as db:
        assert db.query(AuditLog).filter_by(action="ai.reply").count() == 1
        assert db.query(AiJob).one().status == "done"


def test_draft_mode_and_low_confidence_produce_internal_note_only(clients, monkeypatch):
    owner, admin = clients
    with SessionLocal() as db:
        tenant = db.query(Tenant).filter_by(slug="atlas").one()
        tenant.ai_mode = "draft"
        db.commit()
    ticket = create(owner)
    run_jobs(monkeypatch, verdict())
    customer_view = owner.get(f'/api/v1/tickets/{ticket["id"]}').json()
    assert customer_view["status"] == "open" and all(m["author_role"] != "assistant" for m in customer_view["messages"])
    staff_view = admin.get(f'/api/v1/tickets/{ticket["id"]}').json()
    note = staff_view["messages"][-1]
    assert note["kind"] == "internal" and note["author_role"] == "assistant" and "Önerilen yanıt" in note["body"]
    assert any(n["kind"] == "ai" for n in admin.get("/api/v1/notifications").json())
    with SessionLocal() as db:
        tenant.ai_mode = "auto"
        db.merge(tenant)
        db.commit()
    second = create(owner, "ai-test-2")
    run_jobs(monkeypatch, verdict(confidence=0.3))
    assert owner.get(f'/api/v1/tickets/{second["id"]}').json()["status"] == "open"


def test_needs_human_and_reply_limit_hand_off_to_staff(clients, monkeypatch):
    owner, admin = clients
    monkeypatch.setattr(settings, "ai_max_auto_replies", 1)
    ticket = create(owner)
    run_jobs(monkeypatch, verdict())
    detail = owner.get(f'/api/v1/tickets/{ticket["id"]}').json()
    assert detail["status"] == "waiting_customer"
    owner.post(f'/api/v1/tickets/{ticket["id"]}/messages', json={"body": "Hâlâ aynı hatayı alıyorum.", "version": detail["version"]})
    run_jobs(monkeypatch, verdict())
    detail = admin.get(f'/api/v1/tickets/{ticket["id"]}').json()
    assert detail["status"] == "open" and detail["messages"][-1]["kind"] == "internal" and "sınırı doldu" in detail["messages"][-1]["body"]
    owner.post(f'/api/v1/tickets/{ticket["id"]}/messages', json={"body": "Bir insanla görüşmek istiyorum.", "version": detail["version"]})
    run_jobs(monkeypatch, verdict(needs_human=True, reason="Müşteri temsilci istedi."))
    with SessionLocal() as db:
        assert db.query(TicketEvent).filter(TicketEvent.label.contains("insan desteği")).count() == 1


def test_customer_confirmation_resolves_and_stale_job_skipped(clients, monkeypatch):
    owner, admin = clients
    ticket = create(owner)
    run_jobs(monkeypatch, verdict())
    detail = owner.get(f'/api/v1/tickets/{ticket["id"]}').json()
    owner.post(f'/api/v1/tickets/{ticket["id"]}/messages', json={"body": "Teşekkürler, çözüldü.", "version": detail["version"]})
    run_jobs(monkeypatch, verdict(customer_confirms_resolved=True, reply="Rica ederiz, iyi çalışmalar."))
    detail = owner.get(f'/api/v1/tickets/{ticket["id"]}').json()
    assert detail["status"] == "resolved" and any("Çözüldü" in e["label"] for e in detail["events"])
    owner.post(f'/api/v1/tickets/{ticket["id"]}/reopen', json={"version": detail["version"]}) if detail["status"] == "closed" else None
    detail = owner.get(f'/api/v1/tickets/{ticket["id"]}').json()
    owner.post(f'/api/v1/tickets/{ticket["id"]}/messages', json={"body": "Aslında tekrar bozuldu.", "version": detail["version"]})
    detail = owner.get(f'/api/v1/tickets/{ticket["id"]}').json()
    admin.post(f'/api/v1/tickets/{ticket["id"]}/messages', json={"body": "Bakıyoruz.", "version": detail["version"]})
    calls = run_jobs(monkeypatch, verdict())
    assert calls == []
    with SessionLocal() as db:
        assert db.query(AiJob).filter_by(status="skipped").count() == 1


def test_refusal_and_errors_escalate_without_customer_message(clients, monkeypatch):
    owner, admin = clients
    ticket = create(owner)
    run_jobs(monkeypatch, None)
    assert admin.get(f'/api/v1/tickets/{ticket["id"]}').json()["status"] == "open"
    assert any("yanıt üretemedi" in n["text"] for n in admin.get("/api/v1/notifications").json())
    second = create(owner, "ai-test-3")

    def broken(system_text, user_text):
        raise RuntimeError("api down")
    monkeypatch.setattr(ai, "analyze", broken)
    with SessionLocal() as db:
        for _ in range(3):
            ai.process_ai_jobs(db)
        job = db.query(AiJob).filter_by(ticket_id=second["id"]).one()
        assert job.status == "failed" and job.attempts == 3
    assert owner.get(f'/api/v1/tickets/{second["id"]}').json()["status"] == "open"


def test_off_mode_queues_nothing_and_admin_can_switch_tenant_mode(clients, monkeypatch):
    owner, admin = clients
    monkeypatch.setattr(settings, "ai_mode", "off")
    create(owner)
    with SessionLocal() as db:
        assert db.query(AiJob).count() == 0
    monkeypatch.setattr(settings, "ai_mode", "draft")
    tenants = admin.get("/api/v1/admin/tenants").json()
    atlas = next(t for t in tenants if t["slug"] == "atlas")
    assert atlas["ai_mode"] == "inherit" and atlas["ai_effective"] == "draft"
    assert admin.patch(f'/api/v1/admin/tenants/{atlas["id"]}', json={"ai_mode": "auto"}).json()["ai_effective"] == "auto"
    assert admin.patch(f'/api/v1/admin/tenants/{atlas["id"]}', json={"ai_mode": "sahte"}).status_code == 422
    assert admin.get("/api/v1/admin/settings").json()["ai_available"] is True
    assert owner.get("/api/v1/admin/settings").status_code == 403


def test_resolved_tickets_auto_close_after_period(clients, monkeypatch):
    owner, admin = clients
    monkeypatch.setattr(settings, "auto_close_days", 7)
    ticket = create(owner)
    admin.patch(f'/api/v1/admin/tickets/{ticket["id"]}', json={"version": ticket["version"], "status": "resolved"})
    with SessionLocal() as db:
        row = db.get(Ticket, ticket["id"])
        row.updated_at = now() - timedelta(days=8)
        db.commit()
        assert ai.auto_close_resolved(db) == 1
    detail = owner.get(f'/api/v1/tickets/{ticket["id"]}').json()
    assert detail["status"] == "closed" and any("otomatik" in e["label"].lower() or "yanıt gelmedi" in e["label"] for e in detail["events"])
    assert any("kapatıldı" in n["text"] for n in owner.get("/api/v1/notifications").json())
    assert owner.post(f'/api/v1/tickets/{ticket["id"]}/reopen', json={"version": detail["version"]}).json()["status"] == "open"
