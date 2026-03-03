import pendulum
import pandas as pd

log_file = "/mnt/c/Users/digitalscorpyun/notification_log.txt"
current_time = pendulum.now("America/Los_Angeles")
expected_time = current_time.subtract(minutes=10)  # Dynamically set to 10 minutes ago
data = {"time": [current_time.offset_hours], "expected": [-7]}  # PDT vs. cached offset
df = pd.DataFrame(data)
is_aligned = df["time"].iloc[0] == df["expected"].iloc[0]
print(f"Time Audit: {current_time.to_datetime_string()}, Offset: {current_time.offset_hours}")
print(f"Expected Notification: {expected_time.to_datetime_string()}")
with open(log_file, "a") as f:
    f.write(f"Audit: {is_aligned}\n")

