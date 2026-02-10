# Drill 009 - Nested Structures (JSON PARSING)

# A string is a sequence; a dictionary is a map. Use the JSON bridge to cross from one to the other.

import os
import json


raw_json = os.environ.get("GATEWAY_CONFIG", "{}")
config_dict = json.loads(raw_json)
api_url = config_dict.get("url", "No URL Found")
print(f"[GATEWAY_INIT]: Routing to {api_url}")
