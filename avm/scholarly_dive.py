# ==============================================================================
# ✶⌁✶ scholarly_dive.py — SYNTHESIS ENGINE v3.0.2 [LEAN+GATED]
# ==============================================================================
# ROLE: Thin scholarly synthesis client
# DESIGN: Prompt → Model → Minimal Gate → Orchestrator Emit
# PURPOSE: Refuse structurally polished but epistemically weak output
# ==============================================================================

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from vs_enc import VSEncOrchestrator
from watsonx_client import WatsonXClient

# ------------------------------------------------------------------------------
# ENV GUARD
# ------------------------------------------------------------------------------
if not os.getenv("WATSONX_PROJECT_ID"):
    print("❌ ERROR: WATSONX_PROJECT_ID missing.")
    sys.exit(1)

AGENT = os.getenv("SCHOLARLY_DIVE_AGENT", "QWEN-ECHO")
ARTIFACT_DIR = "war_council/_artifacts/scholarly_dive"

REQUIRED_HEADERS = [
    "# Abstract",
    "# Historical Analysis",
    "# Semiotic Analysis",
    "# 📚 BIBLIOGRAPHY",
]

MIN_CITATIONS = 3
FOOTNOTE_REF_RE = re.compile(r"\[\^(\d+)\]")
BIB_LINE_RE = re.compile(r"^\[\^(\d+)\]:(.*)$", flags=re.MULTILINE)

# ------------------------------------------------------------------------------
# PROMPT
# ------------------------------------------------------------------------------
PROMPT = """\
ROLE: You are the Algorithmic Griot.

TASK: Produce a rigorous scholarly synthesis on: {topic}

RULES:
- Historiography > narrative
- No fluff
- No myth-making
- Tie analysis tightly to topic
- No tables
- No placeholder text
- Do not invent citations
- Do not invent quotations
- If you cannot support a claim, omit it

REQUIRED STRUCTURE:
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
- Use [^1] style footnotes in the body
- Include at least 3 in-body footnote references attached to concrete claims
- Bibliography must match footnotes
- Bibliography lines must use exactly this format:
  [^1]: Author. *Title* (Publisher, Year).
  OR
  [^1]: Institution. *Report Title* (Year).
- No bullet lists in bibliography
- Do not list sources that are not actually cited in the body

METADATA:
Return JSON at the end labeled ### METADATA with:
title, tags, key_themes, bias_analysis, grok_ctx_reflection, quotes, adinkra

METADATA RULES:
- quotes must be a list of strings
- every quote string must include attribution inside the same string, e.g.:
  "Quote text — Author/Source"
- if you do not have a real attributable quote, return quotes as an empty list

Return only the report and metadata.
"""

# ------------------------------------------------------------------------------
# BASIC PARSING
# ------------------------------------------------------------------------------
def extract_metadata(text: str) -> Tuple[str, Dict[str, Any]]:
    if "### METADATA" not in text:
        return text.strip(), {}

    body, tail = text.split("### METADATA", 1)
    tail = tail.strip()

    try:
        start = tail.find("{")
        end = tail.rfind("}") + 1
        if start == -1 or end <= 0:
            return body.strip(), {}
        meta = json.loads(tail[start:end])
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}

    return body.strip(), meta


# ------------------------------------------------------------------------------
# VALIDATION
# ------------------------------------------------------------------------------
def _collect_body_footnotes(body: str) -> List[str]:
    main = body.split("# 📚 BIBLIOGRAPHY", 1)[0]
    return FOOTNOTE_REF_RE.findall(main)


def _collect_bibliography_ids(body: str) -> List[str]:
    if "# 📚 BIBLIOGRAPHY" not in body:
        return []
    _, biblio = body.split("# 📚 BIBLIOGRAPHY", 1)
    return re.findall(r"^\[\^(\d+)\]:", biblio, flags=re.MULTILINE)


