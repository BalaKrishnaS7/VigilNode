"""
Tests for alerts/engine.py — cooldown and dedup logic.
"""
import os
import pytest
import tempfile


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    """Each test gets its own fresh SQLite database."""
    db_path = str(tmp_path / "test_vigilnode.db")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "testpass")

    # Patch DB path before any import
    import sys
    for mod in ["app.database", "app.alerts.engine", "app.alerts.telegram", "config"]:
        if mod in sys.modules:
            del sys.modules[mod]

    monkeypatch.setenv("DATABASE_PATH", db_path)
    yield db_path


def test_alert_saved_to_db(isolated_db):
    """trigger_alert should save alert to SQLite."""
    from app.database import init_db, get_recent_alerts
    init_db()

    from app.alerts.engine import trigger_alert
    trigger_alert("HIGH", "test", "Test message", "Some detail")

    alerts = get_recent_alerts(10)
    assert len(alerts) >= 1
    assert alerts[0]["message"] == "Test message"
    assert alerts[0]["level"] == "HIGH"
    assert alerts[0]["category"] == "test"


def test_cooldown_prevents_duplicate_alerts(isolated_db):
    """Second identical alert within cooldown window should not re-notify."""
    from app.database import init_db, get_recent_alerts
    init_db()

    from app.alerts.engine import trigger_alert

    fired1 = trigger_alert("MED", "network", "Port opened: 9999")
    fired2 = trigger_alert("MED", "network", "Port opened: 9999")

    assert fired1 is True   # first alert fires
    assert fired2 is False  # second is on cooldown

    # Both should still be saved in DB
    alerts = get_recent_alerts(10)
    assert len(alerts) == 2


def test_different_alerts_not_blocked_by_cooldown(isolated_db):
    """Two different alert messages should both fire regardless of cooldown."""
    from app.database import init_db
    init_db()

    from app.alerts.engine import trigger_alert

    fired1 = trigger_alert("HIGH", "auth", "Brute force from 1.2.3.4")
    fired2 = trigger_alert("HIGH", "auth", "Brute force from 5.6.7.8")

    assert fired1 is True
    assert fired2 is True


def test_cooldown_key_is_category_and_message(isolated_db):
    """Same message in different categories should not share cooldown."""
    from app.database import init_db
    init_db()

    from app.alerts.engine import trigger_alert

    fired1 = trigger_alert("LOW", "process", "High CPU detected")
    fired2 = trigger_alert("LOW", "system",  "High CPU detected")

    assert fired1 is True
    assert fired2 is True
