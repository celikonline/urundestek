import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@dataclass
class Settings:
    app_env: str = os.getenv("APP_ENV", "production")
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'support.db'}")
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "true").lower() == "true"
    public_url: str = os.getenv("PUBLIC_URL", "http://localhost:5173").rstrip("/")
    senseik_api_url: str = os.getenv("SENSEIK_API_URL", "").rstrip("/")
    senseik_web_origin: str = os.getenv("SENSEIK_WEB_ORIGIN", "").rstrip("/")
    run_reminder_worker: bool = os.getenv("RUN_REMINDER_WORKER", "true").lower() == "true"
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", str(ROOT / "data" / "uploads")))
    smtp_host: str = os.getenv("SMTP_HOST", "").strip()
    smtp_port: int = int(os.getenv("SMTP_PORT", "587") or 587)
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_tls: str = os.getenv("SMTP_TLS", "starttls").strip().lower()
    mail_from: str = os.getenv("MAIL_FROM", "").strip()

    login_lock_threshold: int = int(os.getenv("LOGIN_LOCK_THRESHOLD", "5") or 5)
    login_lock_minutes: int = int(os.getenv("LOGIN_LOCK_MINUTES", "15") or 15)
    staff_idle_minutes: int = int(os.getenv("STAFF_IDLE_MINUTES", "60") or 60)
    audit_retention_days: int = int(os.getenv("AUDIT_RETENTION_DAYS", "730") or 0)
    notification_retention_days: int = int(os.getenv("NOTIFICATION_RETENTION_DAYS", "180") or 0)
    mail_retention_days: int = int(os.getenv("MAIL_RETENTION_DAYS", "30") or 0)
    closed_ticket_retention_days: int = int(os.getenv("CLOSED_TICKET_RETENTION_DAYS", "0") or 0)
    ai_mode: str = os.getenv("AI_MODE", "draft").strip().lower()
    ai_model: str = os.getenv("AI_MODEL", "claude-opus-5-5").strip()
    ai_max_auto_replies: int = int(os.getenv("AI_MAX_AUTO_REPLIES", "3") or 3)
    ai_min_confidence: float = float(os.getenv("AI_MIN_CONFIDENCE", "0.7") or 0.7)
    ai_knowledge_file: Path = Path(os.getenv("AI_KNOWLEDGE_FILE", "docs/ai-bilgi-bankasi.md"))
    auto_close_days: int = int(os.getenv("AUTO_CLOSE_DAYS", "7") or 0)
    worker_interval_seconds: int = int(os.getenv("WORKER_INTERVAL_SECONDS", "10") or 10)
    response_target_hours: dict = None

    def __post_init__(self):
        # Customer-facing first-response promise per priority, in calendar hours.
        self.response_target_hours = {"urgent": int(os.getenv("RESPONSE_HOURS_URGENT", "2") or 2), "high": int(os.getenv("RESPONSE_HOURS_HIGH", "4") or 4), "normal": int(os.getenv("RESPONSE_HOURS_NORMAL", "8") or 8)}

    @property
    def ai_available(self):
        return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")) and self.ai_mode in {"draft", "auto"}

    @property
    def mail_enabled(self):
        return bool(self.smtp_host and self.mail_from)

    @property
    def origins(self):
        return {self.public_url, self.senseik_web_origin} - {""}


settings = Settings()
