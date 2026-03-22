# ==============================================================================
# ✶⌁✶ scholarly_dive.py — THE SYNTHESIS ENGINE v2.0.0 [REFRACTORED+GATED]
# ==============================================================================
# ROLE: Deep synthesis client with semantic validation + hard emission gate.
# GOAL: Prevent bad upstream output from reaching the vault.
# CHANGE (v2.0.0):
#   - Removes "sanitize-and-ship" behavior for referenced bad citations
#   - Blocks placeholder/default text from emission
#   - Adds topic-anchor drift checks
#   - Adds section integrity checks
#   - Adds body-quality checks for sludge/filler patterns
# DEFAULT: ALWAYS historiography-first (no operator prompt)
# COMPLIANCE: SENTINEL-V2.0.0-ALIGN / schema-on-write discipline
# ==============================================================================

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

from vs_enc import VSEncOrchestrator
from watsonx_client import WatsonXClient

# ------------------------------------------------------------------------------
# FAIL-FAST GUARD (Env-Var Authority)
# ------------------------------------------------------------------------------
if not os.getenv("WATSONX_PROJECT_ID"):
    print("❌ ERROR: WATSONX_PROJECT_ID missing.")
    sys.exit(1)

DEFAULT_AGENT = os.getenv("SCHOLARLY_DIVE_AGENT", "QWEN-ECHO")
if not re.fullmatch(r"[A-Z0-9_\-]{2,40}", DEFAULT_AGENT):
    print(
        "❌ ERROR: SCHOLARLY_DIVE_AGENT invalid format "
        "(expected A-Z/0-9/_/- 2..40 chars)."
    )
    sys.exit(1)

PACIFIC = ZoneInfo("America/Los_Angeles")  # reserved for future timestamp needs
ARTIFACT_DIR = "war_council/_artifacts/scholarly_dive"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

# ------------------------------------------------------------------------------
# Strictness knobs
# ------------------------------------------------------------------------------
STRICT_BIBLIO = os.getenv("SCHOLARLY_STRICT_BIBLIO", "1") == "1"
STRICT_META = os.getenv("SCHOLARLY_STRICT_META", "1") == "1"
STRICT_BODY = os.getenv("SCHOLARLY_STRICT_BODY", "1") == "1"
STRICT_TOPIC = os.getenv("SCHOLARLY_STRICT_TOPIC", "1") == "1"

RETRY_ON_FAIL = int(os.getenv("SCHOLARLY_RETRY_ON_FAIL", "1"))

MAX_WORDS = int(os.getenv("SCHOLARLY_MAX_WORDS", "1100"))
MAX_NEW_TOKENS = int(os.getenv("SCHOLARLY_MAX_NEW_TOKENS", "2600"))

MIN_TOPIC_ANCHORS = int(os.getenv("SCHOLARLY_MIN_TOPIC_ANCHORS", "2"))
MIN_BODY_WORDS = int(os.getenv("SCHOLARLY_MIN_BODY_WORDS", "350"))
MAX_BODY_WORDS = int(os.getenv("SCHOLARLY_MAX_BODY_WORDS", "1800"))

ALLOW_UNCERTAIN_UNREFERENCED = os.getenv("SCHOLARLY_ALLOW_UNCERTAIN_UNREFERENCED", "1") == "1"

# ------------------------------------------------------------------------------
# PROMPT LAW
# ------------------------------------------------------------------------------
PROMPT_TEMPLATE = """\
ROLE: You are the Algorithmic Griot.
TASK: Produce a rigorous scholarly synthesis on: {topic}

PRIMARY RULE: Historiography > hagiography.
- Do NOT sanctify individuals or nations.
- Center structures, conflicts, agency from below, and material conditions.
- Explicitly surface contradictions, limits, enforcement realities, and contested interpretations.
- Separate what the document "says" from what it "did" in practice.

EVIDENCE / CITATION LAW (NON-NEGOTIABLE):
- You may ONLY include a bibliography entry if you are confident it exists as a real, citable source.
- If you are not confident a source exists, write "uncertain" and DO NOT fabricate titles, authors, years, journals, or case numbers.
- Prefer fewer, higher-confidence sources over many.
- Every paragraph in the Historical Analysis section should remain tightly specific to the topic.
- Do NOT include tables.
- Target length: <= {max_words} words.

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
- Ensure every footnote referenced in the body has a bibliography entry.
- In bibliography, format as: [^1]: Author. *Title* (Publisher, Year). OR [^1]: Institution. *Report Title* (Year).
- If uncertain, the bibliography entry must be exactly: [^N]: uncertain

METADATA:
- Provide JSON labeled '### METADATA' at the absolute end.
- JSON keys allowed: title, tags, key_themes, bias_analysis, grok_ctx_reflection, quotes, adinkra.
- Metadata values MUST follow these shapes:
  - title: string
  - tags: list[string]
  - key_themes: list[string]
  - bias_analysis: string
  - grok_ctx_reflection: string
  - quotes: list[string] (each item must include attribution, e.g. "Quote text — Name/Source")
  - adinkra: list[string]

QUALITY LAW:
- Do NOT use placeholder text such as "Pending semantic summary" or similar defaults.
- Do NOT pad with generic Civil War/Reconstruction prose unless directly tied to the topic.
- Do NOT cite works irrelevant to the specific place, date, institution, or event being analyzed.
"""

