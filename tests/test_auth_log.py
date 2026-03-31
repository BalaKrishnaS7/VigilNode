"""
Tests for monitors/auth_log.py — file position tracking and brute-force detection.
"""
import os
import sys
import pytest
import tempfile


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    """Fresh DB and clean monitor state for each test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DATABASE_PATH", db_path)
    monkeypatch.setenv("DASHBOARD_PASSWORD", "testpass")

    # Force reimport of affected modules to reset module-level state
    for mod in list(sys.modules.keys()):
        if any(m in mod for m in ["app.monitors.auth_log", "app.database",
                                   "app.alerts", "config"]):
            del sys.modules[mod]

    from app.database import init_db
    init_db()
    yield tmp_path


def _write_log(path, lines):
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def _append_log(path, lines):
    with open(path, "a") as f:
        f.write("\n".join(lines) + "\n")


def test_first_call_primes_position_no_alert(isolated_db, monkeypatch):
    """First check_auth_log call should seek to end and produce no alerts."""
    log_file = isolated_db / "auth.log"
    _write_log(log_file, [
        "Failed password for root from 1.2.3.4 port 22",
        "Failed password for root from 1.2.3.4 port 22",
        "Failed password for root from 1.2.3.4 port 22",
        "Failed password for root from 1.2.3.4 port 22",
        "Failed password for root from 1.2.3.4 port 22",
    ])

    from app.monitors import auth_log as al
    monkeypatch.setattr(al, "get_log_path", lambda: str(log_file))
    monkeypatch.setattr(al, "_log_file_position", 0)

    from app.database import get_recent_alerts
    al.check_auth_log()

    alerts = get_recent_alerts(10)
    # Pre-existing log lines should NOT trigger an alert on first call
    assert len(alerts) == 0


def test_new_failures_after_prime_trigger_alert(isolated_db, monkeypatch):
    """Failures added AFTER first call should trigger brute-force alert."""
    log_file = isolated_db / "auth.log"
    _write_log(log_file, ["sshd: server started"])  # pre-existing harmless content

    from app.monitors import auth_log as al
    monkeypatch.setattr(al, "get_log_path", lambda: str(log_file))
    al._log_file_position = 0
    al._failed_attempts = {}

    # Track alerts via the engine directly
    fired = []
    import app.alerts.engine as eng
    original_trigger = eng.trigger_alert
    def capturing_trigger(level, category, message, detail=""):
        fired.append({"level": level, "category": category, "message": message})
        return original_trigger(level, category, message, detail)
    monkeypatch.setattr(eng, "trigger_alert", capturing_trigger)
    monkeypatch.setattr(al, "trigger_alert", capturing_trigger)

    # First call — primes position, no alerts expected
    al.check_auth_log()
    assert len(fired) == 0

    # Append 5 new failures
    _append_log(log_file, [
        "Failed password for root from 9.9.9.9 port 22",
        "Failed password for root from 9.9.9.9 port 22",
        "Failed password for root from 9.9.9.9 port 22",
        "Failed password for root from 9.9.9.9 port 22",
        "Failed password for root from 9.9.9.9 port 22",
    ])

    al.check_auth_log()
    assert any("9.9.9.9" in a["message"] for a in fired)


def test_old_lines_not_recounted(isolated_db, monkeypatch):
    """Calling check_auth_log multiple times should not recount old lines."""
    log_file = isolated_db / "auth.log"
    _write_log(log_file, ["sshd: started"])

    from app.monitors import auth_log as al
    monkeypatch.setattr(al, "get_log_path", lambda: str(log_file))
    al._log_file_position = 0
    al._failed_attempts = {}

    # Prime
    al.check_auth_log()

    # Add exactly 3 failures (below threshold of 5)
    _append_log(log_file, [
        "Failed password for user from 1.1.1.1 port 22",
        "Failed password for user from 1.1.1.1 port 22",
        "Failed password for user from 1.1.1.1 port 22",
    ])
    al.check_auth_log()

    # Call again — should NOT recount those 3 lines
    al.check_auth_log()
    al.check_auth_log()

    from app.database import get_recent_alerts
    alerts = get_recent_alerts(10)
    # Should have 0 alerts — never reached threshold of 5
    assert len(alerts) == 0
