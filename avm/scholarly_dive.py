# ==============================================================================
# ✶⌁✶ scholarly_dive.py — THE SYNTHESIS ENGINE v1.8.2 [HARDENED+CRITICAL]
# ==============================================================================
# ROLE: Deep synthesis client with strict post-LLM validation + safe emission gate.
# GOAL: Stop fabricated bibliography + enforce metadata shape before VS-ENC emits.
# CHANGE (v1.8.2): Adds a real “release valve” by locally sanitizing bibliography
#                  (suspicious/unverified -> "uncertain") instead of hard-failing.
# DEFAULT: ALWAYS historiography-first (no operator prompt).
# COMPLIANCE: WC-DIR-2026-01-11-ENV-HARDENING / SENTINEL-V2.0.0-ALIGN
# ==============================================================================

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
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
# Strictness knobs (operator override via env vars)
# ------------------------------------------------------------------------------
# Strict modes still exist, but v1.8.2 adds a "release valve" that can repair
# bibliography locally instead of failing emission.
STRICT_BIBLIO = os.getenv("SCHOLARLY_STRICT_BIBLIO", "1") == "1"
STRICT_META = os.getenv("SCHOLARLY_STRICT_META", "1") == "1"
RETRY_ON_FAIL = int(os.getenv("SCHOLARLY_RETRY_ON_FAIL", "1"))

# Release valve behavior:
# - When STRICT_BIBLIO is on, we still *detect* suspicious biblio,
#   but we try to sanitize it automatically (replace with "uncertain")
#   before we refuse emission.
BIBLIO_AUTO_SANITIZE = os.getenv("SCHOLARLY_BIBLIO_AUTO_SANITIZE", "1") == "1"

# Length control (helps avoid "too long" artifacts)
MAX_WORDS = int(os.getenv("SCHOLARLY_MAX_WORDS", "1100"))  # prompt target
MAX_NEW_TOKENS = int(os.getenv("SCHOLARLY_MAX_NEW_TOKENS", "2600"))  # model cap

# ------------------------------------------------------------------------------
# PROMPT LAW (Always historiography-first)
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
"""

REPAIR_TEMPLATE = """\
ROLE: You are the Algorithmic Griot.
TASK: Repair the previous output to satisfy ALL constraints below.

CONSTRAINTS (NON-NEGOTIABLE):
1) Keep the same section headers as required.
2) Remove or rewrite any bibliography entries that you are not confident are real. Prefer marking "uncertain".
3) Ensure footnotes used in body appear in bibliography.
4) Provide '### METADATA' JSON at absolute end using ONLY allowed keys and correct value shapes.
5) quotes: each quote must include attribution inside the same quoted string ("... — Attribution").
6) adinkra must be a JSON list of strings (not a single string).
7) Do NOT include tables.
8) Be concise.

Return ONLY the corrected report (no commentary).

PREVIOUS OUTPUT (for repair):
{bad_output}
"""

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
_FOOTNOTE_REF_RE = re.compile(r"\[\^(\d+)\]")
_BIB_LINE_RE = re.compile(r"^\[\^(\d+)\]:(.*)$")


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


def _looks_like_fabricated_biblio_line(line: str) -> bool:
    """
    Heuristic-only (no web). Flags common hallucination patterns.
    NOTE: This will cause false positives; use auto-sanitize to avoid hard fails.
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
    ]
    has_year = bool(re.search(r"\b(19|20)\d{2}\b", line))
    return any(m in line_lc for m in suspicious_markers) and has_year


def _split_biblio(body: str) -> Tuple[str, str]:
    if "# 📚 BIBLIOGRAPHY" not in body:
        return body, ""
    main, tail = body.split("# 📚 BIBLIOGRAPHY", 1)
    return main.rstrip(), tail.strip()


def _parse_biblio_lines(biblio_text: str) -> Tuple[Dict[str, str], List[str]]:
    """
    Returns:
      - id_to_line: { "1": "[^1]: ...", ... } (keeps first occurrence)
      - extras: non-footnote lines (kept verbatim unless strict sanitization removes them)
    """
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
        # If duplicated ids appear, we silently drop later duplicates.

    return id_to_line, extras