REPAIR_TEMPLATE = """\
ROLE: You are the Algorithmic Griot.
TASK: Repair the previous output to satisfy ALL constraints below.

CONSTRAINTS (NON-NEGOTIABLE):
1) Keep the same section headers as required.
2) Remove or rewrite any bibliography entries that you are not confident are real. Prefer marking "uncertain".
3) Ensure footnotes used in body appear in bibliography.
4) Ensure the body remains tightly tied to the specific topic, not just the broader era.
5) Remove placeholder/default language entirely.
6) Provide '### METADATA' JSON at absolute end using ONLY allowed keys and correct value shapes.
7) quotes: each quote must include attribution inside the same quoted string ("... — Attribution").
8) adinkra must be a JSON list of strings (not a single string).
9) Do NOT include tables.
10) Be concise.

Return ONLY the corrected report (no commentary).

PREVIOUS OUTPUT (for repair):
{bad_output}
"""

# ------------------------------------------------------------------------------
# Regex + constants
# ------------------------------------------------------------------------------
_FOOTNOTE_REF_RE = re.compile(r"\[\^(\d+)\]")
_BIB_LINE_RE = re.compile(r"^\[\^(\d+)\]:(.*)$")
_WORD_RE = re.compile(r"\b[\w'’-]+\b", flags=re.UNICODE)

REQUIRED_HEADERS = [
    "# Abstract",
    "# Historical Analysis",
    "## Historiography & Scholarly Debate",
    "## Material Conditions & Enforcement",
    "## Agency & Counter-Agency",
    "## Contradictions / Limits / Exemptions",
    "# Semiotic Analysis",
    "## Myth / National Narrative (Interrogate, do not affirm)",
    "## Rhetorical Mechanics",
    "# 📚 BIBLIOGRAPHY",
]

PLACEHOLDER_PATTERNS = [
    r"pending semantic summary",
    r"pending semantic longform summary",
    r"lorem ipsum",
    r"todo",
    r"tbd",
    r"insert citation",
    r"citation needed",
    r"fill in later",
    r"placeholder",
]

GENERIC_DRIFT_PATTERNS = [
    r"\bthe civil war\b",
    r"\breconstruction\b",
    r"\bemancipation proclamation\b",
    r"\bpost-civil war america\b",
]

SLUDGE_PATTERNS = [
    r"\buncertainty flux\b",
    r"\bprofund? depths\b",
    r"\bhearts minds generations\b",
    r"\bcollectively pursued together\b",
    r"\btranscending ostensible limitations\b",
    r"\bindelibly\b",
    r"\binexorable march\b",
    r"\bsanitizing complexities\b",
]

ALLOWED_META_KEYS = {
    "title",
    "tags",
    "key_themes",
    "bias_analysis",
    "grok_ctx_reflection",
    "quotes",
    "adinkra",
}

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def _safe_json_loads(maybe_json: str) -> Dict[str, Any]:
    try:
        obj = json.loads(maybe_json)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _extract_first_json_object(text: str) -> str:
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


def _get_topic() -> str:
    topic = input("Enter Research Topic: ").strip()
    if not topic:
        raise ValueError("Topic cannot be empty.")
    return topic


def _escape_braces(s: str) -> str:
    return s.replace("{", "{{").replace("}", "}}")


def _build_prompt(topic: str) -> str:
    safe_topic = _escape_braces(topic)
    return PROMPT_TEMPLATE.format(topic=safe_topic, max_words=MAX_WORDS)


