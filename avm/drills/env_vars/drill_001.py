# drill_001.py — Indentity Retrieval Drill

import os

# THE BUCKET: Capture the data in a local variable
# Ensure the string inside matches the terminal command ($env:DATABASE_URL)
my_db = os.environ.get("DATABASE_URL")

# 2. THE DISPLAY: Send the data to the terminal screen
print(my_db)

