# drill_002.py — Type Conversion Drill / Conditional Logic (if/else).

import os

# We add .get("", "") to provide a default empty string if it's missing
# Then we call .lower() to handle "TRUE", "True", or "true"
debug_mode = os.environ.get("DEBUG_MODE", "").lower()

if debug_mode == "true":
    print("Debug mode is ON")
else:
    print("Debug mode is OFF")

