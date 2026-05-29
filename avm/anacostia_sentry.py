# ==============================================================================
# ✶⌁✶ anacostia_sentry.py — THE SOVEREIGN INFRASTRUCTURE OBSERVER v1.2.0 [HARDENED]
# ==============================================================================
# ROLE: Automated Infrastructure Health Monitoring & Kernel Log Collection.
# ENGINE: Deterministic Logic (Python 3.10+)
# COMPLIANCE: WC-INF-2026-01-16-V028 / NORMALIZATION-LAW-V102
# JURISDICTION: Anacostia Training Grounds — projects_2026 Sovereignty
# ==============================================================================
# PURPOSE:
#   Collect actionable system health data:
#   - Static system identity
#   - CPU / RAM / battery pulse
#   - Per-drive disk usage
#   - Top CPU-consuming processes
#   - Top RAM-consuming processes
#   - Windows System event errors
#   - Network adapter map, including ifIndex for TCP/IP bind failures
#
# NOTE:
#   This version fixes the blind spot caused by psutil.disk_usage("/")
#   by collecting all mounted filesystem drives on Windows.
# ==============================================================================

import os
import json
import psutil
import platform
import datetime
import subprocess
from typing import Any


# --- SYNDICATE CONFIGURATION: PATH SOVEREIGNTY ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "vault_logs")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, f"sentry_report_{datetime.date.today()}.log")


# --- THRESHOLDS ---
CPU_WARN = 80.0
RAM_WARN = 85.0
DISK_WARN = 90.0
DISK_CRITICAL = 97.0


def safe_json_loads(raw: str) -> Any:
    """Safely parse JSON from PowerShell output."""
    if not raw or not raw.strip():
        return []

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return [parsed]
        return parsed
    except json.JSONDecodeError:
        return {
            "error": "JSON parse failed",
            "raw_output": raw.strip()
        }


