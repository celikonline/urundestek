"""SenseİK Asistan: Claude-backed triage, drafting and auto-reply for support tickets.

Every AI action is attributed to a dedicated assistant user, logged as a ticket event and an audit row,
and can be limited per company (off / draft / auto). Attachments and internal notes are never sent to the model.
"""
import html
import logging
from datetime import timedelta
from typing import Literal
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from .audit import audit
from .config import ROOT, settings
from .models import AiJob, Attachment, Message, Reminder, Tenant, Ticket, TicketEvent, User, now, utc

logger = logging.getLogger("support.ai")
ASSISTANT_EMAIL = "asistan@senseik.local"
ASSISTANT_NAME = "SenseİK Asistan"
AI_MODES = ("inherit", "off", "draft", "auto")
PRIORITY_RANK = {"normal": 0, "high": 1, "urgent": 2}
CATEGORY_LABELS = {"general": "Genel", "dataTransfer": "Veri aktarımı", "leaveAndOvertime": "İzin ve fazla mesai", "approvals": "Onaylar",
                   "accessAndPermissions": "Erişim ve yetkiler", "payroll": "Bordro", "billing": "Faturalandırma", "other": "Diğer"}
PRIORITY_LABELS = {"normal": "Normal", "high": "Yüksek", "urgent": "Acil"}
MAX_TRANSCRIPT_CHARS = 24000

SYSTEM_PROMPT = """Sen SenseİK insan kaynakları yazılımının müşteri destek asistanısın. Görevin, bir destek talebindeki yazışmayı okuyup müşteriye yardımcı olacak bir yanıt hazırlamak ve talebi sınıflandırmaktır.

Kurallar:
- Türkçe, nazik ve net yaz; müşteriye "siz" diye hitap et. En fazla 150 kelime kullan. Gereksiz tekrar ve kalıp cümle kullanma.
- Yalnız bilgi bankasında yazan veya yazışmadan açıkça anlaşılan bilgileri ver. Emin olmadığın hiçbir ürün özelliğini, tarihi veya sonucu uydurma.
- Veri düzeltme, yetki değişikliği, bordro/fatura düzeltmesi, silme işlemi, sözleşme veya ücret konusu, hesap güvenliği ya da öfkeli/şikâyetçi bir müşteri varsa needs_human=true yap. Müşteri açıkça bir insanla veya temsilciyle görüşmek istiyorsa da needs_human=true yap.
- needs_human=true olduğunda reply alanına yine kısa, bilgi toplayan ve destek ekibinin inceleyeceğini belirten bir yanıt yaz; destek ekibinin yapacağı işi sen yapmış gibi yazma.
- Asla parola, kimlik numarası veya çalışan kişisel verisi isteme. Müşteri paylaştıysa bunu yanıtta tekrarlama.
- Müşteri sorunun çözüldüğünü, teşekkür ettiğini ve başka isteği olmadığını açıkça belirtiyorsa customer_confirms_resolved=true yap ve kısa bir kapanış yanıtı yaz.
- Yanıtı iki soruyla sınırla; adımları numaralı liste olarak ver. Belirsiz talepte önce hangi ekranda, hangi tarih veya hangi kayıt için sorun yaşandığını sor.
- confidence alanı, yanıtın müşteri için doğru ve yeterli olduğuna dair güvenini 0 ile 1 arasında verir. Bilgi bankasında dayanak yoksa 0.5'in altında kal.
- category ve priority alanlarını yazışmaya göre öner. Veri kaybı, giriş yapamama, bordro günü yaklaşan hatalar ve çok sayıda çalışanı etkileyen sorunlar yüksek veya acil önceliklidir.
- reason alanına destek ekibi için tek cümlelik Türkçe gerekçe yaz."""


class Verdict(BaseModel):
    reply: str = Field(description="Müşteriye gönderilecek veya taslak olarak sunulacak Türkçe yanıt metni.")
    confidence: float = Field(ge=0, le=1, description="Yanıtın doğru ve yeterli olduğuna dair güven, 0 ile 1 arasında.")
    needs_human: bool = Field(description="Destek görevlisinin devreye girmesi gerekiyorsa true.")
    reason: str = Field(description="Destek ekibi için tek cümlelik gerekçe.")
    category: Literal["general", "dataTransfer", "leaveAndOvertime", "approvals", "accessAndPermissions", "payroll", "billing", "other"] = Field(description="Önerilen kategori.")
    priority: Literal["normal", "high", "urgent"] = Field(description="Önerilen öncelik.")
    customer_confirms_resolved: bool = Field(description="Müşteri sorunun çözüldüğünü açıkça onayladıysa true.")


