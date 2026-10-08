"""Scheduled deletion of data past its retention period (ISO 27001 A.8.10)."""
import logging
from datetime import timedelta
from sqlalchemy import delete, select
from .audit import audit
from .config import settings
from .models import Attachment, AuditLog, AuthSession, LaunchCode, Message, Notification, OutboundEmail, Reminder, Ticket, TicketEvent, now

logger = logging.getLogger("support.retention")


def cutoff(days):
    return now() - timedelta(days=days)


def purge_ticket(db, ticket):
    """Remove a ticket and everything attached to it; files go first so a failed commit never leaves rows pointing at deleted files."""
    for item in db.scalars(select(Attachment).where(Attachment.ticket_id == ticket.id)):
        (settings.upload_dir / item.id).unlink(missing_ok=True)
    for model in (Attachment, OutboundEmail, Notification, Reminder, TicketEvent, Message):
        db.execute(delete(model).where(model.ticket_id == ticket.id))
    db.delete(ticket)


def purge(db):
    counts = {}
    counts["sessions"] = db.execute(delete(AuthSession).where(AuthSession.expires_at < now())).rowcount
    counts["launch_codes"] = db.execute(delete(LaunchCode).where(LaunchCode.expires_at < now())).rowcount
    if settings.notification_retention_days > 0:
        counts["notifications"] = db.execute(delete(Notification).where(Notification.created_at < cutoff(settings.notification_retention_days))).rowcount
    if settings.mail_retention_days > 0:
        counts["emails"] = db.execute(delete(OutboundEmail).where(OutboundEmail.status != "pending", OutboundEmail.created_at < cutoff(settings.mail_retention_days))).rowcount
    if settings.closed_ticket_retention_days > 0:
        tickets = db.scalars(select(Ticket).where(Ticket.status == "closed", Ticket.updated_at < cutoff(settings.closed_ticket_retention_days)).limit(200)).all()
        for ticket in tickets:
            purge_ticket(db, ticket)
        counts["tickets"] = len(tickets)
    if settings.audit_retention_days > 0:
        counts["audit_logs"] = db.execute(delete(AuditLog).where(AuditLog.created_at < cutoff(settings.audit_retention_days))).rowcount
    removed = {key: value for key, value in counts.items() if value}
    if removed:
        audit(db, None, None, "retention.purge", "system", "", ", ".join(f"{key}={value}" for key, value in removed.items()))
        logger.info("retention_purge %s", " ".join(f"{key}={value}" for key, value in removed.items()))
    db.commit()
    return removed
