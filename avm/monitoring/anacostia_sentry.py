# ==============================================================================
# ✶⌁✶ anacostia_sentry.py — THE LEAN WATCHER v1.3.0
# ==============================================================================
# ROLE: Lightweight Infrastructure Observer — Monitor and Log Only
# ENGINE: Deterministic Logic (Python 3.10+)
# COMPLIANCE: WC-INF-2026-01-16-V028 / NORMALIZATION-LAW-V102
# JURISDICTION: Anacostia Training Grounds
# MODE: Single-run or manually invoked loop only. No service mode.
# ==============================================================================
# v1.3.0 CHANGES:
#   - Externalized config (sentry_config.json)
#   - Config parsed once, cached for session
#   - Self memory footprint reporting
#   - Optional process command-line capture (config-gated)
#   - Optional network I/O delta
#   - Memory pressure differential (swap/pagefile monitoring)
#   - Alert deduplication (in-memory, time-windowed)
#   - Uptime-aware alerting (suppress non-critical during boot settle)
#   - 7-day log rotation (count-based, no compression)
#   - No remediation actions. No security recommendations.
#   - No SQLite, no webhooks, no GPU, no temperature, no service mode.
# ==============================================================================

import os
import sys
import json
import time
import psutil
import platform
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# --- CONFIG SOVEREIGNTY: Parse once, cache for session ---
BASE_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = BASE_DIR / "sentry_config.json"

_CONFIG_CACHE: Optional[Dict] = None


