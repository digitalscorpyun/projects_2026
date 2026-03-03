# drill_004.py — Mutliple Variable Drill

import os

# Define a function def report_status():

name = os.environ.get("SERVICE_NAME", "")
version = os.environ.get("SERVICE_VERSION", "")


def report_status():
    # Inside the function, get both variables.
    os.environ.get("SERVICE_NAME", "SERVICE_VERSION")


print(f"[SYSTEM]: {name} is running version {version}")

report_status()

