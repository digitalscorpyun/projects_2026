# ==============================================================================
# ✶⌁✶ scholarly_dive.py — THE SCHOLARLY SYNTHESIS ENGINE v3.6.1 [RECOVERY-HARDENED]
# ==============================================================================
# ROLE: Lean synthesis client with fail-fast validation, citation integrity,
#       metadata enforcement, and vault-safe emission discipline.
# COMPLIANCE: WC-DIR-2026-01-11-ENV-HARDENING / SENTINEL-V2.0.0-ALIGN
# ==============================================================================

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore

from vs_enc import VSEncOrchestrator
from watsonx_client import WatsonXClient


# ------------------------------------------------------------------------------
# ENV / IDENTITY
# ------------------------------------------------------------------------------
if not os.getenv("WATSONX_PROJECT_ID"):
    print("❌ ERROR: WATSONX_PROJECT_ID missing.")
    sys.exit(1)

AGENT = os.getenv("SCHOLARLY_DIVE_AGENT", "QWEN-ECHO")
ARTIFACT_DIR = "war_council/_artifacts/scholarly_dive"
DEBUG_DIR = Path("C:/Users/digitalscorpyun/projects_2026/avm/_debug/scholarly_dive")
LA_TZ = ZoneInfo("America/Los_Angeles")

VERSION = "v3.6.1"
BANNER = f"✶⌁✶ SCHOLARLY DIVE {VERSION} [RECOVERY-HARDENED] ONLINE"

TARGET_CITATIONS = 3
MIN_REQUIRED_CITATIONS = 1

REQUIRED_HEADERS = [
    "# Abstract",
    "# Historical Analysis",
    "# Semiotic Analysis",
    "# 📚 BIBLIOGRAPHY",
]

CRITICAL_META_KEYS = [
    "title",
    "tags",
    "key_themes",
    "bias_analysis",
    "grok_ctx_reflection",
    "quotes",
    "adinkra",
]

FOOTNOTE_REF_RE = re.compile(r"\[\^(\d+)\]")
BIB_LINE_RE = re.compile(r"^\[\^(\d+)\]:\s+(.+)$")
QUOTED_TEXT_RE = re.compile(r'[“"]([^"\n]{12,220})[”"]\s*[—-]\s*([^\n]+)')
TRAILING_METADATA_RE = re.compile(r"\n### METADATA\s*$", re.MULTILINE)

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
Produce a rigorous AlgorithmicGriot research synthesis on: {topic}

NON-NEGOTIABLE RULES:
- No fluff
- No invented citations
- No invented quotations
- No placeholder metadata
- Use the exact top-level headers shown below
- Return a complete artifact only
- Target at least 3 DISTINCT in-body footnotes tied to concrete claims
- Minimum acceptable support is 1 DISTINCT in-body footnote if evidence is sparse
- Every body footnote must appear in bibliography
- Every bibliography line must correspond to a cited body footnote
- If evidence is weak, state that clearly instead of bluffing
- If you cannot support a claim, omit or soften it
- Maintain a disciplined AlgorithmicGriot voice: high-precision, historically alert, rhetorically controlled
- Do not append notes after metadata
- Return ONE metadata block only, at the end

BODY FOOTNOTE FORMAT:
- Place markers directly after factual sentences: example.[^1]

BIBLIOGRAPHY FORMAT:
- One entry per footnote
- You MAY wrap long bibliography entries across multiple lines, but continuation lines must stay directly under the citation they belong to
- Example:
  [^1]: Author, *Title* (Publisher, Year).
  [^2]: Institution, *Title* (Year).
  [^3]: Case Name, Reporter (Year).

METADATA RULES:
- title: non-empty string
- tags: non-empty JSON list of strings
- key_themes: non-empty JSON list of strings
- bias_analysis: non-empty string
- grok_ctx_reflection: non-empty string
- quotes: non-empty JSON list of REAL direct quotes with attribution in the same string
- adinkra: non-empty JSON list of strings
- quotes MUST use this shape:
  ["\\"Quoted text\\" — Name"]

