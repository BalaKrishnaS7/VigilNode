import platform
import re
import os
from datetime import datetime, timedelta
from app.alerts.engine import trigger_alert
from config import Config

# Stores recent failed attempts: ip → list of actual datetimes parsed from log
_failed_attempts: dict = {}

# Track file position so we only read NEW lines each scan cycle
# This prevents re-counting old log entries on every call
_log_file_position: int = 0


def get_log_path() -> str | None:
    """Return the correct auth log path for this OS."""
    system = platform.system()
    if system == "Linux":
        # Debian/Ubuntu
        if os.path.exists("/var/log/auth.log"):
            return "/var/log/auth.log"
        # RHEL/CentOS/Fedora
        if os.path.exists("/var/log/secure"):
            return "/var/log/secure"
    elif system == "Darwin":
        return "/var/log/system.log"
    # Windows uses Event Log — not handled via file parsing
    return None


def check_auth_log():
    """
    Parse auth log for failed SSH login attempts.
    Only reads NEW lines since last scan using file position tracking.
    Alerts if an IP exceeds FAILED_LOGIN_THRESHOLD in FAILED_LOGIN_WINDOW seconds.
    """
    global _log_file_position

    log_path = get_log_path()
    if not log_path:
        return  # Windows or unsupported OS

    try:
        with open(log_path, "r", errors="ignore") as f:
            # On first run, seek to end — we only care about new events
            # not historical log entries from before VigilNode started
            if _log_file_position == 0:
                f.seek(0, 2)  # seek to end of file
                _log_file_position = f.tell()
                return

            # Check if log was rotated (file got smaller)
            f.seek(0, 2)
            current_size = f.tell()
            if current_size < _log_file_position:
                # Log was rotated — reset position to start of new file
                _log_file_position = 0

            # Read only new lines since last scan
            f.seek(_log_file_position)
            new_lines = f.readlines()
            _log_file_position = f.tell()

    except (PermissionError, FileNotFoundError):
        return

    if not new_lines:
        return

    now = datetime.now()
    window = timedelta(seconds=Config.FAILED_LOGIN_WINDOW)

    # Pattern matches: "Failed password for [user] from [ip]"
    pattern = re.compile(r"Failed password for .+ from ([\d\.]+)")

    for line in new_lines:
        match = pattern.search(line)
        if not match:
            continue

        ip = match.group(1)
        if ip not in _failed_attempts:
            _failed_attempts[ip] = []

        # Record actual time of this attempt
        _failed_attempts[ip].append(now)

        # Prune attempts outside the time window
        _failed_attempts[ip] = [
            t for t in _failed_attempts[ip] if now - t <= window
        ]

        count = len(_failed_attempts[ip])

        if count >= Config.FAILED_LOGIN_THRESHOLD:
            trigger_alert(
                level="HIGH",
                category="auth",
                message=f"Brute force attempt detected from {ip}",
                detail=f"{count} failed logins in {Config.FAILED_LOGIN_WINDOW}s"
            )
            # Reset count for this IP after alerting
            _failed_attempts[ip] = []