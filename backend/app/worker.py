import logging
import time
from .main import run_reminders

logging.basicConfig(level=logging.INFO)
if __name__ == "__main__":
    while True:
        try:
            run_reminders()
        except Exception as exc:
            logging.error("reminder_worker_failed error_type=%s", type(exc).__name__)
        time.sleep(30)
