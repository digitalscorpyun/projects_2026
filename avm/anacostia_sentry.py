# ==============================================================================
# ✶⌁✶ anacostia_sentry.py — THE SOVEREIGN INFRASTRUCTURE OBSERVER v1.1.0 [HARDENED]
# ==============================================================================
# ROLE: Automated Infrastructure Health Monitoring & Kernel Log Collection.
# ENGINE: Deterministic Logic (Python 3.10+)
# COMPLIANCE: WC-INF-2026-01-16-V028 / NORMALIZATION-LAW-V102
# JURISDICTION: Anacostia Training Grounds — projects_2026 Sovereignty
# ==============================================================================

import os
import psutil
import datetime
import platform
import subprocess
import json

# --- SYNDICATE CONFIGURATION (PATH SOVEREIGNTY) ---
# Logic: Anchors the output to the projects_2026 directory regardless of execution point.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "vault_logs")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, f"sentry_report_{datetime.date.today()}.log")


def get_sys_info():
    """Gathers static system identity (The Metadata)."""
    return {
        "hostname": platform.node(),
        "os": platform.system(),
        "version": platform.version(),
        "processor": platform.processor(),
    }


def get_health_metrics():
    """Gathers real-time resource utilization (The Pulse)."""
    battery = psutil.sensors_battery()
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "battery_percent": battery.percent if battery else "N/A",
        "power_plugged": battery.power_plugged if battery else "N/A",
    }


def get_windows_events():
    """Executes a PowerShell bridge to gather the last 5 Error Events."""
    # Logic: Calling the Kernel via PowerShell for deep diagnostics.
    ps_command = "Get-EventLog -LogName System -EntryType Error -Newest 5 | Select-Object TimeGenerated, Source, Message | ConvertTo-Json"
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_command], capture_output=True, text=True
        )
        return json.loads(result.stdout) if result.stdout else "No recent errors."
    except Exception as e:
        return f"PowerShell Bridge Failed: {str(e)}"


def run_sentry_scan():
    """The Primary Execution Loop."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = {
        "timestamp": timestamp,
        "system_identity": get_sys_info(),
        "health_pulse": get_health_metrics(),
        "recent_system_errors": get_windows_events(),
    }

    # SERIALIZATION: Write to the Vault Log (Absolute Path)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(report, indent=4) + "\n" + ("=" * 50) + "\n")

    # OUTPUT: Console Feedback
    print(f"[{timestamp}] SENTRY SCAN COMPLETE.")
    print(f"SERIALIZED TO: {LOG_FILE}")
    if report["health_pulse"]["cpu_percent"] > 80:
        print("⚠️  WARNING: High CPU Load Detected.")


if __name__ == "__main__":
    run_sentry_scan()