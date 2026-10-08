import csv
import io
from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import ValidationError
from starlette.datastructures import UploadFile
from starlette.concurrency import run_in_threadpool
from .ai import effective_mode
from .attachments import prepare_files
from sqlalchemy import delete, func, select, update
from .audit import ACTION_LABELS, audit, audit_view
from .auth import COOKIE, STAFF_ROLES, authenticate_staff, change_password, consume_launch_code, create_session, current_user, hash_password, password_problem, platform_user, staff_user, user_view
from .config import settings
from .db import get_db
from .integration import launch_from_senseik
from .models import Attachment, AuditLog, AuthSession, Message, Notification, OutboundEmail, Reminder, Tenant, Ticket, User, iso, now, utc
from .repository import get_reminder, get_ticket, list_tickets, reminder_view, ticket_scope, ticket_view
from .schemas import AdminTicketInput, CreateTicket, DemoInput, ExchangeInput, LoginInput, MessageInput, PasswordChangeInput, PreferencesInput, ReminderInput, StaffInput, StaffUpdate, TenantInput, VersionInput
from .services import add_message, admin_update, change_status, create_ticket, follow_up

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health(db=Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok"}


@router.get("/auth/options")
def options():
    return {"development": settings.app_env in {"development", "test"}, "senseik_url": settings.senseik_web_origin or None}


@router.post("/auth/demo")
def demo(data: DemoInput, request: Request, response: Response, db=Depends(get_db)):
    if settings.app_env not in {"development", "test"}:
        raise HTTPException(404, "Sayfa bulunamadı.")
    user = db.scalar(select(User).where(User.account == data.account))
    if not user:
        raise HTTPException(401, "Demo hesabı bulunamadı.")
    return create_session(db, user, response, short=user.role not in STAFF_ROLES, request=request)


@router.post("/auth/login")
def login(data: LoginInput, request: Request, response: Response, db=Depends(get_db)):
    user = authenticate_staff(db, request, data.email, data.password)
    return create_session(db, user, response, request=request)


@router.post("/auth/launch")
async def launch(authorization: Annotated[str, Header()] = "", db=Depends(get_db)):
    return await launch_from_senseik(db, authorization)


@router.post("/auth/exchange")
def exchange(data: ExchangeInput, request: Request, response: Response, db=Depends(get_db)):
    user = consume_launch_code(db, data.code, request)
    return create_session(db, user, response, short=True, request=request, action="session.exchange")


@router.get("/me")
def me(request: Request, user=Depends(current_user), db=Depends(get_db)):
    return user_view(db, user, request.state.session.csrf_token)


@router.patch("/me/preferences")
def preferences(data: PreferencesInput, request: Request, user=Depends(current_user), db=Depends(get_db)):
    user.email_notifications = data.email_notifications
    audit(db, request, user, "preferences.update", "user", user.id, f"email_notifications={data.email_notifications}")
    db.commit()
    return user_view(db, user, request.state.session.csrf_token)


@router.post("/auth/password", status_code=204)
def password(data: PasswordChangeInput, request: Request, user=Depends(staff_user), db=Depends(get_db)):
    change_password(db, request, user, data.current_password, data.new_password)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, user=Depends(current_user), db=Depends(get_db)):
    db.delete(request.state.session)
    audit(db, request, user, "logout", "user", user.id)
    db.commit()
    response.delete_cookie(COOKIE, path="/")


@router.get("/tickets")
@router.get("/admin/tickets", dependencies=[Depends(staff_user)])
def tickets(q: str = Query("", max_length=200), status: str = Query("", max_length=30), priority: str = Query("", max_length=20), tenant_id: str = Query("", max_length=36), assigned_to: str = Query("", max_length=36), category: str = Query("", max_length=40), page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100), user=Depends(current_user), db=Depends(get_db)):
    return list_tickets(db, user, q, status, priority, tenant_id, assigned_to, category, page, page_size)


