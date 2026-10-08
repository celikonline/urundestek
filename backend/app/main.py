import asyncio
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import settings
from .db import SessionLocal
from .routes import router
from .seed import bootstrap_admin, seed_demo
from .services import dispatch_reminders

logger = logging.getLogger("support")
attempts = defaultdict(deque)


async def reminder_loop():
    while True:
        try:
            await asyncio.to_thread(run_reminders)
        except Exception as exc:
            logger.error("reminder_worker_failed error_type=%s", type(exc).__name__)
        await asyncio.sleep(30)


def run_reminders():
    with SessionLocal() as db:
        dispatch_reminders(db)


@asynccontextmanager
async def lifespan(app):
    with SessionLocal() as db:
        if settings.app_env == "development":
            seed_demo(db)
        bootstrap_admin(db)
    task = asyncio.create_task(reminder_loop()) if settings.run_reminder_worker else None
    yield
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def create_app():
    app = FastAPI(title="SenseİK Destek API", version="1.0.0", lifespan=lifespan, docs_url="/api/docs" if settings.app_env != "production" else None, openapi_url="/api/openapi.json" if settings.app_env != "production" else None, redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.origins), allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "Idempotency-Key"])

    @app.middleware("http")
    async def protect(request: Request, call_next):
        correlation = str(uuid4())
        request.state.correlation_id = correlation
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in settings.origins:
            return JSONResponse({"detail": "Bu adresten işlem yapılamıyor."}, status_code=403)
        if request.url.path in {"/api/v1/auth/login", "/api/v1/auth/exchange", "/api/v1/auth/launch"} and request.method == "POST":
            key = (request.client.host if request.client else "unknown", request.url.path)
            current = time.monotonic()
            for old_key in list(attempts):
                if not attempts[old_key] or attempts[old_key][-1] < current - 60:
                    del attempts[old_key]
            queue = attempts[key]
            while queue and queue[0] < current - 60:
                queue.popleft()
            if len(queue) >= 30:
                return JSONResponse({"detail": "Çok fazla deneme. Bir dakika sonra tekrar deneyin."}, 429, headers={"Retry-After": "60"})
            queue.append(current)
        response = await call_next(request)
        response.headers.update({"X-Correlation-ID": correlation, "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})
        return response

    @app.exception_handler(RequestValidationError)
    async def validation(request, exc):
        return JSONResponse({"detail": "Alanları kontrol edin. Zorunlu bilgileri ve geçerli tarih/saat değerlerini girin.", "fields": [str(e["loc"][-1]) for e in exc.errors()]}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        correlation = getattr(request.state, "correlation_id", str(uuid4()))
        logger.error("request_failed correlation_id=%s error_type=%s", correlation, type(exc).__name__)
        return JSONResponse({"detail": "İşlem tamamlanamadı. Tekrar deneyin.", "correlation_id": correlation}, status_code=500)

    app.include_router(router)
    return app


app = create_app()
