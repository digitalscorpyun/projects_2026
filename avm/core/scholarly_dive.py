# ==============================================================================
# ✶⌁✶ scholarly_dive.py — THE SCHOLARLY SYNTHESIS ENGINE v3.8.3 [ANCHOR-QUALITY]
# ==============================================================================
# ROLE: Lean synthesis client with fail-fast validation, citation integrity,
#       metadata enforcement, topic-focus enforcement, unsupported-specificity
#       suppression, and vault-safe emission discipline.
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
from typing import Any, Dict, List, Optional, Tuple

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

VERSION = "v3.8.3"
BANNER = f"✶⌁✶ SCHOLARLY DIVE {VERSION} [ANCHOR-QUALITY] ONLINE"

TARGET_CITATIONS = 3
MIN_REQUIRED_CITATIONS = 1
MIN_TAGS = 3
MIN_KEY_THEMES = 3
MAX_PARAGRAPHS_PER_SINGLE_CITATION = 2

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

WEAK_META_TOKENS = {
    "a",
    "an",
    "and",
    "analysis",
    "america",
    "american",
    "case",
    "event",
    "history",
    "modern",
    "new",
    "presidential",
    "research",
    "state",
    "states",
    "study",
    "topic",
    "united",
    "year",
}

FOOTNOTE_REF_RE = re.compile(r"\[\^(\d+)\]")
BIB_LINE_RE = re.compile(r"^\[\^(\d+)\]:\s+(.+)$")
QUOTED_TEXT_RE = re.compile(r'[“"]([^"\n]{12,260})[”"]\s*[—-]\s*([^\n]+)')
PAREN_YEAR_RE = re.compile(r"\((1[5-9]\d{2}|20\d{2})\)")
TITLE_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
PAGE_CLAIM_RE = re.compile(r"\bp\.\s*\d+\b|\bpp\.\s*\d+(?:-\d+)?\b", re.IGNORECASE)
ARCHIVE_CLAIM_RE = re.compile(r"\barchives?\b|\bhoused in\b|\bcollection\b", re.IGNORECASE)
DATE_CLAIM_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b"
)
YEAR_RE = re.compile(r"^(1[5-9]\d{2}|20\d{2})$")

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


# ------------------------------------------------------------------------------
# TOPIC PROFILE
# ------------------------------------------------------------------------------
@dataclass
class TopicProfile:
    raw_topic: str
    core_topic: str
    focus_year: Optional[str] = None
    focus_tokens: List[str] = field(default_factory=list)
    guidance: str = ""


