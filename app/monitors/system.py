import psutil
import platform
from app.alerts.engine import trigger_alert
from config import Config


def get_system_stats() -> dict:
    """Collect current system stats. Called every 2 seconds."""
    stats = {
        "cpu": psutil.cpu_percent(interval=1),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage("/").percent,
        "temp": get_temperature(),
        "platform": platform.system(),
    }
    return stats


def get_temperature() -> float | None:
    """Get CPU temperature. Returns None if not available."""
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        # Try common sensor names
        for key in ["coretemp", "cpu_thermal", "k10temp", "acpitz"]:
            if key in temps:
                return round(temps[key][0].current, 1)
        # Fallback to first available
        first_key = list(temps.keys())[0]
        return round(temps[first_key][0].current, 1)
    except (AttributeError, Exception):
        return None


def check_system_thresholds(stats: dict):
    """Check if any system metric has crossed alert thresholds."""
    if stats["cpu"] >= Config.CPU_ALERT_THRESHOLD:
        trigger_alert(
            level="MED",
            category="system",
            message=f"High CPU usage: {stats['cpu']}%",
            detail=f"Threshold: {Config.CPU_ALERT_THRESHOLD}%"
        )

    if stats["ram"] >= Config.RAM_ALERT_THRESHOLD:
        trigger_alert(
            level="MED",
            category="system",
            message=f"High RAM usage: {stats['ram']}%",
            detail=f"Threshold: {Config.RAM_ALERT_THRESHOLD}%"
        )

    if stats["disk"] >= Config.DISK_ALERT_THRESHOLD:
        trigger_alert(
            level="HIGH",
            category="system",
            message=f"Disk almost full: {stats['disk']}%",
            detail=f"Threshold: {Config.DISK_ALERT_THRESHOLD}%"
        )

    if stats["temp"] and stats["temp"] >= Config.TEMP_ALERT_THRESHOLD:
        trigger_alert(
            level="HIGH",
            category="system",
            message=f"High CPU temperature: {stats['temp']}°C",
            detail=f"Threshold: {Config.TEMP_ALERT_THRESHOLD}°C"
        )
