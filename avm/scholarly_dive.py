# ==============================================================================
# ✶⌁✶ scholarly_dive.py — SYNTHESIS ENGINE v3.3.6 [LEAN+SOFT-GATED+RECOVERY]
# ==============================================================================

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
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

# Citation policy:
# - TARGET_CITATIONS is the preferred strength threshold
# - MIN_REQUIRED_CITATIONS is the actual refusal floor
TARGET_CITATIONS = 3
MIN_REQUIRED_CITATIONS = 1

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
- Target at least 3 DISTINCT in-body footnotes tied to concrete claims
- Minimum acceptable support is 1 DISTINCT in-body footnote if evidence is sparse
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
- Target at least 3 DISTINCT body footnotes
- Minimum acceptable support is 1 DISTINCT body footnote if evidence is sparse
- Every bibliography id must match a body footnote
- Every body footnote must have a bibliography line
- No invented citations
- No invented quotations
- Use quotes: [] unless you have a real direct quote with attribution
- Keep ### METADATA and valid JSON
- If evidence is thin, say so plainly and avoid unsupported claims
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
- Target at least 3 DISTINCT in-body footnotes
- Minimum acceptable support is 1 DISTINCT in-body footnote if evidence is sparse
- Every bibliography line must match a cited body footnote
- Use quotes: [] unless you have real direct quotes
- If evidence is limited, state that clearly instead of inventing support
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
        or "*" not in line
        or "(" not in line
        or ")" not in line
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


@dataclass
class ValidationResult:
    ok: bool
    error: str = ""
    warnings: List[str] = field(default_factory=list)
    distinct_citations: int = 0


def validate(body: str, meta: Dict[str, Any]) -> ValidationResult:
    if not body.strip():
        return ValidationResult(False, "Empty output")

    for h in REQUIRED_HEADERS:
        if h not in body:
            return ValidationResult(False, f"Missing section: {h}")

    refs = set(_body_refs(body))
    ref_count = len(refs)

    if ref_count < MIN_REQUIRED_CITATIONS:
        return ValidationResult(
            False,
            f"Only {ref_count} distinct citations",
            distinct_citations=ref_count,
        )

    bib_ids = set(_bib_ids(body))
    if not bib_ids:
        return ValidationResult(False, "Missing bibliography", distinct_citations=ref_count)

    if refs != bib_ids:
        return ValidationResult(
            False,
            "Citation mismatch between body and bibliography",
            distinct_citations=ref_count,
        )

    lines = _bib_lines(body)
    if not lines:
        return ValidationResult(False, "Empty bibliography", distinct_citations=ref_count)

    for line in lines:
        if not BIB_LINE_RE.match(line):
            return ValidationResult(False, "Invalid bibliography format", distinct_citations=ref_count)
        if _has_fake_patterns(line):
            return ValidationResult(False, f"Suspicious citation: {line}", distinct_citations=ref_count)

    if not _quotes_ok(meta):
        return ValidationResult(False, "Invalid metadata quotes", distinct_citations=ref_count)

    warnings: List[str] = []
    if ref_count < TARGET_CITATIONS:
        warnings.append(
            f"Low citation density: {ref_count} distinct citation(s); target is {TARGET_CITATIONS}."
        )

    return ValidationResult(True, "", warnings, ref_count)


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


def _attempt(
    syn: Synapse,
    topic: str,
    label: str,
    prompt: str,
) -> Tuple[str, Dict[str, Any], ValidationResult]:
    save_debug(topic, f"{label}_prompt", prompt)
    raw = syn.ask(prompt)
    save_debug(topic, f"{label}_raw", raw)

    body, meta = extract_metadata(raw)
    meta = _meta_normalize(meta)
    result = validate(body, meta)

    save_debug(topic, f"{label}_body", body)
    save_debug(topic, f"{label}_meta", json.dumps(meta, indent=2, ensure_ascii=False))
    save_debug(
        topic,
        f"{label}_validation",
        json.dumps(
            {
                "ok": result.ok,
                "error": result.error,
                "warnings": result.warnings,
                "distinct_citations": result.distinct_citations,
            },
            indent=2,
            ensure_ascii=False,
        ),
    )

    return body, meta, result


