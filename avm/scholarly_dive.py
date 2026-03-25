# ==============================================================================
# ✶⌁✶ scholarly_dive.py — SYNTHESIS ENGINE v3.3.4 [LEAN+GATED+BRANCHED]
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

if not os.getenv("WATSONX_PROJECT_ID"):
    print("❌ ERROR: WATSONX_PROJECT_ID missing.")
    sys.exit(1)

AGENT = os.getenv("SCHOLARLY_DIVE_AGENT", "QWEN-ECHO")
ARTIFACT_DIR = "war_council/_artifacts/scholarly_dive"
MIN_CITATIONS = 3

REQUIRED_HEADERS = [
    "# Abstract",
    "# Historical Analysis",
    "# Semiotic Analysis",
    "# 📚 BIBLIOGRAPHY",
]

FOOTNOTE_REF_RE = re.compile(r"\[\^(\d+)\]")
BIB_LINE_RE = re.compile(r"^\[\^(\d+)\]:\s+(.+)$", re.MULTILINE)
BAD_AUTHORS = {"smith, john", "doe, john", "doe, jane", "author unknown"}
BAD_TITLE_PATTERNS = ["case study", "analysis of", "study of", "reassessment", "dark side of"]
BAD_QUOTE_PATTERNS = ["unknown", "historian", "analysis", "source", "[^"]

PROMPT = """\
Produce a rigorous scholarly synthesis on: {topic}

NON-NEGOTIABLE RULES:
- No fluff
- No invented citations
- No invented quotations
- Use at least 3 DISTINCT in-body footnotes tied to concrete claims
- Every body footnote must appear in bibliography
- Every bibliography entry must be cited in the body
- If support is weak, explicitly say evidence is limited
- If you cannot support a claim, omit it

STRUCTURE:
# Abstract
# Historical Analysis
## Historiography & Scholarly Debate
## Material Conditions / Actors / Events
## Contradictions / Limits / Ambiguities
# Semiotic Analysis
## Narrative Framing
## Rhetorical Mechanics
# 📚 BIBLIOGRAPHY

CITATION FORMAT:
- Body: [^1]
- Bibliography lines only, one per line:
  [^1]: Author. *Title* (Publisher, Year).
  OR
  [^1]: Institution. *Title* (Year).
- No bullets in bibliography
- No extra commentary in bibliography

METADATA:
Return JSON after ### METADATA with:
title, tags, key_themes, bias_analysis, grok_ctx_reflection, quotes, adinkra

METADATA RULES:
- quotes must be a JSON list of strings
- use [] unless you have a REAL direct quote with attribution
- do not include paraphrases as quotes
- adinkra must be a JSON list of strings

Return only the report and metadata.
"""

REBUILD_PROMPT = """\
Your last response failed because it had no usable footnote structure.

Rewrite from scratch on: {topic}

REQUIRED OUTPUT SHAPE:
# Abstract
# Historical Analysis
## Historiography & Scholarly Debate [^1]
## Material Conditions / Actors / Events [^2]
## Contradictions / Limits / Ambiguities [^3]
# Semiotic Analysis
## Narrative Framing
## Rhetorical Mechanics
# 📚 BIBLIOGRAPHY
[^1]: ...
[^2]: ...
[^3]: ...

RULES:
- Use those exact top-level headers
- Keep at least 3 DISTINCT body footnotes
- Every bibliography id must match a body footnote
- No invented citations
- No invented quotations
- Use quotes: [] unless you have a real direct quote with attribution
- Keep ### METADATA and valid JSON

Return only the rewritten report and metadata.
"""

REPAIR_PROMPT = """\
Repair the draft below without changing its required top-level structure.

TOPIC: {topic}
VALIDATION ERROR: {error}

RULES:
- Preserve exact top-level headers:
  # Abstract
  # Historical Analysis
  # Semiotic Analysis
  # 📚 BIBLIOGRAPHY
- Remove invented or suspicious citations
- Fix body/bibliography alignment
- Keep at least 3 DISTINCT in-body footnotes
- Use quotes: [] unless you have real direct quotes
- Keep ### METADATA and valid JSON

DRAFT:
{draft}

Return only the repaired report and metadata.
"""

