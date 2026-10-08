from typing import Annotated
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import func, select, update
from .auth import COOKIE, STAFF_ROLES, check_password, consume_launch_code, create_session, current_user, digest, hash_password, platform_user, staff_user, user_view
from .config import settings
from .db import get_db
from .integration import launch_from_senseik
from .models import AuthSession, Notification, Reminder, Tenant, Ticket, User, iso, now, utc
from .repository import get_reminder, get_ticket, list_tickets, reminder_view, ticket_scope, ticket_view
from .schemas import AdminTicketInput, CreateTicket, DemoInput, ExchangeInput, LoginInput, MessageInput, ReminderInput, StaffInput, StaffUpdate, TenantInput, VersionInput
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
def demo(data: DemoInput, response: Response, db=Depends(get_db)):
    if settings.app_env not in {"development", "test"}:
        raise HTTPException(404, "Sayfa bulunamadı.")
    user = db.scalar(select(User).where(User.account == data.account))
    if not user:
        raise HTTPException(401, "Demo hesabı bulunamadı.")
    return create_session(db, user, response)


@router.post("/auth/login")
def login(data: LoginInput, response: Response, db=Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower(), User.role.in_(STAFF_ROLES), User.active == True))
    # A dummy hash path prevents a fast non-existent-account branch.
    valid = check_password(data.password, user.password_hash if user else "0" * 32 + ":" + "0" * 128)
    if not user or not valid:
        raise HTTPException(401, "E-posta veya parola hatalı.")
    return create_session(db, user, response)


@router.post("/auth/launch")
async def launch(authorization: Annotated[str, Header()] = "", db=Depends(get_db)):
    return await launch_from_senseik(db, authorization)


@router.post("/auth/exchange")
def exchange(data: ExchangeInput, response: Response, db=Depends(get_db)):
    user = consume_launch_code(db, data.code)
    return create_session(db, user, response, short=True)


@router.get("/me")
def me(request: Request, user=Depends(current_user), db=Depends(get_db)):
    return user_view(db, user, request.state.session.csrf_token)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, user=Depends(current_user), db=Depends(get_db)):
    db.delete(request.state.session)
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
    return [{"id": t.id, "name": t.name, "slug": t.slug, "external_id": t.external_id, "active": t.active, "open_count": db.scalar(select(func.count()).select_from(Ticket).where(Ticket.tenant_id == t.id, Ticket.status != "closed"))} for t in rows]


@router.patch("/admin/tenants/{tenant_id}")
def tenant_edit(tenant_id: str, data: TenantInput, user=Depends(platform_user), db=Depends(get_db)):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Firma bulunamadı.")
    tenant.active = data.active
    db.commit()
    return {"id": tenant.id, "active": tenant.active}


@router.get("/admin/staff")
def staff(user=Depends(staff_user), db=Depends(get_db)):
    return [{"id": u.id, "name": u.name, "email": u.email, "role": u.role, "active": u.active} for u in db.scalars(select(User).where(User.role.in_(STAFF_ROLES)).order_by(User.name))]


@router.post("/admin/staff", status_code=201)
def staff_create(data: StaffInput, user=Depends(platform_user), db=Depends(get_db)):
    if db.scalar(select(User).where(User.email == data.email.lower(), User.role.in_(STAFF_ROLES))):
        raise HTTPException(409, "Bu e-posta ile bir destek görevlisi var.")
    person = User(name=data.name, email=data.email.lower(), role=data.role, password_hash=hash_password(data.password))
    db.add(person)
    db.commit()
    return {"id": person.id, "name": person.name, "role": person.role}


@router.patch("/admin/staff/{staff_id}")
def staff_edit(staff_id: str, data: StaffUpdate, user=Depends(platform_user), db=Depends(get_db)):
    person = db.get(User, staff_id)
    if not person or person.role not in STAFF_ROLES:
        raise HTTPException(404, "Destek görevlisi bulunamadı.")
    if person.id == user.id:
        raise HTTPException(409, "Kendi yönetici erişiminizi bu ekrandan değiştiremezsiniz.")
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(person, key, value)
    db.commit()
    return {"id": person.id, "active": person.active, "role": person.role}