def _build_repair_prompt(bad_output: str) -> str:
    safe = _escape_braces(bad_output)
    return REPAIR_TEMPLATE.format(bad_output=safe)


def _ensure_list_of_str(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, list) and all(isinstance(x, str) for x in value):
        return value
    if isinstance(value, str):
        return [value]
    return None


def _ensure_str(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _split_biblio(body: str) -> Tuple[str, str]:
    if "# 📚 BIBLIOGRAPHY" not in body:
        return body, ""
    main, tail = body.split("# 📚 BIBLIOGRAPHY", 1)
    return main.rstrip(), tail.strip()


def _parse_biblio_lines(biblio_text: str) -> Tuple[Dict[str, str], List[str]]:
    id_to_line: Dict[str, str] = {}
    extras: List[str] = []

    for raw_ln in biblio_text.splitlines():
        ln = raw_ln.strip()
        if not ln:
            continue
        m = _BIB_LINE_RE.match(ln)
        if not m:
            extras.append(ln)
            continue
        fid = m.group(1)
        if fid not in id_to_line:
            id_to_line[fid] = ln

    return id_to_line, extras


def _looks_like_fabricated_biblio_line(line: str) -> bool:
    """
    Heuristic-only (no web).
    Flags common hallucination markers and malformed bibliography patterns.
    """
    line_lc = line.lower()

    suspicious_markers = [
        "judgment no.",
        "working paper",
        "policy brief no.",
        "annual report",
        "update",
        "transcript #",
        "unpub. lexis",
        "lexis",
        "forthcoming",
        "draft",
        "manuscript",
    ]

    has_year = bool(re.search(r"\b(18|19|20)\d{2}\b", line))
    has_title_marker = "*" in line or "report" in line_lc
    too_short = len(line.strip()) < 18

    return (
        (any(m in line_lc for m in suspicious_markers) and has_year)
        or too_short
        or ("[^" in line and not has_title_marker and "uncertain" not in line_lc)
    )


def _extract_topic_anchors(topic: str) -> List[str]:
    """
    Pulls coarse anchor phrases from the topic so we can detect drift.
    Tries to preserve capitalized names, quoted terms, years, and salient words.
    """
    raw = topic.strip()

    quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', raw)
    anchors: List[str] = []
    for pair in quoted:
        q = pair[0] or pair[1]
        q = q.strip()
        if q and len(q) >= 3:
            anchors.append(q)

    years = re.findall(r"\b(1[6-9]\d{2}|20\d{2})\b", raw)
    anchors.extend(years)

    cap_phrases = re.findall(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", raw)
    anchors.extend(cap_phrases)

    words = re.findall(r"\b[a-zA-Z][a-zA-Z\-]{3,}\b", raw)
    stop = {
        "the", "and", "with", "from", "into", "about", "after", "before", "during",
        "under", "over", "that", "this", "those", "these", "their", "there", "where",
        "what", "when", "which", "whose", "party", "history", "historical",
        "organizational", "genesis", "analysis", "study", "research",
    }
    for w in words:
        wl = w.lower()
        if wl not in stop:
            anchors.append(w)

    deduped: List[str] = []
    seen: Set[str] = set()
    for a in anchors:
        norm = a.strip().lower()
        if len(norm) < 3:
            continue
        if norm not in seen:
            seen.add(norm)
            deduped.append(a.strip())

    return deduped[:12]


def _count_anchor_hits(text: str, anchors: List[str]) -> Tuple[int, List[str]]:
    hit_count = 0
    hits: List[str] = []
    text_lc = text.lower()
    for anchor in anchors:
        a = anchor.lower()
        if a in text_lc:
            hit_count += 1
            hits.append(anchor)
    return hit_count, hits


def _validate_required_headers(body: str) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    for header in REQUIRED_HEADERS:
        if header == "# Historical Analysis":
            if not re.search(r"^# Historical Analysis(?:\s+\[\^\d+\])?$", body, flags=re.MULTILINE):
                errors.append("Missing or malformed '# Historical Analysis [^1]' header.")
        elif header not in body:
            errors.append(f"Missing required header: {header}")

    return (len(errors) == 0), errors


def _validate_placeholders(body: str, meta: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    haystacks = [body, json.dumps(meta or {}, ensure_ascii=False)]

    for hay in haystacks:
        hay_lc = hay.lower()
        for pat in PLACEHOLDER_PATTERNS:
            if re.search(pat, hay_lc):
                errors.append(f"Placeholder/default text detected: pattern='{pat}'")

    return (len(errors) == 0), errors


def _validate_topic_alignment(topic: str, body: str) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    main, _ = _split_biblio(body)
    anchors = _extract_topic_anchors(topic)
    if not anchors:
        return True, errors

    hit_count, hits = _count_anchor_hits(main, anchors)

    if hit_count < MIN_TOPIC_ANCHORS:
        errors.append(
            f"Topic drift detected: only {hit_count} topic anchors found; "
            f"need at least {MIN_TOPIC_ANCHORS}. Anchors={anchors}"
        )

    # Penalize body that leans too hard on broad-era language without topic anchors
    generic_hits = 0
    for pat in GENERIC_DRIFT_PATTERNS:
        generic_hits += len(re.findall(pat, main.lower()))

    if generic_hits >= 4 and hit_count < max(MIN_TOPIC_ANCHORS + 1, 3):
        errors.append(
            "Body appears dominated by broad-era prose rather than topic-specific analysis."
        )

    # Abstract should usually mention at least one anchor
    abstract_match = re.search(
        r"(?s)^# Abstract\s*(.*?)\n# Historical Analysis",
        body,
    )
    if abstract_match:
        abstract = abstract_match.group(1)
        abstract_hits, _ = _count_anchor_hits(abstract, anchors)
        if abstract_hits == 0:
            errors.append("Abstract does not mention any topic anchor.")

    return (len(errors) == 0), errors


def _validate_body_quality(body: str) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    main, _ = _split_biblio(body)
    wc = _word_count(main)

    if wc < MIN_BODY_WORDS:
        errors.append(f"Body too short for scholarly synthesis: {wc} words.")
    if wc > MAX_BODY_WORDS:
        errors.append(f"Body too long: {wc} words.")

    for pat in SLUDGE_PATTERNS:
        if re.search(pat, main.lower()):
            errors.append(f"Sludge/filler pattern detected: '{pat}'")

    # Detect very long sentences that often indicate generated sludge
    sentences = re.split(r"(?<=[.!?])\s+", _normalize_spaces(main))
    long_sentences = [s for s in sentences if _word_count(s) > 55]
    if len(long_sentences) >= 3:
        errors.append(
            "Too many overlong sentences (>55 words), suggesting uncontrolled generated prose."
        )

    # Detect footnote density so low that the piece is basically uncited
    refs = _FOOTNOTE_REF_RE.findall(main)
    if len(refs) == 0:
        errors.append("No in-body footnote references found.")
    elif len(refs) < 3:
        errors.append("Too few in-body footnote references for claimed scholarly synthesis.")

    return (len(errors) == 0), errors


def _validate_bibliography(body: str) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    if "# 📚 BIBLIOGRAPHY" not in body:
        errors.append("Missing '# 📚 BIBLIOGRAPHY' section.")
        return False, errors

    main, biblio = _split_biblio(body)
    if not biblio.strip():
        errors.append("Empty bibliography section.")
        return False, errors

    lines = [ln.strip() for ln in biblio.splitlines() if ln.strip()]
    refs = set(_FOOTNOTE_REF_RE.findall(main))
    bib_ids = set(re.findall(r"^\[\^(\d+)\]:", "\n".join(lines), flags=re.MULTILINE))

    missing = sorted(refs - bib_ids, key=lambda x: int(x))
    if missing:
        errors.append(
            "Footnotes referenced in body but missing from bibliography: " + ", ".join(missing)
        )

    # Block uncertain for referenced citations
    for ln in lines:
        m = _BIB_LINE_RE.match(ln)
        if not m:
            errors.append(f"Non-footnote line in bibliography not allowed: {ln}")
            continue

        fid = m.group(1)
        content = m.group(2).strip()
        is_uncertain = content.lower() == "uncertain"

        if fid in refs and is_uncertain:
            errors.append(f"Referenced footnote [^{fid}] cannot be 'uncertain'.")

        if not ALLOW_UNCERTAIN_UNREFERENCED and is_uncertain:
            errors.append(f"Unreferenced footnote [^{fid}] cannot be 'uncertain' under current policy.")

        if STRICT_BIBLIO:
            if "unverified" in ln.lower():
                errors.append(f"Unverified bibliography entry not allowed: {ln}")
            if _looks_like_fabricated_biblio_line(ln):
                errors.append(f"Suspicious bibliography entry (possible fabrication): {ln}")

    return (len(errors) == 0), errors


def _validate_metadata(meta: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    errors: List[str] = []
    meta = {k: v for k, v in (meta or {}).items() if k in ALLOWED_META_KEYS}
    normalized: Dict[str, Any] = {}

    title = _ensure_str(meta.get("title"))
    if title:
        normalized["title"] = title

    for key in ("tags", "key_themes", "adinkra"):
        lv = _ensure_list_of_str(meta.get(key))
        if lv is not None:
            normalized[key] = lv
        elif meta.get(key) is not None:
            errors.append(f"Metadata '{key}' must be list[string].")

    for key in ("bias_analysis", "grok_ctx_reflection"):
        sv = _ensure_str(meta.get(key))
        if sv is not None:
            normalized[key] = sv
        elif meta.get(key) is not None:
            errors.append(f"Metadata '{key}' must be string.")

    qv = _ensure_list_of_str(meta.get("quotes"))
    if qv is not None:
        bad = [q for q in qv if ("—" not in q and " - " not in q and "(" not in q)]
        if bad:
            errors.append(
                "Each quote must include attribution inside the same string "
                "(e.g. '... — Source')."
            )
        normalized["quotes"] = qv
    elif meta.get("quotes") is not None:
        errors.append("Metadata 'quotes' must be list[string].")

    if STRICT_META and errors:
        return False, errors, normalized
    return True, errors, normalized


def _sanitize_bibliography(body: str) -> Tuple[str, List[str]]:
    """
    Conservative local repair:
    - ensures every in-body footnote id exists in bibliography
    - replaces explicit 'unverified' entries with uncertain
    - strips commentary lines
    IMPORTANT:
    - This function no longer guarantees emission.
    - Referenced 'uncertain' still fails validation afterward.
    """
    notes: List[str] = []
    main, biblio = _split_biblio(body)

    if not biblio:
        return body, notes

    refs = sorted(set(_FOOTNOTE_REF_RE.findall(main)), key=lambda x: int(x))
    id_to_line, extras = _parse_biblio_lines(biblio)

    kept_extras: List[str] = []
    for ln in extras:
        if "unverified" in ln.lower() or "commentary" in ln.lower():
            notes.append(f"Removed bibliography commentary line: {ln}")
            continue
        kept_extras.append(ln)
    extras = kept_extras

    for fid in refs:
        current = id_to_line.get(fid)
        if current is None:
            id_to_line[fid] = f"[^{fid}]: uncertain"
            notes.append(f"Added missing bibliography entry as uncertain: [^{fid}]")
            continue

        if "unverified" in current.lower():
            id_to_line[fid] = f"[^{fid}]: uncertain"
            notes.append(f"Replaced UNVERIFIED bibliography entry with uncertain: [^{fid}]")

    rebuilt: List[str] = []
    for fid in refs:
        rebuilt.append(id_to_line[fid])

    unref = sorted((set(id_to_line.keys()) - set(refs)), key=lambda x: int(x))
    for fid in unref:
        rebuilt.append(id_to_line[fid])

    final_biblio_lines: List[str] = []
    if extras:
        final_biblio_lines.extend(extras)
    final_biblio_lines.extend(rebuilt)

    new_body = f"{main}\n\n# 📚 BIBLIOGRAPHY\n" + "\n".join(final_biblio_lines).rstrip() + "\n"
    return new_body, notes


def _strip_trailing_garbage(body: str) -> str:
    return body.rstrip() + "\n"


def _collect_validation_results(
    topic: str,
    body: str,
    meta: Dict[str, Any],
) -> Tuple[bool, Dict[str, List[str]], Dict[str, Any]]:
    """
    Returns:
      ok: overall pass/fail
      errors_by_domain: grouped errors
      normalized_meta: cleaned metadata
    """
    errors_by_domain: Dict[str, List[str]] = {}

    ok_headers, header_errors = _validate_required_headers(body)
    if not ok_headers:
        errors_by_domain["headers"] = header_errors

    ok_bib, bib_errors = _validate_bibliography(body)
    if not ok_bib:
        errors_by_domain["bibliography"] = bib_errors

    ok_meta, meta_errors, meta_norm = _validate_metadata(meta)
    if not ok_meta:
        errors_by_domain["metadata"] = meta_errors

    ok_place, place_errors = _validate_placeholders(body, meta)
    if not ok_place:
        errors_by_domain["placeholders"] = place_errors

    if STRICT_TOPIC:
        ok_topic, topic_errors = _validate_topic_alignment(topic, body)
        if not ok_topic:
            errors_by_domain["topic_alignment"] = topic_errors

    if STRICT_BODY:
        ok_body, body_errors = _validate_body_quality(body)
        if not ok_body:
            errors_by_domain["body_quality"] = body_errors

    overall_ok = len(errors_by_domain) == 0
    return overall_ok, errors_by_domain, meta_norm


def _print_grouped_errors(errors_by_domain: Dict[str, List[str]]) -> None:
    for domain, errs in errors_by_domain.items():
        print(f"— {domain}:")
        for err in errs:
            print(f"  • {err}")


# ------------------------------------------------------------------------------
# Core classes
# ------------------------------------------------------------------------------
@dataclass
class ScholarlySynapse:
    agent_name: str = DEFAULT_AGENT

    def __post_init__(self) -> None:
        self.client = WatsonXClient()
        self.client.set_agent(self.agent_name)

    def ask(self, prompt: str, max_new_tokens: int = MAX_NEW_TOKENS) -> str:
        return self.client.ask(
            prompt,
            max_new_tokens=max_new_tokens,
            repetition_penalty=1.1,
        )


class StubAgent:
    def run(self, text: str) -> str:
        return text


# ------------------------------------------------------------------------------
# Main workflow
# ------------------------------------------------------------------------------
def run_synthesis() -> None:
    version = "v2.0.0"
    print(f"✶⌁✶ SCHOLARLY DIVE {version} [REFRACTORED+GATED] ONLINE")
    print(f"✶ Synapse: {DEFAULT_AGENT} identity manifested.")

    try:
        topic = _get_topic()
        prompt = _build_prompt(topic)

        synapse = ScholarlySynapse(agent_name=DEFAULT_AGENT)
        orch = VSEncOrchestrator({"SCHOLARLY_STUB": StubAgent()})

        print(f"✶ Synthesizing deep artifact for '{topic}' (agent={synapse.agent_name})...")

        raw = synapse.ask(prompt)
        body, meta = _extract_metadata(raw)

        if not body.strip():
            raise ValueError("Model returned empty body content; refusing emission.")

        attempts = 0
        while True:
            attempts += 1

            overall_ok, errors_by_domain, meta_norm = _collect_validation_results(topic, body, meta)

            if overall_ok:
                meta = meta_norm
                break

            # One conservative local bibliography cleanup pass before asking model to repair.
            if attempts == 1 and "bibliography" in errors_by_domain:
                body2, notes = _sanitize_bibliography(body)
                if notes:
                    print("⚠️  Conservative local bibliography cleanup applied.")
                    for note in notes:
                        print(f"  • {note}")

                # Re-run validation after cleanup
                overall_ok, errors_by_domain, meta_norm = _collect_validation_results(topic, body2, meta)
                body = body2
                if overall_ok:
                    meta = meta_norm
                    break

            if attempts > (RETRY_ON_FAIL + 1):
                print("❌ REFUSING EMISSION: validation failed.")
                _print_grouped_errors(errors_by_domain)
                sys.exit(2)

            print("⚠️  Validation failed; attempting bounded repair pass...")
            _print_grouped_errors(errors_by_domain)

            repair_prompt = _build_repair_prompt(
                body + ("\n\n### METADATA\n" + json.dumps(meta, ensure_ascii=False))
            )
            raw2 = synapse.ask(repair_prompt)
            body, meta = _extract_metadata(raw2)

            if not body.strip():
                raise ValueError("Repair pass returned empty body content; refusing emission.")

        body = _strip_trailing_garbage(body)
        meta = {k: v for k, v in (meta or {}).items() if k in ALLOWED_META_KEYS}

        payload = orch.run(
            agent_name="SCHOLARLY_STUB",
            input_text=body,
            invocation_type="scholarly_dive",
            custom_params={
                "title": meta.get("title") or f"Deep Research — {topic}",
                "relative_dir": ARTIFACT_DIR,
                "category": "research",
                "style": "AlgorithmicGriot",
                "priority": "medium",
                "status": "active",
                **{k: v for k, v in meta.items() if k != "title"},
            },
        )

        orch.emit_to_vault(payload)
        print(f"✓ Research Emitted: {payload.get('filename', '<unknown>')}")

    except KeyboardInterrupt:
        print("\n⏹️  Aborted by operator.")
    except SystemExit:
        raise
    except Exception as exc:
        print(f"❌ ERROR: {exc}")


if __name__ == "__main__":
    run_synthesis()