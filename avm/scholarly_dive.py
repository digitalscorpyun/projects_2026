# ==============================================================================
# ✶⌁✶ scholarly_dive.py — THE SYNTHESIS ENGINE v1.7.0 [HARDENED+CRITICAL]
# ==============================================================================
# ROLE: Deep synthesis client with loop prevention, env-hardening, and
#       anti-hagiography historiography constraints.
# COMPLIANCE: WC-DIR-2026-01-11-ENV-HARDENING / SENTINEL-V2.0.0-ALIGN
# ==============================================================================

import os
import sys
import re
import json
from typing import Any, Dict, Tuple, Optional
from datetime import timedelta, timezone

from watsonx_client import WatsonXClient
from vs_enc import VSEncOrchestrator

# ------------------------------------------------------------------------------
# FAIL-FAST GUARD (Env-Var Authority)
# ------------------------------------------------------------------------------
if not os.getenv("WATSONX_PROJECT_ID"):
    print("❌ ERROR: WATSONX_PROJECT_ID missing.")
    sys.exit(1)

PST = timezone(timedelta(hours=-8))
ARTIFACT_DIR = "war_council/_artifacts/scholarly_dive"

# ------------------------------------------------------------------------------
# PROMPT LAW (Anti-hagiography / Historiography-first)
# ------------------------------------------------------------------------------
DEFAULT_AGENT = os.getenv("SCHOLARLY_DIVE_AGENT", "QWEN-ECHO")

PROMPT_TEMPLATE = """\
ROLE: You are the Algorithmic Griot.
TASK: Produce a rigorous scholarly synthesis on: {topic}

PRIMARY RULE: Historiography > hagiography.
- Do NOT sanctify individuals or nations.
- Center structures, conflicts, agency from below, and material conditions.
- Explicitly surface contradictions, limits, enforcement realities, and contested interpretations.
- Separate what the document "says" from what it "did" in practice.

OUTPUT STRUCTURE (use these exact headers):
# Abstract
# Historical Analysis [^1]
## Historiography & Scholarly Debate
## Material Conditions & Enforcement
## Agency & Counter-Agency
## Contradictions / Limits / Exemptions
# Semiotic Analysis
## Myth / National Narrative (Interrogate, do not affirm)
## Rhetorical Mechanics
# 📚 BIBLIOGRAPHY

CITATIONS:
- Use Markdown footnotes [^1] in the body.
- In bibliography, format as: [^1]: Author. *Title* (Publisher, Year).
- If uncertain, say "uncertain" rather than inventing details.

METADATA:
- Provide JSON labeled '### METADATA' at the absolute end.
- JSON keys allowed: title, tags, key_themes, bias_analysis, grok_ctx_reflection, quotes, adinkra.
"""


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def _safe_json_loads(maybe_json: str) -> Dict[str, Any]:
    """Attempt to parse JSON safely; return {} on failure."""
    try:
        return json.loads(maybe_json)
    except Exception:
        return {}


def _extract_metadata(raw_response: str) -> Tuple[str, Dict[str, Any]]:
    """
    Splits model output into (body, meta_json).
    Expects metadata block after '### METADATA'.
    """
    meta_json: Dict[str, Any] = {}
    body_content = raw_response.strip()

    if "### METADATA" not in raw_response:
        return body_content, meta_json

    parts = raw_response.split("### METADATA", 1)
    body_content = parts[0].strip()
    tail = parts[1]

    # Prefer the first balanced JSON object in the tail.
    found_json = re.search(r"\{.*\}", tail, re.DOTALL)
    if not found_json:
        return body_content, meta_json

    meta_json = _safe_json_loads(found_json.group())
    return body_content, meta_json


def _prompt_user_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    ans = input(prompt + suffix).strip().lower()
    if not ans:
        return default
    return ans in {"y", "yes"}


def _get_topic() -> str:
    topic = input("Enter Research Topic: ").strip()
    if not topic:
        raise ValueError("Topic cannot be empty.")
    return topic


def _build_prompt(topic: str) -> str:
    return PROMPT_TEMPLATE.format(topic=topic)


# ------------------------------------------------------------------------------
# Core Classes
# ------------------------------------------------------------------------------
class ScholarlySynapse:
    """
    Thin wrapper around WatsonXClient for this synthesis workflow.
    Model/agent identity is explicitly manifested.
    """

    def __init__(self, agent_name: str = DEFAULT_AGENT):
        self.client = WatsonXClient()
        self.client.set_agent(agent_name)
        self.agent_name = agent_name

    def ask(self, prompt: str) -> str:
        # Increased token budget; deterministic defaults come from watsonx_client.
        return self.client.ask(
            prompt,
            max_new_tokens=4000,
            repetition_penalty=1.1,
        )


class StubAgent:
    """Orchestrator-compatible pass-through agent."""

    def run(self, text: str):
        return text


# ------------------------------------------------------------------------------
# Main Workflow
# ------------------------------------------------------------------------------
def run_synthesis() -> None:
    version = "v1.7.0"
    print(f"✶⌁✶ SCHOLARLY DIVE {version} [HARDENED+CRITICAL] ONLINE")

    try:
        topic = _get_topic()

        # Optional: show the operator the posture shift before emission.
        if _prompt_user_yes_no("Use historiography-first (anti-hagiography) prompt?", default=True):
            prompt = _build_prompt(topic)
        else:
            # Operator override: minimal legacy prompt (still structured, but less strict)
            prompt = f"""
ROLE: You are the Algorithmic Griot.
TASK: Provide a deep scholarly synthesis on {topic}.
STRUCTURE: # Abstract, # Historical Analysis [^1], # Semiotic Analysis, # 📚 BIBLIOGRAPHY.
CITATIONS: Use standard Markdown [^1]: Author, Year.
METADATA: Provide JSON labeled '### METADATA' at the absolute end.
""".strip()

        synapse = ScholarlySynapse(agent_name=DEFAULT_AGENT)
        orch = VSEncOrchestrator({"SCHOLARLY_STUB": StubAgent()})

        print(f"✶ Synthesizing deep artifact for '{topic}' (agent={synapse.agent_name})...")
        raw_response = synapse.ask(prompt)

        body_content, meta_json = _extract_metadata(raw_response)

        # Enforce allowed metadata keys to prevent schema drift through model output.
        allowed_meta_keys = {
            "title",
            "tags",
            "key_themes",
            "bias_analysis",
            "grok_ctx_reflection",
            "quotes",
            "adinkra",
        }
        meta_json = {k: v for k, v in (meta_json or {}).items() if k in allowed_meta_keys}

        payload = orch.run(
            agent_name="SCHOLARLY_STUB",
            input_text=body_content,
            invocation_type="scholarly_dive",
            custom_params={
                "title": meta_json.get("title") or f"Deep Research — {topic}",
                "relative_dir": ARTIFACT_DIR,
                "category": "research",
                "style": "AlgorithmicGriot",
                "priority": "medium",
                "status": "active",
                **{k: v for k, v in meta_json.items() if k != "title"},
            },
        )

        orch.emit_to_vault(payload)
        print(f"✓ Research Emitted: {payload.get('filename', '<unknown>')}")

    except KeyboardInterrupt:
        print("\n⏹️  Aborted by operator.")
    except Exception as e:
        print(f"❌ ERROR: {e}")


if __name__ == "__main__":
    run_synthesis()
