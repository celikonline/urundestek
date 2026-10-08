from io import BytesIO
from PIL import Image
import pytest
from test_portal import clients, create
from app.config import settings


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    return tmp_path


def png():
    stream = BytesIO()
    Image.new("RGB", (20, 20), "navy").save(stream, "PNG")
    return stream.getvalue()


def upload(client, ticket, files, internal=False, body="", html=""):
    prefix = "/admin" if internal else ""
    kind = "notes" if internal else "messages"
    return client.post(f'/api/v1{prefix}/tickets/{ticket["id"]}/{kind}/with-files',
                       data={"version": ticket["version"], "body": body, "body_html": html}, files=files)


def test_rich_text_sanitizes_and_derives_plain_body(clients):
    owner, _, _ = clients
    ticket = create(owner)
    response = owner.post(f'/api/v1/tickets/{ticket["id"]}/messages', json={"version": 1, "body": "faked", "body_html": '<p onclick="alert(1)"><strong>Kalın yanıt</strong></p><script>alert(1)</script><a href="javascript:alert(1)">Bağlantı</a><img src="https://tracker.test/pixel">'})
    assert response.status_code == 200, response.text
    message = response.json()["messages"][-1]
    assert "Kalın yanıt" in message["body"] and "faked" not in message["body"]
    assert "<strong>Kalın yanıt</strong>" in message["body_html"]
    for unsafe in ("onclick", "script", "javascript:", "<img", "alert(1)"):
        assert unsafe not in message["body_html"]


def test_file_only_message_persists_and_authorizes_download(clients, uploads):
    owner, other, agent = clients
    ticket = create(owner)
    image = png()
    response = upload(owner, ticket, [("files", ("ekran.png", image, "image/png")), ("files", ("bilgi.txt", "Açıklama".encode(), "text/plain"))])
    assert response.status_code == 200, response.text
    message = response.json()["messages"][-1]
    assert len(message["attachments"]) == 2
    for item in message["attachments"]:
        path = f'/api/v1/attachments/{item["id"]}'
        assert other.get(path).status_code == 404
        assert agent.get(path).status_code == 200
        downloaded = owner.get(path)
        assert downloaded.status_code == 200
        assert "attachment" in downloaded.headers["content-disposition"]
        assert owner.get(path + "?preview=true").status_code == 200
    assert owner.get(f'/api/v1/tickets/{ticket["id"]}').json()["messages"][-1]["attachments"] == message["attachments"]
    assert len(list(uploads.iterdir())) == 2


def test_internal_attachment_is_hidden_and_customer_cannot_upload_note(clients):
    owner, _, agent = clients
    ticket = create(owner)
    assert upload(owner, ticket, [("files", ("secret.txt", b"secret", "text/plain"))], internal=True).status_code == 403
    response = upload(agent, ticket, [("files", ("secret.txt", b"secret", "text/plain"))], internal=True, body="Ekip notu")
    assert response.status_code == 200, response.text
    item = response.json()["messages"][-1]["attachments"][0]
    assert owner.get(f'/api/v1/attachments/{item["id"]}').status_code == 404
    assert agent.get(f'/api/v1/attachments/{item["id"]}').status_code == 200
    assert item["id"] not in str(owner.get(f'/api/v1/tickets/{ticket["id"]}').json())


def test_failed_uploads_leave_no_files_or_message(clients, uploads):
    owner, other, _ = clients
    ticket = create(owner)
    files = [("files", ("ekran.png", png(), "image/png"))]
    assert upload(other, ticket, files).status_code == 404
    assert upload(owner, {**ticket, "version": 999}, files).status_code == 409
    assert upload(owner, ticket, [("files", ("fake.png", b"not a png", "image/png"))]).status_code == 422
    assert upload(owner, ticket, [("files", ("attack.html", b"<script>evil</script>", "text/html"))]).status_code == 422
    assert upload(owner, ticket, [("files", ("large.txt", b"x" * (10 * 1024 * 1024 + 1), "text/plain"))]).status_code == 413
    assert upload(owner, ticket, files * 6).status_code in (400, 413, 422)
    assert not list(uploads.iterdir())
    assert len(owner.get(f'/api/v1/tickets/{ticket["id"]}').json()["messages"]) == 1
    assert owner.post(f'/api/v1/tickets/{ticket["id"]}/messages', json={"body": "", "version": 1}).status_code == 422


def test_closed_ticket_rejects_files(clients, uploads):
    owner, _, _ = clients
    ticket = create(owner)
    closed = owner.post(f'/api/v1/tickets/{ticket["id"]}/close', json={"version": 1}).json()
    assert upload(owner, closed, [("files", ("image.png", png(), "image/png"))]).status_code == 409
    assert not list(uploads.iterdir())


def test_multipart_csrf_and_chunked_body_limit(clients, uploads, monkeypatch):
    owner, _, _ = clients
    ticket = create(owner)
    csrf = owner.headers.pop("X-CSRF-Token")
    files = [("files", ("image.png", png(), "image/png"))]
    assert upload(owner, ticket, files).status_code == 403
    owner.headers["X-CSRF-Token"] = csrf
    monkeypatch.setattr("app.upload_limits.MAX_REQUEST", 1024)
    body = b'--boundary\r\nContent-Disposition: form-data; name="files"; filename="large.txt"\r\nContent-Type: text/plain\r\n\r\n' + b"x" * 2048 + b"\r\n--boundary--\r\n"
    response = owner.post(f'/api/v1/tickets/{ticket["id"]}/messages/with-files',
                          headers={"Content-Type": "multipart/form-data; boundary=boundary"}, content=iter([body[:512], body[512:]]))
    assert response.status_code == 413, response.text
    assert not list(uploads.iterdir())


def test_storage_failure_rolls_back_version_and_files(clients, uploads, monkeypatch):
    owner, _, _ = clients
    ticket = create(owner)

    def failed_storage(db, ticket, message, files, written):
        path = uploads / "unfinished"
        written.append(path)
        path.write_bytes(b"partial")
        raise OSError("disk unavailable")

    monkeypatch.setattr("app.services.store_files", failed_storage)
    with pytest.raises(OSError):
        upload(owner, ticket, [("files", ("image.png", png(), "image/png"))])
    detail = owner.get(f'/api/v1/tickets/{ticket["id"]}').json()
    assert detail["version"] == ticket["version"]
    assert len(detail["messages"]) == 1
    assert not list(uploads.iterdir())
