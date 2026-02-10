# ==============================================================================
# ✶⌁✶ scholarly_dive.py — THE SYNTHESIS ENGINE v1.6.3 [HARDENED]
# ==============================================================================
# ROLE: Deep synthesis client with loop prevention and env-hardening.
# COMPLIANCE: WC-DIR-2026-01-11-ENV-HARDENING / SENTINEL-V2.0.0-ALIGN
# ==============================================================================

import os
import sys
import re
import json
from datetime import timedelta, timezone
from watsonx_client import WatsonXClient
from vs_enc import VSEncOrchestrator

# FAIL-FAST GUARD
if not os.getenv("WATSONX_PROJECT_ID"):
    print("❌ ERROR: WATSONX_PROJECT_ID missing.")
    sys.exit(1)

PST = timezone(timedelta(hours=-8))
ARTIFACT_DIR = "war_council/_artifacts/scholarly_dive"


class ScholarlySynapse:
    def __init__(self):
        self.client = WatsonXClient()
        self.client.set_agent("QWEN-ECHO")

    def ask(self, prompt: str) -> str:
        return self.client.ask(prompt, max_new_tokens=4000, repetition_penalty=1.1)


class StubAgent:
    def run(self, text: str):
        return text


def run_synthesis():
    print("✶⌁✶ SCHOLARLY DIVE v1.6.3 [HARDENED] ONLINE")
    topic = input("Enter Research Topic: ")
    synapse = ScholarlySynapse()
    orch = VSEncOrchestrator({"SCHOLARLY_STUB": StubAgent()})

    scholarly_prompt = f"""
    ROLE: You are the Algorithmic Griot.
    TASK: Provide a deep scholarly synthesis on {topic}.
    STRUCTURE: # Abstract, # Historical Analysis [^1], # Semiotic Analysis, # 📚 BIBLIOGRAPHY.
    CITATIONS: Use standard Markdown [^1]: Author, Year.
    METADATA: Provide JSON labeled '### METADATA' at the absolute end.
    """

    try:
        print(f"✶ Synthesizing deep artifact for '{topic}'...")
        raw_response = synapse.ask(scholarly_prompt)
        meta_json = {}
        body_content = raw_response
        if "### METADATA" in raw_response:
            parts = raw_response.split("### METADATA")
            body_content = parts[0].strip()
            found_json = re.search(r"\{.*\}", parts[1], re.DOTALL)
            if found_json:
                meta_json = json.loads(found_json.group())

        payload = orch.run(
            agent_name="SCHOLARLY_STUB",
            input_text=body_content,
            invocation_type="scholarly_dive",
            custom_params={
                "title": f"Deep Research — {topic}",
                "relative_dir": ARTIFACT_DIR,
                "category": "research",
                "style": "AlgorithmicGriot",
                "priority": "medium",
                "status": "active",
                **meta_json,
            },
        )
        orch.emit_to_vault(payload)
        print(f"✓ Research Emitted: {payload['filename']}")
    except Exception as e:
        print(f"❌ ERROR: {e}")


if __name__ == "__main__":
    run_synthesis()
