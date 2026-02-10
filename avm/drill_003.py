# drill_003.py — the Deconstruction Drill

import os

# THE FALLBACK: If LOG_LEVEL is missing, use "INFO"
log_setting = os.environ.get("LOG_LEVEL", "INFO")

print(f"[SYNAPSE_LOG]: Level set to {log_setting}")