def extract_metadata(text: str) -> Tuple[str, Dict[str, Any]]:
    if "### METADATA" not in text:
        return text.strip(), {}
    body, tail = text.split("### METADATA", 1)
    tail = tail.strip()
    try:
        start = tail.find("{")
        end = tail.rfind("}") + 1
        meta = json.loads(tail[start:end]) if start != -1 and end > 0 else {}
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}
    return body.strip(), meta

def _split(body: str) -> Tuple[str, str]:
    return body.split("# 📚 BIBLIOGRAPHY", 1) if "# 📚 BIBLIOGRAPHY" in body else (body, "")

def _body_refs(body: str) -> List[str]:
    main, _ = _split(body)
    return FOOTNOTE_REF_RE.findall(main)

def _bib_ids(body: str) -> List[str]:
    _, bib = _split(body)
    return re.findall(r"\[\^(\d+)\]:", bib)

def _bib_lines(body: str) -> List[str]:
    _, bib = _split(body)
    return [ln.strip() for ln in bib.splitlines() if ln.strip()]

def _has_fake_patterns(line: str) -> bool:
    lower = line.lower()
    return (
        any(a in lower for a in BAD_AUTHORS)
        or any(p in lower for p in BAD_TITLE_PATTERNS)
        or "*" not in line or "(" not in line or ")" not in line
    )

def _quotes_ok(meta: Dict[str, Any]) -> bool:
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
        if any(p in q.lower() for p in BAD_QUOTE_PATTERNS):
            return False
    return True

def _meta_normalize(meta: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(meta.get("quotes"), list):
        meta["quotes"] = []
    if not isinstance(meta.get("adinkra"), list):
        v = meta.get("adinkra", [])
        meta["adinkra"] = [v] if isinstance(v, str) and v.strip() else []
    return meta

def validate(body: str, meta: Dict[str, Any]) -> Tuple[bool, str]:
    if not body.strip():
        return False, "Empty output"
    for h in REQUIRED_HEADERS:
        if h not in body:
            return False, f"Missing section: {h}"

    refs = set(_body_refs(body))
    if len(refs) < MIN_CITATIONS:
        return False, f"Only {len(refs)} distinct citations"

    bib_ids = set(_bib_ids(body))
    if not bib_ids:
        return False, "Missing bibliography"
    if refs != bib_ids:
        return False, "Citation mismatch between body and bibliography"

    lines = _bib_lines(body)
    if not lines:
        return False, "Empty bibliography"
    for line in lines:
        if not BIB_LINE_RE.match(line):
            return False, "Invalid bibliography format"
        if _has_fake_patterns(line):
            return False, f"Suspicious citation: {line}"

    if not _quotes_ok(meta):
        return False, "Invalid metadata quotes"
    return True, ""

@dataclass
class Synapse:
    agent: str = AGENT

    def __post_init__(self) -> None:
        self.client = WatsonXClient()
        self.client.set_agent(self.agent)
        print(f"✶ Synapse: {self.agent} online")

    def ask(self, prompt: str) -> str:
        return self.client.ask(prompt, max_new_tokens=2200)

class OrchestratorAgent:
    def run(self, text: str) -> str:
        return text

def _attempt(syn: Synapse, prompt: str) -> Tuple[str, Dict[str, Any], bool, str]:
    raw = syn.ask(prompt)
    body, meta = extract_metadata(raw)
    meta = _meta_normalize(meta)
    ok, err = validate(body, meta)
    return body, meta, ok, err

def generate(syn: Synapse, topic: str) -> Tuple[str, Dict[str, Any], bool, str]:
    body, meta, ok, err = _attempt(syn, PROMPT.format(topic=topic))
    if ok:
        return body, meta, ok, err

    print(f"⚠ Failed: {err}")
    if err.startswith("Only 0 distinct citations"):
        return _attempt(syn, REBUILD_PROMPT.format(topic=topic))

    return _attempt(syn, REPAIR_PROMPT.format(topic=topic, error=err, draft=body))

def run() -> None:
    print("✶⌁✶ SCHOLARLY DIVE v3.3.4 [LEAN+GATED+BRANCHED] ONLINE")

    topic = input("Enter Research Topic: ").strip()
    if not topic:
        print("❌ No topic")
        return

    syn = Synapse()
    orch = VSEncOrchestrator({"orchestrator": OrchestratorAgent()})

    print(f"✶ Synthesizing: {topic}")
    body, meta, ok, err = generate(syn, topic)
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
            "priority": "medium",
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
    print("✓ Emitted")

if __name__ == "__main__":
    run()