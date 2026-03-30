import psutil
from app.alerts.engine import trigger_alert

# Ports that are always expected to be open (customize per setup)
EXPECTED_PORTS = {5000, 22, 80, 443}

_baseline_ports: set = set()


def build_baseline():
    """Snapshot of open ports at startup."""
    global _baseline_ports
    _baseline_ports = _get_listening_ports()
    print(f"[NetworkMonitor] Baseline ports: {_baseline_ports}")


def _get_listening_ports() -> set:
    ports = set()
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.status == "LISTEN" and conn.laddr:
                ports.add(conn.laddr.port)
    except (psutil.AccessDenied, Exception):
        pass
    return ports


def check_network():
    """Detect newly opened ports since baseline."""
    current_ports = _get_listening_ports()
    new_ports = current_ports - _baseline_ports - EXPECTED_PORTS

    for port in new_ports:
        trigger_alert(
            level="MED",
            category="network",
            message=f"New port opened: {port}",
            detail=f"Not in baseline. Current listening ports: {sorted(current_ports)}"
        )
        _baseline_ports.add(port)  # add to baseline so we don't re-alert


def get_network_stats() -> dict:
    """Return basic network I/O stats."""
    try:
        io = psutil.net_io_counters()
        return {
            "bytes_sent": io.bytes_sent,
            "bytes_recv": io.bytes_recv,
            "open_ports": sorted(_get_listening_ports()),
        }
    except Exception:
        return {}