def run_powershell(command: str) -> Any:
    """Run PowerShell command and return parsed JSON when possible."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            timeout=20
        )

        if result.returncode != 0:
            return {
                "error": "PowerShell command failed",
                "returncode": result.returncode,
                "stderr": result.stderr.strip(),
                "stdout": result.stdout.strip()
            }

        return safe_json_loads(result.stdout)

    except subprocess.TimeoutExpired:
        return {
            "error": "PowerShell command timed out"
        }
    except Exception as e:
        return {
            "error": f"PowerShell bridge failed: {str(e)}"
        }


def get_sys_info() -> dict:
    """Gather static system identity metadata."""
    return {
        "hostname": platform.node(),
        "os": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version()
    }


def get_health_metrics() -> dict:
    """Gather real-time resource utilization pulse."""
    battery = psutil.sensors_battery()
    memory = psutil.virtual_memory()

    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "ram_percent": memory.percent,
        "ram_used_gb": round(memory.used / (1024 ** 3), 2),
        "ram_total_gb": round(memory.total / (1024 ** 3), 2),
        "battery_percent": battery.percent if battery else "N/A",
        "power_plugged": battery.power_plugged if battery else "N/A"
    }


def get_disk_report() -> list:
    """Collect per-drive disk utilization instead of ambiguous '/' usage."""
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
                "status": classify_disk_status(usage.percent)
            })
        except PermissionError:
            disks.append({
                "device": partition.device,
                "mountpoint": mountpoint,
                "filesystem": partition.fstype,
                "error": "Permission denied"
            })
        except Exception as e:
            disks.append({
                "device": partition.device,
                "mountpoint": mountpoint,
                "filesystem": partition.fstype,
                "error": str(e)
            })

    return disks


def classify_disk_status(percent_used: float) -> str:
    """Classify disk pressure."""
    if percent_used >= DISK_CRITICAL:
        return "critical"
    if percent_used >= DISK_WARN:
        return "warning"
    return "normal"


def get_top_processes(limit: int = 10) -> dict:
    """
    Gather top CPU and RAM consumers.

    CPU requires a two-pass sampling ritual:
    first call initializes counters, second call captures useful percentages.
    """
    processes = []

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            proc.cpu_percent(interval=None)
        except Exception:
            continue

    psutil.cpu_percent(interval=1)

    for proc in psutil.process_iter(["pid", "name", "username", "memory_info", "status", "create_time"]):
        try:
            info = proc.info
            memory_mb = round(info["memory_info"].rss / (1024 ** 2), 2) if info.get("memory_info") else 0

            processes.append({
                "pid": info.get("pid"),
                "name": info.get("name"),
                "username": info.get("username"),
                "status": info.get("status"),
                "cpu_percent": proc.cpu_percent(interval=None),
                "memory_mb": memory_mb,
                "created": datetime.datetime.fromtimestamp(info["create_time"]).isoformat()
                if info.get("create_time") else None
            })

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        except Exception:
            continue

    top_cpu = sorted(processes, key=lambda x: x["cpu_percent"], reverse=True)[:limit]
    top_memory = sorted(processes, key=lambda x: x["memory_mb"], reverse=True)[:limit]

    return {
        "top_cpu": top_cpu,
        "top_memory": top_memory
    }


def get_windows_events(limit: int = 10) -> Any:
    """
    Gather recent System log Error/Critical events using Get-WinEvent.

    This replaces Get-EventLog because Get-WinEvent gives cleaner modern event data.
    """
    ps_command = f"""
    Get-WinEvent -FilterHashtable @{{LogName='System'; Level=1,2}} -MaxEvents {limit} |
    Select-Object `
        @{{Name='TimeCreated';Expression={{$_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')}}}},
        Id,
        LevelDisplayName,
        ProviderName,
        Message |
    ConvertTo-Json -Depth 4
    """

    return run_powershell(ps_command)


def get_network_adapters() -> Any:
    """
    Map network interface indexes to adapter names.

    This directly addresses errors like:
    'The IPv6 TCP/IP interface with index 5 failed to bind to its provider.'
    """
    ps_command = """
    Get-NetAdapter |
    Select-Object `
        ifIndex,
        Name,
        Status,
        InterfaceDescription,
        MacAddress,
        LinkSpeed |
    Sort-Object ifIndex |
    ConvertTo-Json -Depth 4
    """

    return run_powershell(ps_command)


def get_ip_configuration() -> Any:
    """Collect useful IP interface state without flooding the report."""
    ps_command = """
    Get-NetIPInterface |
    Select-Object `
        ifIndex,
        InterfaceAlias,
        AddressFamily,
        ConnectionState,
        Dhcp,
        NlMtu,
        InterfaceMetric |
    Sort-Object ifIndex, AddressFamily |
    ConvertTo-Json -Depth 4
    """

    return run_powershell(ps_command)


def get_alerts(report: dict) -> list:
    """Generate human-readable alerts from collected telemetry."""
    alerts = []
    pulse = report.get("health_pulse", {})

    cpu = pulse.get("cpu_percent")
    ram = pulse.get("ram_percent")

    if isinstance(cpu, (int, float)) and cpu >= CPU_WARN:
        alerts.append(f"High CPU load detected: {cpu}%")

    if isinstance(ram, (int, float)) and ram >= RAM_WARN:
        alerts.append(f"High RAM usage detected: {ram}%")

    for disk in report.get("disk_report", []):
        percent = disk.get("percent_used")
        mount = disk.get("mountpoint")

        if isinstance(percent, (int, float)) and percent >= DISK_CRITICAL:
            alerts.append(f"Critical disk pressure on {mount}: {percent}% used")
        elif isinstance(percent, (int, float)) and percent >= DISK_WARN:
            alerts.append(f"Disk warning on {mount}: {percent}% used")

    return alerts


def run_sentry_scan() -> dict:
    """Primary execution loop."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = {
        "timestamp": timestamp,
        "system_identity": get_sys_info(),
        "health_pulse": get_health_metrics(),
        "disk_report": get_disk_report(),
        "process_pressure": get_top_processes(limit=10),
        "network_adapters": get_network_adapters(),
        "ip_interfaces": get_ip_configuration(),
        "recent_system_errors": get_windows_events(limit=10)
    }

    report["alerts"] = get_alerts(report)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(report, indent=4, ensure_ascii=False))
        f.write("\n" + ("=" * 80) + "\n")

    print(f"[{timestamp}] SENTRY SCAN COMPLETE.")
    print(f"SERIALIZED TO: {LOG_FILE}")

    if report["alerts"]:
        print("\n⚠️  ALERTS:")
        for alert in report["alerts"]:
            print(f"- {alert}")
    else:
        print("No threshold alerts detected.")

    print("\nTop CPU Processes:")
    for proc in report["process_pressure"]["top_cpu"][:5]:
        print(f"- {proc['name']} | PID {proc['pid']} | CPU {proc['cpu_percent']}% | RAM {proc['memory_mb']} MB")

    print("\nTop RAM Processes:")
    for proc in report["process_pressure"]["top_memory"][:5]:
        print(f"- {proc['name']} | PID {proc['pid']} | RAM {proc['memory_mb']} MB | CPU {proc['cpu_percent']}%")

    return report


if __name__ == "__main__":
    run_sentry_scan()
```
