# ==============================================================================
# ✶⌁✶ scholarly_dive.py — SYNTHESIS ENGINE v3.3.5 [LEAN+GATED+RECOVERY]
# ==============================================================================

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from vs_enc import VSEncOrchestrator
from watsonx_client import WatsonXClient

if not os.getenv("WATSONX_PROJECT_ID"):
    print("❌ ERROR: WATSONX_PROJECT_ID missing.")
    sys.exit(1)

AGENT = os.getenv("SCHOLARLY_DIVE_AGENT", "QWEN-ECHO")
ARTIFACT_DIR = "war_council/_artifacts/scholarly_dive"
DEBUG_DIR = Path("C:/Users/digitalscorpyun/projects_2026/avm/_debug/scholarly_dive")
MIN_CITATIONS = 3
PST = timezone(timedelta(hours=-8))

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

HARD_SCAFFOLD = """# Abstract

# Historical Analysis
## Historiography & Scholarly Debate
## Material Conditions / Actors / Events
## Contradictions / Limits / Ambiguities

# Semiotic Analysis
## Narrative Framing
## Rhetorical Mechanics

# 📚 BIBLIOGRAPHY
[^1]:
[^2]:
[^3]:

### METADATA
{
  "title": "",
  "tags": [],
  "key_themes": [],
  "bias_analysis": "",
  "grok_ctx_reflection": "",
  "quotes": [],
  "adinkra": []
}
"""

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
- Use the exact top-level headers shown below
- Return a complete artifact, not notes about the artifact
- Do not omit # Abstract
- Do not omit ### METADATA

REQUIRED SCAFFOLD:
{scaffold}

CITATION FORMAT:
- Body: [^1]
- Bibliography lines only, one per line:
  [^1]: Author. *Title* (Publisher, Year).
  OR
  [^1]: Institution. *Title* (Year).
- No bullets in bibliography
- No extra commentary in bibliography

METADATA RULES:
- quotes must be a JSON list of strings
- use [] unless you have a REAL direct quote with attribution
- do not include paraphrases as quotes
- adinkra must be a JSON list of strings

Return only the report and metadata.
"""

REBUILD_PROMPT = """\
Your last response failed validation.

Rewrite from scratch on: {topic}

YOU MUST RETURN THIS EXACT TOP-LEVEL SHAPE:
{scaffold}

RULES:
- Use those exact top-level headers
- Keep at least 3 DISTINCT body footnotes
- Every bibliography id must match a body footnote
- Every body footnote must have a bibliography line
- No invented citations
- No invented quotations
- Use quotes: [] unless you have a real direct quote with attribution
- Keep ### METADATA and valid JSON
- Do not explain what you are doing
- Do not apologize
- Return only the rewritten report and metadata
"""

REPAIR_PROMPT = """\
Repair the draft below without changing its required top-level structure.

TOPIC: {topic}
VALIDATION ERROR: {error}

REQUIRED SCAFFOLD:
{scaffold}

RULES:
- Preserve exact top-level headers:
  # Abstract
  # Historical Analysis
  # Semiotic Analysis
  # 📚 BIBLIOGRAPHY
- Preserve ### METADATA
- Remove invented or suspicious citations
- Fix body/bibliography alignment
- Keep at least 3 DISTINCT in-body footnotes
- Every bibliography line must match a cited body footnote
- Use quotes: [] unless you have real direct quotes
- Return only the repaired report and metadata

DRAFT:
{draft}
"""


def now_pst() -> datetime:
    return datetime.now(PST)


def ensure_debug_dir() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)


def debug_path(topic: str, label: str) -> Path:
    stamp = now_pst().strftime("%Y%m%d_%H%M%S")
    safe_topic = re.sub(r"[^a-zA-Z0-9]+", "_", topic).strip("_")[:80] or "topic"
    return DEBUG_DIR / f"{stamp}__{safe_topic}__{label}.txt"


def save_debug(topic: str, label: str, content: str) -> None:
    path = debug_path(topic, label)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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
    if not isinstance(meta.get("tags"), list):
        meta["tags"] = []
    if not isinstance(meta.get("key_themes"), list):
        meta["key_themes"] = []
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
        return self.client.ask(prompt, max_new_tokens=2600)


class OrchestratorAgent:
    def run(self, text: str) -> str:
        return text


def _attempt(syn: Synapse, topic: str, label: str, prompt: str) -> Tuple[str, Dict[str, Any], bool, str]:
    save_debug(topic, f"{label}_prompt", prompt)
    raw = syn.ask(prompt)
    save_debug(topic, f"{label}_raw", raw)

    body, meta = extract_metadata(raw)
    meta = _meta_normalize(meta)
    ok, err = validate(body, meta)

    save_debug(topic, f"{label}_body", body)
    save_debug(topic, f"{label}_meta", json.dumps(meta, indent=2, ensure_ascii=False))

    return body, meta, ok, err


def generate(syn: Synapse, topic: str) -> Tuple[str, Dict[str, Any], bool, str]:
    attempts = []

    prompt_1 = PROMPT.format(topic=topic, scaffold=HARD_SCAFFOLD)
    body, meta, ok, err = _attempt(syn, topic, "attempt1_primary", prompt_1)
    attempts.append(("attempt1_primary", err))
    if ok:
        return body, meta, ok, err

    print(f"⚠ Failed: {err}")

    prompt_2 = REBUILD_PROMPT.format(topic=topic, scaffold=HARD_SCAFFOLD)
    body2, meta2, ok2, err2 = _attempt(syn, topic, "attempt2_rebuild", prompt_2)
    attempts.append(("attempt2_rebuild", err2))
    if ok2:
        return body2, meta2, ok2, err2

    print(f"⚠ Failed: {err2}")

    repair_seed = body2 if body2.strip() else body
    prompt_3 = REPAIR_PROMPT.format(
        topic=topic,
        error=err2,
        draft=repair_seed,
        scaffold=HARD_SCAFFOLD,
    )
    body3, meta3, ok3, err3 = _attempt(syn, topic, "attempt3_repair", prompt_3)
    attempts.append(("attempt3_repair", err3))
    if ok3:
        return body3, meta3, ok3, err3

    print(f"⚠ Failed: {err3}")

    # Final hard reset rebuild
    prompt_4 = REBUILD_PROMPT.format(topic=topic, scaffold=HARD_SCAFFOLD)
    body4, meta4, ok4, err4 = _attempt(syn, topic, "attempt4_final_rebuild", prompt_4)
    attempts.append(("attempt4_final_rebuild", err4))

    save_debug(
        topic,
        "attempt_summary",
        "\n".join(f"{name}: {msg}" for name, msg in attempts),
    )

    return body4, meta4, ok4, err4


def run() -> None:
    print("✶⌁✶ SCHOLARLY DIVE v3.3.5 [LEAN+GATED+RECOVERY] ONLINE")

    topic = input("Enter Research Topic: ").strip()
    if not topic:
        print("❌ No topic")
        return

    ensure_debug_dir()

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