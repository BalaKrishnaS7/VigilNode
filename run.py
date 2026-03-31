import eventlet
# Patch for async I/O (required for SocketIO)
# Don't patch thread module to avoid Python 3.14 compatibility issues  
eventlet.monkey_patch(socket=True, select=True)

import threading
import time
from app import create_app, socketio
from app.monitors.system import get_system_stats, check_system_thresholds
from app.monitors.process import check_processes, build_baseline
from app.monitors.network import check_network, build_baseline as net_baseline, get_network_stats
from app.monitors.auth_log import check_auth_log
from config import Config

app = create_app()


def system_monitor_thread():
    """Thread 1: Collect system stats every 2s, push to WebSocket."""
    print("[Thread] System monitor started.")
    with app.app_context():
        while True:
            try:
                stats = get_system_stats()
                # Merge network stats so dashboard ports panel updates live
                stats["network"] = get_network_stats()
                # Push to all connected dashboard clients
                socketio.emit("system_stats", stats)
                # Check thresholds and trigger alerts if needed
                check_system_thresholds(stats)
            except Exception as e:
                print(f"[Thread][SystemMonitor] Error: {e}")
            time.sleep(Config.SYSTEM_MONITOR_INTERVAL)


def security_monitor_thread():
    """Thread 2: Run security checks every 10s."""
    print("[Thread] Security monitor started.")
    with app.app_context():
        while True:
            try:
                check_processes()
                check_network()
                check_auth_log()
            except Exception as e:
                print(f"[Thread][SecurityMonitor] Error: {e}")
            time.sleep(Config.SECURITY_MONITOR_INTERVAL)


def alert_push_thread():
    """Thread 3: Poll for new alerts and push to dashboard via WebSocket."""
    from app.database import get_recent_alerts
    last_id = 0

    print("[Thread] Alert push thread started.")
    with app.app_context():
        # Get current max ID as starting point
        alerts = get_recent_alerts(1)
        if alerts:
            last_id = alerts[0]["id"]

        while True:
            try:
                alerts = get_recent_alerts(10)
                for alert in reversed(alerts):
                    if alert["id"] > last_id:
                        socketio.emit("new_alert", alert)
                        last_id = alert["id"]
            except Exception as e:
                print(f"[Thread][AlertPush] Error: {e}")
            time.sleep(2)


if __name__ == "__main__":
    # Validate config before anything else — exits with clear message if misconfigured
    Config.validate()

    print("""
  ██╗   ██╗██╗ ██████╗ ██╗██╗     ███╗   ██╗ ██████╗ ██████╗ ███████╗
  ██║   ██║██║██╔════╝ ██║██║     ████╗  ██║██╔═══██╗██╔══██╗██╔════╝
  ██║   ██║██║██║  ███╗██║██║     ██╔██╗ ██║██║   ██║██║  ██║█████╗
  ╚██╗ ██╔╝██║██║   ██║██║██║     ██║╚██╗██║██║   ██║██║  ██║██╔══╝
   ╚████╔╝ ██║╚██████╔╝██║███████╗██║ ╚████║╚██████╔╝██████╔╝███████╗
    ╚═══╝  ╚═╝ ╚═════╝ ╚═╝╚══════╝╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝
    Security-Aware Home Server Agent | http://localhost:5000
    """)

    # Build baselines before starting monitors
    build_baseline()
    net_baseline()

    # Start background threads (daemon=True so they die when main exits)
    threads = [
        threading.Thread(target=system_monitor_thread, daemon=True),
        threading.Thread(target=security_monitor_thread, daemon=True),
        threading.Thread(target=alert_push_thread, daemon=True),
    ]

    for t in threads:
        t.start()

    print("[VigilNode] All monitors running. Dashboard at http://localhost:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)