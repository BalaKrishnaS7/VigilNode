"""
Tests for config.py — startup validation logic.
"""
import os
import sys
import pytest


def test_validate_passes_with_password(monkeypatch):
    """validate() should not exit when DASHBOARD_PASSWORD is set."""
    monkeypatch.setenv("DASHBOARD_PASSWORD", "strongpass123")

    # Re-import config fresh with the patched env
    if "config" in sys.modules:
        del sys.modules["config"]

    from config import Config
    Config.DASHBOARD_PASSWORD = "strongpass123"
    # Should not raise SystemExit
    Config.validate()


def test_validate_blocks_empty_password(monkeypatch):
    """validate() must call sys.exit(1) when password is empty."""
    monkeypatch.setenv("DASHBOARD_PASSWORD", "")

    if "config" in sys.modules:
        del sys.modules["config"]

    from config import Config
    Config.DASHBOARD_PASSWORD = ""

    with pytest.raises(SystemExit) as exc_info:
        Config.validate()

    assert exc_info.value.code == 1


def test_secret_key_default_warning(monkeypatch, capsys):
    """validate() should warn (not exit) if SECRET_KEY is still the default."""
    monkeypatch.setenv("DASHBOARD_PASSWORD", "somepass")

    if "config" in sys.modules:
        del sys.modules["config"]

    from config import Config
    Config.DASHBOARD_PASSWORD = "somepass"
    Config.SECRET_KEY = "change-this-in-production"

    Config.validate()  # Should not exit
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
