from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def iso(value):
    return utc(value).isoformat() if value else None


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    external_id: Mapped[str] = mapped_column(String(120), unique=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_mode: Mapped[str] = mapped_column(String(10), default="inherit")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "external_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str | None] = mapped_column(ForeignKey("tenants.id"), nullable=True)
    external_id: Mapped[str] = mapped_column(String(120), default=uid)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200))
    account: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(30), default="customer")
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LaunchCode(Base):
    __tablename__ = "launch_codes"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (UniqueConstraint("id", "tenant_id"), UniqueConstraint("created_by", "idempotency_key"), Index("ix_ticket_tenant_status_updated", "tenant_id", "status", "updated_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    number: Mapped[int] = mapped_column(Integer)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40))
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    status: Mapped[str] = mapped_column(String(30), default="open")
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_followup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (ForeignKeyConstraint(["ticket_id", "tenant_id"], ["tickets.id", "tickets.tenant_id"]), Index("ix_message_ticket_created", "ticket_id", "created_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36))
    ticket_id: Mapped[str] = mapped_column(String(36))
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (ForeignKeyConstraint(["ticket_id", "tenant_id"], ["tickets.id", "tickets.tenant_id"]), Index("ix_attachment_message", "message_id"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36))
    ticket_id: Mapped[str] = mapped_column(String(36))
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"))
    filename: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)


class TicketEvent(Base):
    __tablename__ = "ticket_events"
    __table_args__ = (ForeignKeyConstraint(["ticket_id", "tenant_id"], ["tickets.id", "tickets.tenant_id"]),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36))
    ticket_id: Mapped[str] = mapped_column(String(36))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    label: Mapped[str] = mapped_column(String(300))
    internal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (ForeignKeyConstraint(["ticket_id", "tenant_id"], ["tickets.id", "tickets.tenant_id"]), Index("ix_reminder_status_due", "status", "due_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36))
    ticket_id: Mapped[str] = mapped_column(String(36))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    note: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    notified: Mapped[bool] = mapped_column(Boolean, default=False)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (ForeignKeyConstraint(["ticket_id", "tenant_id"], ["tickets.id", "tickets.tenant_id"]), Index("ix_notification_user_created", "user_id", "created_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36))
    ticket_id: Mapped[str] = mapped_column(String(36))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reminder_id: Mapped[str | None] = mapped_column(ForeignKey("reminders.id"), unique=True, nullable=True)
    kind: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(String(500))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class OutboundEmail(Base):
    __tablename__ = "outbound_emails"
    __table_args__ = (ForeignKeyConstraint(["ticket_id", "tenant_id"], ["tickets.id", "tickets.tenant_id"]), Index("ix_outbound_email_status_created", "status", "created_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36))
    ticket_id: Mapped[str] = mapped_column(String(36))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiJob(Base):
    __tablename__ = "ai_jobs"
    __table_args__ = (ForeignKeyConstraint(["ticket_id", "tenant_id"], ["tickets.id", "tickets.tenant_id"]), Index("ix_ai_job_status_created", "status", "created_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(36))
    ticket_id: Mapped[str] = mapped_column(String(36))
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"))
    trigger: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    """Append-only security trail; the API exposes no update or delete for these rows."""
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_created", "created_at"), Index("ix_audit_actor_created", "actor_id", "created_at"), Index("ix_audit_action_created", "action", "created_at"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(200), default="")
    actor_role: Mapped[str] = mapped_column(String(30), default="")
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    target_type: Mapped[str] = mapped_column(String(30), default="")
    target_id: Mapped[str] = mapped_column(String(120), default="")
    detail: Mapped[str] = mapped_column(String(300), default="")
    outcome: Mapped[str] = mapped_column(String(20), default="success")
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(200), default="")
    correlation_id: Mapped[str] = mapped_column(String(36), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
