from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from .auth import STAFF_ROLES
from .models import Message, Notification, Reminder, Tenant, Ticket, TicketEvent, User, now, utc
from .repository import get_ticket, ticket_scope, ticket_view

STATUS_LABELS = {"open": "Açık", "in_progress": "İnceleniyor", "waiting_customer": "Yanıtınız bekleniyor", "resolved": "Çözüldü", "closed": "Kapalı"}


def event(db, ticket, user, label, internal=False):
    db.add(TicketEvent(tenant_id=ticket.tenant_id, ticket_id=ticket.id, actor_id=user.id, label=label, internal=internal))


def notify(db, ticket, actor, text, kind="message"):
    if actor.role in STAFF_ROLES:
        recipient_ids = [ticket.created_by]
        recipient_ids += list(db.scalars(select(User.id).where(User.tenant_id == ticket.tenant_id, User.role == "tenant_admin", User.active == True)))
    else:
        assignee = db.get(User, ticket.assigned_to) if ticket.assigned_to else None
        recipient_ids = [assignee.id] if assignee and assignee.active and assignee.role in STAFF_ROLES else list(db.scalars(select(User.id).where(User.role.in_(STAFF_ROLES), User.active == True)))
    for user_id in set(recipient_ids) - {actor.id, None}:
        db.add(Notification(tenant_id=ticket.tenant_id, ticket_id=ticket.id, user_id=user_id, kind=kind, text=text[:500]))


def bump(db, ticket, expected, **values):
    if ticket.version != expected:
        raise HTTPException(409, "Talep güncellendi. Son durumu yükleyip tekrar deneyin.")
    changed = db.execute(update(Ticket).where(Ticket.id == ticket.id, Ticket.version == expected).values(version=expected + 1, updated_at=now(), **values))
    if changed.rowcount != 1:
        raise HTTPException(409, "Talep başka bir kullanıcı tarafından güncellendi.")
    db.refresh(ticket)


def create_ticket(db, user, data, key):
    if not user.tenant_id or user.role in STAFF_ROLES:
        raise HTTPException(403, "Yeni talepler müşteri hesabından açılır.")
    previous = db.scalar(select(Ticket).where(Ticket.created_by == user.id, Ticket.idempotency_key == key))
    if previous:
        return ticket_view(db, previous, user, True)
    # Tenant row lock serializes company-local numbering in PostgreSQL.
    db.scalar(select(Tenant).where(Tenant.id == user.tenant_id).with_for_update())
    number = (db.scalar(select(func.max(Ticket.number)).where(Ticket.tenant_id == user.tenant_id)) or 1000) + 1
    ticket = Ticket(tenant_id=user.tenant_id, created_by=user.id, subject=data.subject, category=data.category, priority=data.priority, number=number, idempotency_key=key)
    db.add(ticket)
    try:
        db.flush()
        db.add(Message(tenant_id=ticket.tenant_id, ticket_id=ticket.id, author_id=user.id, body=data.body, kind="customer"))
        event(db, ticket, user, "Talep oluşturuldu")
        notify(db, ticket, user, f"Yeni talep: {ticket.subject}", "ticket")
        db.commit()
    except IntegrityError:
        db.rollback()
        previous = db.scalar(select(Ticket).where(Ticket.created_by == user.id, Ticket.idempotency_key == key))
        if not previous:
            raise
        return ticket_view(db, previous, user, True)
    return ticket_view(db, ticket, user, True)


def add_message(db, user, ticket_id, data, internal=False):
    ticket = get_ticket(db, user, ticket_id)
    if ticket.status == "closed":
        raise HTTPException(409, "Mesaj yazmak için önce talebi yeniden açın.")
    if internal:
        bump(db, ticket, data.version)
    else:
        bump(db, ticket, data.version, status="waiting_customer" if user.role in STAFF_ROLES else "open")
    db.add(Message(tenant_id=ticket.tenant_id, ticket_id=ticket.id, author_id=user.id, body=data.body, kind="internal" if internal else ("support" if user.role in STAFF_ROLES else "customer")))
    if not internal:
        notify(db, ticket, user, f"#{ticket.number} · {user.name} yeni bir yanıt yazdı.")
    db.commit()
    return ticket_view(db, ticket, user, True)


