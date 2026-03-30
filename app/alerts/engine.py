from app.database import save_alert, is_on_cooldown, set_cooldown
from app.alerts.telegram import send_telegram
from datetime import datetime


def trigger_alert(level: str, category: str, message: str, detail: str = ""):
    """
    Central alert handler.
    - Checks cooldown to prevent spam
    - Saves to SQLite
    - Sends Telegram if not on cooldown
    - Returns True if alert was fired
    """
    cooldown_key = f"{category}:{message[:40]}"

    on_cooldown = is_on_cooldown(cooldown_key)

    # Always save to DB
    notified = False
    if not on_cooldown:
        msg = format_telegram_message(level, category, message, detail)
        notified = send_telegram(msg)
        set_cooldown(cooldown_key)

    save_alert(level, category, message, detail, notified)

    status = "fired" if not on_cooldown else "cooldown"
    print(f"[Alert][{status}] [{level}] {category}: {message}")
    return not on_cooldown


def format_telegram_message(level, category, message, detail):
    icons = {"HIGH": "🔴", "MED": "🟡", "LOW": "🔵"}
    icon = icons.get(level, "⚪")
    time = datetime.now().strftime("%H:%M:%S")

    msg = f"{icon} <b>VigilNode Alert</b>\n"
    msg += f"<b>Level:</b> {level}\n"
    msg += f"<b>Category:</b> {category}\n"
    msg += f"<b>Message:</b> {message}\n"
    if detail:
        msg += f"<b>Detail:</b> {detail}\n"
    msg += f"<b>Time:</b> {time}"
    return msg