@router.post("/tickets", status_code=201)
def create(data: CreateTicket, idempotency_key: Annotated[str, Header(min_length=8, max_length=100)], user=Depends(current_user), db=Depends(get_db)):
    return create_ticket(db, user, data, idempotency_key)


@router.get("/tickets/{ticket_id}")
def detail(ticket_id: str, user=Depends(current_user), db=Depends(get_db)):
    return ticket_view(db, get_ticket(db, user, ticket_id), user, True)


@router.post("/tickets/{ticket_id}/messages")
def message(ticket_id: str, data: MessageInput, user=Depends(current_user), db=Depends(get_db)):
    return add_message(db, user, ticket_id, data)


@router.post("/admin/tickets/{ticket_id}/notes")
def note(ticket_id: str, data: MessageInput, user=Depends(staff_user), db=Depends(get_db)):
    return add_message(db, user, ticket_id, data, True)


async def upload_message(request, db, user, ticket_id, internal=False):
    ticket = get_ticket(db, user, ticket_id)
    if ticket.status == "closed":
        raise HTTPException(409, "Mesaj yazmak için önce talebi yeniden açın.")
    async with request.form(max_files=5, max_fields=3, max_part_size=60000) as form:
        try:
            data = MessageInput(version=form.get("version"), body=form.get("body", ""), body_html=form.get("body_html"))
        except ValidationError:
            raise HTTPException(422, "Mesaj alanlarını kontrol edin.")
        files = form.getlist("files")
        if any(not isinstance(file, UploadFile) for file in files):
            raise HTTPException(422, "Geçerli dosyalar seçin.")
        prepared = await prepare_files(files)
        return await run_in_threadpool(add_message, db, user, ticket_id, data, internal, prepared)


@router.post("/tickets/{ticket_id}/messages/with-files")
async def message_files(ticket_id: str, request: Request, user=Depends(current_user), db=Depends(get_db)):
    return await upload_message(request, db, user, ticket_id)


@router.post("/admin/tickets/{ticket_id}/notes/with-files")
async def note_files(ticket_id: str, request: Request, user=Depends(staff_user), db=Depends(get_db)):
    return await upload_message(request, db, user, ticket_id, True)


