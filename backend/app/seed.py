import os
from sqlalchemy import select
from .auth import hash_password
from .models import Message, Tenant, Ticket, TicketEvent, User


def seed_demo(db):
    if db.scalar(select(User).where(User.account == "admin")):
        return
    atlas = Tenant(external_id="demo-atlas", slug="atlas", name="Atlas Teknoloji")
    nova = Tenant(external_id="demo-nova", slug="nova", name="Nova Lojistik")
    db.add_all([atlas, nova])
    db.flush()
    people = [User(tenant_id=atlas.id, name="Ayşe Yılmaz", email="ayse@example.test", account="ayse", role="customer"),
              User(tenant_id=atlas.id, name="Emre Kaya", email="emre@example.test", account="emre", role="customer"),
              User(tenant_id=atlas.id, name="Selin Acar", email="selin@example.test", account="manager", role="tenant_admin"),
              User(tenant_id=nova.id, name="Deniz Demir", email="deniz@example.test", account="deniz", role="customer"),
              User(name="Ece Arslan", email="ece@example.test", account="admin", role="platform_admin"),
              User(name="Mert Akın", email="mert@example.test", account="agent", role="support_agent")]
    db.add_all(people)
    db.flush()
    ayse, emre, manager, deniz, admin, agent = people
    rows = [(atlas, ayse, "Ekim bordro raporunu indiremiyorum", "payroll", "high", "in_progress", "Bordro raporunda indirme düğmesine bastığımda rapor hazırlanıyor ekranında kalıyor. Ekim dönemini kontrol edebilir misiniz?"),
            (atlas, ayse, "İzin onayı yöneticime ulaşmadı", "leaveAndOvertime", "normal", "waiting_customer", "12–14 Ekim tarihleri için oluşturduğum izin talebi yöneticimin onay listesinde görünmüyor."),
            (atlas, ayse, "Yeni çalışan için yetki tanımı", "accessAndPermissions", "normal", "open", "Yeni başlayan çalışma arkadaşımıza yalnızca kendi ekibini göreceği bir yetki tanımlamak istiyoruz."),
            (atlas, ayse, "Personel aktarımı tamamlandı", "dataTransfer", "normal", "resolved", "Personel listesindeki departman eşleştirmesi için yardım rica ediyorum."),
            (atlas, ayse, "Fazla mesai toplamları hakkında", "leaveAndOvertime", "normal", "closed", "Haftalık fazla mesai toplamlarını rapordan nasıl görebilirim?"),
            (atlas, emre, "Onay akışı güncellemesi", "approvals", "normal", "open", "Satın alma onay zincirindeki ikinci yöneticiyi değiştirmek istiyorum."),
            (nova, deniz, "Vardiya raporundaki eksik kayıtlar", "general", "urgent", "open", "Gece vardiyasında çalışan ekibimizin raporunda bazı giriş kayıtları eksik görünüyor.")]
    for index, (tenant, creator, subject, category, priority, status, body) in enumerate(rows):
        ticket = Ticket(tenant_id=tenant.id, created_by=creator.id, number=1001 + index, subject=subject, category=category, priority=priority, status=status, assigned_to=agent.id if status in {"in_progress", "waiting_customer", "resolved"} else None, idempotency_key=f"seed-{index}")
        db.add(ticket)
        db.flush()
        db.add(Message(tenant_id=tenant.id, ticket_id=ticket.id, author_id=creator.id, body=body, kind="customer"))
        db.add(TicketEvent(tenant_id=tenant.id, ticket_id=ticket.id, actor_id=creator.id, label="Talep oluşturuldu"))
        if status in {"waiting_customer", "resolved", "closed"}:
            reply = "İzin talebinin numarasını paylaşabilir misiniz? Birlikte kontrol edelim." if status == "waiting_customer" else "İlgili düzenlemeyi tamamladık. Kontrol edip sonucu bizimle paylaşabilirsiniz."
            db.add(Message(tenant_id=tenant.id, ticket_id=ticket.id, author_id=agent.id, body=reply, kind="support"))
    db.commit()


def bootstrap_admin(db):
    email, password = os.getenv("ADMIN_EMAIL", "").strip().lower(), os.getenv("ADMIN_PASSWORD", "")
    if not email or not password or db.scalar(select(User).where(User.role == "platform_admin")):
        return
    if len(password) < 12:
        raise RuntimeError("ADMIN_PASSWORD en az 12 karakter olmalı.")
    db.add(User(name=os.getenv("ADMIN_NAME", "Destek Yöneticisi"), email=email, role="platform_admin", password_hash=hash_password(password)))
    db.commit()
