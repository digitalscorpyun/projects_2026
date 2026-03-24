# ==============================================================================
# ✶⌁✶ scholarly_dive.py — SYNTHESIS ENGINE v3.3.0 [LEAN+GATED+REPAIR]
# ==============================================================================
# PURPOSE: Enforce real citation discipline without bloated parsing logic
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
# ENV
# ------------------------------------------------------------------------------
if not os.getenv("WATSONX_PROJECT_ID"):
    print("❌ ERROR: WATSONX_PROJECT_ID missing.")
    sys.exit(1)

AGENT = os.getenv("SCHOLARLY_DIVE_AGENT", "QWEN-ECHO")
ARTIFACT_DIR = "war_council/_artifacts/scholarly_dive"
MAX_REPAIR_ATTEMPTS = 1
MIN_CITATIONS = 3

REQUIRED_HEADERS = [
    "# Abstract",
    "# Historical Analysis",
    "# Semiotic Analysis",
    "# 📚 BIBLIOGRAPHY",
]

FOOTNOTE_REF_RE = re.compile(r"\[\^(\d+)\]")
BIB_LINE_RE = re.compile(r"^\[\^(\d+)\]:(.+)$", re.MULTILINE)

# Minimal suspicion patterns (tight, not overengineered)
BAD_AUTHORS = {"Smith, John", "Doe, John", "Doe, Jane"}
BAD_TITLE_PATTERNS = ["case of", "case study", "analysis of", "study of"]

# ------------------------------------------------------------------------------
# PROMPT
# ------------------------------------------------------------------------------
PROMPT = """\
Produce a rigorous scholarly synthesis on: {topic}

RULES:
- No fluff
- No invented citations
- Use at least 3 DISTINCT in-body footnotes tied to real claims
- Do NOT fabricate books, reports, or institutions
- If support is weak, say so

STRUCTURE:
# Abstract
# Historical Analysis
# Semiotic Analysis
# 📚 BIBLIOGRAPHY

CITATIONS:
- Use [^1] style
- Bibliography must match body exactly
- No extra entries

METADATA:
Return JSON after ### METADATA
"""

REPAIR_PROMPT = """\
Fix this report so it passes validation.

ERROR:
{error}

RULES:
- Keep structure
- Remove fake citations
- Ensure at least 3 distinct real citations
- Ensure body ↔ bibliography match

REPORT:
{report}
"""

# ------------------------------------------------------------------------------
# PARSE
# ------------------------------------------------------------------------------
def extract_metadata(text: str) -> Tuple[str, Dict[str, Any]]:
    if "### METADATA" not in text:
        return text.strip(), {}

    body, tail = text.split("### METADATA", 1)

    try:
        meta = json.loads(tail.strip())
    except Exception:
        meta = {}

    return body.strip(), meta


# ------------------------------------------------------------------------------
# VALIDATION (LEAN)
# ------------------------------------------------------------------------------
def _split(body: str):
    if "# 📚 BIBLIOGRAPHY" not in body:
        return body, ""
    return body.split("# 📚 BIBLIOGRAPHY", 1)


def _body_refs(body: str) -> List[str]:
    main, _ = _split(body)
    return FOOTNOTE_REF_RE.findall(main)


def _bib_ids(body: str) -> List[str]:
    _, bib = _split(body)
    return re.findall(r"\[\^(\d+)\]:", bib)


def _bib_lines(body: str) -> List[str]:
    _, bib = _split(body)
    return [l.strip() for l in bib.splitlines() if l.strip()]


def _has_fake_patterns(line: str) -> bool:
    lower = line.lower()

    # generic fake titles
    if any(p in lower for p in BAD_TITLE_PATTERNS):
        return True

    # fake authors
    for a in BAD_AUTHORS:
        if a.lower() in lower:
            return True

    return False


def validate(body: str, meta: Dict[str, Any]) -> Tuple[bool, str]:
    if not body:
        return False, "Empty output"

    for h in REQUIRED_HEADERS:
        if h not in body:
            return False, f"Missing section: {h}"

    refs = _body_refs(body)
    unique_refs = set(refs)

    if len(unique_refs) < MIN_CITATIONS:
        return False, f"Only {len(unique_refs)} distinct citations"

    bib_ids = _bib_ids(body)
    if not bib_ids:
        return False, "Missing bibliography"

    # match body ↔ bibliography
    if set(refs) != set(bib_ids):
        return False, "Citation mismatch between body and bibliography"

    # format check
    for line in _bib_lines(body):
        if not BIB_LINE_RE.match(line):
            return False, "Invalid bibliography format"

        if _has_fake_patterns(line):
            return False, f"Suspicious citation: {line}"

    return True, ""


# ------------------------------------------------------------------------------
# SYNAPSE
# ------------------------------------------------------------------------------
@dataclass
class Synapse:
    agent: str = AGENT

    def __post_init__(self):
        self.client = WatsonXClient()
        self.client.set_agent(self.agent)
        print(f"✶ Synapse: {self.agent} online")

    def ask(self, prompt: str) -> str:
        return self.client.ask(prompt, max_new_tokens=2000)


# ------------------------------------------------------------------------------
# CORE
# ------------------------------------------------------------------------------
def generate(s: Synapse, topic: str):
    raw = s.ask(PROMPT.format(topic=topic))
    body, meta = extract_metadata(raw)
    ok, err = validate(body, meta)
    return body, meta, ok, err


def repair(s: Synapse, topic: str, report: str, error: str):
    raw = s.ask(REPAIR_PROMPT.format(report=report, error=error))
    body, meta = extract_metadata(raw)
    ok, err = validate(body, meta)
    return body, meta, ok, err


# ------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------
def run():
    print("✶⌁✶ SCHOLARLY DIVE v3.3.0 [LEAN] ONLINE")

    topic = input("Enter Research Topic: ").strip()
    if not topic:
        print("❌ No topic")
        return

    syn = Synapse()
    orch = VSEncOrchestrator({"orchestrator": lambda x: x})

    print(f"✶ Synthesizing: {topic}")

    body, meta, ok, err = generate(syn, topic)

    if not ok:
        print(f"⚠ Failed: {err}")
        body, meta, ok, err = repair(syn, topic, body, err)

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
            "status": "active",
        },
    )

    orch.emit_to_vault(payload)
    print("✓ Emitted")


if __name__ == "__main__":
    run()