@router.get("/attachments/{attachment_id}")
def download_attachment(attachment_id: str, request: Request, preview: bool = False, user=Depends(current_user), db=Depends(get_db)):
    item = db.get(Attachment, attachment_id)
    if not item:
        raise HTTPException(404, "Dosya bulunamadı.")
    ticket = get_ticket(db, user, item.ticket_id)
    message = db.get(Message, item.message_id)
    if not message or (message.kind == "internal" and user.role not in STAFF_ROLES):
        raise HTTPException(404, "Dosya bulunamadı.")
    path = settings.upload_dir / item.id
    if not path.is_file():
        raise HTTPException(404, "Dosya bulunamadı.")
    inline = preview and item.content_type in {"image/png", "image/jpeg", "image/webp", "image/gif"}
    if not inline:
        audit(db, request, user, "attachment.download", "attachment", item.id, f"#{ticket.number} · {item.filename}", tenant_id=ticket.tenant_id)
        db.commit()
    return FileResponse(path, media_type=item.content_type, filename=item.filename, content_disposition_type="inline" if inline else "attachment",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.patch("/admin/tickets/{ticket_id}")
def edit(ticket_id: str, data: AdminTicketInput, user=Depends(staff_user), db=Depends(get_db)):
    return admin_update(db, user, ticket_id, data)


@router.post("/tickets/{ticket_id}/close")
def close(ticket_id: str, data: VersionInput, user=Depends(current_user), db=Depends(get_db)):
    return change_status(db, user, ticket_id, data.version, "closed")


@router.post("/tickets/{ticket_id}/reopen")
def reopen(ticket_id: str, data: VersionInput, user=Depends(current_user), db=Depends(get_db)):
    return change_status(db, user, ticket_id, data.version, "open")


@router.post("/tickets/{ticket_id}/follow-up")
def followup(ticket_id: str, data: VersionInput, user=Depends(current_user), db=Depends(get_db)):
    return follow_up(db, user, ticket_id, data.version)


@router.post("/tickets/{ticket_id}/reminders", status_code=201)
def remind(ticket_id: str, data: ReminderInput, user=Depends(current_user), db=Depends(get_db)):
    ticket = get_ticket(db, user, ticket_id)
    if ticket.status == "closed":
        raise HTTPException(409, "Hatırlatma için talebi yeniden açın.")
    if utc(data.due_at) <= now():
        raise HTTPException(422, "Gelecekte bir tarih ve saat seçin.")
    reminder = Reminder(tenant_id=ticket.tenant_id, ticket_id=ticket.id, user_id=user.id, due_at=utc(data.due_at), note=data.note)
    db.add(reminder)
    db.commit()
    return reminder_view(db, reminder)


@router.get("/reminders")
def reminders(user=Depends(current_user), db=Depends(get_db)):
    visible_ids = ticket_scope(user).with_only_columns(Ticket.id)
    rows = db.scalars(select(Reminder).where(Reminder.user_id == user.id, Reminder.ticket_id.in_(visible_ids)).order_by(Reminder.due_at).limit(500))
    return [reminder_view(db, r) for r in rows]


@router.post("/reminders/{reminder_id}/complete")
def complete(reminder_id: str, user=Depends(current_user), db=Depends(get_db)):
    reminder = get_reminder(db, user, reminder_id)
    reminder.status = "completed"
    db.commit()
    return reminder_view(db, reminder)


@router.delete("/reminders/{reminder_id}", status_code=204)
def cancel(reminder_id: str, user=Depends(current_user), db=Depends(get_db)):
    reminder = get_reminder(db, user, reminder_id)
    reminder.status = "cancelled"
    db.commit()


@router.get("/notifications")
def notifications(user=Depends(current_user), db=Depends(get_db)):
    visible_ids = ticket_scope(user).with_only_columns(Ticket.id)
    return [{"id": n.id, "ticket_id": n.ticket_id, "kind": n.kind, "text": n.text, "read": n.read, "created_at": iso(n.created_at)} for n in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.ticket_id.in_(visible_ids)).order_by(Notification.created_at.desc()).limit(100))]


@router.post("/notifications/{notification_id}/read", status_code=204)
def read_notification(notification_id: str, user=Depends(current_user), db=Depends(get_db)):
    row = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id))
    if not row:
        raise HTTPException(404, "Bildirim bulunamadı.")
    get_ticket(db, user, row.ticket_id)
    row.read = True
    db.commit()


@router.post("/tickets/{ticket_id}/read", status_code=204)
def read_ticket(ticket_id: str, user=Depends(current_user), db=Depends(get_db)):
    get_ticket(db, user, ticket_id)
    db.execute(update(Notification).where(Notification.ticket_id == ticket_id, Notification.user_id == user.id).values(read=True))
    db.commit()


@router.get("/admin/tenants")
def tenants(user=Depends(staff_user), db=Depends(get_db)):
    rows = db.scalars(select(Tenant).order_by(Tenant.name))
    return [{"id": t.id, "name": t.name, "slug": t.slug, "external_id": t.external_id, "active": t.active, "ai_mode": t.ai_mode, "ai_effective": effective_mode(t),
             "open_count": db.scalar(select(func.count()).select_from(Ticket).where(Ticket.tenant_id == t.id, Ticket.status != "closed"))} for t in rows]


@router.get("/admin/settings")
def admin_settings(user=Depends(staff_user)):
    return {"ai_available": settings.ai_available, "ai_mode": settings.ai_mode if settings.ai_available else "off", "ai_model": settings.ai_model, "ai_max_auto_replies": settings.ai_max_auto_replies,
            "auto_close_days": settings.auto_close_days, "mail_enabled": settings.mail_enabled, "staff_idle_minutes": settings.staff_idle_minutes,
            "login_lock_threshold": settings.login_lock_threshold, "login_lock_minutes": settings.login_lock_minutes,
            "retention": {"audit_days": settings.audit_retention_days, "notification_days": settings.notification_retention_days, "mail_days": settings.mail_retention_days, "closed_ticket_days": settings.closed_ticket_retention_days}}


