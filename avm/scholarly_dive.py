# ==============================================================================
# ✶⌁✶ scholarly_dive.py — THE SYNTHESIS ENGINE v1.8.0 [HARDENED+CRITICAL]
# ==============================================================================
# ROLE: Deep synthesis client with strict post-LLM validation + safe emission gate.
# GOAL: Stop fabricated bibliography + enforce metadata shape before VS-ENC emits.
# COMPLIANCE: WC-DIR-2026-01-11-ENV-HARDENING / SENTINEL-V2.0.0-ALIGN
# ==============================================================================

import os
import sys
import re
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional
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

# Strictness knobs (operator override via env vars)
STRICT_BIBLIO = os.getenv("SCHOLARLY_STRICT_BIBLIO", "1") == "1"   # block invented bibliography
STRICT_META = os.getenv("SCHOLARLY_STRICT_META", "1") == "1"       # block malformed metadata shapes
RETRY_ON_FAIL = int(os.getenv("SCHOLARLY_RETRY_ON_FAIL", "1"))     # number of auto-repair attempts


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

EVIDENCE / CITATION LAW (NON-NEGOTIABLE):
- You may ONLY include a bibliography entry if you are confident it exists as a real, citable source.
- If you are not confident a source exists, write "uncertain" and DO NOT fabricate titles, authors, years, journals, or court case numbers.
- Prefer fewer, higher-confidence sources over many.
- If you cannot support claims with real sources, keep claims general and label uncertainty.

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
- In bibliography, format as: [^1]: Author. *Title* (Publisher, Year). OR [^1]: Institution. *Report Title* (Year).
- If uncertain, say "uncertain" rather than inventing details.

METADATA:
- Provide JSON labeled '### METADATA' at the absolute end.
- JSON keys allowed: title, tags, key_themes, bias_analysis, grok_ctx_reflection, quotes, adinkra.
- Metadata values MUST follow these shapes:
  - title: string
  - tags: list[string]
  - key_themes: list[string]
  - bias_analysis: string
  - grok_ctx_reflection: string
  - quotes: list[string]  (each item must include attribution, e.g. "Quote text — Name/Source")
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

Return ONLY the corrected report (no commentary).

PREVIOUS OUTPUT (for repair):
{bad_output}
"""


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
    return s.replace("{", "{{").replace("}", "}}")


def _build_prompt(topic: str) -> str:
    safe_topic = _escape_braces(topic)
    return PROMPT_TEMPLATE.format(topic=safe_topic)


def _build_repair_prompt(bad_output: str) -> str:
    safe = _escape_braces(bad_output)
    return REPAIR_TEMPLATE.format(bad_output=safe)


def _ensure_list_of_str(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, list) and all(isinstance(x, str) for x in value):
        return value
    if isinstance(value, str):
        # allow single string -> list[str]
        return [value]
    return None


def _ensure_str(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def _looks_like_fabricated_biblio_line(line: str) -> bool:
    """
    Heuristic only (no web): flags common hallucination patterns.
    - fake-sounding court judgment numbers, generic "Policy Brief No.", "Working Paper #"
    - overly specific institutional doc numbers without context
    """
    l = line.lower()
    suspicious_markers = [
        "judgment no.",
        "working paper",
        "policy brief no.",
        "annual report",
        "update",
        "transcript #",
        "case",
        "no.",
    ]
    # If it contains a suspicious marker AND also a year-like token, treat as suspect.
    has_year = bool(re.search(r"\b(19|20)\d{2}\b", line))
    return any(m in l for m in suspicious_markers) and has_year


def _validate_bibliography(body: str) -> Tuple[bool, List[str]]:
    """
    Enforces:
    - bibliography section exists
    - no obviously fabricated lines (heuristic)
    - footnotes referenced exist in bibliography lines
    """
    errors: List[str] = []
    if "# 📚 BIBLIOGRAPHY" not in body:
        errors.append("Missing '# 📚 BIBLIOGRAPHY' section.")
        return False, errors

    biblio = body.split("# 📚 BIBLIOGRAPHY", 1)[1].strip()
    lines = [ln.strip() for ln in biblio.splitlines() if ln.strip()]

    # Collect footnote ids referenced in body (before bibliography)
    main = body.split("# 📚 BIBLIOGRAPHY", 1)[0]
    refs = set(re.findall(r"\[\^(\d+)\]", main))
    bib_ids = set(re.findall(r"^\[\^(\d+)\]:", "\n".join(lines), flags=re.MULTILINE))

    # Any referenced ids missing in bibliography?
    missing = sorted(refs - bib_ids)
    if missing:
        errors.append(f"Footnotes referenced in body but missing from bibliography: {', '.join(missing)}")

    # Flag suspicious bibliography lines
    if STRICT_BIBLIO:
        for ln in lines:
            if ln.startswith("[^") and _looks_like_fabricated_biblio_line(ln):
                errors.append(f"Suspicious bibliography entry (possible fabrication): {ln}")

    return (len(errors) == 0), errors


def _validate_metadata(meta: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Enforces allowed keys + value shapes.
    Coerces where safe (e.g., string -> [string] for list fields).
    """
    errors: List[str] = []
    allowed = {"title", "tags", "key_themes", "bias_analysis", "grok_ctx_reflection", "quotes", "adinkra"}
    meta = {k: v for k, v in (meta or {}).items() if k in allowed}

    normalized: Dict[str, Any] = {}

    # title
    title = _ensure_str(meta.get("title"))
    if title:
        normalized["title"] = title

    # tags / key_themes / adinkra
    for k in ("tags", "key_themes", "adinkra"):
        lv = _ensure_list_of_str(meta.get(k))
        if lv is not None:
            normalized[k] = lv
        elif meta.get(k) is not None:
            errors.append(f"Metadata '{k}' must be list[string].")

    # bias_analysis / grok_ctx_reflection
    for k in ("bias_analysis", "grok_ctx_reflection"):
        sv = _ensure_str(meta.get(k))
        if sv is not None:
            normalized[k] = sv
        elif meta.get(k) is not None:
            errors.append(f"Metadata '{k}' must be string.")

    # quotes
    qv = _ensure_list_of_str(meta.get("quotes"))
    if qv is not None:
        # enforce attribution presence (simple heuristic: "—" or "-" or "(")
        bad = [q for q in qv if ("—" not in q and " - " not in q and "(" not in q)]
        if bad:
            errors.append("Each quote must include attribution inside the same string (e.g. '... — Source').")
        normalized["quotes"] = qv
    elif meta.get("quotes") is not None:
        errors.append("Metadata 'quotes' must be list[string].")

    if STRICT_META and errors:
        return False, errors, normalized
    return True, errors, normalized


