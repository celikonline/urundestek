import os
from datetime import timedelta

os.environ.update(APP_ENV="test", DATABASE_URL=os.getenv("TEST_DATABASE_URL", "sqlite://"), COOKIE_SECURE="false", RUN_REMINDER_WORKER="false")

import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.auth import hash_password
from app.config import settings
from app.db import Base, engine, SessionLocal
from app.models import AuditLog, AuthSession, Notification, Ticket, User, now
from app.retention import purge
from app.seed import seed_demo

PASSWORD = "Guclu-Parola-2026!"


@pytest.fixture()
def staff():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_demo(db)
        admin = db.query(User).filter_by(account="admin").one()
        admin.password_hash = hash_password(PASSWORD)
        db.commit()
    with TestClient(create_app()) as client:
        yield client


def login(client, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": "ece@example.test", "password": password})


def test_login_failures_lock_account_and_are_audited(staff, monkeypatch):
    monkeypatch.setattr(settings, "login_lock_threshold", 3)
    for _ in range(3):
        assert login(staff, "yanlis-parola-123").status_code == 401
    assert login(staff).status_code == 423
    with SessionLocal() as db:
        actions = [row.action for row in db.query(AuditLog).order_by(AuditLog.created_at)]
        assert actions.count("login.failed") == 3 and "login.locked" in actions
        admin = db.query(User).filter_by(account="admin").one()
        admin.locked_until = None
        db.commit()
    response = login(staff)
    assert response.status_code == 200
    staff.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert staff.get("/api/v1/admin/audit").json()["total"] >= 5


def test_password_change_policy_and_session_revocation(staff):
    session = login(staff).json()
    staff.headers["X-CSRF-Token"] = session["csrf_token"]
    with TestClient(create_app()) as other:
        other.headers["X-CSRF-Token"] = login(other).json()["csrf_token"]
        assert other.get("/api/v1/me").status_code == 200
        assert staff.post("/api/v1/auth/password", json={"current_password": "yanlis", "new_password": "Baska-Guclu-Parola-9"}).status_code == 403
        assert staff.post("/api/v1/auth/password", json={"current_password": PASSWORD, "new_password": "kisa"}).status_code == 422
        assert staff.post("/api/v1/auth/password", json={"current_password": PASSWORD, "new_password": "ece-example-test-123"}).status_code == 422
        assert staff.post("/api/v1/auth/password", json={"current_password": PASSWORD, "new_password": "Baska-Guclu-Parola-9"}).status_code == 204
        assert staff.get("/api/v1/me").status_code == 200
        assert other.get("/api/v1/me").status_code == 401
    assert login(staff, PASSWORD).status_code == 401
    assert login(staff, "Baska-Guclu-Parola-9").status_code == 200


def test_idle_staff_session_expires(staff, monkeypatch):
    staff.headers["X-CSRF-Token"] = login(staff).json()["csrf_token"]
    with SessionLocal() as db:
        for row in db.query(AuthSession):
            row.last_seen_at = now() - timedelta(minutes=settings.staff_idle_minutes + 1)
        db.commit()
    assert staff.get("/api/v1/me").status_code == 401
    with SessionLocal() as db:
        assert db.query(AuditLog).filter_by(action="session.idle_expired").count() == 1


def test_audit_requires_platform_admin_and_export_is_logged(staff):
    with TestClient(create_app()) as agent:
        agent.post("/api/v1/auth/demo", json={"account": "agent"})
        assert agent.get("/api/v1/admin/audit").status_code == 403
    staff.headers["X-CSRF-Token"] = login(staff).json()["csrf_token"]
    export = staff.get("/api/v1/admin/audit/export", params={"action": "login.success"})
    assert export.status_code == 200 and export.headers["content-type"].startswith("text/csv")
    assert "Giriş yapıldı" in export.text
    listing = staff.get("/api/v1/admin/audit", params={"action": "audit.export"}).json()
    assert listing["total"] == 1 and listing["items"][0]["label"] == "Denetim kaydı dışa aktarıldı"


def test_staff_deactivation_ends_sessions_and_weak_staff_password_rejected(staff):
    staff.headers["X-CSRF-Token"] = login(staff).json()["csrf_token"]
    assert staff.post("/api/v1/admin/staff", json={"name": "Yeni Görevli", "email": "yeni@example.test", "password": "yeni-example-test1", "role": "support_agent"}).status_code == 422
    with TestClient(create_app()) as agent:
        agent.post("/api/v1/auth/demo", json={"account": "agent"})
        with SessionLocal() as db:
            agent_id = db.query(User).filter_by(account="agent").one().id
        assert staff.patch(f"/api/v1/admin/staff/{agent_id}", json={"active": False}).status_code == 200
        assert agent.get("/api/v1/me").status_code == 401


def test_security_headers_present(staff):
    response = staff.get("/api/v1/health")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Cache-Control"] == "no-store"


def test_retention_purge_removes_old_notifications_and_closed_tickets(staff, monkeypatch):
    monkeypatch.setattr(settings, "closed_ticket_retention_days", 30)
    monkeypatch.setattr(settings, "notification_retention_days", 10)
    with SessionLocal() as db:
        closed = db.query(Ticket).filter_by(status="closed").first()
        closed.updated_at = now() - timedelta(days=31)
        fresh = db.query(Ticket).filter_by(status="open").first()
        owner = db.get(User, fresh.created_by)
        db.add(Notification(tenant_id=fresh.tenant_id, ticket_id=fresh.id, user_id=owner.id, kind="message", text="eski", created_at=now() - timedelta(days=11)))
        db.add(Notification(tenant_id=fresh.tenant_id, ticket_id=fresh.id, user_id=owner.id, kind="message", text="yeni"))
        db.commit()
        closed_id = closed.id
        removed = purge(db)
        assert removed["tickets"] == 1 and removed["notifications"] == 1
        assert db.get(Ticket, closed_id) is None
        assert db.query(Notification).count() == 1
        assert db.query(AuditLog).filter_by(action="retention.purge").count() == 1