@router.patch("/admin/tenants/{tenant_id}")
def tenant_edit(tenant_id: str, data: TenantInput, request: Request, user=Depends(platform_user), db=Depends(get_db)):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Firma bulunamadı.")
    changes = {key: value for key, value in data.model_dump(exclude_unset=True).items() if value is not None}
    if not changes:
        raise HTTPException(422, "Değiştirilecek bir alan seçin.")
    for key, value in changes.items():
        setattr(tenant, key, value)
    audit(db, request, user, "tenant.update", "tenant", tenant.id, f"{tenant.name}: " + ", ".join(f"{k}={v}" for k, v in changes.items()), tenant_id=tenant.id)
    db.commit()
    return {"id": tenant.id, "active": tenant.active, "ai_mode": tenant.ai_mode, "ai_effective": effective_mode(tenant)}


@router.get("/admin/staff")
def staff(user=Depends(staff_user), db=Depends(get_db)):
    return [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "active": u.active, "locked": bool(u.locked_until and utc(u.locked_until) > now()), "password_changed_at": iso(u.password_changed_at)} for u in db.scalars(select(User).where(User.role.in_(STAFF_ROLES)).order_by(User.name))]


@router.post("/admin/staff", status_code=201)
def staff_create(data: StaffInput, request: Request, user=Depends(platform_user), db=Depends(get_db)):
    if db.scalar(select(User).where(User.email == data.email.lower(), User.role.in_(STAFF_ROLES))):
        raise HTTPException(409, "Bu e-posta ile bir destek görevlisi var.")
    problem = password_problem(data.password, data.email, data.name)
    if problem:
        raise HTTPException(422, problem)
    person = User(name=data.name, email=data.email.lower(), role=data.role, password_hash=hash_password(data.password))
    db.add(person)
    db.flush()
    audit(db, request, user, "staff.create", "user", person.id, f"{person.email} · {person.role}")
    db.commit()
    return {"id": person.id, "name": person.name, "role": person.role}


@router.patch("/admin/staff/{staff_id}")
def staff_edit(staff_id: str, data: StaffUpdate, request: Request, user=Depends(platform_user), db=Depends(get_db)):
    person = db.get(User, staff_id)
    if not person or person.role not in STAFF_ROLES:
        raise HTTPException(404, "Destek görevlisi bulunamadı.")
    if person.id == user.id:
        raise HTTPException(409, "Kendi yönetici erişiminizi bu ekrandan değiştiremezsiniz.")
    changes = {key: value for key, value in data.model_dump(exclude_unset=True).items() if value is not None}
    for key, value in changes.items():
        setattr(person, key, value)
    if changes.get("active") is False:
        db.execute(delete(AuthSession).where(AuthSession.user_id == person.id))
    audit(db, request, user, "staff.update", "user", person.id, ", ".join(f"{k}={v}" for k, v in changes.items()))
    db.commit()
    return {"id": person.id, "active": person.active, "role": person.role}


@router.post("/admin/staff/{staff_id}/unlock", status_code=204)
def staff_unlock(staff_id: str, request: Request, user=Depends(platform_user), db=Depends(get_db)):
    person = db.get(User, staff_id)
    if not person or person.role not in STAFF_ROLES:
        raise HTTPException(404, "Destek görevlisi bulunamadı.")
    person.locked_until, person.failed_logins = None, 0
    audit(db, request, user, "staff.update", "user", person.id, "Kilit kaldırıldı")
    db.commit()


def parse_day(value, end=False):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, "Tarih biçimi YYYY-AA-GG olmalı.")
    parsed = parsed.replace(hour=23, minute=59, second=59) if end and len(value) == 10 else parsed
    return utc(parsed)


