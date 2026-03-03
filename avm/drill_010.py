# TASK 10: ADVANCED ERROR HANDLING (CIRCUIT FINISHER)
# Iteration (Looping) and Error Handling.
import os


required_vars = ["API_KEY", "ORG_ID", "ENV_TAG"]
missing_count = 0

for var in required_vars:
    if var not in os.environ:
        missing_count += 1
        print(f"[!] MISSING: {var}")

if missing_count == 0:
    print("All required environment variables are present.")
else:
    print(f"{missing_count} required environment variable(s) missing.")