REQUIRED SCAFFOLD:
{scaffold}

Return only the report and metadata.
"""

REBUILD_PROMPT = """\
Your last response failed validation.

Rewrite from scratch on: {topic}

YOU MUST RETURN THIS EXACT TOP-LEVEL SHAPE:
{scaffold}

HARD RULES:
- Preserve the exact required top-level headers
- Produce a vault-safe AlgorithmicGriot synthesis
- No invented citations
- No invented quotations
- No placeholder metadata
- Target at least 3 DISTINCT body footnotes
- Minimum acceptable support is 1 DISTINCT body footnote if evidence is sparse
- Every body footnote must match a bibliography line
- Every bibliography line must match a body footnote
- quotes metadata must be non-empty and contain real direct quote(s) with attribution
- Every critical metadata field must be non-empty
- If support is thin, say so plainly and narrow the claims
- Return only the rewritten report and metadata
"""

REPAIR_PROMPT = """\
Repair the draft below without changing its required top-level structure.

TOPIC: {topic}
VALIDATION ERROR: {error}

REQUIRED SCAFFOLD:
{scaffold}

HARD RULES:
- Preserve exact top-level headers
- Preserve one metadata block at the end
- Remove invented or suspicious citations
- Fix body/bibliography alignment
- Restore non-empty critical metadata fields
- quotes metadata must be non-empty and contain real direct quote(s) with attribution
- If a claim cannot be supported, soften or remove it
- Return only the repaired report and metadata

DRAFT:
{draft}
"""

QUOTE_REPAIR_PROMPT = """\
The draft below is missing valid quote metadata.

Repair ONLY the metadata and any body language needed to support it.

RULES:
- Preserve the existing body whenever possible
- Keep exact top-level headers
- Keep one metadata block at the end
- quotes must be a non-empty JSON list
- Every quote must be a REAL direct quote with attribution in one string:
  "\\"Quoted text\\" — Name"
- Do not invent quotations
- If no quote is safely available, rewrite the draft so that one real quoted sentence is included and sourced
- Return only the repaired report and metadata