def audit_query(action="", actor_id="", q="", since="", until=""):
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
    if actor_id:
        query = query.where(AuditLog.actor_id == actor_id)
    if q:
        term = q.replace("%", "\\%").replace("_", "\\_")
        query = query.where((AuditLog.detail.ilike(f"%{term}%", escape="\\")) | (AuditLog.actor_name.ilike(f"%{term}%", escape="\\")) | (AuditLog.target_id == q) | (AuditLog.ip == q))
    if since:
        query = query.where(AuditLog.created_at >= parse_day(since))
    if until:
        query = query.where(AuditLog.created_at <= parse_day(until, True))
    return query


@router.get("/admin/audit")
def audit_list(action: str = Query("", max_length=60), actor_id: str = Query("", max_length=36), q: str = Query("", max_length=200), since: str = Query("", max_length=25), until: str = Query("", max_length=25), page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), user=Depends(platform_user), db=Depends(get_db)):
    query = audit_query(action, actor_id, q, since, until)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(AuditLog.created_at.desc(), AuditLog.id).offset((page - 1) * page_size).limit(page_size))
    return {"items": [audit_view(r) for r in rows], "total": total, "page": page, "page_size": page_size, "actions": ACTION_LABELS}


@router.get("/admin/audit/export")
def audit_export(request: Request, action: str = Query("", max_length=60), actor_id: str = Query("", max_length=36), q: str = Query("", max_length=200), since: str = Query("", max_length=25), until: str = Query("", max_length=25), user=Depends(platform_user), db=Depends(get_db)):
    rows = db.scalars(audit_query(action, actor_id, q, since, until).order_by(AuditLog.created_at.desc()).limit(20000)).all()
    audit(db, request, user, "audit.export", "audit", "", f"{len(rows)} kayıt")
    db.commit()
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Zaman (UTC)", "İşlem", "Açıklama", "Sonuç", "Kullanıcı", "Rol", "Hedef türü", "Hedef", "Ayrıntı", "IP", "Korelasyon"])
    for r in rows:
        writer.writerow([iso(r.created_at), r.action, ACTION_LABELS.get(r.action, r.action), r.outcome, r.actor_name, r.actor_role, r.target_type, r.target_id, r.detail, r.ip, r.correlation_id])
    stamp = now().strftime("%Y%m%d-%H%M")
    return StreamingResponse(iter(["﻿" + buffer.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="denetim-kaydi-{stamp}.csv"'})


@router.get("/admin/mail-queue")
def mail_queue(user=Depends(platform_user), db=Depends(get_db)):
    counts = {status: 0 for status in ("pending", "sent", "failed", "skipped")}
    for status, count in db.execute(select(OutboundEmail.status, func.count()).group_by(OutboundEmail.status)):
        counts[status] = count
    rows = db.scalars(select(OutboundEmail).where(OutboundEmail.status.in_(["failed", "pending"])).order_by(OutboundEmail.created_at.desc()).limit(50))
    items = []
    for row in rows:
        recipient = db.get(User, row.user_id)
        ticket = db.get(Ticket, row.ticket_id)
        items.append({"id": row.id, "status": row.status, "kind": row.kind, "subject": row.subject, "recipient": recipient.email if recipient else "", "ticket_id": row.ticket_id,
                      "ticket_number": ticket.number if ticket else None, "attempts": row.attempts, "last_error": row.last_error, "created_at": iso(row.created_at), "sent_at": iso(row.sent_at)})
    return {"enabled": settings.mail_enabled, "counts": counts, "items": items}


@router.post("/admin/mail-queue/{email_id}/retry", status_code=204)
def mail_retry(email_id: str, request: Request, user=Depends(platform_user), db=Depends(get_db)):
    row = db.get(OutboundEmail, email_id)
    if not row or row.status != "failed":
        raise HTTPException(404, "Yeniden denenecek e-posta bulunamadı.")
    row.status, row.attempts, row.last_error = "pending", 0, None
    audit(db, request, user, "mail.retry", "email", row.id, row.subject)
    db.commit()
