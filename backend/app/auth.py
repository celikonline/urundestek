import hashlib
import secrets
from datetime import timedelta
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, select, update
from .config import settings
from .db import get_db
from .models import AuthSession, LaunchCode, Tenant, User, now, utc

STAFF_ROLES = {"support_agent", "platform_admin"}
COOKIE = "support_session"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password):
    salt = secrets.token_hex(16)
    hashed = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"{salt}:{hashed}"


def check_password(password, stored):
    if not stored:
        return False
    salt, expected = stored.split(":")
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return secrets.compare_digest(actual, expected)


def ensure_active(db, user):
    if not user or not user.active:
        raise HTTPException(401, "Oturumunuz sona erdi. Tekrar giriş yapın.")
    if user.role not in STAFF_ROLES:
        tenant = db.get(Tenant, user.tenant_id)
        if not tenant or not tenant.active:
            raise HTTPException(403, "Firmanızın destek erişimi kapalı.")


def user_view(db, user, csrf_token):
    tenant = db.get(Tenant, user.tenant_id) if user.tenant_id else None
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "is_staff": user.role in STAFF_ROLES,
            "tenant": {"id": tenant.id, "name": tenant.name, "slug": tenant.slug} if tenant else None, "csrf_token": csrf_token}


def create_session(db, user, response, short=False):
    ensure_active(db, user)
    token, csrf = secrets.token_urlsafe(40), secrets.token_urlsafe(32)
    duration = 900 if short else 28800
    db.execute(delete(AuthSession).where(AuthSession.expires_at < now()))
    db.add(AuthSession(token_hash=digest(token), user_id=user.id, csrf_token=csrf, expires_at=now() + timedelta(seconds=duration)))
    db.commit()
    response.set_cookie(COOKIE, token, max_age=duration, httponly=True, secure=settings.cookie_secure, samesite="lax", path="/")
    return user_view(db, user, csrf)


def current_user(request: Request, db=Depends(get_db)):
    raw = request.cookies.get(COOKIE, "")
    session = db.get(AuthSession, digest(raw)) if raw else None
    if not session or utc(session.expires_at) <= now():
        raise HTTPException(401, "Devam etmek için giriş yapın.")
    user = db.get(User, session.user_id)
    ensure_active(db, user)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("X-CSRF-Token", "")
        if not csrf or not secrets.compare_digest(csrf, session.csrf_token):
            raise HTTPException(403, "Oturum doğrulanamadı. Sayfayı yenileyin.")
    request.state.session = session
    return user


def staff_user(user=Depends(current_user)):
    if user.role not in STAFF_ROLES:
        raise HTTPException(403, "Bu işlem için destek ekibi yetkisi gerekiyor.")
    return user


def platform_user(user=Depends(staff_user)):
    if user.role != "platform_admin":
        raise HTTPException(403, "Bu işlem için platform yöneticisi yetkisi gerekiyor.")
    return user


def create_launch_code(db, user):
    code = secrets.token_urlsafe(40)
    db.execute(delete(LaunchCode).where(LaunchCode.expires_at < now()))
    db.add(LaunchCode(token_hash=digest(code), user_id=user.id, expires_at=now() + timedelta(seconds=60)))
    db.commit()
    return code


def consume_launch_code(db, code):
    token_hash = digest(code)
    row = db.execute(update(LaunchCode).where(LaunchCode.token_hash == token_hash, LaunchCode.consumed == False, LaunchCode.expires_at > now()).values(consumed=True).returning(LaunchCode.user_id)).first()
    if not row:
        raise HTTPException(401, "Giriş bağlantısının süresi dolmuş veya kullanılmış. SenseİK'ten tekrar açın.")
    user = db.get(User, row[0])
    ensure_active(db, user)
    return user