def _strip_trailing_garbage(body: str) -> str:
    """
    Safety: if model leaks after bibliography or metadata, keep as-is but trim
    extreme trailing whitespace.
    """
    return body.rstrip() + "\n"


# ------------------------------------------------------------------------------
# Core Classes
# ------------------------------------------------------------------------------
@dataclass
class ScholarlySynapse:
    agent_name: str = DEFAULT_AGENT

    def __post_init__(self):
        self.client = WatsonXClient()
        self.client.set_agent(self.agent_name)

    def ask(self, prompt: str, max_new_tokens: int = 3500) -> str:
        return self.client.ask(
            prompt,
            max_new_tokens=max_new_tokens,
            repetition_penalty=1.1,
        )


class StubAgent:
    def run(self, text: str):
        return text


# ------------------------------------------------------------------------------
# Main Workflow
# ------------------------------------------------------------------------------
def run_synthesis() -> None:
    version = "v1.8.0"
    print(f"✶⌁✶ SCHOLARLY DIVE {version} [HARDENED+CRITICAL] ONLINE")

    try:
        topic = _get_topic()

        use_strict_prompt = _prompt_user_yes_no(
            "Use historiography-first (anti-hagiography) prompt?", default=True
        )

        prompt = _build_prompt(topic) if use_strict_prompt else f"""
ROLE: You are the Algorithmic Griot.
TASK: Provide a deep scholarly synthesis on: {topic}

NON-NEGOTIABLE:
- Historiography > hagiography.
- Separate claims from outcomes in practice.
- If uncertain, say "uncertain" rather than inventing details.
- You may ONLY include bibliography entries you are confident are real.

STRUCTURE:
# Abstract
# Historical Analysis [^1]
# Semiotic Analysis
# 📚 BIBLIOGRAPHY

CITATIONS:
- Use Markdown footnotes [^1] in the body.
- In bibliography: [^1]: Author. *Title* (Publisher, Year). OR "uncertain".

METADATA:
- Provide JSON labeled '### METADATA' at the absolute end.
""".strip()

        synapse = ScholarlySynapse(agent_name=DEFAULT_AGENT)
        orch = VSEncOrchestrator({"SCHOLARLY_STUB": StubAgent()})

        print(f"✶ Synthesizing deep artifact for '{topic}' (agent={synapse.agent_name})...")

        raw = synapse.ask(prompt)
        body, meta = _extract_metadata(raw)

        if not body.strip():
            raise ValueError("Model returned empty body content; refusing emission.")

        # Validation pass (with optional auto-repair)
        attempts = 0
        while True:
            attempts += 1
            ok_bib, bib_errors = _validate_bibliography(body)
            ok_meta, meta_errors, meta_norm = _validate_metadata(meta)

            # If strict, we block on errors
            hard_fail = (STRICT_BIBLIO and not ok_bib) or (STRICT_META and not ok_meta)

            if not hard_fail:
                meta = meta_norm
                break

            if attempts > (RETRY_ON_FAIL + 1):
                print("❌ REFUSING EMISSION: validation failed.")
                if bib_errors:
                    print("— Bibliography issues:")
                    for e in bib_errors:
                        print(f"  • {e}")
                if meta_errors:
                    print("— Metadata issues:")
                    for e in meta_errors:
                        print(f"  • {e}")
                sys.exit(2)

            # Attempt repair via model
            print("⚠️  Validation failed; attempting repair pass...")
            repair_prompt = _build_repair_prompt(body + ("\n\n### METADATA\n" + json.dumps(meta, ensure_ascii=False)))
            raw2 = synapse.ask(repair_prompt, max_new_tokens=3500)
            body, meta = _extract_metadata(raw2)
            if not body.strip():
                raise ValueError("Repair pass returned empty body content; refusing emission.")

        body = _strip_trailing_garbage(body)

        # Enforce allowed metadata keys (and normalized shapes already)
        allowed_meta_keys = {"title", "tags", "key_themes", "bias_analysis", "grok_ctx_reflection", "quotes", "adinkra"}
        meta = {k: v for k, v in (meta or {}).items() if k in allowed_meta_keys}

        # VS-ENC emission (metadata merged + canonical frontmatter handled by vs_enc.py)
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
    except Exception as e:
        print(f"❌ ERROR: {e}")


if __name__ == "__main__":
    run_synthesis()