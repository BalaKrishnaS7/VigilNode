import sqlite3
import os
from datetime import datetime
from config import Config

DB_PATH = Config.DATABASE_PATH


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,           -- HIGH, MED, LOW
            category TEXT NOT NULL,        -- system, process, network, auth
            message TEXT NOT NULL,
            detail TEXT,
            timestamp TEXT NOT NULL,
            notified INTEGER DEFAULT 0     -- 1 if Telegram sent
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_cooldowns (
            key TEXT PRIMARY KEY,          -- unique key per alert type
            last_sent TEXT NOT NULL        -- ISO timestamp
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialized.")


def save_alert(level, category, message, detail="", notified=False):
    conn = get_db()
    conn.execute(
        "INSERT INTO alerts (level, category, message, detail, timestamp, notified) VALUES (?,?,?,?,?,?)",
        (level, category, message, detail, datetime.now().isoformat(), 1 if notified else 0)
    )
    conn.commit()
    conn.close()


def get_recent_alerts(limit=50):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def is_on_cooldown(key):
    """Returns True if this alert type was sent within ALERT_COOLDOWN seconds."""
    from datetime import timezone
    conn = get_db()
    row = conn.execute(
        "SELECT last_sent FROM alert_cooldowns WHERE key = ?", (key,)
    ).fetchone()
    conn.close()

    if not row:
        return False

    last = datetime.fromisoformat(row["last_sent"])
    now = datetime.now()
    diff = (now - last).total_seconds()
    return diff < Config.ALERT_COOLDOWN


def set_cooldown(key):
    conn = get_db()
    conn.execute(
        "INSERT INTO alert_cooldowns (key, last_sent) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET last_sent=excluded.last_sent",
        (key, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