def _sanitize_bibliography(body: str) -> Tuple[str, List[str]]:
    """
    Local “release valve”:
    - ensures every in-body footnote id exists in bibliography
    - replaces suspicious/unverified bibliography lines with "[^N]: uncertain"
    - removes any 'UNVERIFIED' text lines
    """
    notes: List[str] = []
    main, biblio = _split_biblio(body)

    if not biblio:
        return body, notes

    refs = sorted(set(_FOOTNOTE_REF_RE.findall(main)), key=lambda x: int(x))
    id_to_line, extras = _parse_biblio_lines(biblio)

    # Drop explicit "unverified" commentary lines in strict mode
    if STRICT_BIBLIO and extras:
        kept_extras: List[str] = []
        for ln in extras:
            if "unverified" in ln.lower():
                notes.append(f"Removed bibliography commentary line: {ln}")
                continue
            kept_extras.append(ln)
        extras = kept_extras

    # Ensure all referenced ids exist and are safe
    for fid in refs:
        current = id_to_line.get(fid)
        if current is None:
            id_to_line[fid] = f"[^{fid}]: uncertain"
            notes.append(f"Added missing bibliography entry as uncertain: [^{fid}]")
            continue

        if "unverified" in current.lower():
            id_to_line[fid] = f"[^{fid}]: uncertain"
            notes.append(f"Replaced UNVERIFIED bibliography entry with uncertain: [^{fid}]")
            continue

        if STRICT_BIBLIO and _looks_like_fabricated_biblio_line(current):
            id_to_line[fid] = f"[^{fid}]: uncertain"
            notes.append(f"Sanitized suspicious bibliography entry to uncertain: [^{fid}]")

    # Rebuild bibliography deterministically in numeric order (refs first)
    rebuilt: List[str] = []
    for fid in refs:
        rebuilt.append(id_to_line[fid])

    # Optionally keep additional (unreferenced) bibliography entries if present
    unref = sorted((set(id_to_line.keys()) - set(refs)), key=lambda x: int(x))
    for fid in unref:
        # If strict, also sanitize these if suspicious
        ln = id_to_line[fid]
        if STRICT_BIBLIO and ("unverified" in ln.lower() or _looks_like_fabricated_biblio_line(ln)):
            ln = f"[^{fid}]: uncertain"
            notes.append(f"Sanitized unreferenced suspicious entry to uncertain: [^{fid}]")
        rebuilt.append(ln)

    # Keep extras at the very top if any remain (rare)
    final_biblio_lines = []
    if extras:
        final_biblio_lines.extend(extras)
    final_biblio_lines.extend(rebuilt)

    new_body = f"{main}\n\n# 📚 BIBLIOGRAPHY\n" + "\n".join(final_biblio_lines).rstrip() + "\n"
    return new_body, notes


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

    if STRICT_BIBLIO:
        for ln in lines:
            if "unverified" in ln.lower():
                errors.append(f"Unverified bibliography entry not allowed in strict mode: {ln}")
        for ln in lines:
            if ln.startswith("[^") and _looks_like_fabricated_biblio_line(ln):
                errors.append(f"Suspicious bibliography entry (possible fabrication): {ln}")

    return (len(errors) == 0), errors


def _validate_metadata(meta: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    errors: List[str] = []
    allowed = {
        "title",
        "tags",
        "key_themes",
        "bias_analysis",
        "grok_ctx_reflection",
        "quotes",
        "adinkra",
    }
    meta = {k: v for k, v in (meta or {}).items() if k in allowed}
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


def _strip_trailing_garbage(body: str) -> str:
    return body.rstrip() + "\n"


# ------------------------------------------------------------------------------
# Core Classes
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
# Main Workflow
# ------------------------------------------------------------------------------
def run_synthesis() -> None:
    version = "v1.8.2"
    print(f"✶⌁✶ SCHOLARLY DIVE {version} [HARDENED+CRITICAL] ONLINE")
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

            # 1) Validate
            ok_bib, bib_errors = _validate_bibliography(body)
            ok_meta, meta_errors, meta_norm = _validate_metadata(meta)
            hard_fail = (STRICT_BIBLIO and not ok_bib) or (STRICT_META and not ok_meta)

            # 2) If bibliography fails and auto-sanitize is enabled, try local repair first
            if hard_fail and STRICT_BIBLIO and not ok_bib and BIBLIO_AUTO_SANITIZE:
                body2, notes = _sanitize_bibliography(body)
                if notes:
                    print("⚠️  Bibliography sanitized locally (release valve engaged).")
                body = body2

                # Re-validate after local repair
                ok_bib, bib_errors = _validate_bibliography(body)
                hard_fail = (STRICT_BIBLIO and not ok_bib) or (STRICT_META and not ok_meta)

            if not hard_fail:
                meta = meta_norm
                break

            # 3) If still failing, optional model repair pass (bounded)
            if attempts > (RETRY_ON_FAIL + 1):
                print("❌ REFUSING EMISSION: validation failed.")
                if bib_errors:
                    print("— Bibliography issues:")
                    for err in bib_errors:
                        print(f"  • {err}")
                if meta_errors:
                    print("— Metadata issues:")
                    for err in meta_errors:
                        print(f"  • {err}")
                sys.exit(2)

            print("⚠️  Validation failed; attempting repair pass...")
            repair_prompt = _build_repair_prompt(
                body + ("\n\n### METADATA\n" + json.dumps(meta, ensure_ascii=False))
            )
            raw2 = synapse.ask(repair_prompt)
            body, meta = _extract_metadata(raw2)

            if not body.strip():
                raise ValueError("Repair pass returned empty body content; refusing emission.")

        body = _strip_trailing_garbage(body)

        allowed_meta_keys = {
            "title",
            "tags",
            "key_themes",
            "bias_analysis",
            "grok_ctx_reflection",
            "quotes",
            "adinkra",
        }
        meta = {k: v for k, v in (meta or {}).items() if k in allowed_meta_keys}

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