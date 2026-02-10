# ==============================================================================
# ✶⌁✶ watsonx_client.py — THE UNIVERSAL SYNAPSE v3.6 [HARDENED]
# ==============================================================================
# ROLE: Hardened infrastructure bridge with Env-Var Authority.
# ENGINE: IBM Watsonx AI (Granite 4.0)
# COMPLIANCE: WC-DIR-2026-01-11-ENV-HARDENING
# ==============================================================================

import os
import sys
from pathlib import Path
from datetime import datetime
import pytz

from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference

LOCAL_TZ = pytz.timezone("America/Los_Angeles")
VAULT_BASE_PATH = Path("C:/Users/digitalscorpyun/sankofa_temple/Anacostia")

# FAIL-FAST GUARD: Authority of the Execution Layer
REQUIRED_VARS = [
    "WATSONX_APIKEY",
    "WATSONX_PROJECT_ID",
    "WATSONX_URL",
    "WATSONX_REGION",
]
missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
if missing:
    print(f"❌ CRITICAL INFRASTRUCTURE FAILURE: Missing env vars {missing}")
    sys.exit(1)


class WatsonXClient:
    def __init__(self, model_id: str = "ibm/granite-4-h-small"):
        self.api_key = os.getenv("WATSONX_APIKEY")
        self.project_id = os.getenv("WATSONX_PROJECT_ID")
        self.url = os.getenv("WATSONX_URL")
        self.region = os.getenv("WATSONX_REGION")
        self.model_id = model_id
        self.current_agent = "SYNAPSE-CORE"
        self.system_prompt = "You are a cognitive node of the AVM Syndicate."

        self.creds = Credentials(api_key=self.api_key, url=self.url)
        self.default_params = {
            "decoding_method": "greedy",
            "max_new_tokens": 1500,
            "temperature": 0.0,
        }

    def now_iso(self) -> str:
        return datetime.now(LOCAL_TZ).isoformat(timespec="seconds")

    def set_agent(self, agent_name: str):
        """MANIFEST RESOLUTION: Maps agent names to protocol markdown files."""
        alias_map = {
            "OD-COMPLY": "war_council/avm_syndicate/agents/protocols/oracular_decree_protocol_manifest.md",
            "KIMI-DEUX": "war_council/avm_syndicate/agents/protocols/twin_warden_protocol_manifest.md",
            "QWEN-ECHO": "war_council/avm_syndicate/agents/protocols/echo_prophet_protocol_manifest.md",
            "VS-ENC": "war_council/avm_syndicate/agents/protocols/vault_sentinel_protocol_manifest.md",
        }

        rel_path = (
            alias_map.get(agent_name)
            or f"war_council/avm_syndicate/agents/protocols/{agent_name.lower().replace('-', '_')}_protocol_manifest.md"
        )
        full_path = VAULT_BASE_PATH / rel_path

        if not full_path.exists():
            raise FileNotFoundError(
                f"✶ ERROR: Manifest missing for {agent_name} at: {full_path}"
            )

        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
            parts = content.split("---")
            if len(parts) < 3:
                raise ValueError(f"✶ ERROR: Manifest at {full_path} is malformed.")

            self.system_prompt = parts[-1].strip()
            self.current_agent = agent_name
            print(f"✶ Synapse: {self.current_agent} identity manifested.")

    def ask(self, prompt: str, **kwargs) -> str:
        """EXECUTION: Wraps prompts in Absolute String Siloing."""
        call_params = {**self.default_params, **kwargs}
        full_prompt = (
            f"SYSTEM_RULES_START\n{self.system_prompt}\nSYSTEM_RULES_END\n\n"
            f"USER_DATA_START\n{prompt}\nUSER_DATA_END\n\n"
            f"ASSISTANT_EMISSION_START\n"
        )

        model = ModelInference(
            model_id=self.model_id,
            credentials=self.creds,
            project_id=self.project_id,
            params=call_params,
        )

        raw_text = (
            model.generate(full_prompt)
            .get("results", [{}])[0]
            .get("generated_text", "")
            .strip()
        )
        clean_text = raw_text.split("ASSISTANT_EMISSION_START")[-1].strip()

        terminal_tags = [
            "ROLES_START",
            "AVM_SYNDIKAT_VERIFICATION",
            "SYSTEM_RULES_VERIFICATION",
            "USER_DATA_VERIFICATION",
            "EMISSION_VERIFICATION",
            "FINAL_VERDICT",
            "USER_DATA_END",
            "SYSTEM_RULES_END",
            "ASSISTANT_EMISSION_END",
        ]
        for tag in terminal_tags:
            if tag in clean_text:
                clean_text = clean_text.split(tag)[0].strip()

        return clean_text.strip()
