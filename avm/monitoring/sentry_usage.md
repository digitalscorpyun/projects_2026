# Anacostia Sentry v1.3 — Lean Watcher
## Usage Instructions

### Prerequisites
- Python 3.10+
- psutil (`pip install psutil`)
- Windows 10/11 (PowerShell features used where psutil is insufficient)

### Files
| File | Purpose |
|------|---------|
| `anacostia_sentry.py` | Main observer script |
| `sentry_config.json` | Externalized configuration |

Place both files in the same directory.

### Single Run (Default)
```powershell
python anacostia_sentry.py
```
Executes one scan, prints summary to console, appends JSON to `vault_logs/sentry_report_YYYY-MM-DD.log`.

### Manual Loop Mode
```powershell
python anacostia_sentry.py --loop --interval 60
```
Runs indefinitely, scanning every 60 seconds. Press **Ctrl+C** to stop.

```powershell
python anacostia_sentry.py --loop --interval 30 --max 10
```
Runs 10 scans at 30-second intervals, then exits automatically.

### Configuration
Edit `sentry_config.json` to adjust:

| Section | Controls |
|---------|----------|
| `thresholds` | CPU, RAM, disk, swap rate warning levels |
| `features` | Toggle: cmdline capture, network I/O delta, deduplication, uptime awareness |
| `paths` | Log directory name and retention days |
| `process_snapshot` | Top-N limit, exclusion rules |

**Note:** `process_cmdline_capture` is **disabled by default** (privacy/performance). Enable in config if needed.

### Log Rotation
- Logs are kept for 7 days by default.
- Older logs are deleted automatically on each run.
- No compression (CPU budget reserved).

### What It Does Not Do
- No remediation actions
- No Windows service mode
- No SQLite, webhooks, email, GPU, or temperature monitoring
- No security recommendations (VBS/Hyper-V, BIOS, etc.)
- No automatic background execution

### Operator Controls
| Action | Command |
|--------|---------|
| Single scan | `python anacostia_sentry.py` |
| Loop mode | `python anacostia_sentry.py --loop -i 60` |
| Limited loop | `python anacostia_sentry.py --loop -i 30 -m 10` |
| Adjust thresholds | Edit `sentry_config.json` |
| Enable cmdline capture | Set `"process_cmdline_capture": true` in config |

---
*Anacostia Sentry v1.3 — Lean Watcher*
*Monitor and log only. No remediation. No security recommendations.*
