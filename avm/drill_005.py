# TASK 05: ERROR HANDLING (THE TRY-EXCEPT SHIELD)
# Defensive logic gate.
import os

try:
    key = os.environ["SECRET_KEY"]
    print("Success: Key Found.")
except KeyError:
    print("ERROR: Critical Secret Key is missing from the environment.")
