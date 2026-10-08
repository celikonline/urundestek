import os
from datetime import timedelta

os.environ.update(APP_ENV="test", DATABASE_URL=os.getenv("TEST_DATABASE_URL", "sqlite://"), COOKIE_SECURE="false", RUN_REMINDER_WORKER="false")

import pytest
from fastapi.testclient import TestClient
from app.db import Base, engine, SessionLocal
from app.main import create_app
from app.models import Ticket, now
from app.seed import seed_demo


@pytest.fixture()
def clients():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_demo(db)
    with TestClient(create_app()) as owner, TestClient(create_app()) as admin:
        for client, account in ((owner, "ayse"), (admin, "admin")):
            client.headers["X-CSRF-Token"] = client.post("/api/v1/auth/demo", json={"account": account}).json()["csrf_token"]
        yield owner, admin


def create(client, priority="normal"):
    response = client.post("/api/v1/tickets", headers={"Idempotency-Key": "customer-test-1"}, json={"subject": "Bordro raporu açılmıyor", "body": "Ekim ayı bordro raporunu indirirken hata alıyorum.", "category": "payroll", "priority": priority})
    assert response.status_code == 201, response.text
    return response.json()


def test_response_target_follows_priority_and_first_staff_reply(clients):
    owner, admin = clients
    ticket = create(owner, "urgent")
    target = ticket["response_target"]
    assert target["hours"] == 2 and target["first_response_at"] is None and target["met"] is None
    owner.post(f'/api/v1/tickets/{ticket["id"]}/messages', json={"body": "Ek bilgi: tarayıcı Chrome.", "version": ticket["version"]})
    detail = owner.get(f'/api/v1/tickets/{ticket["id"]}').json()
    assert detail["response_target"]["first_response_at"] is None  # customer messages do not count
    admin.post(f'/api/v1/tickets/{ticket["id"]}/messages', json={"body": "Bakıyoruz.", "version": detail["version"]})
    detail = owner.get(f'/api/v1/tickets/{ticket["id"]}').json()
    assert detail["response_target"]["first_response_at"] and detail["response_target"]["met"] is True
    first = detail["response_target"]["first_response_at"]
    admin.post(f'/api/v1/tickets/{ticket["id"]}/messages', json={"body": "Düzelttik.", "version": detail["version"]})
    assert owner.get(f'/api/v1/tickets/{ticket["id"]}').json()["response_target"]["first_response_at"] == first


def test_late_first_response_is_marked(clients):
    owner, admin = clients
    ticket = create(owner)
    with SessionLocal() as db:
        db.get(Ticket, ticket["id"]).created_at = now() - timedelta(hours=9)
        db.commit()
    admin.post(f'/api/v1/tickets/{ticket["id"]}/messages', json={"body": "Geç yanıt.", "version": ticket["version"]})
    assert owner.get(f'/api/v1/tickets/{ticket["id"]}').json()["response_target"]["met"] is False


def test_rating_only_after_resolution_once_and_by_customer(clients):
    owner, admin = clients
    ticket = create(owner)
    path = f'/api/v1/tickets/{ticket["id"]}/rating'
    assert ticket["can_rate"] is False
    assert owner.post(path, json={"score": 5}).status_code == 409
    admin.patch(f'/api/v1/admin/tickets/{ticket["id"]}', json={"version": ticket["version"], "status": "resolved"})
    assert owner.get(f'/api/v1/tickets/{ticket["id"]}').json()["can_rate"] is True
    assert admin.post(path, json={"score": 5}).status_code == 403
    assert owner.post(path, json={"score": 6}).status_code == 422
    rated = owner.post(path, json={"score": 4, "comment": "Hızlı dönüş, teşekkürler."})
    assert rated.status_code == 200 and rated.json()["rating"] == 4 and rated.json()["can_rate"] is False
    assert owner.post(path, json={"score": 1}).status_code == 409
    staff_view = admin.get(f'/api/v1/tickets/{ticket["id"]}').json()
    assert staff_view["rating"] == 4 and staff_view["rating_comment"] == "Hızlı dönüş, teşekkürler."
    assert any("4/5" in e["label"] for e in staff_view["events"])
    assert any(n["kind"] == "rating" for n in admin.get("/api/v1/notifications").json())


def test_help_search_returns_knowledge_sections(clients):
    owner, _ = clients
    items = owner.get("/api/v1/help", params={"q": "bordro raporu indiremiyorum"}).json()["items"]
    assert items and items[0]["title"] == "Bordro ve raporlar" and items[0]["lines"]
    assert owner.get("/api/v1/help", params={"q": "ab"}).json()["items"] == []
    assert owner.get("/api/v1/help", params={"q": "qqqq zzzz"}).json()["items"] == []
    with TestClient(create_app()) as anonymous:
        assert anonymous.get("/api/v1/help", params={"q": "bordro"}).status_code == 401
