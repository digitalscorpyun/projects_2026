# MANUAL DRAFTING (drill_006.py)

import os

vars_to_check = ["VAR_A", "VAR_B", "VAR_C"]

for var in vars_to_check:
    value = os.environ.get(var, "value")
    print(f"Checking {var}... Value: {value}")
