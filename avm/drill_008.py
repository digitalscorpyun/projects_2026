# Drill 008 - Computational Ingestion/Type Mutation

# transforming raw system strings into mathematical truths.

import os

memory_limit = os.environ.get("MEMORY_LIMIT")
mb_int = int(memory_limit)
gb_val = mb_int / 1024
print(f"[HARDWARE_MONITOR]: {gb_val} GB allocated.")