def assistant_user(db):
    user = db.scalar(select(User).where(User.email == ASSISTANT_EMAIL, User.role == "assistant"))
    if not user:
        user = User(name=ASSISTANT_NAME, email=ASSISTANT_EMAIL, role="assistant", active=True, email_notifications=False)
        db.add(user)
        db.flush()
    return user


def effective_mode(tenant):
    if not settings.ai_available:
        return "off"
    mode = tenant.ai_mode if tenant and tenant.ai_mode in AI_MODES else "inherit"
    return settings.ai_mode if mode == "inherit" else mode


def queue_job(db, ticket, message, trigger):
    tenant = db.get(Tenant, ticket.tenant_id)
    if effective_mode(tenant) == "off":
        return None
    job = AiJob(tenant_id=ticket.tenant_id, ticket_id=ticket.id, message_id=message.id, trigger=trigger)
    db.add(job)
    return job


def knowledge_text():
    path = settings.ai_knowledge_file if settings.ai_knowledge_file.is_absolute() else ROOT / settings.ai_knowledge_file
    try:
        return path.read_text(encoding="utf-8")[:60000]
    except OSError:
        return "Bilgi bankası dosyası bulunamadı; yalnız yazışmadaki bilgilere dayan ve güveni düşük tut."


def transcript(db, ticket, tenant):
    rows = db.scalars(select(Message).where(Message.ticket_id == ticket.id, Message.kind != "internal").order_by(Message.created_at, Message.id)).all()
    files = {}
    for item in db.scalars(select(Attachment).where(Attachment.ticket_id == ticket.id)):
        files.setdefault(item.message_id, []).append(item.filename)
    lines = [f"Firma: {tenant.name}", f"Talep #{ticket.number}: {ticket.subject}", f"Kategori: {CATEGORY_LABELS.get(ticket.category, ticket.category)} · Öncelik: {PRIORITY_LABELS.get(ticket.priority, ticket.priority)} · Durum: {ticket.status}", "", "Yazışma (eskiden yeniye):"]
    for message in rows:
        author = db.get(User, message.author_id)
        who = "Asistan" if author and author.role == "assistant" else ("Destek" if message.kind == "support" else "Müşteri")
        body = message.body.strip()
        if message.id in files:
            body += f"\n[Ekler: {', '.join(files[message.id])} — içerik paylaşılmadı]"
        lines.append(f"{who} ({author.name if author else '—'}): {body}")
    text = "\n\n".join(lines)
    if len(text) > MAX_TRANSCRIPT_CHARS:
        text = text[-MAX_TRANSCRIPT_CHARS:]
    return text + "\n\nBu yazışmaya göre müşteriye yanıt hazırla ve talebi sınıflandır."


def analyze(system_text, user_text):
    """One structured call; returns a Verdict or None when the model declined."""
    import anthropic
    client = anthropic.Anthropic(timeout=90.0, max_retries=2)
    response = client.messages.parse(
        model=settings.ai_model,
        max_tokens=4000,
        output_config={"effort": "medium"},
        system=[{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_text}],
        output_format=Verdict,
    )
    if response.stop_reason == "refusal":
        logger.warning("ai_refusal category=%s", getattr(response.stop_details, "category", None))
        return None
    return response.parsed_output


def paragraphs_html(text):
    parts = [p.strip() for p in text.replace("\r", "").split("\n\n") if p.strip()]
    return "".join("<p>" + html.escape(p).replace("\n", "<br>") + "</p>" for p in parts)


def bump_ticket(db, ticket, **values):
    db.execute(update(Ticket).where(Ticket.id == ticket.id).values(version=Ticket.version + 1, updated_at=now(), **values))
    db.refresh(ticket)


def add_event(db, ticket, actor, label, internal=False):
    db.add(TicketEvent(tenant_id=ticket.tenant_id, ticket_id=ticket.id, actor_id=actor.id, label=label[:300], internal=internal))


def customer_recipients(db, ticket):
    rows = [db.get(User, ticket.created_by)]
    rows += list(db.scalars(select(User).where(User.tenant_id == ticket.tenant_id, User.role == "tenant_admin", User.active == True)))
    return rows


