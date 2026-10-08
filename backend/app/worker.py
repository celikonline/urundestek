"""Standalone background worker: reminders, assistant jobs, mail delivery, auto-close and retention purge."""
import logging
import time
from .config import settings
from .main import run_jobs

logging.basicConfig(level=logging.INFO)
if __name__ == "__main__":
    while True:
        try:
            run_jobs()
        except Exception as exc:
            logging.error("background_worker_failed error_type=%s", type(exc).__name__)
        time.sleep(settings.worker_interval_seconds)
