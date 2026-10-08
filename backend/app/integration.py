import httpx
from fastapi import HTTPException
from sqlalchemy import select
from .auth import create_launch_code, ensure_active
from .config import settings
from .models import Tenant, User


async def launch_from_senseik(db, authorization):
    if not settings.senseik_api_url:
        raise HTTPException(503, "SenseİK bağlantısı henüz yapılandırılmadı.")
    if not authorization.startswith("Bearer ") or len(authorization) > 16000:
        raise HTTPException(401, "SenseİK oturumunuz doğrulanamadı.")
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.get(f"{settings.senseik_api_url}/v1/identity/me", headers={"Authorization": authorization})
        if response.status_code != 200:
            raise HTTPException(401, "SenseİK oturumunuz sona erdi. Ürüne yeniden giriş yapın.")
        data = response.json()
        source = data["tenant"]
        if str(source.get("status", "")).lower() in {"suspended", "closed", "disabled"}:
            raise HTTPException(403, "Firmanızın erişimi kapalı.")
        external_id, user_id = str(source["id"]), str(data["userId"])
        name = f'{data["firstName"]} {data["lastName"]}'.strip()
        slug, tenant_name = str(source["slug"]), str(source["name"])
        if not external_id or not user_id or not name or not slug or len(slug) > 120:
            raise ValueError("Invalid identity context")
    except HTTPException:
        raise
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        raise HTTPException(502, "SenseİK bağlantısı doğrulanamadı. Daha sonra tekrar deneyin.")
    tenant = db.scalar(select(Tenant).where(Tenant.external_id == external_id))
    if not tenant:
        tenant = Tenant(external_id=external_id, name=tenant_name[:200], slug=slug)
        db.add(tenant)
        db.flush()
    else:
        tenant.name = tenant_name[:200]
    user = db.scalar(select(User).where(User.tenant_id == tenant.id, User.external_id == user_id))
    role = "tenant_admin" if "announcements.support_tickets.manage" in data.get("permissions", []) else "customer"
    if not user:
        user = User(tenant_id=tenant.id, external_id=user_id, name=name[:200], email=str(data["email"])[:200], role=role)
        db.add(user)
        db.flush()
    else:
        user.name, user.role = name[:200], role
    ensure_active(db, user)
    code = create_launch_code(db, user)
    return {"url": f"{settings.public_url}/giris#code={code}", "expires_in": 60}