def _bibliography_has_only_footnote_lines(body: str) -> bool:
    if "# 📚 BIBLIOGRAPHY" not in body:
        return False

    _, biblio = body.split("# 📚 BIBLIOGRAPHY", 1)
    lines = [ln.strip() for ln in biblio.splitlines() if ln.strip()]
    if not lines:
        return False

    for line in lines:
        if not BIB_LINE_RE.match(line):
            return False
    return True


def _has_attributed_quotes(meta: Dict[str, Any]) -> bool:
    quotes = meta.get("quotes", [])
    if quotes is None:
        return True
    if not isinstance(quotes, list):
        return False
    for q in quotes:
        if not isinstance(q, str):
            return False
        if "—" not in q and " - " not in q:
            return False
    return True


def validate(body: str, meta: Dict[str, Any]) -> Tuple[bool, str]:
    if not body.strip():
        return False, "Empty output"

    for header in REQUIRED_HEADERS:
        if header not in body:
            return False, f"Missing required section: {header}"

    body_refs = _collect_body_footnotes(body)
    if len(body_refs) < MIN_CITATIONS:
        return False, f"Insufficient citation binding: found {len(body_refs)} in-body footnotes"

    bib_ids = _collect_bibliography_ids(body)
    if not bib_ids:
        return False, "Missing bibliography entries"

    if not _bibliography_has_only_footnote_lines(body):
        return False, "Bibliography contains non-footnote lines"

    missing = sorted(set(body_refs) - set(bib_ids), key=int)
    if missing:
        return False, f"Body footnotes missing from bibliography: {', '.join(missing)}"

    if not _has_attributed_quotes(meta):
        return False, "Metadata quotes must include inline attribution"

    return True, ""


# ------------------------------------------------------------------------------
# SYNAPSE
# ------------------------------------------------------------------------------
@dataclass
class Synapse:
    agent: str = AGENT

    def __post_init__(self) -> None:
        self.client = WatsonXClient()
        self.client.set_agent(self.agent)
        print(f"✶ Synapse: {self.agent} identity manifested.")

    def ask(self, prompt: str) -> str:
        return self.client.ask(prompt, max_new_tokens=2000)


# ------------------------------------------------------------------------------
# LOCAL PASS-THROUGH ORCHESTRATOR AGENT
# ------------------------------------------------------------------------------
class OrchestratorAgent:
    def run(self, text: str) -> str:
        return text


# ------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------
def run() -> None:
    print("✶⌁✶ SCHOLARLY DIVE v3.0.2 [LEAN+GATED] ONLINE")

    topic = input("Enter Research Topic: ").strip()
    if not topic:
        print("❌ No topic provided.")
        return

    prompt = PROMPT.format(topic=topic)

    synapse = Synapse()
    orch = VSEncOrchestrator({"orchestrator": OrchestratorAgent()})

    print(f"✶ Synthesizing: {topic}")

    raw = synapse.ask(prompt)
    body, meta = extract_metadata(raw)

    ok, err = validate(body, meta)
    if not ok:
        print(f"❌ REFUSED: {err}")
        return

    payload = orch.run(
        agent_name="orchestrator",
        input_text=body,
        invocation_type="scholarly_dive",
        custom_params={
            "title": meta.get("title", f"Research — {topic}"),
            "relative_dir": ARTIFACT_DIR,
            "summary": "Scholarly synthesis generated.",
            "longform_summary": "See full analysis.",
            "category": "research",
            "style": "AlgorithmicGriot",
            "priority": "medium",
            "status": "active",
            "tags": meta.get("tags", []),
            "key_themes": meta.get("key_themes", []),
            "bias_analysis": meta.get("bias_analysis", "Grounded scholarly synthesis."),
            "grok_ctx_reflection": meta.get(
                "grok_ctx_reflection",
                "Research artifact generated through scholarly_dive."
            ),
            "quotes": meta.get("quotes", []),
            "adinkra": meta.get("adinkra", []),
        },
    )

    orch.emit_to_vault(payload)
    print("✓ Emitted successfully")


# ------------------------------------------------------------------------------
if __name__ == "__main__":
    run()