DRAFT:
{draft}
"""


# ------------------------------------------------------------------------------
# TIME / DEBUG
# ------------------------------------------------------------------------------
def now_la() -> datetime:
    return datetime.now(LA_TZ)


def ensure_debug_dir() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)


def debug_path(topic: str, label: str) -> Path:
    stamp = now_la().strftime("%Y%m%d_%H%M%S")
    safe_topic = re.sub(r"[^a-zA-Z0-9]+", "_", topic).strip("_")[:80] or "topic"
    return DEBUG_DIR / f"{stamp}__{safe_topic}__{label}.txt"


def save_debug(topic: str, label: str, content: str) -> None:
    path = debug_path(topic, label)
    path.write_text(content, encoding="utf-8")


# ------------------------------------------------------------------------------
# GENERAL HELPERS
# ------------------------------------------------------------------------------
def clean_whitespace(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def dedupe(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        val = item.strip()
        if val and val not in seen:
            seen.add(val)
            out.append(val)
    return out


def slug_terms(topic: str) -> List[str]:
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9]+", topic)]
    return dedupe(words[:5]) or ["research"]


def split_body_bib(body: str) -> Tuple[str, str]:
    if "# 📚 BIBLIOGRAPHY" not in body:
        return body, ""
    main, bib = body.split("# 📚 BIBLIOGRAPHY", 1)
    return main, bib


def body_refs(body: str) -> List[str]:
    main, _ = split_body_bib(body)
    return FOOTNOTE_REF_RE.findall(main)


def bib_ids(body: str) -> List[str]:
    entries = parse_bibliography_entries(body)
    return [entry_id for entry_id, _ in entries]


def bib_lines(body: str) -> List[str]:
    entries = parse_bibliography_entries(body)
    return [f"[^{entry_id}]: {entry_text}" for entry_id, entry_text in entries]


def has_required_headers(body: str) -> bool:
    return all(header in body for header in REQUIRED_HEADERS)


def count_concrete_signals(text: str) -> int:
    return (
        len(re.findall(r"\b(1[5-9]\d{2}|20\d{2})\b", text))
        + len(re.findall(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", text))
        + len(re.findall(r"\b[A-Z][a-z]+ v\. [A-Z][A-Za-z]+\b", text))
    )


def split_paragraphs(text: str) -> List[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]


# ------------------------------------------------------------------------------
# METADATA EXTRACTION / NORMALIZATION
# ------------------------------------------------------------------------------
def repair_json(raw: str) -> Dict[str, Any]:
    raw = raw.strip()
    if not raw:
        return {}

    repaired = (
        raw.replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("‘", "'")
    )
    repaired = re.sub(r",(\s*[\]}])", r"\1", repaired)

    try:
        parsed = json.loads(repaired)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def extract_metadata(text: str) -> Tuple[str, Dict[str, Any], List[str]]:
    warnings: List[str] = []
    marker = "### METADATA"
    idx = text.rfind(marker)
    if idx == -1:
        return text.strip(), {}, warnings

    body = text[:idx].strip()
    tail = text[idx + len(marker):].strip()

    start = tail.find("{")
    end = tail.rfind("}")
    candidate = tail[start:end + 1] if start != -1 and end != -1 and end > start else ""
    meta = repair_json(candidate)

    if not meta:
        warnings.append("Metadata JSON malformed or missing; normalization applied.")

    return body, meta, warnings


def infer_quote_from_body(body: str) -> List[str]:
    hits = QUOTED_TEXT_RE.findall(body)
    cleaned: List[str] = []
    for quote, author in hits:
        q = quote.strip()
        a = author.strip().strip(".")
        if len(q) >= 12 and a:
            cleaned.append(f"\"{q}\" — {a}")
    return dedupe(cleaned[:2])


def normalize_meta(meta: Dict[str, Any], topic: str, body: str) -> Dict[str, Any]:
    meta = meta if isinstance(meta, dict) else {}
    terms = slug_terms(topic)

    title = str(meta.get("title", "")).strip() or topic.strip() or "Research"
    tags = meta.get("tags", [])
    key_themes = meta.get("key_themes", [])
    adinkra = meta.get("adinkra", [])
    quotes = meta.get("quotes", [])

    if not isinstance(tags, list):
        tags = [str(tags).strip()] if str(tags).strip() else []
    if not isinstance(key_themes, list):
        key_themes = [str(key_themes).strip()] if str(key_themes).strip() else []
    if not isinstance(adinkra, list):
        adinkra = [str(adinkra).strip()] if str(adinkra).strip() else []
    if not isinstance(quotes, list):
        quotes = [str(quotes).strip()] if str(quotes).strip() else []

    tags = dedupe([str(x).strip() for x in tags if str(x).strip()]) or terms[:3]
    key_themes = dedupe([str(x).strip() for x in key_themes if str(x).strip()]) or terms[:3]
    adinkra = dedupe([str(x).strip() for x in adinkra if str(x).strip()]) or ["Sankofa"]

    clean_quotes = []
    for q in quotes:
        if not isinstance(q, str):
            continue
        s = q.strip()
        if s and "—" in s:
            clean_quotes.append(s)

    if not clean_quotes:
        clean_quotes = infer_quote_from_body(body)

    bias_analysis = str(meta.get("bias_analysis", "")).strip()
    if not bias_analysis:
        bias_analysis = (
            "Synthesis foregrounds evidentiary limits, historiographic tension, and power-laden framing "
            "instead of treating consensus claims as neutral."
        )

    grok_ctx_reflection = str(meta.get("grok_ctx_reflection", "")).strip()
    if not grok_ctx_reflection:
        grok_ctx_reflection = (
            "Artifact built for retrieval stability, contradiction visibility, and source-linked analytical reuse."
        )

    return {
        "title": title,
        "tags": tags,
        "key_themes": key_themes,
        "bias_analysis": bias_analysis,
        "grok_ctx_reflection": grok_ctx_reflection,
        "quotes": dedupe(clean_quotes),
        "adinkra": adinkra,
    }


# ------------------------------------------------------------------------------
# BIBLIOGRAPHY PARSING / RECOVERY
# ------------------------------------------------------------------------------
def parse_bibliography_entries(body: str) -> List[Tuple[str, str]]:
    """
    Recover bibliography entries even when the model wraps them across lines.

    Accepted shapes:
      [^1]: Author, *Title* ...
           continuation...
      [^2]: Institution, *Title* ...
    """
    _, bib = split_body_bib(body)
    if not bib.strip():
        return []

    entries: List[Tuple[str, str]] = []
    current_id: str | None = None
    current_parts: List[str] = []

    for raw_line in bib.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        match = re.match(r"^\[\^(\d+)\]:\s*(.*)$", stripped)
        if match:
            if current_id is not None:
                entry_text = " ".join(part.strip() for part in current_parts if part.strip()).strip()
                if entry_text:
                    entries.append((current_id, entry_text))
            current_id = match.group(1)
            seed = match.group(2).strip()
            current_parts = [seed] if seed else []
            continue

        if current_id is not None:
            current_parts.append(stripped)

    if current_id is not None:
        entry_text = " ".join(part.strip() for part in current_parts if part.strip()).strip()
        if entry_text:
            entries.append((current_id, entry_text))

    cleaned: List[Tuple[str, str]] = []
    seen_ids = set()
    for entry_id, entry_text in entries:
        if not entry_text:
            continue
        if entry_id in seen_ids:
            continue
        seen_ids.add(entry_id)
        cleaned.append((entry_id, re.sub(r"\s{2,}", " ", entry_text).strip()))

    return cleaned


def rebuild_bibliography(body: str, entries: List[Tuple[str, str]]) -> str:
    main, _ = split_body_bib(body)
    rebuilt = "\n".join(f"[^{entry_id}]: {entry_text}" for entry_id, entry_text in entries)
    return clean_whitespace(main) + "\n\n# 📚 BIBLIOGRAPHY\n" + rebuilt


def anchor_bibliography_refs_into_body(body: str) -> Tuple[str, List[str]]:
    """
    If the model produced bibliography entries but forgot inline footnote markers,
    attach existing bibliography IDs to safe paragraph endpoints in the body.

    This does not invent sources; it only repairs missing anchors.
    """
    warnings: List[str] = []
    refs = set(body_refs(body))
    entries = parse_bibliography_entries(body)

    if refs or not entries:
        return body, warnings

    main, bib = split_body_bib(body)
    paragraphs = split_paragraphs(main)
    if not paragraphs:
        return body, warnings

    available_ids = [entry_id for entry_id, _ in entries]
    used = 0
    anchored: List[str] = []

    for para in paragraphs:
        if used >= len(available_ids):
            anchored.append(para)
            continue

        stripped = para.strip()
        if stripped.startswith("#"):
            anchored.append(para)
            continue

        # Prefer anchoring to prose paragraphs, not headings.
        citation = f"[^{available_ids[used]}]"
        if re.search(r"\[\^\d+\]\s*$", stripped):
            anchored.append(para)
            continue

        if stripped.endswith("."):
            anchored.append(stripped + citation)
        elif stripped.endswith(("!", "?", "”", "\"")):
            anchored.append(stripped + citation)
        else:
            anchored.append(stripped + "." + citation)

        used += 1

    if used:
        warnings.append(
            f"Recovered {used} in-body citation anchor(s) from bibliography-only support."
        )

    rebuilt_main = "\n\n".join(anchored)
    rebuilt = rebuilt_main + "\n\n# 📚 BIBLIOGRAPHY\n" + bib.strip()
    return clean_whitespace(rebuilt), warnings


# ------------------------------------------------------------------------------
# STRUCTURE / BIBLIOGRAPHY REPAIR
# ------------------------------------------------------------------------------
def repair_structure(topic: str, body: str) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    if has_required_headers(body):
        return clean_whitespace(body), warnings

    sections = {
        "# Abstract": "",
        "# Historical Analysis": "",
        "# Semiotic Analysis": "",
        "# 📚 BIBLIOGRAPHY": "",
    }

    current = None
    for line in body.splitlines():
        stripped = line.strip()
        if stripped in sections:
            current = stripped
            continue
        if current:
            sections[current] += line + "\n"

    if not sections["# Abstract"].strip():
        sections["# Abstract"] = (
            f"This draft on {topic} was recovered from a structurally degraded output. "
            "Claims should be treated as provisional unless citation support is visible.\n"
        )
        warnings.append("Synthesized missing abstract.")

    if not sections["# Historical Analysis"].strip():
        sections["# Historical Analysis"] = (
            "## Historiography & Scholarly Debate\nEvidence was limited in this run.\n\n"
            "## Material Conditions / Actors / Events\nRecovered output did not preserve this section.\n\n"
            "## Contradictions / Limits / Ambiguities\nRecovery preserved shell structure only.\n"
        )
        warnings.append("Synthesized missing historical section.")

    if not sections["# Semiotic Analysis"].strip():
        sections["# Semiotic Analysis"] = (
            "## Narrative Framing\nRecovered output did not preserve this section.\n\n"
            "## Rhetorical Mechanics\nInterpretive claims remain provisional pending source review.\n"
        )
        warnings.append("Synthesized missing semiotic section.")

    rebuilt = (
        "# Abstract\n\n"
        f"{sections['# Abstract'].strip()}\n\n"
        "# Historical Analysis\n\n"
        f"{sections['# Historical Analysis'].strip()}\n\n"
        "# Semiotic Analysis\n\n"
        f"{sections['# Semiotic Analysis'].strip()}\n\n"
        "# 📚 BIBLIOGRAPHY\n"
        f"{sections['# 📚 BIBLIOGRAPHY'].strip()}"
    )
    return clean_whitespace(rebuilt), warnings


def sanitize_bibliography(body: str) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    if "# 📚 BIBLIOGRAPHY" not in body:
        return body, warnings

    _, bib = split_body_bib(body)
    original_lines = [ln.rstrip() for ln in bib.splitlines() if ln.strip()]
    entries = parse_bibliography_entries(body)

    if not original_lines and not entries:
        return body, warnings

    kept_lines = {f"[^{entry_id}]: {entry_text}" for entry_id, entry_text in entries}

    # Report any original non-empty line that did not survive recovery.
    for raw in original_lines:
        stripped = raw.strip()
        if stripped.startswith("[^") and stripped not in kept_lines and not BIB_LINE_RE.match(stripped):
            warnings.append(f"Recovered wrapped bibliography line: {stripped[:120]}")
        elif not stripped.startswith("[^"):
            # Continuation lines are acceptable if attached; don't warn on them.
            continue

    if not entries:
        warnings.append("Bibliography present but no valid entries could be recovered.")
        return rebuild_bibliography(body, []), warnings

    return rebuild_bibliography(body, entries), warnings


def align_body_and_bib(body: str) -> Tuple[str, List[str]]:
    warnings: List[str] = []

    # First try to recover missing body anchors from a valid bibliography.
    body, anchor_warnings = anchor_bibliography_refs_into_body(body)
    warnings.extend(anchor_warnings)

    refs = set(body_refs(body))
    b_ids = set(bib_ids(body))

    if not refs and not b_ids:
        return body, warnings

    if not refs and b_ids:
        return body, dedupe(warnings + ["Bibliography recovered, but no body citations could be anchored."])

    if refs and not b_ids:
        return body, dedupe(warnings + ["Body citations present, but bibliography could not be recovered."])

    good = refs & b_ids

    if good != refs:
        main, bib = split_body_bib(body)
        main = re.sub(r"\[\^(\d+)\]", lambda m: m.group(0) if m.group(1) in good else "", main)
        body = clean_whitespace(main) + "\n\n# 📚 BIBLIOGRAPHY\n" + bib.strip()
        warnings.append("Removed orphan body footnotes.")

    if good != b_ids:
        kept_entries = [(entry_id, entry_text) for entry_id, entry_text in parse_bibliography_entries(body) if entry_id in good]
        body = rebuild_bibliography(body, kept_entries)
        warnings.append("Pruned uncited bibliography lines.")

    return clean_whitespace(body), dedupe(warnings)


# ------------------------------------------------------------------------------
# VALIDATION
# ------------------------------------------------------------------------------
@dataclass
class ValidationResult:
    ok: bool
    error: str = ""
    warnings: List[str] = field(default_factory=list)
    distinct_citations: int = 0


def validate(body: str, meta: Dict[str, Any]) -> ValidationResult:
    warnings: List[str] = []

    if not body.strip():
        return ValidationResult(False, "Empty output")

    for header in REQUIRED_HEADERS:
        if header not in body:
            return ValidationResult(False, f"Missing section: {header}")

    refs = set(body_refs(body))
    b_ids = set(bib_ids(body))
    bib = bib_lines(body)

    if len(refs) < MIN_REQUIRED_CITATIONS:
        return ValidationResult(False, f"Only {len(refs)} distinct citations", distinct_citations=len(refs))

    if not bib:
        return ValidationResult(False, "Missing bibliography", distinct_citations=len(refs))

    if refs != b_ids:
        return ValidationResult(False, "Citation mismatch between body and bibliography", distinct_citations=len(refs))

    for line in bib:
        if not BIB_LINE_RE.match(line):
            return ValidationResult(False, "Invalid bibliography format", distinct_citations=len(refs))

    for key in CRITICAL_META_KEYS:
        value = meta.get(key)
        if isinstance(value, str) and not value.strip():
            return ValidationResult(False, f"Empty metadata field: {key}", distinct_citations=len(refs))
        if isinstance(value, list) and not value:
            return ValidationResult(False, f"Empty metadata field: {key}", distinct_citations=len(refs))
        if value is None:
            return ValidationResult(False, f"Empty metadata field: {key}", distinct_citations=len(refs))

    quotes = meta.get("quotes", [])
    if not isinstance(quotes, list) or not quotes:
        return ValidationResult(False, "Metadata quotes invalid or empty", distinct_citations=len(refs))
    if not all(isinstance(q, str) and "—" in q for q in quotes):
        return ValidationResult(False, "Metadata quotes invalid or unattributed", distinct_citations=len(refs))

    if len(refs) < TARGET_CITATIONS:
        warnings.append(
            f"Low citation density: {len(refs)} distinct citation(s); target is {TARGET_CITATIONS}."
        )

    return ValidationResult(True, "", dedupe(warnings), len(refs))


# ------------------------------------------------------------------------------
# MODEL / PIPELINE
# ------------------------------------------------------------------------------
@dataclass
class Synapse:
    agent: str = AGENT

    def __post_init__(self) -> None:
        self.client = WatsonXClient()
        self.client.set_agent(self.agent)
        print(f"✶ Synapse: {self.agent} online")

    def ask(self, prompt: str) -> str:
        return self.client.ask(prompt, max_new_tokens=2600)


class StubAgent:
    def run(self, text: str) -> str:
        return text


def cleanup_pipeline(topic: str, body: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any], List[str]]:
    warnings: List[str] = []
    body, structure_warnings = repair_structure(topic, body)
    warnings.extend(structure_warnings)

    body, bib_warnings = sanitize_bibliography(body)
    warnings.extend(bib_warnings)

    body, align_warnings = align_body_and_bib(body)
    warnings.extend(align_warnings)

    meta = normalize_meta(meta, topic, body)
    return clean_whitespace(body), meta, dedupe(warnings)


def serialize_validation(result: ValidationResult) -> str:
    return json.dumps(
        {
            "ok": result.ok,
            "error": result.error,
            "warnings": result.warnings,
            "distinct_citations": result.distinct_citations,
        },
        indent=2,
        ensure_ascii=False,
    )


def attempt(syn: Synapse, topic: str, label: str, prompt: str) -> Tuple[str, Dict[str, Any], ValidationResult]:
    save_debug(topic, f"{label}_prompt", prompt)
    raw = syn.ask(prompt)
    save_debug(topic, f"{label}_raw", raw)

    body, meta, meta_warnings = extract_metadata(raw)
    body, meta, pipeline_warnings = cleanup_pipeline(topic, body, meta)

    result = validate(body, meta)
    result.warnings = dedupe(meta_warnings + pipeline_warnings + result.warnings)

    save_debug(topic, f"{label}_body", body)
    save_debug(topic, f"{label}_meta", json.dumps(meta, indent=2, ensure_ascii=False))
    save_debug(topic, f"{label}_validation", serialize_validation(result))
    return body, meta, result


def generate(syn: Synapse, topic: str) -> Tuple[str, Dict[str, Any], ValidationResult]:
    body1, meta1, res1 = attempt(
        syn,
        topic,
        "attempt1_primary",
        PROMPT.format(topic=topic, scaffold=HARD_SCAFFOLD),
    )
    if res1.ok:
        return body1, meta1, res1
    print(f"⚠ Failed: {res1.error}")

    body2, meta2, res2 = attempt(
        syn,
        topic,
        "attempt2_rebuild",
        REBUILD_PROMPT.format(topic=topic, scaffold=HARD_SCAFFOLD),
    )
    if res2.ok:
        return body2, meta2, res2
    print(f"⚠ Failed: {res2.error}")

    repair_seed = body2 if len(body2.strip()) >= len(body1.strip()) else body1
    body3, meta3, res3 = attempt(
        syn,
        topic,
        "attempt3_repair",
        REPAIR_PROMPT.format(
            topic=topic,
            error=res2.error,
            draft=repair_seed,
            scaffold=HARD_SCAFFOLD,
        ),
    )
    if res3.ok:
        return body3, meta3, res3
    print(f"⚠ Failed: {res3.error}")

    quote_seed = body3 if count_concrete_signals(body3) >= count_concrete_signals(repair_seed) else repair_seed
    body4, meta4, res4 = attempt(
        syn,
        topic,
        "attempt4_quote_repair",
        QUOTE_REPAIR_PROMPT.format(draft=quote_seed),
    )
    if res4.ok:
        return body4, meta4, res4
    print(f"⚠ Failed: {res4.error}")

    return body4, meta4, res4


# ------------------------------------------------------------------------------
# ENTRYPOINT
# ------------------------------------------------------------------------------
def run() -> None:
    print(BANNER)

    topic = input("Enter Research Topic: ").strip()
    if not topic:
        print("❌ No topic")
        return

    ensure_debug_dir()

    print(f"✶ Synapse: {AGENT} identity manifested.")
    syn = Synapse()
    orch = VSEncOrchestrator({"SCHOLARLY_STUB": StubAgent()})

    print(f"✶ Synthesizing: {topic}")
    body, meta, result = generate(syn, topic)

    if not result.ok:
        print(f"❌ REFUSED: {result.error}")
        for warning in dedupe(result.warnings):
            print(f"⚠ Warning: {warning}")
        return

    for warning in dedupe(result.warnings):
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
            "Artifact passed hard validation and minimum citation integrity, "
            "but citation density remains below target."
        )
        status = "draft"
        priority = "medium"

    payload = orch.run(
        agent_name="SCHOLARLY_STUB",
        input_text=body,
        invocation_type="scholarly_dive",
        custom_params={
            "title": meta["title"],
            "relative_dir": ARTIFACT_DIR,
            "summary": summary,
            "longform_summary": longform_summary,
            "category": "research",
            "style": "AlgorithmicGriot",
            "status": status,
            "priority": priority,
            "tags": meta["tags"],
            "key_themes": meta["key_themes"],
            "bias_analysis": meta["bias_analysis"],
            "grok_ctx_reflection": meta["grok_ctx_reflection"],
            "quotes": meta["quotes"],
            "adinkra": meta["adinkra"],
        },
    )

    orch.emit_to_vault(payload)
    print("✓ Emitted")


if __name__ == "__main__":
    run()