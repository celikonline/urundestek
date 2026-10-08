from fastapi import HTTPException
from sqlalchemy import or_, select, func
from .auth import STAFF_ROLES
from .models import Message, Notification, Reminder, Tenant, Ticket, TicketEvent, User, iso


def ticket_scope(user):
    query = select(Ticket)
    if user.role not in STAFF_ROLES:
        query = query.where(Ticket.tenant_id == user.tenant_id)
        if user.role != "tenant_admin":
            query = query.where(Ticket.created_by == user.id)
    return query


def get_ticket(db, user, ticket_id):
    ticket = db.scalar(ticket_scope(user).where(Ticket.id == ticket_id))
    if not ticket:
        raise HTTPException(404, "Talep bulunamadı.")
    return ticket


def ticket_view(db, ticket, user, detail=False):
    tenant = db.get(Tenant, ticket.tenant_id)
    creator = db.get(User, ticket.created_by)
    assignee = db.get(User, ticket.assigned_to) if ticket.assigned_to else None
    unread = db.scalar(select(func.count()).select_from(Notification).where(Notification.ticket_id == ticket.id, Notification.user_id == user.id, Notification.read == False))
    result = {"id": ticket.id, "number": ticket.number, "tenant_id": ticket.tenant_id, "tenant_name": tenant.name, "tenant_slug": tenant.slug,
              "subject": ticket.subject, "category": ticket.category, "priority": ticket.priority, "status": ticket.status,
              "created_by": ticket.created_by, "requester_name": creator.name, "assigned_to": ticket.assigned_to,
              "assignee_name": assignee.name if assignee else None, "version": ticket.version, "created_at": iso(ticket.created_at), "updated_at": iso(ticket.updated_at), "unread": unread}
    if detail:
        messages = select(Message).where(Message.ticket_id == ticket.id, Message.tenant_id == ticket.tenant_id).order_by(Message.created_at, Message.id)
        events = select(TicketEvent).where(TicketEvent.ticket_id == ticket.id).order_by(TicketEvent.created_at)
        if user.role not in STAFF_ROLES:
            messages = messages.where(Message.kind != "internal")
            events = events.where(TicketEvent.internal == False)
        result["messages"] = [{"id": m.id, "body": m.body, "kind": m.kind, "author_id": m.author_id, "author_name": db.get(User, m.author_id).name, "created_at": iso(m.created_at)} for m in db.scalars(messages)]
        result["events"] = [{"id": e.id, "label": e.label, "created_at": iso(e.created_at)} for e in db.scalars(events)]
    return result


def list_tickets(db, user, q="", status="", priority="", tenant_id="", assigned_to="", category="", page=1, page_size=30):
    query = ticket_scope(user)
    if q:
        term = q.replace("%", "\\%").replace("_", "\\_")
        clauses = [Ticket.subject.ilike(f"%{term}%", escape="\\")]
        if q.lstrip("#").isdigit():
            clauses.append(Ticket.number == int(q.lstrip("#")))
        query = query.where(or_(*clauses))
    if status == "active":
        query = query.where(Ticket.status.in_(["open", "in_progress", "waiting_customer"]))
        status = ""
    for field, value in ((Ticket.status, status), (Ticket.priority, priority), (Ticket.tenant_id, tenant_id), (Ticket.category, category)):
        if value:
            query = query.where(field == value)
    if assigned_to:
        query = query.where(Ticket.assigned_to == (user.id if assigned_to == "me" else assigned_to)) if assigned_to != "unassigned" else query.where(Ticket.assigned_to == None)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    tickets = db.scalars(query.order_by(Ticket.updated_at.desc(), Ticket.id).offset((page - 1) * page_size).limit(page_size))
    return {"items": [ticket_view(db, t, user) for t in tickets], "total": total, "page": page, "page_size": page_size}


def get_reminder(db, user, reminder_id):
    reminder = db.scalar(select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user.id))
    if not reminder:
        raise HTTPException(404, "Hatırlatma bulunamadı.")
    get_ticket(db, user, reminder.ticket_id)
    return reminder


def reminder_view(db, reminder):
    ticket = db.get(Ticket, reminder.ticket_id)
    return {"id": reminder.id, "ticket_id": reminder.ticket_id, "ticket_number": ticket.number, "subject": ticket.subject, "due_at": iso(reminder.due_at), "note": reminder.note, "status": reminder.status, "notified": reminder.notified}