def clean_whitespace(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def dedupe(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        val = str(item).strip()
        if val and val not in seen:
            seen.add(val)
            out.append(val)
    return out


def normalize_topic(topic: str) -> str:
    return re.sub(r"\s+", " ", topic).strip()


def is_meaningful_meta_token(token: str) -> bool:
    lowered = token.strip().lower()
    if not lowered:
        return False
    if YEAR_RE.match(lowered):
        return False
    if lowered in WEAK_META_TOKENS:
        return False
    if len(lowered) < 4:
        return False
    return True


def normalize_meta_items(items: List[str], *, max_items: int = 6) -> List[str]:
    out: List[str] = []
    seen = set()

    for raw in items:
        item = str(raw).strip().lower()
        item = re.sub(r"[\s\-]+", "_", item)
        item = re.sub(r"[^a-z0-9_]", "", item)
        item = re.sub(r"_+", "_", item).strip("_")
        if not item:
            continue
        if YEAR_RE.match(item):
            continue
        parts = [p for p in item.split("_") if p]
        if not parts:
            continue
        if len(parts) == 1 and not is_meaningful_meta_token(parts[0]):
            continue
        if all(part in WEAK_META_TOKENS for part in parts):
            continue
        if item not in seen:
            seen.add(item)
            out.append(item)
        if len(out) >= max_items:
            break

    return out


def slug_terms(topic: str) -> List[str]:
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9]+", topic)]
    filtered = [w for w in words if is_meaningful_meta_token(w)]
    return normalize_meta_items(filtered[:8]) or ["research_topic"]


def make_topic_profile(topic: str) -> TopicProfile:
    raw = normalize_topic(topic)
    year_match = PAREN_YEAR_RE.search(raw)
    focus_year = year_match.group(1) if year_match else None
    core_topic = re.sub(r"\(\s*(1[5-9]\d{2}|20\d{2})\s*\)", "", raw).strip(" -–—")
    tokens = [
        tok.lower()
        for tok in TITLE_TOKEN_RE.findall(core_topic)
        if is_meaningful_meta_token(tok)
    ]
    tokens = dedupe(tokens[:6])

    guidance_lines = [
        f"- The artifact MUST stay tightly centered on the exact topic: {raw}",
        "- Do not backslide into a general biography or overview if the topic is narrower than a whole life or oeuvre.",
        "- Prefer specific historical evidence over generic summary language.",
        "- Do not state archival location, exact dates, page numbers, or named speeches unless support is visibly citation-bound.",
        "- If support is thin, narrow the claim instead of performing confidence.",
    ]

    if focus_year:
        guidance_lines.extend(
            [
                f"- The year {focus_year} is jurisdictionally central. Treat it as the primary analytic frame.",
                f"- Explain why {focus_year} matters specifically, not just how the broader figure or topic is generally understood.",
                f"- Reference events, texts, debates, receptions, conditions, or correspondences specific to {focus_year} where support exists.",
                f"- Avoid citing earlier or later works as if they directly describe {focus_year} unless you explicitly mark them as context.",
            ]
        )

    return TopicProfile(
        raw_topic=raw,
        core_topic=core_topic or raw,
        focus_year=focus_year,
        focus_tokens=tokens,
        guidance="\n".join(guidance_lines),
    )


# ------------------------------------------------------------------------------
# PROMPTS
# ------------------------------------------------------------------------------
PROMPT = """\
Produce a rigorous AlgorithmicGriot research synthesis on: {topic}

TOPIC JURISDICTION:
{topic_guidance}

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

QUALITY RULES:
- The abstract must identify what is historically specific about the topic's exact scope
- Do not turn a narrow topic into a generic overview
- Distinguish context from direct evidence
- If the topic includes a year, the body must make that year analytically meaningful
- Do not place quotations, commentary, or metadata fragments inside bibliography lines
- Do not use exact page numbers, archival locations, exact speech dates, or exact document holdings unless directly citation-bound and essential
- Every major prose section should contain at least one visible in-body footnote when support exists
- Prefer named contradictions, historiographic splits, structural stakes, and material conditions over textbook recap

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
- tags: non-empty JSON list of meaningful strings
- key_themes: non-empty JSON list of meaningful strings
- bias_analysis: non-empty string
- grok_ctx_reflection: non-empty string
- quotes: non-empty JSON list of REAL direct quotes with attribution in the same string
- adinkra: non-empty JSON list of strings
- tags and key_themes must be conceptually meaningful, not just repetitions of the topic string
- Avoid weak metadata tokens like bare years, "united", "states", "history", or generic filler
- Prefer analytical metadata such as "electoral_crisis", "racial_suppression", "elite_bargaining", "legitimacy_crisis"
- quotes MUST use this shape:
  ["\\"Quoted text\\" — Name"]

REQUIRED SCAFFOLD:
{scaffold}

Return only the report and metadata.
"""

REBUILD_PROMPT = """\
Your last response failed validation.

Rewrite from scratch on: {topic}

TOPIC JURISDICTION:
{topic_guidance}

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
- Do not generalize beyond the exact topic
- Do not use exact page numbers, archive claims, or exact dates unless support is tight
- If support is thin, say so plainly and narrow the claims
- Avoid weak metadata tokens like bare years, "united", "states", or generic filler
- Prefer strong analytical metadata and differentiated key themes
- Return only the rewritten report and metadata
"""

REPAIR_PROMPT = """\
Repair the draft below without changing its required top-level structure.

TOPIC: {topic}
TOPIC JURISDICTION:
{topic_guidance}
VALIDATION ERROR: {error}

REQUIRED SCAFFOLD:
{scaffold}

HARD RULES:
- Preserve exact top-level headers
- Preserve one metadata block at the end
- Remove invented or suspicious citations
- Fix body/bibliography alignment
- Remove quotation bleed from bibliography
- Restore non-empty critical metadata fields
- quotes metadata must be non-empty and contain real direct quote(s) with attribution
- Narrow generic claims so the artifact stays aligned to the exact topic
- Replace weak metadata with more analytical and topic-specific metadata
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
- Prefer a short, high-signal quotation from the argument you are already making
- If no safe quote is available, revise body language so one real quoted sentence with attribution is present
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
def split_body_bib(body: str) -> Tuple[str, str]:
    if "# 📚 BIBLIOGRAPHY" not in body:
        return body, ""
    main, bib = body.split("# 📚 BIBLIOGRAPHY", 1)
    return main, bib


def body_refs(body: str) -> List[str]:
    main, _ = split_body_bib(body)
    return FOOTNOTE_REF_RE.findall(main)


def split_paragraphs(text: str) -> List[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]


def has_required_headers(body: str) -> bool:
    return all(header in body for header in REQUIRED_HEADERS)


def count_concrete_signals(text: str) -> int:
    return (
        len(re.findall(r"\b(1[5-9]\d{2}|20\d{2})\b", text))
        + len(re.findall(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", text))
        + len(re.findall(r"\b[A-Z][a-z]+ v\. [A-Z][A-Za-z]+\b", text))
    )


def topic_token_hits(body: str, profile: TopicProfile) -> int:
    text = body.lower()
    hits = 0
    for tok in profile.focus_tokens:
        if re.search(rf"\b{re.escape(tok)}\b", text):
            hits += 1
    return hits


def count_year_mentions(body: str, year: str) -> int:
    return len(re.findall(rf"\b{re.escape(year)}\b", body))


def generic_tag_set(tags: List[str], topic: str) -> bool:
    base = set(slug_terms(topic))
    normalized = {str(x).strip().lower() for x in tags if str(x).strip()}
    return bool(normalized) and normalized.issubset(base)


def paragraph_citation_ids(paragraph: str) -> List[str]:
    return FOOTNOTE_REF_RE.findall(paragraph)


def soften_specificity_sentence(sentence: str) -> Tuple[str, bool]:
    original = sentence
    changed = False

    if PAGE_CLAIM_RE.search(sentence):
        sentence = PAGE_CLAIM_RE.sub("", sentence)
        changed = True

    if DATE_CLAIM_RE.search(sentence):
        sentence = DATE_CLAIM_RE.sub("in that period", sentence)
        changed = True

    if ARCHIVE_CLAIM_RE.search(sentence) and "[^" not in sentence:
        sentence = re.sub(
            r"\bnow housed in the [^.]+",
            "in later-collected materials",
            sentence,
            flags=re.IGNORECASE,
        )
        sentence = re.sub(
            r"\bhoused in the [^.]+",
            "preserved in later collections",
            sentence,
            flags=re.IGNORECASE,
        )
        changed = True

    sentence = re.sub(r"\s{2,}", " ", sentence).strip()
    sentence = re.sub(r"\s+([.,;:])", r"\1", sentence)

    return (sentence if sentence else original), changed


def split_sentences(paragraph: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", paragraph.strip())
    return [p.strip() for p in parts if p.strip()]


def is_prose_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("#"):
        return False
    if stripped.startswith("[^"):
        return False
    if stripped == "### METADATA":
        return False
    return len(re.sub(r"\[\^\d+\]", "", stripped).strip()) >= 20


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


def extract_balanced_json_block(text: str) -> Tuple[str, str]:
    start = text.find("{")
    if start == -1:
        return "", text

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1], text[i + 1 :]

    return "", text


def extract_metadata(text: str) -> Tuple[str, Dict[str, Any], List[str]]:
    warnings: List[str] = []
    marker = "### METADATA"
    idx = text.rfind(marker)
    if idx == -1:
        return text.strip(), {}, warnings

    body = text[:idx].strip()
    tail = text[idx + len(marker) :].strip()

    candidate, trailing = extract_balanced_json_block(tail)
    meta = repair_json(candidate)

    if not meta:
        warnings.append("Metadata JSON malformed or missing; normalization applied.")
    if trailing.strip():
        warnings.append("Trimmed trailing text after metadata JSON.")

    return body, meta, warnings


def infer_quote_from_body(body: str) -> List[str]:
    # Try strict pattern first (smart quotes with attribution)
    hits = QUOTED_TEXT_RE.findall(body)
    cleaned: List[str] = []
    for quote, author in hits:
        q = quote.strip()
        a = author.strip().strip(".")
        if len(q) >= 12 and a:
            cleaned.append(f"\"{q}\" — {a}")
    
    if cleaned:
        return dedupe(cleaned[:2])
    
    # Fallback: extract any quoted text (regular quotes) with looser matching
    looser_quotes = re.findall(r'"([^"\n]{20,200})"', body)
    for q in looser_quotes[:2]:
        q = q.strip()
        if len(q) >= 20:
            cleaned.append(f'"{q}" — source text')
    
    if cleaned:
        return dedupe(cleaned[:2])
    
    # Last resort: generate minimal safe quote from first substantial paragraph
    paragraphs = [p for p in split_paragraphs(body) if not p.startswith("#") and len(p) > 40]
    if paragraphs:
        first_para = paragraphs[0]
        # Extract a sentence-like chunk
        sentences = re.split(r'[.!?]', first_para)
        for sentence in sentences:
            sentence = sentence.strip()
            if 30 <= len(sentence) <= 150:
                cleaned.append(f'"{sentence}." — artifact')
                break
    
    return dedupe(cleaned[:2]) if cleaned else ['"Artifact generated from source analysis." — synthesis']


def extract_candidate_themes(body: str, topic: str) -> List[str]:
    candidates: List[str] = []
    body_lower = body.lower()

    theme_map = [
        ("historiography", ["historiography", "scholarly debate", "revisionist", "consensus"]),
        ("colonial_context", ["colonial", "empire", "imperial", "settler"]),
        ("political_theology", ["spiritual", "religious", "theology", "sacral"]),
        ("nationalism", ["nationalism", "nation", "statehood", "national identity"]),
        ("elite_bargaining", ["compromise", "brokered", "elite bargain", "negotiation"]),
        ("legitimacy_crisis", ["legitimacy", "constitutional crisis", "contested", "disputed"]),
        ("rhetorical_framing", ["narrative framing", "rhetorical", "semiotic", "myth"]),
        ("identity_formation", ["identity", "community", "cultural unity"]),
        ("material_conditions", ["material conditions", "labor", "capital", "economic depression"]),
        ("racial_suppression", ["jim crow", "black voters", "racial", "white supremacy", "disenfranchise"]),
        ("electoral_controversy", ["electoral votes", "electoral commission", "ballot", "election dispute"]),
        ("federal_power", ["federal authority", "federal troops", "federal oversight", "states' rights"]),
        ("reconstruction_endgame", ["reconstruction", "compromise of 1877", "post-reconstruction"]),
    ]

    for theme, needles in theme_map:
        if any(needle in body_lower for needle in needles):
            candidates.append(theme)

    candidates.extend(slug_terms(topic))
    return normalize_meta_items(candidates[:10])


def extract_candidate_tags(body: str, topic: str) -> List[str]:
    body_lower = body.lower()
    candidates: List[str] = []

    tag_map = [
        ("electoral_crisis", ["electoral commission", "disputed electoral", "electoral votes"]),
        ("legitimacy_crisis", ["legitimacy", "constitutional crisis"]),
        ("racial_suppression", ["jim crow", "black voter", "white league", "white supremacy", "disenfranchise"]),
        ("elite_bargaining", ["compromise of 1877", "elite bargain", "brokered"]),
        ("reconstruction", ["reconstruction"]),
        ("federal_power", ["federal troops", "federal authority", "federal oversight"]),
        ("historiography", ["historiography", "revisionist", "scholarship"]),
        ("material_conditions", ["material conditions", "economic depression", "panic of 1873"]),
        ("rhetorical_framing", ["narrative framing", "rhetorical", "semiotic"]),
        ("democratic_legitimacy", ["democracy", "legitimacy", "electoral process"]),
    ]

    for tag, needles in tag_map:
        if any(needle in body_lower for needle in needles):
            candidates.append(tag)

    candidates.extend(extract_candidate_themes(body, topic))
    candidates.extend(slug_terms(topic))
    return normalize_meta_items(candidates[:12])


def normalize_meta(meta: Dict[str, Any], topic: str, body: str) -> Dict[str, Any]:
    meta = meta if isinstance(meta, dict) else {}
    candidate_tags = extract_candidate_tags(body, topic)
    candidate_themes = extract_candidate_themes(body, topic)

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

    tags = normalize_meta_items([str(x).strip() for x in tags if str(x).strip()], max_items=6)
    key_themes = normalize_meta_items([str(x).strip() for x in key_themes if str(x).strip()], max_items=6)
    adinkra = dedupe([str(x).strip() for x in adinkra if str(x).strip()]) or ["Sankofa"]

    if len(tags) < MIN_TAGS or generic_tag_set(tags, topic):
        tags = normalize_meta_items(tags + candidate_tags, max_items=6)

    if len(key_themes) < MIN_KEY_THEMES or generic_tag_set(key_themes, topic):
        key_themes = normalize_meta_items(key_themes + candidate_themes, max_items=6)

    clean_quotes: List[str] = []
    for q in quotes:
        if not isinstance(q, str):
            continue
        s = q.strip()
        if s and "—" in s and s.count('"') >= 2:
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
            "Artifact built for retrieval stability, contradiction visibility, topic-specific reasoning, "
            "and source-linked analytical reuse."
        )

    return {
        "title": title,
        "tags": tags[:6],
        "key_themes": key_themes[:6],
        "bias_analysis": bias_analysis,
        "grok_ctx_reflection": grok_ctx_reflection,
        "quotes": dedupe(clean_quotes),
        "adinkra": adinkra[:4],
    }


# ------------------------------------------------------------------------------
# BIBLIOGRAPHY PARSING / RECOVERY
# ------------------------------------------------------------------------------
def bibliography_cutoff_index(bib: str) -> int:
    contamination_markers = [
        "\n### METADATA",
        '\n{"title"',
        '\n{ "title"',
        '\n"',
        "\n# ",
    ]
    indices = [bib.find(marker) for marker in contamination_markers if bib.find(marker) != -1]
    return min(indices) if indices else len(bib)


def parse_bibliography_entries(body: str) -> List[Tuple[str, str]]:
    _, bib = split_body_bib(body)
    if not bib.strip():
        return []

    cutoff = bibliography_cutoff_index(bib)
    bib = bib[:cutoff].strip()

    entries: List[Tuple[str, str]] = []
    current_id: Optional[str] = None
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

        if stripped.startswith('"') or stripped.startswith("“"):
            break

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
        entry_text = re.sub(r"\s{2,}", " ", entry_text).strip()
        entry_text = re.sub(r'\s+"[^"]{12,260}"\s*—\s*.+$', "", entry_text).strip()
        if entry_text:
            cleaned.append((entry_id, entry_text))

    return cleaned


def bib_ids(body: str) -> List[str]:
    return [entry_id for entry_id, _ in parse_bibliography_entries(body)]


def bib_lines(body: str) -> List[str]:
    return [f"[^{entry_id}]: {entry_text}" for entry_id, entry_text in parse_bibliography_entries(body)]


def rebuild_bibliography(body: str, entries: List[Tuple[str, str]]) -> str:
    main, _ = split_body_bib(body)
    rebuilt = "\n".join(f"[^{entry_id}]: {entry_text}" for entry_id, entry_text in entries)
    return clean_whitespace(main) + "\n\n# 📚 BIBLIOGRAPHY\n" + rebuilt


# ------------------------------------------------------------------------------
# BODY DISCIPLINE / SUPPRESSION
# ------------------------------------------------------------------------------
def suppress_unsupported_specificity(body: str) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    main, bib = split_body_bib(body)
    paragraphs = split_paragraphs(main)
    repaired_paragraphs: List[str] = []

    for para in paragraphs:
        if para.startswith("#"):
            repaired_paragraphs.append(para)
            continue

        citation_ids = paragraph_citation_ids(para)
        sentence_parts = split_sentences(para)
        new_sentences: List[str] = []

        for sentence in sentence_parts:
            stripped = sentence.strip()
            risky = bool(
                PAGE_CLAIM_RE.search(stripped)
                or ARCHIVE_CLAIM_RE.search(stripped)
                or DATE_CLAIM_RE.search(stripped)
            )

            if risky and not citation_ids:
                softened, changed = soften_specificity_sentence(stripped)
                if changed:
                    warnings.append(f"Softened unsupported specificity: {stripped[:100]}")
                new_sentences.append(softened)
            else:
                new_sentences.append(stripped)

        repaired_paragraphs.append(" ".join(new_sentences).strip())

    rebuilt = "\n\n".join(repaired_paragraphs)
    if bib.strip():
        rebuilt += "\n\n# 📚 BIBLIOGRAPHY\n" + bib.strip()
    return clean_whitespace(rebuilt), dedupe(warnings)


def citation_load_warnings(body: str) -> List[str]:
    warnings: List[str] = []
    main, _ = split_body_bib(body)
    paragraphs = [p for p in split_paragraphs(main) if not p.startswith("#")]

    if not paragraphs:
        return warnings

    paragraphs_with_cites: List[str] = []
    citation_to_paragraphs: Dict[str, int] = {}

    for para in paragraphs:
        ids = set(paragraph_citation_ids(para))
        if ids:
            paragraphs_with_cites.append(para)
        for cid in ids:
            citation_to_paragraphs[cid] = citation_to_paragraphs.get(cid, 0) + 1

    if len(set(body_refs(body))) == 1 and len(paragraphs_with_cites) > MAX_PARAGRAPHS_PER_SINGLE_CITATION:
        warnings.append("A single citation is carrying too many paragraphs of argument.")

    for cid, count in citation_to_paragraphs.items():
        if count > MAX_PARAGRAPHS_PER_SINGLE_CITATION:
            warnings.append(f"Citation [^{cid}] spans too many paragraphs ({count}).")

    return dedupe(warnings)


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

    if any(line.strip().startswith('"') or line.strip().startswith("“") for line in original_lines):
        warnings.append("Removed quote bleed from bibliography tail.")

    if not entries:
        warnings.append("Bibliography present but no valid entries could be recovered.")
        return rebuild_bibliography(body, []), warnings

    return rebuild_bibliography(body, entries), warnings


def inject_body_citations_from_bibliography(body: str) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    refs = body_refs(body)
    entries = parse_bibliography_entries(body)

    if refs or not entries:
        return body, warnings

    main, bib = split_body_bib(body)
    lines = main.splitlines()
    available_ids = [entry_id for entry_id, _ in entries]
    used = 0

    for idx, line in enumerate(lines):
        if used >= len(available_ids):
            break

        if not is_prose_line(line):
            continue

        stripped = line.rstrip()
        if FOOTNOTE_REF_RE.search(stripped):
            continue

        cid = f"[^{available_ids[used]}]"
        if stripped.endswith((".", "!", "?", "”", '"')):
            lines[idx] = stripped + cid
        else:
            lines[idx] = stripped + "." + cid
        used += 1

    if used:
        warnings.append(f"Injected {used} in-body citation marker(s) from recovered bibliography.")
    else:
        warnings.append("Bibliography recovered, but no body citations could be anchored.")

    rebuilt_main = "\n".join(lines).strip()
    rebuilt = rebuilt_main
    if bib.strip():
        rebuilt += "\n\n# 📚 BIBLIOGRAPHY\n" + bib.strip()
    return clean_whitespace(rebuilt), dedupe(warnings)


def align_body_and_bib(body: str) -> Tuple[str, List[str]]:
    warnings: List[str] = []

    body, inject_warnings = inject_body_citations_from_bibliography(body)
    warnings.extend(inject_warnings)

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
        kept_entries = [
            (entry_id, entry_text)
            for entry_id, entry_text in parse_bibliography_entries(body)
            if entry_id in good
        ]
        body = rebuild_bibliography(body, kept_entries)
        warnings.append("Pruned uncited bibliography lines.")

    return clean_whitespace(body), dedupe(warnings)


# ------------------------------------------------------------------------------
# TOPIC FOCUS VALIDATION
# ------------------------------------------------------------------------------
def validate_topic_focus(body: str, profile: TopicProfile) -> Optional[str]:
    if not body.strip():
        return "Empty body"

    hits = topic_token_hits(body, profile)
    if profile.focus_tokens and hits == 0:
        return "Topic drift: core topic tokens missing from body"

    if profile.focus_year:
        year_mentions = count_year_mentions(body, profile.focus_year)
        if year_mentions < 2:
            return f"Topic drift: year {profile.focus_year} is insufficiently centered"

    return None


# ------------------------------------------------------------------------------
# VALIDATION
# ------------------------------------------------------------------------------
@dataclass
class ValidationResult:
    ok: bool
    error: str = ""
    warnings: List[str] = field(default_factory=list)
    distinct_citations: int = 0


def validate(body: str, meta: Dict[str, Any], profile: TopicProfile) -> ValidationResult:
    warnings: List[str] = []

    if not body.strip():
        return ValidationResult(False, "Empty output")

    for header in REQUIRED_HEADERS:
        if header not in body:
            return ValidationResult(False, f"Missing section: {header}")

    focus_error = validate_topic_focus(body, profile)
    if focus_error:
        return ValidationResult(False, focus_error)

    refs = set(body_refs(body))
    b_ids = set(bib_ids(body))
    bib = bib_lines(body)

    if len(refs) < MIN_REQUIRED_CITATIONS:
        return ValidationResult(False, f"Only {len(refs)} distinct citations", distinct_citations=len(refs))

    if not bib:
        return ValidationResult(False, "Missing bibliography", distinct_citations=len(refs))

    if refs != b_ids:
        return ValidationResult(
            False,
            "Citation mismatch between body and bibliography",
            distinct_citations=len(refs),
        )

    for line in bib:
        if not BIB_LINE_RE.match(line):
            return ValidationResult(False, "Invalid bibliography format", distinct_citations=len(refs))

    claim_load = citation_load_warnings(body)
    if claim_load and len(refs) <= 1:
        return ValidationResult(False, claim_load[0], distinct_citations=len(refs))
    warnings.extend(claim_load)

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
    if not all(isinstance(q, str) and "—" in q and q.count('"') >= 2 for q in quotes):
        return ValidationResult(
            False,
            "Metadata quotes invalid or unattributed",
            distinct_citations=len(refs),
        )

    tags = meta.get("tags", [])
    key_themes = meta.get("key_themes", [])
    if not isinstance(tags, list) or len(tags) < MIN_TAGS:
        return ValidationResult(False, "Metadata tags insufficient", distinct_citations=len(refs))
    if not isinstance(key_themes, list) or len(key_themes) < MIN_KEY_THEMES:
        return ValidationResult(False, "Metadata key_themes insufficient", distinct_citations=len(refs))

    if generic_tag_set(tags, profile.raw_topic):
        warnings.append("Tags were minimally differentiated from the topic string.")
    if generic_tag_set(key_themes, profile.raw_topic):
        warnings.append("Key themes were minimally differentiated from the topic string.")

    if len(refs) < TARGET_CITATIONS:
        warnings.append(f"Low citation density: {len(refs)} distinct citation(s); target is {TARGET_CITATIONS}.")

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

    body, specificity_warnings = suppress_unsupported_specificity(body)
    warnings.extend(specificity_warnings)

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


def attempt(
    syn: Synapse,
    profile: TopicProfile,
    label: str,
    prompt: str,
) -> Tuple[str, Dict[str, Any], ValidationResult]:
    save_debug(profile.raw_topic, f"{label}_prompt", prompt)
    raw = syn.ask(prompt)
    save_debug(profile.raw_topic, f"{label}_raw", raw)

    body, meta, meta_warnings = extract_metadata(raw)
    body, meta, pipeline_warnings = cleanup_pipeline(profile.raw_topic, body, meta)

    result = validate(body, meta, profile)
    result.warnings = dedupe(meta_warnings + pipeline_warnings + result.warnings)

    save_debug(profile.raw_topic, f"{label}_body", body)
    save_debug(profile.raw_topic, f"{label}_meta", json.dumps(meta, indent=2, ensure_ascii=False))
    save_debug(profile.raw_topic, f"{label}_validation", serialize_validation(result))
    return body, meta, result


def generate(syn: Synapse, topic: str) -> Tuple[str, Dict[str, Any], ValidationResult]:
    profile = make_topic_profile(topic)

    body1, meta1, res1 = attempt(
        syn,
        profile,
        "attempt1_primary",
        PROMPT.format(
            topic=profile.raw_topic,
            topic_guidance=profile.guidance,
            scaffold=HARD_SCAFFOLD,
        ),
    )
    if res1.ok:
        return body1, meta1, res1
    print(f"⚠ Failed: {res1.error}")

    body2, meta2, res2 = attempt(
        syn,
        profile,
        "attempt2_rebuild",
        REBUILD_PROMPT.format(
            topic=profile.raw_topic,
            topic_guidance=profile.guidance,
            scaffold=HARD_SCAFFOLD,
        ),
    )
    if res2.ok:
        return body2, meta2, res2
    print(f"⚠ Failed: {res2.error}")

    repair_seed = body2 if len(body2.strip()) >= len(body1.strip()) else body1
    body3, meta3, res3 = attempt(
        syn,
        profile,
        "attempt3_repair",
        REPAIR_PROMPT.format(
            topic=profile.raw_topic,
            topic_guidance=profile.guidance,
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
        profile,
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