def generate(syn: Synapse, topic: str) -> Tuple[str, Dict[str, Any], ValidationResult]:
    attempts: List[Tuple[str, str]] = []

    prompt_1 = PROMPT.format(topic=topic, scaffold=HARD_SCAFFOLD)
    body, meta, result = _attempt(syn, topic, "attempt1_primary", prompt_1)
    attempts.append(("attempt1_primary", result.error or "; ".join(result.warnings)))
    if result.ok:
        return body, meta, result

    print(f"⚠ Failed: {result.error}")

    prompt_2 = REBUILD_PROMPT.format(topic=topic, scaffold=HARD_SCAFFOLD)
    body2, meta2, result2 = _attempt(syn, topic, "attempt2_rebuild", prompt_2)
    attempts.append(("attempt2_rebuild", result2.error or "; ".join(result2.warnings)))
    if result2.ok:
        return body2, meta2, result2

    print(f"⚠ Failed: {result2.error}")

    repair_seed = body2 if body2.strip() else body
    prompt_3 = REPAIR_PROMPT.format(
        topic=topic,
        error=result2.error,
        draft=repair_seed,
        scaffold=HARD_SCAFFOLD,
    )
    body3, meta3, result3 = _attempt(syn, topic, "attempt3_repair", prompt_3)
    attempts.append(("attempt3_repair", result3.error or "; ".join(result3.warnings)))
    if result3.ok:
        return body3, meta3, result3

    print(f"⚠ Failed: {result3.error}")

    prompt_4 = REBUILD_PROMPT.format(topic=topic, scaffold=HARD_SCAFFOLD)
    body4, meta4, result4 = _attempt(syn, topic, "attempt4_final_rebuild", prompt_4)
    attempts.append(("attempt4_final_rebuild", result4.error or "; ".join(result4.warnings)))

    save_debug(
        topic,
        "attempt_summary",
        "\n".join(f"{name}: {msg}" for name, msg in attempts),
    )

    return body4, meta4, result4


def run() -> None:
    print("✶⌁✶ SCHOLARLY DIVE v3.3.6 [LEAN+SOFT-GATED+RECOVERY] ONLINE")

    topic = input("Enter Research Topic: ").strip()
    if not topic:
        print("❌ No topic")
        return

    ensure_debug_dir()

    syn = Synapse()
    orch = VSEncOrchestrator({"orchestrator": OrchestratorAgent()})

    print(f"✶ Synthesizing: {topic}")
    body, meta, result = generate(syn, topic)

    if not result.ok:
        print(f"❌ REFUSED: {result.error}")
        return

    if result.warnings:
        for warning in result.warnings:
            print(f"⚠ Warning: {warning}")

    summary = "Scholarly synthesis generated."
    longform_summary = "See full analysis."
    status = "active"
    priority = "medium"

    if result.distinct_citations < TARGET_CITATIONS:
        summary = (
            f"Scholarly synthesis generated with limited evidentiary support "
            f"({result.distinct_citations} distinct citation(s))."
        )
        longform_summary = (
            "Artifact emitted under soft gate. Structure and citation integrity passed, "
            "but citation density is below target. Claims should be treated as provisional "
            "and revisited with stronger sourcing."
        )
        status = "draft"
        priority = "medium"

    payload = orch.run(
        agent_name="orchestrator",
        input_text=body,
        invocation_type="scholarly_dive",
        custom_params={
            "title": meta.get("title", f"Research — {topic}"),
            "relative_dir": ARTIFACT_DIR,
            "summary": summary,
            "longform_summary": longform_summary,
            "category": "research",
            "style": "AlgorithmicGriot",
            "status": status,
            "priority": priority,
            "tags": meta.get("tags", []),
            "key_themes": meta.get("key_themes", []),
            "bias_analysis": meta.get(
                "bias_analysis",
                "Grounded scholarly synthesis with explicit handling of evidentiary limits."
            ),
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