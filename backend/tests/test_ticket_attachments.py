import pytest
from sqlalchemy import func, select
from test_messages import clients, uploads, png
from app.db import SessionLocal
from app.models import Ticket


def create_with_image(client, key="new-ticket-image-1", content=None, subject="Ekran görüntülü destek talebi", body=""):
    return client.post("/api/v1/tickets/with-files", headers={"Idempotency-Key": key},
                       data={"subject": subject, "category": "general", "priority": "normal", "body": body, "body_html": f"<p>{body}</p>"},
                       files=[("files", ("ekran.png", png() if content is None else content, "image/png"))])


def test_create_with_clipboard_image_is_atomic_scoped_and_idempotent(clients, uploads):
    owner, other, agent = clients
    response = create_with_image(owner)
    assert response.status_code == 201, response.text
    ticket = response.json()
    assert len(ticket["messages"]) == 1
    attachment = ticket["messages"][0]["attachments"][0]
    assert ticket["messages"][0]["body"] == ""
    assert owner.get(f'/api/v1/attachments/{attachment["id"]}').content == png()
    assert agent.get(f'/api/v1/attachments/{attachment["id"]}').status_code == 200
    assert other.get(f'/api/v1/attachments/{attachment["id"]}').status_code == 404
    assert create_with_image(owner).json()["id"] == ticket["id"]
    assert len(list(uploads.iterdir())) == 1
    assert owner.get(f'/api/v1/tickets/{ticket["id"]}').json()["messages"][0]["attachments"] == [attachment]


def test_invalid_initial_file_fields_and_staff_create_nothing(clients, uploads):
    owner, _, agent = clients
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(Ticket))
    assert create_with_image(owner, content=b"fake image").status_code == 422
    assert create_with_image(owner, subject="x").status_code == 422
    assert create_with_image(agent).status_code == 403
    assert not list(uploads.iterdir())
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Ticket)) == before


def test_initial_storage_failure_rolls_back_ticket(clients, uploads, monkeypatch):
    owner, _, _ = clients
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(Ticket))

    def failed_storage(db, ticket, message, files, written):
        path = uploads / "partial"
        written.append(path)
        path.write_bytes(b"partial")
        raise OSError("disk unavailable")

    monkeypatch.setattr("app.services.store_files", failed_storage)
    with pytest.raises(OSError):
        create_with_image(owner)
    assert not list(uploads.iterdir())
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Ticket)) == before


def test_rich_opening_text_is_sanitized_and_short_empty_text_rejected(clients):
    owner, _, _ = clients
    payload = {"subject": "Biçimli ilk açıklama", "body_html": '<p onclick="evil()"><strong>İlk talep açıklaması</strong></p><script>evil()</script>', "category": "general", "priority": "normal"}
    response = owner.post("/api/v1/tickets", headers={"Idempotency-Key": "rich-opening-1"}, json=payload)
    assert response.status_code == 201, response.text
    opening = response.json()["messages"][0]
    assert opening["body"] == "İlk talep açıklaması"
    assert "<strong>" in opening["body_html"]
    assert "evil" not in opening["body_html"]
    assert owner.post("/api/v1/tickets", headers={"Idempotency-Key": "empty-opening-1"}, json={**payload, "body_html": "<p></p>"}).status_code == 422
    assert owner.post("/api/v1/tickets", headers={"Idempotency-Key": "short-opening-1"}, json={**payload, "body_html": "<p>Kısa</p>"}).status_code == 422