def staff_recipients(db, ticket):
    from .auth import STAFF_ROLES
    assignee = db.get(User, ticket.assigned_to) if ticket.assigned_to else None
    if assignee and assignee.active and assignee.role in STAFF_ROLES:
        return [assignee]
    return list(db.scalars(select(User).where(User.role.in_(STAFF_ROLES), User.active == True)))


def assistant_reply_count(db, ticket, bot):
    return db.scalar(select(func.count()).select_from(Message).where(Message.ticket_id == ticket.id, Message.author_id == bot.id, Message.kind == "support")) or 0


def apply_triage(db, ticket, bot, verdict, trigger):
    if trigger != "created":
        return
    changes = {}
    if verdict.category != ticket.category and ticket.category == "general":
        changes["category"] = verdict.category
    if PRIORITY_RANK.get(verdict.priority, 0) > PRIORITY_RANK.get(ticket.priority, 0):
        changes["priority"] = verdict.priority
    if changes:
        bump_ticket(db, ticket, **changes)
        labels = [f"kategori → {CATEGORY_LABELS[changes['category']]}" if "category" in changes else "", f"öncelik → {PRIORITY_LABELS[changes['priority']]}" if "priority" in changes else ""]
        add_event(db, ticket, bot, f"{ASSISTANT_NAME} sınıflandırdı: " + ", ".join(label for label in labels if label), internal=True)


def process_job(db, job):
    from .services import notify
    ticket = db.get(Ticket, job.ticket_id)
    tenant = db.get(Tenant, job.tenant_id) if ticket else None
    bot = assistant_user(db)
    mode = effective_mode(tenant)
    if not ticket or not tenant or mode == "off" or ticket.status in {"closed", "resolved"}:
        job.status, job.result = "skipped", "Talep kapalı, çözülmüş veya asistan devre dışı"
        return
    # The newest customer message decides; a staff reply after this job was queued makes it stale.
    latest = db.scalar(select(Message).where(Message.ticket_id == ticket.id, Message.kind != "internal").order_by(Message.created_at.desc(), Message.id.desc()))
    if not latest or latest.id != job.message_id:
        job.status, job.result = "skipped", "Daha yeni bir mesaj var"
        return
    replies = assistant_reply_count(db, ticket, bot)
    if mode == "auto" and replies >= settings.ai_max_auto_replies:
        mode = "draft"
    verdict = analyze(SYSTEM_PROMPT + "\n\nBilgi bankası:\n" + knowledge_text(), transcript(db, ticket, tenant))
    if verdict is None:
        job.status, job.result = "done", "Model yanıt vermedi; insan desteğine bırakıldı"
        add_event(db, ticket, bot, f"{ASSISTANT_NAME} yanıt üretemedi; destek ekibi inceleyecek", internal=True)
        notify(db, ticket, bot, f"#{ticket.number} · Asistan yanıt üretemedi, inceleme gerekli.", "ai", staff_recipients(db, ticket))
        return
    apply_triage(db, ticket, bot, verdict, job.trigger)
    reply = verdict.reply.strip()[:10000]
    if mode == "auto" and verdict.customer_confirms_resolved and not verdict.needs_human:
        bump_ticket(db, ticket, status="resolved")
        add_event(db, ticket, bot, f"{ASSISTANT_NAME} · Çözüldü (müşteri onayladı)")
        if reply:
            db.add(Message(tenant_id=ticket.tenant_id, ticket_id=ticket.id, author_id=bot.id, body=reply, body_html=paragraphs_html(reply), kind="support"))
        notify(db, ticket, bot, f"#{ticket.number} · Talep çözüldü olarak işaretlendi.", "status", customer_recipients(db, ticket))
        notify(db, ticket, bot, f"#{ticket.number} · Asistan talebi çözüldü olarak kapattı.", "ai", staff_recipients(db, ticket))
        audit(db, None, bot, "ai.resolve", "ticket", ticket.id, f"#{ticket.number} güven={verdict.confidence:.2f}", tenant_id=ticket.tenant_id)
        job.status, job.result = "done", f"resolved güven={verdict.confidence:.2f}"
        return
    confident = verdict.confidence >= settings.ai_min_confidence and not verdict.needs_human
    if mode == "auto" and confident and reply:
        db.add(Message(tenant_id=ticket.tenant_id, ticket_id=ticket.id, author_id=bot.id, body=reply, body_html=paragraphs_html(reply), kind="support"))
        bump_ticket(db, ticket, status="waiting_customer")
        add_event(db, ticket, bot, f"{ASSISTANT_NAME} yanıtladı (güven {int(verdict.confidence * 100)}%)", internal=True)
        notify(db, ticket, bot, f"#{ticket.number} · {ASSISTANT_NAME} yanıt yazdı.", "message", customer_recipients(db, ticket))
        audit(db, None, bot, "ai.reply", "ticket", ticket.id, f"#{ticket.number} güven={verdict.confidence:.2f}", tenant_id=ticket.tenant_id)
        job.status, job.result = "done", f"auto güven={verdict.confidence:.2f}"
        return
    why = "İnsan desteği gerekli" if verdict.needs_human else ("Güven düşük" if verdict.confidence < settings.ai_min_confidence else ("Otomatik yanıt sınırı doldu" if replies >= settings.ai_max_auto_replies else "Taslak modu"))
    note = f"{why} · {verdict.reason.strip()}\n\nÖnerilen yanıt:\n\n{reply}" if reply else f"{why} · {verdict.reason.strip()}"
    db.add(Message(tenant_id=ticket.tenant_id, ticket_id=ticket.id, author_id=bot.id, body=note[:10000], body_html=paragraphs_html(note[:10000]), kind="internal"))
    bump_ticket(db, ticket, priority=ticket.priority)
    if verdict.needs_human and ticket.status == "open":
        add_event(db, ticket, bot, f"{ASSISTANT_NAME} · insan desteği istendi: {verdict.reason.strip()[:120]}", internal=True)
    notify(db, ticket, bot, f"#{ticket.number} · {ASSISTANT_NAME} taslak hazırladı ({why.lower()}).", "ai", staff_recipients(db, ticket))
    audit(db, None, bot, "ai.draft", "ticket", ticket.id, f"#{ticket.number} {why} güven={verdict.confidence:.2f}", tenant_id=ticket.tenant_id)
    job.status, job.result = "done", f"draft {why} güven={verdict.confidence:.2f}"


