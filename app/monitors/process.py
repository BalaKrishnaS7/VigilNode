import psutil
from app.alerts.engine import trigger_alert

# Known suspicious process names (basic list — extend as needed)
SUSPICIOUS_NAMES = [
    "cryptominer", "xmrig", "minerd", "cgminer", "bfgminer",
    "nmap", "masscan", "hydra", "sqlmap", "metasploit",
]

# Paths that are unusual for legitimate processes
SUSPICIOUS_PATHS = ["/tmp/", "/dev/shm/", "\\Temp\\", "\\AppData\\Roaming\\"]

# Baseline: process PIDs seen at startup
_baseline_pids: set = set()

# Cache of psutil.Process objects for CPU measurement.
# psutil.cpu_percent() returns 0.0 on first call per process — it needs
# two calls with a time gap to calculate actual usage. We keep Process
# objects alive between scan cycles so the second call returns real data.
_process_cache: dict = {}   # pid → psutil.Process
_high_cpu_counts: dict = {} # pid → consecutive high-CPU reading count


def build_baseline():
    """Take a snapshot of running PIDs at startup and prime CPU counters."""
    global _baseline_pids
    _baseline_pids = {p.pid for p in psutil.process_iter(["pid"])}

    # Prime the CPU percent counters — first call always returns 0,
    # so we call it now at baseline so the NEXT call (in check_processes)
    # returns a real value.
    for pid in _baseline_pids:
        try:
            proc = psutil.Process(pid)
            proc.cpu_percent()          # first call — primes the counter
            _process_cache[pid] = proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    print(f"[ProcessMonitor] Baseline: {len(_baseline_pids)} processes.")


def check_processes():
    """Scan all running processes for suspicious behavior."""
    current_pids = set()

    for proc in psutil.process_iter(["pid", "name", "exe", "username"]):
        try:
            pid = proc.info["pid"]
            name = (proc.info["name"] or "").lower()
            exe = (proc.info["exe"] or "").replace("\\", "/")
            current_pids.add(pid)

            # Get CPU% from cached Process object (second call = real value)
            # If not in cache yet, add it now and skip CPU check this cycle
            if pid not in _process_cache:
                try:
                    p = psutil.Process(pid)
                    p.cpu_percent()         # prime — real value next cycle
                    _process_cache[pid] = p
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                cpu = 0.0
            else:
                try:
                    cpu = _process_cache[pid].cpu_percent()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    cpu = 0.0

            # 1. Known bad process name
            if any(bad in name for bad in SUSPICIOUS_NAMES):
                trigger_alert(
                    level="HIGH",
                    category="process",
                    message=f"Suspicious process detected: {name}",
                    detail=f"PID: {pid} | Path: {exe}"
                )

            # 2. Running from suspicious path
            if exe and any(path in exe for path in SUSPICIOUS_PATHS):
                trigger_alert(
                    level="MED",
                    category="process",
                    message=f"Process running from suspicious path: {name}",
                    detail=f"PID: {pid} | Path: {exe}"
                )

            # 3. Sustained high CPU — only reliable after first scan cycle
            if cpu > 80:
                _high_cpu_counts[pid] = _high_cpu_counts.get(pid, 0) + 1
                if _high_cpu_counts[pid] >= 3:
                    trigger_alert(
                        level="LOW",
                        category="process",
                        message=f"Process sustained high CPU: {name} ({cpu:.1f}%)",
                        detail=f"PID: {pid}"
                    )
            else:
                _high_cpu_counts.pop(pid, None)

            # 4. New process not in baseline
            if pid not in _baseline_pids:
                trigger_alert(
                    level="LOW",
                    category="process",
                    message=f"New process appeared: {name}",
                    detail=f"PID: {pid} | Path: {exe}"
                )
                _baseline_pids.add(pid)  # add so we don't re-alert

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Clean up caches for processes that no longer exist
    dead = set(_process_cache.keys()) - current_pids
    for pid in dead:
        _process_cache.pop(pid, None)
        _high_cpu_counts.pop(pid, None)