def load_config() -> Dict:
    """Parse config once per session. Return cached on subsequent calls."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Config not found: {CONFIG_PATH}\n"
            f"Run with default config or create {CONFIG_PATH.name}"
        )

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Strip comment keys for runtime use
    _CONFIG_CACHE = {k: v for k, v in raw.items() if not k.startswith("_")}
    return _CONFIG_CACHE


# --- LOG ROTATION: Keep last N daily files ---
def rotate_logs(log_dir: Path, max_days: int) -> None:
    """Remove log files older than max_days. Count-based, no compression."""
    if not log_dir.exists():
        return

    cutoff = datetime.datetime.now() - datetime.timedelta(days=max_days)
    removed = 0

    for log_file in log_dir.glob("sentry_report_*.log"):
        try:
            mtime = datetime.datetime.fromtimestamp(log_file.stat().st_mtime)
            if mtime < cutoff:
                log_file.unlink()
                removed += 1
        except (OSError, PermissionError):
            continue

    return removed


# --- SYSTEM IDENTITY ---
def get_sys_info() -> Dict:
    """Gather static system identity metadata."""
    return {
        "hostname": platform.node(),
        "os": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "boot_time": datetime.datetime.fromtimestamp(psutil.boot_time()).isoformat()
    }


# --- HEALTH PULSE ---
def get_health_metrics() -> Dict:
    """Gather real-time resource utilization pulse."""
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "ram_percent": memory.percent,
        "ram_used_gb": round(memory.used / (1024 ** 3), 2),
        "ram_total_gb": round(memory.total / (1024 ** 3), 2),
        "ram_available_mb": round(memory.available / (1024 ** 2), 1),
        "swap_percent": swap.percent,
        "swap_used_gb": round(swap.used / (1024 ** 3), 2),
        "swap_total_gb": round(swap.total / (1024 ** 3), 2),
        "swap_rate_mbps": None  # Populated differentially if prior snapshot exists
    }


# --- DISK REPORT ---
def classify_disk_status(percent_used: float, cfg: Dict) -> str:
    """Classify disk pressure per config thresholds."""
    if percent_used >= cfg["thresholds"]["disk_critical"]:
        return "critical"
    if percent_used >= cfg["thresholds"]["disk_warn"]:
        return "warning"
    return "normal"


def get_disk_report(cfg: Dict) -> List[Dict]:
    """Collect per-drive disk utilization."""
    disks = []
    for partition in psutil.disk_partitions(all=False):
        mountpoint = partition.mountpoint
        try:
            usage = psutil.disk_usage(mountpoint)
            disks.append({
                "device": partition.device,
                "mountpoint": mountpoint,
                "filesystem": partition.fstype,
                "total_gb": round(usage.total / (1024 ** 3), 2),
                "used_gb": round(usage.used / (1024 ** 3), 2),
                "free_gb": round(usage.free / (1024 ** 3), 2),
                "percent_used": usage.percent,
                "status": classify_disk_status(usage.percent, cfg)
            })
        except (PermissionError, OSError):
            disks.append({
                "device": partition.device,
                "mountpoint": mountpoint,
                "filesystem": partition.fstype,
                "error": "Permission denied or inaccessible"
            })
    return disks


# --- PROCESS PRESSURE SNAPSHOT ---
def get_process_snapshot(cfg: Dict) -> Dict:
    """Gather top CPU and RAM consumers."""
    features = cfg.get("features", {})
    proc_cfg = cfg.get("process_snapshot", {})
    limit = proc_cfg.get("top_limit", 10)
    exclude_idle = proc_cfg.get("exclude_system_idle", True)
    exclude_self = proc_cfg.get("exclude_self", True)
    capture_cmdline = features.get("process_cmdline_capture", False)
    current_pid = os.getpid()

    processes = []

    # Initialize CPU counters
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            proc.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    psutil.cpu_percent(interval=1)

    for proc in psutil.process_iter([
        "pid", "name", "username", "memory_info", "status", "create_time"
    ]):
        try:
            info = proc.info
            pid = info.get("pid")
            name = info.get("name", "")

            if exclude_idle and name and "idle" in name.lower():
                continue
            if exclude_self and pid == current_pid:
                continue

            memory_mb = 0.0
            if info.get("memory_info"):
                memory_mb = round(info["memory_info"].rss / (1024 ** 2), 2)

            proc_data = {
                "pid": pid,
                "name": name,
                "username": info.get("username"),
                "status": info.get("status"),
                "cpu_percent": round(proc.cpu_percent(interval=None), 1),
                "memory_mb": memory_mb,
                "created": datetime.datetime.fromtimestamp(
                    info["create_time"]
                ).isoformat() if info.get("create_time") else None
            }

            if capture_cmdline:
                try:
                    cmdline = proc.cmdline()
                    proc_data["cmdline"] = cmdline[:3] if cmdline else []
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    proc_data["cmdline"] = ["<access_denied>"]

            processes.append(proc_data)

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    top_cpu = sorted(processes, key=lambda x: x["cpu_percent"], reverse=True)[:limit]
    top_memory = sorted(processes, key=lambda x: x["memory_mb"], reverse=True)[:limit]

    return {
        "top_cpu": top_cpu,
        "top_memory": top_memory,
        "total_processes": len(processes)
    }


# --- NETWORK I/O DELTA ---
def get_network_io_delta(cfg: Dict, prior_io: Optional[Dict] = None) -> Dict:
    """Capture per-interface network I/O. If prior snapshot exists, compute delta."""
    features = cfg.get("features", {})
    if not features.get("network_io_delta", True):
        return {"enabled": False, "interfaces": []}

    interfaces = []
    net_io = psutil.net_io_counters(pernic=True)
    timestamp = datetime.datetime.now().isoformat()

    for iface, counters in net_io.items():
        iface_data = {
            "interface": iface,
            "bytes_sent": counters.bytes_sent,
            "bytes_recv": counters.bytes_recv,
            "packets_sent": counters.packets_sent,
            "packets_recv": counters.packets_recv,
            "timestamp": timestamp
        }

        if prior_io and iface in prior_io:
            prior = prior_io[iface]
            time_delta = time.time() - prior.get("_epoch", time.time())
            if time_delta > 0:
                sent_delta = counters.bytes_sent - prior.get("bytes_sent", 0)
                recv_delta = counters.bytes_recv - prior.get("bytes_recv", 0)
                iface_data["delta_seconds"] = round(time_delta, 1)
                iface_data["sent_delta_mb"] = round(sent_delta / (1024 ** 2), 2)
                iface_data["recv_delta_mb"] = round(recv_delta / (1024 ** 2), 2)
                iface_data["sent_rate_mbps"] = round(
                    (sent_delta * 8) / (time_delta * 1024 ** 2), 2
                )
                iface_data["recv_rate_mbps"] = round(
                    (recv_delta * 8) / (time_delta * 1024 ** 2), 2
                )

        iface_data["_epoch"] = time.time()
        interfaces.append(iface_data)

    return {
        "enabled": True,
        "interfaces": interfaces,
        "snapshot_count": len(interfaces)
    }


# --- SELF MEMORY FOOTPRINT ---
def get_self_memory() -> Dict:
    """Report the sentry's own approximate memory footprint."""
    try:
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        return {
            "self_pid": os.getpid(),
            "self_rss_mb": round(mem.rss / (1024 ** 2), 2),
            "self_vms_mb": round(mem.vms / (1024 ** 2), 2),
            "self_percent": round(proc.memory_percent(), 2)
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {"error": "Unable to measure self memory"}


# --- ALERT GENERATION ---
class AlertDeduper:
    """In-memory alert deduplication with configurable time window."""

    def __init__(self, window_minutes: float = 15.0):
        self.window = datetime.timedelta(minutes=window_minutes)
        self._seen: Dict[str, datetime.datetime] = {}

    def is_fresh(self, alert_key: str) -> bool:
        """Return True if this alert has not been seen within the window."""
        now = datetime.datetime.now()
        last_seen = self._seen.get(alert_key)
        if last_seen is None or (now - last_seen) > self.window:
            self._seen[alert_key] = now
            return True
        return False

    def prune(self) -> int:
        """Remove entries older than window. Return count removed."""
        now = datetime.datetime.now()
        stale = [k for k, v in self._seen.items() if (now - v) > self.window]
        for k in stale:
            del self._seen[k]
        return len(stale)


def get_alerts(report: Dict, cfg: Dict, deduper: AlertDeduper) -> List[str]:
    """Generate alerts with deduplication and uptime awareness."""
    alerts = []
    features = cfg.get("features", {})
    thresholds = cfg.get("thresholds", {})

    # Uptime awareness: suppress non-critical during boot settle
    if features.get("uptime_aware_alerting", True):
        uptime = time.time() - psutil.boot_time()
        settle = features.get("boot_settle_seconds", 300)
        in_settle = uptime < settle
    else:
        in_settle = False

    pulse = report.get("health_pulse", {})
    cpu = pulse.get("cpu_percent")
    ram = pulse.get("ram_percent")
    swap_rate = pulse.get("swap_rate_mbps")

    # CPU alert
    if isinstance(cpu, (int, float)) and cpu >= thresholds.get("cpu_warn", 80.0):
        key = f"cpu:{cpu:.0f}"
        if deduper.is_fresh(key):
            alerts.append(f"High CPU load: {cpu:.1f}%")

    # RAM alert (always critical, not suppressed during settle)
    if isinstance(ram, (int, float)) and ram >= thresholds.get("ram_warn", 85.0):
        key = f"ram:{ram:.0f}"
        if deduper.is_fresh(key):
            alerts.append(f"High RAM usage: {ram:.1f}%")

    # Swap rate alert
    if isinstance(swap_rate, (int, float)):
        swap_warn = thresholds.get("swap_rate_warn_mbps", 50.0)
        if swap_rate >= swap_warn:
            key = f"swap:{swap_rate:.0f}"
            if deduper.is_fresh(key):
                alerts.append(f"Elevated swap activity: {swap_rate:.1f} MB/s")

    # Disk alerts (critical never suppressed; warning suppressed during settle)
    for disk in report.get("disk_report", []):
        percent = disk.get("percent_used")
        mount = disk.get("mountpoint")
        free = disk.get("free_gb")

        if not isinstance(percent, (int, float)):
            continue

        if percent >= thresholds.get("disk_critical", 97.0):
            key = f"disk_critical:{mount}"
            if deduper.is_fresh(key):
                alerts.append(
                    f"CRITICAL disk pressure on {mount}: {percent:.1f}% used, {free} GB free"
                )
        elif percent >= thresholds.get("disk_warn", 90.0):
            if not in_settle:
                key = f"disk_warn:{mount}"
                if deduper.is_fresh(key):
                    alerts.append(
                        f"Disk warning on {mount}: {percent:.1f}% used, {free} GB free"
                    )

    # Boot settle notice (informational, not an alert)
    if in_settle and alerts:
        alerts.insert(0, f"[BOOT SETTLE: {int(settle - uptime)}s remaining; non-critical alerts suppressed]")

    return alerts


# --- MEMORY PRESSURE DIFFERENTIAL ---
def get_swap_differential(prior_swap: Optional[Dict] = None) -> Dict:
    """Monitor swap/pagefile activity rate."""
    swap = psutil.swap_memory()
    now = time.time()
    current = {
        "used": swap.used,
        "free": swap.free,
        "percent": swap.percent,
        "timestamp": now
    }

    if prior_swap and prior_swap.get("timestamp"):
        time_delta = now - prior_swap["timestamp"]
        if time_delta > 0:
            used_delta = abs(swap.used - prior_swap.get("used", 0))
            rate_mbps = (used_delta / time_delta) / (1024 ** 2)
            current["rate_mbps"] = round(rate_mbps, 2)
            current["delta_seconds"] = round(time_delta, 1)

    return current


# --- MAIN EXECUTION LOOP ---
def run_sentry_scan(prior_state: Optional[Dict] = None) -> Dict:
    """Primary execution loop. Returns full report + state for next iteration."""
    cfg = load_config()
    features = cfg.get("features", {})
    paths = cfg.get("paths", {})

    log_dir = BASE_DIR / paths.get("log_dir", "vault_logs")
    log_dir.mkdir(exist_ok=True)

    # Rotate logs before writing
    max_days = paths.get("max_log_days", 7)
    rotated = rotate_logs(log_dir, max_days)

    log_file = log_dir / f"sentry_report_{datetime.date.today()}.log"
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Initialize deduper from prior state or fresh
    dedup_window = features.get("dedup_window_minutes", 15.0)
    if prior_state and "deduper_state" in prior_state:
        deduper = AlertDeduper(dedup_window)
        deduper._seen = {
            k: datetime.datetime.fromisoformat(v)
            for k, v in prior_state["deduper_state"].items()
        }
    else:
        deduper = AlertDeduper(dedup_window)

    # Prune stale dedup entries
    deduper.prune()

    # Gather telemetry
    sys_info = get_sys_info()
    health_pulse = get_health_metrics()
    disk_report = get_disk_report(cfg)
    process_pressure = get_process_snapshot(cfg)
    self_memory = get_self_memory()

    # Swap differential
    prior_swap = prior_state.get("swap_snapshot") if prior_state else None
    swap_snapshot = get_swap_differential(prior_swap)
    if "rate_mbps" in swap_snapshot:
        health_pulse["swap_rate_mbps"] = swap_snapshot["rate_mbps"]

    # Network I/O delta
    prior_net = prior_state.get("network_io") if prior_state else None
    network_io = get_network_io_delta(cfg, prior_net)

    # Build report
    report = {
        "timestamp": timestamp,
        "script_version": cfg["script_meta"]["version"],
        "script_codename": cfg["script_meta"]["codename"],
        "system_identity": sys_info,
        "health_pulse": health_pulse,
        "disk_report": disk_report,
        "process_pressure": process_pressure,
        "network_io": network_io,
        "swap_snapshot": swap_snapshot,
        "self_memory": self_memory,
        "log_rotation": {
            "max_days": max_days,
            "files_rotated": rotated
        }
    }

    # Generate alerts
    report["alerts"] = get_alerts(report, cfg, deduper)

    # Serialize to log
    with open(log_file, "a", encoding="utf-8") as f:
        json.dump(report, f, indent=cfg["output"].get("json_indent", 2), ensure_ascii=False)
        f.write("\n" + ("=" * 80) + "\n")

    # Console output
    if cfg["output"].get("console_summary", True):
        print(f"[{timestamp}] SENTRY SCAN COMPLETE — {cfg['script_meta']['codename']}")
        print(f"  Log: {log_file}")
        print(f"  Logs rotated: {rotated}")

        if self_memory.get("self_rss_mb"):
            print(f"  Self footprint: {self_memory['self_rss_mb']} MB RSS")

        if report["alerts"]:
            print("\n⚠️  ALERTS:")
            for alert in report["alerts"]:
                print(f"  - {alert}")
        else:
            print("  No threshold alerts.")

        print("\nTop CPU:")
        for proc in report["process_pressure"]["top_cpu"][:5]:
            print(f"  {proc['name']:<20} PID {proc['pid']:<6} CPU {proc['cpu_percent']:>5.1f}%  RAM {proc['memory_mb']:>6.1f} MB")

        print("\nTop RAM:")
        for proc in report["process_pressure"]["top_memory"][:5]:
            print(f"  {proc['name']:<20} PID {proc['pid']:<6} RAM {proc['memory_mb']:>6.1f} MB  CPU {proc['cpu_percent']:>5.1f}%")

        if network_io.get("enabled") and network_io.get("interfaces"):
            print("\nNetwork I/O:")
            for iface in network_io["interfaces"][:3]:
                if "sent_rate_mbps" in iface:
                    print(f"  {iface['interface']:<15} ↑ {iface['sent_rate_mbps']:>6.2f} Mbps  ↓ {iface['recv_rate_mbps']:>6.2f} Mbps")
                else:
                    print(f"  {iface['interface']:<15} Sent {iface['bytes_sent'] / (1024**2):.1f} MB  Recv {iface['bytes_recv'] / (1024**2):.1f} MB (baseline)")

    # Prepare state for next iteration
    next_state = {
        "swap_snapshot": swap_snapshot,
        "network_io": {
            iface["interface"]: iface for iface in network_io.get("interfaces", [])
        },
        "deduper_state": {
            k: v.isoformat() for k, v in deduper._seen.items()
        }
    }

    return report, next_state


# --- MANUAL LOOP MODE ---
def run_loop(interval_seconds: int = 60, max_iterations: Optional[int] = None) -> None:
    """Manually invoked loop. Not a service. Operator controls start and stop."""
    state = None
    iteration = 0
    print(f"\n[Lean Watcher] Entering manual loop: {interval_seconds}s interval")
    print(f"[Lean Watcher] Press Ctrl+C to exit\n")

    try:
        while True:
            iteration += 1
            _, state = run_sentry_scan(state)

            if max_iterations and iteration >= max_iterations:
                print(f"\n[Lean Watcher] Max iterations ({max_iterations}) reached. Exiting.")
                break

            print(f"\n[Lean Watcher] Next scan in {interval_seconds}s... (Ctrl+C to stop)")
            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\n[Lean Watcher] Loop terminated by operator.")


# --- ENTRY POINT ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Anacostia Sentry v1.3 — Lean Watcher"
    )
    parser.add_argument(
        "--loop", "-l",
        action="store_true",
        help="Run in manual loop mode (operator-controlled, not a service)"
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=60,
        help="Loop interval in seconds (default: 60)"
    )
    parser.add_argument(
        "--max", "-m",
        type=int,
        default=None,
        help="Maximum loop iterations (default: unlimited)"
    )

    args = parser.parse_args()

    if args.loop:
        run_loop(args.interval, args.max)
    else:
        run_sentry_scan()
