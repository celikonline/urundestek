from datetime import timedelta
import httpx
from sqlalchemy import select
from test_portal import clients
from app.config import settings
from app.db import SessionLocal
from app.models import LaunchCode, User, now


def source(monkeypatch, status, payload):
    monkeypatch.setattr(settings, "senseik_api_url", "https://identity.example.test/api")
    real_client = httpx.AsyncClient
    def reply(request):
        assert request.url.path == "/api/v1/identity/me"
        assert request.headers["authorization"] == "Bearer source-token"
        return httpx.Response(status, json=payload)
    monkeypatch.setattr("app.integration.httpx.AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(reply), **kwargs))


def test_source_identity_controls_tenant_and_customer_role(clients, monkeypatch):
    source(monkeypatch, 200, {"userId":"source-user-1","email":"source@example.test","firstName":"Can","lastName":"Yıldız","tenant":{"id":"external-new-firm","slug":"new-firm","name":"Yeni Firma","status":"Active"},"permissions":[],"roles":[{"code":"PlatformAdmin"}]})
    owner=clients[0]
    response=owner.post("/api/v1/auth/launch",headers={"Authorization":"Bearer source-token"})
    assert response.status_code == 200
    code=response.json()["url"].split("#code=")[1]
    session=owner.post("/api/v1/auth/exchange",json={"code":code}).json()
    assert session["tenant"]["slug"] == "new-firm"
    assert session["role"] == "customer"
    assert session["is_staff"] is False
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.external_id=="source-user-1"))
        assert "source-token" not in str(user.__dict__)


def test_source_disabled_user_unauthorized_is_rejected(clients, monkeypatch):
    source(monkeypatch, 401, {"detail":"Disabled source user"})
    assert clients[0].post("/api/v1/auth/launch",headers={"Authorization":"Bearer source-token"}).status_code == 401


def test_source_suspended_tenant_is_rejected(clients, monkeypatch):
    source(monkeypatch, 200, {"userId":"source-user-2","email":"source@example.test","firstName":"Can","lastName":"Yıldız","tenant":{"id":"blocked-firm","slug":"blocked","name":"Kapalı Firma","status":"Suspended"},"permissions":[]})
    assert clients[0].post("/api/v1/auth/launch",headers={"Authorization":"Bearer source-token"}).status_code == 403


def test_expired_launch_code_and_foreign_origin_rejected(clients):
    from app.auth import create_launch_code, digest
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.account=="ayse"))
        code=create_launch_code(db,user)
        db.get(LaunchCode,digest(code)).expires_at=now()-timedelta(seconds=1)
        db.commit()
    assert clients[0].post("/api/v1/auth/exchange",json={"code":code}).status_code == 401
    assert clients[0].post("/api/v1/auth/logout",headers={"Origin":"https://foreign.example.test"}).status_code == 403
