import hashlib
import secrets
from datetime import timedelta
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, select, update
from .audit import audit
from .config import settings
from .db import get_db
from .models import AuthSession, LaunchCode, Tenant, User, iso, now, utc

STAFF_ROLES = {"support_agent", "platform_admin"}
COOKIE = "support_session"
CUSTOMER_SESSION_SECONDS = 900
STAFF_SESSION_SECONDS = 28800
WEAK_PASSWORDS = {"password", "parola", "123456789012", "qwertyuiop12", "senseikdestek", "destekdestek", "algosense123"}


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


def password_problem(password, email="", name=""):
    """Plain-language policy check (ISO 27001 A.5.17): length, no personal data, no trivial patterns."""
    if len(password) < 12:
        return "Parola en az 12 karakter olmalı."
    if len(password) > 200:
        return "Parola en fazla 200 karakter olabilir."
    lowered = password.lower()
    if lowered.replace(" ", "") in WEAK_PASSWORDS or len(set(lowered)) < 4:
        return "Bu parola tahmin edilebilir. Daha uzun ve çeşitli bir parola seçin."
    local = email.lower().split("@")[0]
    if local and len(local) >= 3 and local in lowered:
        return "Parola e-posta adresinizi içeremez."
    for part in name.lower().split():
        if len(part) >= 3 and part in lowered:
            return "Parola adınızı içeremez."
    return None


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
            "tenant": {"id": tenant.id, "name": tenant.name, "slug": tenant.slug} if tenant else None, "csrf_token": csrf_token,
            "email_notifications": user.email_notifications, "mail_enabled": settings.mail_enabled,
            "password_changed_at": iso(user.password_changed_at), "has_password": bool(user.password_hash)}


def create_session(db, user, response, short=False, request=None, action="login.success"):
    ensure_active(db, user)
    token, csrf = secrets.token_urlsafe(40), secrets.token_urlsafe(32)
    duration = CUSTOMER_SESSION_SECONDS if short else STAFF_SESSION_SECONDS
    db.execute(delete(AuthSession).where(AuthSession.expires_at < now()))
    db.add(AuthSession(token_hash=digest(token), user_id=user.id, csrf_token=csrf, expires_at=now() + timedelta(seconds=duration), last_seen_at=now()))
    if request is not None:
        audit(db, request, user, action, "user", user.id)
    db.commit()
    response.set_cookie(COOKIE, token, max_age=duration, httponly=True, secure=settings.cookie_secure, samesite="lax", path="/")
    return user_view(db, user, csrf)


def lock_state(user):
    return bool(user and user.locked_until and utc(user.locked_until) > now())


def record_login_failure(db, request, user, email):
    """Per-account lockout complements the per-IP rate limit; failures are always audited."""
    if not user:
        audit(db, request, None, "login.failed", "user", email[:120], outcome="failure")
        db.commit()
        return
    user.failed_logins = (user.failed_logins or 0) + 1
    if user.failed_logins >= settings.login_lock_threshold:
        user.locked_until = now() + timedelta(minutes=settings.login_lock_minutes)
        user.failed_logins = 0
        audit(db, request, user, "login.locked", "user", user.id, f"{settings.login_lock_minutes} dakika", outcome="failure")
    else:
        audit(db, request, user, "login.failed", "user", user.id, outcome="failure")
    db.commit()


def authenticate_staff(db, request, email, password):
    user = db.scalar(select(User).where(User.email == email.lower(), User.role.in_(STAFF_ROLES), User.active == True))
    # A dummy hash path prevents a fast non-existent-account branch.
    valid = check_password(password, user.password_hash if user else "0" * 32 + ":" + "0" * 128)
    if lock_state(user):
        audit(db, request, user, "login.failed", "user", user.id, "Hesap kilitli", outcome="failure")
        db.commit()
        raise HTTPException(423, f"Hesap geçici olarak kilitlendi. {settings.login_lock_minutes} dakika sonra tekrar deneyin.")
    if not user or not valid:
        record_login_failure(db, request, user, email)
        raise HTTPException(401, "E-posta veya parola hatalı.")
    user.failed_logins, user.locked_until = 0, None
    return user


def current_user(request: Request, db=Depends(get_db)):
    raw = request.cookies.get(COOKIE, "")
    session = db.get(AuthSession, digest(raw)) if raw else None
    if not session or utc(session.expires_at) <= now():
        raise HTTPException(401, "Devam etmek için giriş yapın.")
    user = db.get(User, session.user_id)
    ensure_active(db, user)
    if user.role in STAFF_ROLES and session.last_seen_at and utc(session.last_seen_at) < now() - timedelta(minutes=settings.staff_idle_minutes):
        db.delete(session)
        audit(db, request, user, "session.idle_expired", "user", user.id)
        db.commit()
        raise HTTPException(401, "Oturumunuz hareketsizlik nedeniyle kapatıldı. Tekrar giriş yapın.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("X-CSRF-Token", "")
        if not csrf or not secrets.compare_digest(csrf, session.csrf_token):
            raise HTTPException(403, "Oturum doğrulanamadı. Sayfayı yenileyin.")
    if not session.last_seen_at or utc(session.last_seen_at) < now() - timedelta(minutes=1):
        session.last_seen_at = now()
        db.commit()
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


def change_password(db, request, user, current, new):
    if not check_password(current, user.password_hash):
        audit(db, request, user, "password.change_failed", "user", user.id, "Mevcut parola hatalı", outcome="failure")
        db.commit()
        raise HTTPException(403, "Mevcut parola hatalı.")
    problem = password_problem(new, user.email, user.name)
    if problem:
        raise HTTPException(422, problem)
    if check_password(new, user.password_hash):
        raise HTTPException(422, "Yeni parola mevcut paroladan farklı olmalı.")
    user.password_hash = hash_password(new)
    user.password_changed_at = now()
    # Every other session of this account ends; the current one keeps working.
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.token_hash != request.state.session.token_hash))
    audit(db, request, user, "password.change", "user", user.id)
    db.commit()


def create_launch_code(db, user):
    code = secrets.token_urlsafe(40)
    db.execute(delete(LaunchCode).where(LaunchCode.expires_at < now()))
    db.add(LaunchCode(token_hash=digest(code), user_id=user.id, expires_at=now() + timedelta(seconds=60)))
    db.commit()
    return code


def consume_launch_code(db, code, request=None):
    token_hash = digest(code)
    row = db.execute(update(LaunchCode).where(LaunchCode.token_hash == token_hash, LaunchCode.consumed == False, LaunchCode.expires_at > now()).values(consumed=True).returning(LaunchCode.user_id)).first()
    if not row:
        if request is not None:
            audit(db, request, None, "session.exchange_failed", "launch_code", "", outcome="failure")
            db.commit()
        raise HTTPException(401, "Giriş bağlantısının süresi dolmuş veya kullanılmış. SenseİK'ten tekrar açın.")
    user = db.get(User, row[0])
    ensure_active(db, user)
    return user
