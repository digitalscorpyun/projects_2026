# TASK 07: CONDITIONAL LOGIC (ENVIRONMENT SENSING)
import os

env = os.environ.get("OS_ENVIRONMENT", "").lower()

if env == "development":
    print("ACCESS GRANTED: DEV MODE")

elif env == "production":
    print("SECURITY WARNING: PRODUCTION MODE ACTIVE")

else:
    print("UNKNOWN ENVIRONMENT: LOCKING SYSTEM")
