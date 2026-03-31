"""
Tests for monitors/process.py — baseline, CPU cache, suspicious detection.
"""
import sys
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    """Fresh DB for each test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DATABASE_PATH", db_path)
    monkeypatch.setenv("DASHBOARD_PASSWORD", "testpass")

    for mod in list(sys.modules.keys()):
        if any(m in mod for m in ["app.monitors.process", "app.database",
                                   "app.alerts", "config"]):
            del sys.modules[mod]

    from app.database import init_db
    init_db()
    yield tmp_path


def _make_proc(pid, name, exe="", cpu=0.0):
    """Helper: create a mock psutil process info dict."""
    proc = MagicMock()
    proc.info = {"pid": pid, "name": name, "exe": exe, "username": "user"}
    proc.cpu_percent.return_value = cpu
    proc.pid = pid
    return proc


def test_build_baseline_captures_pids(monkeypatch):
    """build_baseline should populate _baseline_pids."""
    from app.monitors import process as pm

    fake_procs = [_make_proc(1, "init"), _make_proc(2, "bash")]

    with patch("psutil.process_iter", return_value=fake_procs), \
         patch("psutil.Process", side_effect=lambda pid: _make_proc(pid, "x")):
        pm.build_baseline()

    assert 1 in pm._baseline_pids
    assert 2 in pm._baseline_pids


def test_new_process_triggers_alert(monkeypatch, tmp_path):
    """A process not in baseline should trigger a LOW alert."""
    from app.monitors import process as pm
    pm._baseline_pids = {1, 2}
    pm._process_cache = {}
    pm._high_cpu_counts = {}

    new_proc = _make_proc(3, "mystery", exe="/tmp/mystery")

    alerts_fired = []
    def fake_trigger(level, category, message, detail=""):
        alerts_fired.append({"level": level, "category": category, "message": message})
        return True

    # Patch at the module where trigger_alert is USED (process.py), not where defined
    monkeypatch.setattr("app.monitors.process.trigger_alert", fake_trigger)

    with patch("psutil.process_iter", return_value=[new_proc]), \
         patch("psutil.Process", return_value=new_proc):
        pm.check_processes()

    messages = [a["message"] for a in alerts_fired]
    assert any("mystery" in m for m in messages)


def test_suspicious_name_triggers_high_alert(monkeypatch):
    """A process with a known bad name should trigger a HIGH alert."""
    from app.monitors import process as pm
    pm._baseline_pids = {99}
    pm._process_cache = {}
    pm._high_cpu_counts = {}

    bad_proc = _make_proc(99, "xmrig", exe="/usr/bin/xmrig")

    alerts_fired = []
    def fake_trigger(level, category, message, detail=""):
        alerts_fired.append({"level": level, "message": message})
        return True

    monkeypatch.setattr("app.monitors.process.trigger_alert", fake_trigger)

    with patch("psutil.process_iter", return_value=[bad_proc]), \
         patch("psutil.Process", return_value=bad_proc):
        pm.check_processes()

    high_alerts = [a for a in alerts_fired if a["level"] == "HIGH"]
    assert len(high_alerts) >= 1
    assert any("xmrig" in a["message"] for a in high_alerts)


def test_high_cpu_requires_3_consecutive_readings(monkeypatch):
    """Sustained CPU alert should only fire after 3 consecutive high readings."""
    from app.monitors import process as pm
    pm._baseline_pids = {10}
    pm._process_cache = {}
    pm._high_cpu_counts = {}

    high_cpu_proc = _make_proc(10, "heavyjob", exe="/usr/bin/heavyjob", cpu=90.0)
    cached_proc = MagicMock()
    cached_proc.cpu_percent.return_value = 90.0
    pm._process_cache[10] = cached_proc

    alerts_fired = []
    def fake_trigger(level, category, message, detail=""):
        alerts_fired.append({"level": level, "category": category})
        return True

    monkeypatch.setattr("app.monitors.process.trigger_alert", fake_trigger)

    with patch("psutil.process_iter", return_value=[high_cpu_proc]):
        # First two calls — count builds but no CPU alert yet
        pm.check_processes()
        pm.check_processes()
        cpu_alerts = [a for a in alerts_fired if a["category"] == "process" and a["level"] == "LOW"]
        assert len(cpu_alerts) == 0

        # Third call — should now fire
        pm.check_processes()
        cpu_alerts = [a for a in alerts_fired if a["category"] == "process" and a["level"] == "LOW"]
        assert len(cpu_alerts) >= 1
