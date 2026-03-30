import os
import sys
from dotenv import load_dotenv

load_dotenv()

def _require(key: str, default: str | None = None) -> str:
    """Get env var. If it's still the insecure default, warn loudly."""
    val = os.getenv(key, default)
    return val

class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")

    # Dashboard auth — warn if using defaults
    DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME", "admin")
    DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # Thresholds
    CPU_ALERT_THRESHOLD = int(os.getenv("CPU_ALERT_THRESHOLD", 85))
    RAM_ALERT_THRESHOLD = int(os.getenv("RAM_ALERT_THRESHOLD", 90))
    DISK_ALERT_THRESHOLD = int(os.getenv("DISK_ALERT_THRESHOLD", 95))
    TEMP_ALERT_THRESHOLD = int(os.getenv("TEMP_ALERT_THRESHOLD", 80))

    # Security
    FAILED_LOGIN_THRESHOLD = int(os.getenv("FAILED_LOGIN_THRESHOLD", 5))
    FAILED_LOGIN_WINDOW = int(os.getenv("FAILED_LOGIN_WINDOW", 60))  # seconds
    ALERT_COOLDOWN = int(os.getenv("ALERT_COOLDOWN", 600))           # 10 minutes

    # Monitor intervals (seconds)
    SYSTEM_MONITOR_INTERVAL = 2
    SECURITY_MONITOR_INTERVAL = 10

    # Database
    DATABASE_PATH = os.getenv("DATABASE_PATH", "vigilnode.db")

    @classmethod
    def validate(cls):
        """Called at startup — blocks launch if critical config is missing."""
        errors = []

        if not cls.DASHBOARD_PASSWORD:
            errors.append(
                "  DASHBOARD_PASSWORD is not set.\n"
                "  Copy .env.example to .env and set a strong password."
            )

        if cls.SECRET_KEY == "change-this-in-production":
            print("[Config] WARNING: SECRET_KEY is using the insecure default. Set a random value in .env.")

        if errors:
            print("\n[VigilNode] Cannot start — missing required configuration:\n")
            for e in errors:
                print(e)
            print()
            sys.exit(1)