def process_ai_jobs(db, limit=10):
    if not settings.ai_available:
        return 0
    jobs = db.scalars(select(AiJob).where(AiJob.status == "pending").order_by(AiJob.created_at).limit(limit).with_for_update(skip_locked=True)).all()
    handled = 0
    for job in jobs:
        job_id, attempts = job.id, job.attempts + 1
        job.attempts = attempts
        try:
            process_job(db, job)
            job.processed_at = now()
            db.commit()
            handled += 1
        except Exception as exc:
            db.rollback()  # the job row is expired after rollback, so the retry bookkeeping uses local copies
            logger.warning("ai_job_failed id=%s attempt=%s error_type=%s", job_id, attempts, type(exc).__name__)
            db.execute(update(AiJob).where(AiJob.id == job_id).values(attempts=attempts, status="failed" if attempts >= 3 else "pending", result=f"{type(exc).__name__}"[:300]))
            db.commit()
    return handled


def auto_close_resolved(db):
    """Resolved tickets nobody touched for AUTO_CLOSE_DAYS close themselves; the customer is told and can reopen."""
    from .services import notify
    if settings.auto_close_days <= 0:
        return 0
    bot = assistant_user(db)
    stale = db.scalars(select(Ticket).where(Ticket.status == "resolved", Ticket.updated_at < now() - timedelta(days=settings.auto_close_days)).limit(100).with_for_update(skip_locked=True)).all()
    for ticket in stale:
        bump_ticket(db, ticket, status="closed")
        db.execute(update(Reminder).where(Reminder.ticket_id == ticket.id, Reminder.status == "pending").values(status="cancelled"))
        add_event(db, ticket, bot, f"{ASSISTANT_NAME} · Kapalı ({settings.auto_close_days} gün yanıt gelmedi)")
        notify(db, ticket, bot, f"#{ticket.number} · Talep {settings.auto_close_days} gün boyunca yanıt gelmediği için kapatıldı. Gerekirse yeniden açabilirsiniz.", "status", customer_recipients(db, ticket))
        audit(db, None, bot, "ai.auto_close", "ticket", ticket.id, f"#{ticket.number}", tenant_id=ticket.tenant_id)
    db.commit()
    return len(stale)
