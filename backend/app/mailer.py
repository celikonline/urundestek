import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from sqlalchemy import select
from .config import settings
from .models import OutboundEmail, Ticket, User, now

logger = logging.getLogger("support.mail")
MAX_ATTEMPTS = 3
FOOTER = "Bu e-posta SenseİK Destek tarafından otomatik gönderildi. Yanıtlarınızı portal üzerinden yazın; bildirim tercihinizi portaldaki zil simgesinden değiştirebilirsiniz."


def ticket_link(ticket):
    return f"{settings.public_url}/?talep={ticket.id}"


def queue_email(db, ticket, user, text, kind="message"):
    """Queue a short plain-text notice; message bodies and attachments never leave the portal."""
    if not settings.mail_enabled or not user or not user.active or not user.email_notifications or not user.email:
        return None
    subject = f"[SenseİK Destek] #{ticket.number} · {ticket.subject}"[:200]
    body = f"Merhaba {user.name},\n\n{text}\n\nTalebi görüntülemek için: {ticket_link(ticket)}\n\n{FOOTER}"
    row = OutboundEmail(tenant_id=ticket.tenant_id, ticket_id=ticket.id, user_id=user.id, kind=kind, subject=subject, body=body)
    db.add(row)
    return row


def deliver(recipient, subject, body):
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = recipient
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid()
    message["Auto-Submitted"] = "auto-generated"
    message.set_content(body)
    context = ssl.create_default_context()
    if settings.smtp_tls == "ssl":
        client = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=context)
    else:
        client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
    with client:
        if settings.smtp_tls == "starttls":
            client.starttls(context=context)
        if settings.smtp_user:
            client.login(settings.smtp_user, settings.smtp_password)
        client.send_message(message)


def send_pending(db, limit=50):
    """Deliver queued mail; each row is locked so parallel workers never send twice."""
    if not settings.mail_enabled:
        return 0
    rows = db.scalars(select(OutboundEmail).where(OutboundEmail.status == "pending").order_by(OutboundEmail.created_at).limit(limit).with_for_update(skip_locked=True)).all()
    sent = 0
    for row in rows:
        user = db.get(User, row.user_id)
        ticket = db.get(Ticket, row.ticket_id)
        if not user or not user.active or not user.email_notifications or not user.email or not ticket:
            row.status = "skipped"
            continue
        row.attempts += 1
        try:
            deliver(user.email, row.subject, row.body)
            row.status, row.sent_at, row.last_error = "sent", now(), None
            sent += 1
        except Exception as exc:
            row.last_error = f"{type(exc).__name__}: {exc}"[:300]
            row.status = "failed" if row.attempts >= MAX_ATTEMPTS else "pending"
            logger.warning("mail_delivery_failed id=%s attempt=%s error_type=%s", row.id, row.attempts, type(exc).__name__)
    db.commit()
    return sent
