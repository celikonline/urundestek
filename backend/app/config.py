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

    @property
    def origins(self):
        return {self.public_url, self.senseik_web_origin} - {""}


settings = Settings()
