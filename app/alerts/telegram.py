import requests
from config import Config


def send_telegram(message: str) -> bool:
    """Send a message via Telegram bot. Returns True if successful."""
    token = Config.TELEGRAM_BOT_TOKEN
    chat_id = Config.TELEGRAM_CHAT_ID

    if not token or not chat_id:
        print("[Telegram] Not configured — skipping notification.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code == 200:
            print(f"[Telegram] Sent: {message[:60]}...")
            return True
        else:
            print(f"[Telegram] Failed: {resp.status_code} {resp.text}")
            return False
    except requests.RequestException as e:
        print(f"[Telegram] Error: {e}")
        return False