def change_status(db, user, ticket_id, expected, status):
    ticket = get_ticket(db, user, ticket_id)
    if user.role not in STAFF_ROLES and status not in {"closed", "open"}:
        raise HTTPException(403, "Bu durum değişikliği destek ekibine aittir.")
    if status == "open" and ticket.status != "closed":
        raise HTTPException(409, "Yalnız kapalı bir talep yeniden açılabilir.")
    if status == "closed" and ticket.status == "closed":
        raise HTTPException(409, "Talep zaten kapalı.")
    bump(db, ticket, expected, status=status)
    event(db, ticket, user, f"{user.name} · {STATUS_LABELS[status]}")
    if status == "closed":
        db.execute(update(Reminder).where(Reminder.ticket_id == ticket.id, Reminder.status == "pending").values(status="cancelled"))
    notify(db, ticket, user, f"#{ticket.number} · Talep {STATUS_LABELS[status].lower()} durumuna alındı.", "status")
    db.commit()
    return ticket_view(db, ticket, user, True)


def follow_up(db, user, ticket_id, expected):
    ticket = get_ticket(db, user, ticket_id)
    if ticket.status == "closed":
        raise HTTPException(409, "Takip için talebi yeniden açın.")
    if ticket.last_followup_at and utc(ticket.last_followup_at) > now() - timedelta(hours=24):
        raise HTTPException(429, "Güncel durum isteği 24 saatte bir gönderilebilir.")
    bump(db, ticket, expected, last_followup_at=now())
    db.add(Message(tenant_id=ticket.tenant_id, ticket_id=ticket.id, author_id=user.id, kind="customer" if user.role not in STAFF_ROLES else "support", body="Talebimle ilgili güncel durumu paylaşabilir misiniz?"))
    notify(db, ticket, user, f"#{ticket.number} · Güncel durum istendi.", "followup")
    db.commit()
    return ticket_view(db, ticket, user, True)


def admin_update(db, user, ticket_id, data):
    ticket = get_ticket(db, user, ticket_id)
    values = data.model_dump(exclude_unset=True, exclude={"version"})
    assigned = values.get("assigned_to")
    if assigned:
        agent = db.get(User, assigned)
        if not agent or agent.role not in STAFF_ROLES or not agent.active:
            raise HTTPException(422, "Aktif bir destek görevlisi seçin.")
    values = {k: v for k, v in values.items() if v is not None or k == "assigned_to"}
    old_status = ticket.status
    bump(db, ticket, data.version, **values)
    if ticket.status == "closed":
        db.execute(update(Reminder).where(Reminder.ticket_id == ticket.id, Reminder.status == "pending").values(status="cancelled"))
    if "status" in values and old_status != ticket.status:
        event(db, ticket, user, f"{user.name} · {STATUS_LABELS[ticket.status]}")
        notify(db, ticket, user, f"#{ticket.number} · Durum: {STATUS_LABELS[ticket.status]}", "status")
    if "assigned_to" in values:
        event(db, ticket, user, "Sorumlu değiştirildi", True)
    if "priority" in values:
        event(db, ticket, user, "Öncelik değiştirildi")
    db.commit()
    return ticket_view(db, ticket, user, True)


def dispatch_reminders(db):
    due = db.scalars(select(Reminder).where(Reminder.status == "pending", Reminder.notified == False, Reminder.due_at <= now()).with_for_update(skip_locked=True)).all()
    for reminder in due:
        ticket = db.get(Ticket, reminder.ticket_id)
        owner = db.get(User, reminder.user_id)
        tenant = db.get(Tenant, reminder.tenant_id)
        accessible = owner and owner.active and db.scalar(ticket_scope(owner).where(Ticket.id == ticket.id))
        if ticket.status == "closed" or not accessible or not tenant.active:
            reminder.status = "cancelled"
            continue
        reminder.notified = True
        db.add(Notification(tenant_id=reminder.tenant_id, ticket_id=reminder.ticket_id, user_id=reminder.user_id, reminder_id=reminder.id, kind="reminder", text=f"#{ticket.number} · {reminder.note}"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # Unique reminder ID keeps duplicate delivery out even with concurrent SQLite workers.
