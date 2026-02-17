# ==============================================================================
# ✶⌁✶ scholarly_dive.py — THE SYNTHESIS ENGINE v1.7.1 [HARDENED+CRITICAL]
# ==============================================================================
# ROLE: Deep synthesis client with loop prevention, env-hardening, and
#       anti-hagiography historiography constraints.
# COMPLIANCE: WC-DIR-2026-01-11-ENV-HARDENING / SENTINEL-V2.0.0-ALIGN
# ==============================================================================

import os
import sys
import re
import json
from typing import Any, Dict, Tuple
from zoneinfo import ZoneInfo

from watsonx_client import WatsonXClient
from vs_enc import VSEncOrchestrator

# ------------------------------------------------------------------------------
# FAIL-FAST GUARD (Env-Var Authority)
# ------------------------------------------------------------------------------
if not os.getenv("WATSONX_PROJECT_ID"):
    print("❌ ERROR: WATSONX_PROJECT_ID missing.")
    sys.exit(1)

DEFAULT_AGENT = os.getenv("SCHOLARLY_DIVE_AGENT", "QWEN-ECHO")
if not re.fullmatch(r"[A-Z0-9_\-]{2,40}", DEFAULT_AGENT):
    print("❌ ERROR: SCHOLARLY_DIVE_AGENT invalid format (expected A-Z/0-9/_/- 2..40 chars).")
    sys.exit(1)

PACIFIC = ZoneInfo("America/Los_Angeles")
ARTIFACT_DIR = "war_council/_artifacts/scholarly_dive"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

# ------------------------------------------------------------------------------
# PROMPT LAW (Anti-hagiography / Historiography-first)
# ------------------------------------------------------------------------------
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
        obj = json.loads(maybe_json)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _extract_first_json_object(text: str) -> str:
    """
    Extracts the first balanced JSON object (starting at the first '{') from text.
    Uses a brace-balance scan to avoid greedy regex failures.
    """
    start = text.find("{")
    if start == -1:
        return ""
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return ""


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

    json_blob = _extract_first_json_object(tail)
    if not json_blob:
        return body_content, meta_json

    meta_json = _safe_json_loads(json_blob)
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


def _escape_braces(s: str) -> str:
    """Prevent str.format() injection/KeyError if topic contains braces."""
    return s.replace("{", "{{").replace("}", "}}")


def _build_prompt(topic: str) -> str:
    safe_topic = _escape_braces(topic)
    return PROMPT_TEMPLATE.format(topic=safe_topic)


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
    version = "v1.7.1"
    print(f"✶⌁✶ SCHOLARLY DIVE {version} [HARDENED+CRITICAL] ONLINE")

    try:
        topic = _get_topic()

        # Optional: show the operator the posture shift before emission.
        if _prompt_user_yes_no("Use historiography-first (anti-hagiography) prompt?", default=True):
            prompt = _build_prompt(topic)
        else:
            # Operator override: lighter structure, but still governed (non-negotiables remain).
            prompt = f"""
ROLE: You are the Algorithmic Griot.
TASK: Provide a deep scholarly synthesis on: {topic}

NON-NEGOTIABLE:
- Historiography > hagiography.
- Separate claims from outcomes in practice.
- If uncertain, say "uncertain" rather than inventing details.

STRUCTURE:
# Abstract
# Historical Analysis [^1]
# Semiotic Analysis
# 📚 BIBLIOGRAPHY

CITATIONS:
- Use Markdown footnotes [^1] in the body.
- In bibliography: [^1]: Author. *Title* (Publisher, Year).

METADATA:
- Provide JSON labeled '### METADATA' at the absolute end.
""".strip()

        synapse = ScholarlySynapse(agent_name=DEFAULT_AGENT)
        orch = VSEncOrchestrator({"SCHOLARLY_STUB": StubAgent()})

        print(f"✶ Synthesizing deep artifact for '{topic}' (agent={synapse.agent_name})...")
        raw_response = synapse.ask(prompt)

        body_content, meta_json = _extract_metadata(raw_response)

        if not body_content.strip():
            raise ValueError("Model returned empty body content; refusing emission.")

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
