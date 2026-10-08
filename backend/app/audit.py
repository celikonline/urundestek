"""Append-only audit trail for security-relevant actions (ISO 27001 A.8.15)."""
from .models import AuditLog, iso

ACTION_LABELS = {"login.success": "Giriş yapıldı", "login.failed": "Hatalı giriş", "login.locked": "Hesap kilitlendi", "logout": "Çıkış yapıldı",
                 "session.exchange": "SenseİK ile giriş", "session.exchange_failed": "Geçersiz giriş kodu", "session.idle_expired": "Boşta kalan oturum kapatıldı",
                 "password.change": "Parola değiştirildi", "password.change_failed": "Parola değişikliği reddedildi",
                 "staff.create": "Görevli eklendi", "staff.update": "Görevli güncellendi", "tenant.update": "Firma erişimi güncellendi",
                 "attachment.download": "Dosya indirildi", "tickets.export": "Talepler dışa aktarıldı", "audit.export": "Denetim kaydı dışa aktarıldı",
                 "preferences.update": "Bildirim tercihi değiştirildi", "retention.purge": "Saklama süresi dolan veriler silindi", "mail.retry": "E-posta yeniden kuyruğa alındı",
                 "ai.reply": "Asistan müşteriye yanıt verdi", "ai.draft": "Asistan taslak hazırladı", "ai.resolve": "Asistan talebi çözüldü yaptı", "ai.auto_close": "Talep otomatik kapatıldı"}


def client_ip(request):
    if request is None or not request.client:
        return ""
    return (request.client.host or "")[:64]


def audit(db, request, actor, action, target_type="", target_id="", detail="", outcome="success", tenant_id=None):
    db.add(AuditLog(actor_id=actor.id if actor else None, actor_name=(actor.name if actor else "")[:200], actor_role=(actor.role if actor else "")[:30],
                    tenant_id=tenant_id or (actor.tenant_id if actor else None), action=action[:60], target_type=target_type[:30], target_id=str(target_id)[:120],
                    detail=detail[:300], outcome=outcome[:20], ip=client_ip(request),
                    user_agent=(request.headers.get("user-agent", "") if request is not None else "")[:200],
                    correlation_id=(getattr(request.state, "correlation_id", "") if request is not None else "")[:36]))


def audit_view(row):
    return {"id": row.id, "action": row.action, "label": ACTION_LABELS.get(row.action, row.action), "actor_id": row.actor_id, "actor_name": row.actor_name, "actor_role": row.actor_role,
            "tenant_id": row.tenant_id, "target_type": row.target_type, "target_id": row.target_id, "detail": row.detail, "outcome": row.outcome, "ip": row.ip,
            "correlation_id": row.correlation_id, "created_at": iso(row.created_at)}
