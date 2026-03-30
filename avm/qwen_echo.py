# ==============================================================================
# ✶⌁✶ qwen_echo.py — THE CONSOLIDATED ECHO ENGINE v4.3.0 [AUDITED + HARDENED]
# ==============================================================================
# ROLE: Flagship refinery client via VS-ENC v1.0.0.
# COMPLIANCE: WC-DIR-2026-01-11-ENV-HARDENING / SENTINEL-V2.0.0-ALIGN
# PURPOSE:
#   - Apply a selected Anacostia summary/refinery protocol to source text
#   - Emit structured artifacts through VS-ENC
#   - Preserve debug receipts for auditability
# ==============================================================================
#
# HARDENING NOTES:
#   1. Added debug logging for source length, protocol extraction, compiled prompt,
#      and raw model output.
#   2. Strengthened prompt to resist generic, topic-only summaries.
#   3. Added basic specificity gate to catch mushy emissions.
#   4. Added optional UBW refinement pass when first-pass output looks generic.
#   5. Improved input sanitation and validation.
#   6. Added clearer failure messages and receipt preservation.
# ==============================================================================

import os
import sys
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Tuple, Optional

from watsonx_client import WatsonXClient
from vs_enc import VSEncOrchestrator

# ------------------------------------------------------------------------------
# FAIL-FAST ENVIRONMENT GUARD
# ------------------------------------------------------------------------------
if not os.getenv("WATSONX_PROJECT_ID"):
    print("❌ ERROR: WATSONX_PROJECT_ID not found in environment.")
    sys.exit(1)

# ------------------------------------------------------------------------------
# STATIC PATHS / GLOBALS
# ------------------------------------------------------------------------------
VAULT_ROOT = Path("C:/Users/digitalscorpyun/sankofa_temple/Anacostia")
ARTIFACT_ROOT = "war_council/_artifacts/qwen_echo"
STYLE_GUIDE_PATH = (
    VAULT_ROOT / "war_council/documentation/writing_protocols/summary_styles_guide.md"
)
DEBUG_ROOT = VAULT_ROOT / ARTIFACT_ROOT / "_debug"

PST = timezone(timedelta(hours=-8))
GENERIC_MARKERS = [
    "systemic racism",
    "despite progress",
    "ongoing struggles",
    "social justice movements",
    "more equitable society",
    "historical trauma",
    "calls for a comprehensive approach",
    "the need for policy reforms",
    "persistent challenges",
    "root causes of inequality",
]
STYLE_ALIASES = {
    "ubw": "UBW",
    "sankofacut": "SankofaCut",
    "abolition systems cut": "Abolition Systems Cut",
    "scorpyunstyle": "ScorpyunStyle",
    "griotbox": "GriotBox",
    "intelbrief": "IntelBrief",
    "carrscroll": "CarrScroll",
    "coderitual": "CodeRitual",
    "warcouncilprotocol": "WarCouncilProtocol",
}


# ------------------------------------------------------------------------------
# UTILITY HELPERS
# ------------------------------------------------------------------------------
def now_pst() -> datetime:
    return datetime.now(PST)


def ensure_debug_root() -> None:
    DEBUG_ROOT.mkdir(parents=True, exist_ok=True)


def sanitize_input_path(raw: str) -> Path:
    """
    Sanitize user-pasted input for source file paths.
    Removes wrapping quotes and surrounding whitespace.
    """
    cleaned = raw.strip().strip('"').strip("'").strip()
    return Path(cleaned)


def truncate_for_preview(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[TRUNCATED FOR PREVIEW]..."


def save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "untitled"


def resolve_style_name(style_name: str, available: Dict[str, str]) -> Optional[str]:
    """
    Resolve style name robustly against extracted style guide names.
    """
    if style_name in available:
        return style_name

    lowered = style_name.strip().lower()
    if lowered in STYLE_ALIASES:
        canonical = STYLE_ALIASES[lowered]
        if canonical in available:
            return canonical

    for candidate in available.keys():
        if candidate.strip().lower() == lowered:
            return candidate

    return None


def classify_research_title(title: str) -> bool:
    return any(k in title.upper() for k in ["ICWC-", "CARR-", "WALKER-", "GWW-"])


def detect_source_profile(text: str) -> str:
    """
    Lightweight source profile used to make prompt more source-aware.
    """
    word_count = len(text.split())

    signals = []
    if word_count > 6000:
        signals.append("longform")
    elif word_count > 2500:
        signals.append("midform")
    else:
        signals.append("shortform")

    if re.search(r"\b(I\.|II\.|III\.|IV\.|V\.|VI\.|VII\.|VIII\.)\b", text):
        signals.append("sectioned")

    if len(re.findall(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", text)) > 15:
        signals.append("named_entities_dense")

    if any(token in text for token in ["FHA", "HR 40", "Supreme Court", "Congress"]):
        signals.append("policy_dense")

    return ", ".join(signals)


def count_named_signals(text: str) -> int:
    """
    Very rough heuristic for specific named content.
    """
    patterns = [
        r"\b[A-Z][a-z]+ [A-Z][a-z]+\b",  # two-word proper names
        r"\b[A-Z]{2,}\b",                # acronyms like FHA, FBI, DHS
        r"\b\d{4}\b",                    # years
    ]
    total = 0
    for pat in patterns:
        total += len(re.findall(pat, text))
    return total


def generic_score(text: str) -> int:
    lowered = text.lower()
    return sum(1 for marker in GENERIC_MARKERS if marker in lowered)


def fails_specificity_gate(text: str, style_name: str) -> Tuple[bool, str]:
    """
    Coarse quality gate.
    Goal: catch ultra-generic emissions before canonization.
    """
    if not text or len(text.strip()) < 300:
        return True, "Output too short to qualify as a valid refinery emission."

    score = generic_score(text)
    named_signals = count_named_signals(text)

    # UBW is the style where evidence/mechanism drift hurts most.
    if style_name == "UBW":
        if score >= 4 and named_signals < 12:
            return True, (
                "UBW emission appears overly generic: too many generic markers and "
                "insufficient named examples/mechanisms."
            )

    return False, ""


# ------------------------------------------------------------------------------
# STYLE EXTRACTION
# ------------------------------------------------------------------------------
def extract_styles_from_guide(content: str) -> Dict[str, str]:
    """
    Extract style blocks from summary_styles_guide.md.

    This implementation is more forgiving than the original regex-only approach.
    It scans for numbered bold headings and captures until the next numbered bold
    heading. It expects lines like:
        1. **SankofaCut**
        3. **UBW — ...**
    """
    lines = content.splitlines()
    header_re = re.compile(r"^\s*#.*?\d+\.\s+\*\*(.+?)\*\*\s*$")

    headers = []
    for idx, line in enumerate(lines):
        match = header_re.match(line)
        if match:
            raw_name = match.group(1).strip()
            clean_name = raw_name.split("—")[0].strip()
            clean_name = clean_name.split("(")[0].strip()
            headers.append((idx, clean_name))

    styles: Dict[str, str] = {}
    if not headers:
        return styles

    for i, (start_idx, style_name) in enumerate(headers):
        end_idx = headers[i + 1][0] if i + 1 < len(headers) else len(lines)
        block = "\n".join(lines[start_idx + 1:end_idx]).strip()
        styles[style_name] = block

    return styles


def get_available_styles() -> Dict[str, str]:
    if not STYLE_GUIDE_PATH.exists():
        raise FileNotFoundError(f"Style Guide missing: {STYLE_GUIDE_PATH}")

    with open(STYLE_GUIDE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    styles = extract_styles_from_guide(content)
    if not styles:
        raise ValueError(
            "No styles could be extracted from summary_styles_guide.md. "
            "Check guide formatting or extraction logic."
        )

    return styles


# ------------------------------------------------------------------------------
# REFINERY AGENTS
# ------------------------------------------------------------------------------
class EchoSynapse:
    def __init__(self, style_name: str, protocol_text: str, debug_session_dir: Path):
        self.client = WatsonXClient()
        self.client.set_agent("QWEN-ECHO")
        self.style_name = style_name
        self.protocol_text = protocol_text
        self.debug_session_dir = debug_session_dir

    def build_prompt(self, data: str) -> str:
        profile = detect_source_profile(data)

        prompt = (
            f"INSTRUCTION: Apply the '{self.style_name}' protocol to the source text below.\n\n"
            f"PROTOCOL_RULES:\n{self.protocol_text}\n\n"
            "NON-NEGOTIABLE REQUIREMENTS:\n"
            "- Analyze the source's actual argument, not just its general topic.\n"
            "- Use specific names, events, institutions, policies, or mechanisms from the source whenever available.\n"
            "- Do not produce a generic historical overview.\n"
            "- Preserve causal logic, chronology, and material specificity.\n"
            "- If the source makes a concrete case, reflect that case directly.\n"
            "- Avoid vague summary language unless the source itself is vague.\n"
            "- Do NOT return the raw transcript.\n"
            "- Do NOT echo the input data.\n"
            f"- Return only the analysis defined by the {self.style_name} standard.\n\n"
            f"SOURCE_PROFILE: {profile}\n\n"
            f"SOURCE_TEXT:\n{data}"
        )
        return prompt

    def ask(self, data: str, max_new_tokens: int = 3000) -> str:
        compiled_prompt = self.build_prompt(data)
        save_text(self.debug_session_dir / "compiled_prompt.txt", compiled_prompt)
        return self.client.ask(compiled_prompt, max_new_tokens=max_new_tokens)

    def refine_ubw(self, source_text: str, first_pass: str) -> str:
        """
        Second-pass repair for weak UBW emissions.
        """
        prompt = (
            "You are refining a UBW emission that is too generic.\n\n"
            "TASK:\n"
            "- Rewrite the analysis so it is grounded in the source's actual argument.\n"
            "- Increase specificity.\n"
            "- Add concrete names, policies, institutions, events, and mechanisms from the source.\n"
            "- Preserve UBW structure: Origins → Modifications → Current State.\n"
            "- Do not drift into a generic overview.\n"
            "- Do not add made-up details.\n"
            "- Return only the refined UBW analysis.\n\n"
            f"UBW_PROTOCOL_RULES:\n{self.protocol_text}\n\n"
            f"ORIGINAL_SOURCE_TEXT:\n{source_text}\n\n"
            f"WEAK_FIRST_PASS:\n{first_pass}"
        )
        save_text(self.debug_session_dir / "ubw_refinement_prompt.txt", prompt)
        return self.client.ask(prompt, max_new_tokens=2500)


class StubAgent:
    def run(self, text: str):
        return text


# ------------------------------------------------------------------------------
# MAIN REFINERY FLOW
# ------------------------------------------------------------------------------
def build_debug_session_dir(style_name: str, title: str) -> Path:
    stamp = now_pst().strftime("%Y%m%d_%H%M%S")
    style_slug = slugify(style_name)
    title_slug = slugify(title)
    session_dir = DEBUG_ROOT / f"{stamp}__{style_slug}__{title_slug}"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def write_debug_receipts(
    debug_session_dir: Path,
    style_name: str,
    protocol_text: str,
    source_path: Path,
    raw_data: str,
) -> None:
    metadata = (
        f"timestamp_pst: {now_pst().isoformat()}\n"
        f"style_name: {style_name}\n"
        f"source_path: {source_path}\n"
        f"source_exists: {source_path.exists()}\n"
        f"source_chars: {len(raw_data)}\n"
        f"source_words: {len(raw_data.split())}\n"
        f"protocol_chars: {len(protocol_text)}\n"
        f"protocol_lines: {len(protocol_text.splitlines())}\n"
        f"source_profile: {detect_source_profile(raw_data)}\n"
    )
    save_text(debug_session_dir / "debug_metadata.txt", metadata)
    save_text(debug_session_dir / "extracted_protocol.txt", protocol_text)
    save_text(debug_session_dir / "source_head.txt", truncate_for_preview(raw_data[:4000], 4000))
    save_text(debug_session_dir / "source_tail.txt", truncate_for_preview(raw_data[-4000:], 4000))


def prompt_for_protocol_choice(style_names: list[str]) -> str:
    while True:
        raw = input("\nSelect Protocol: ").strip()
        if not raw:
            print("⚠️ Please select a protocol.")
            continue

        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(style_names):
                return style_names[idx - 1]
            print("⚠️ Invalid numeric selection.")
            continue

        lowered = raw.lower()
        for candidate in style_names:
            if candidate.lower() == lowered:
                return candidate

        print("⚠️ Protocol not recognized. Use number or exact style name.")


def run_refinery() -> None:
    print("✶⌁✶ QWEN-ECHO REFINERY v4.3.0 [AUDITED + HARDENED] ONLINE")

    try:
        ensure_debug_root()

        styles = get_available_styles()
        style_names = list(styles.keys())

        for i, name in enumerate(style_names, 1):
            print(f"{i}. {name}")

        style_name = prompt_for_protocol_choice(style_names)
        title = input("Target Title: ").strip()
        if not title:
            raise ValueError("Target Title cannot be empty.")

        source_path = sanitize_input_path(input("Source Data Path: "))
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        if not source_path.is_file():
            raise ValueError(f"Source path is not a file: {source_path}")

        with open(source_path, "r", encoding="utf-8") as f:
            raw_data = f.read()

        if not raw_data.strip():
            raise ValueError("Source file is empty.")

        resolved_style = resolve_style_name(style_name, styles)
        if not resolved_style:
            raise ValueError(f"Selected style could not be resolved: {style_name}")

        protocol_text = styles[resolved_style]
        if not protocol_text.strip():
            raise ValueError(f"Protocol extraction failed for style: {resolved_style}")

        debug_session_dir = build_debug_session_dir(resolved_style, title)
        write_debug_receipts(debug_session_dir, resolved_style, protocol_text, source_path, raw_data)

        print("✶ Synapse: QWEN-ECHO identity manifested.")
        print(f"✶ DEBUG session dir: {debug_session_dir}")
        print(f"✶ DEBUG source chars: {len(raw_data)}")
        print(f"✶ DEBUG source words: {len(raw_data.split())}")
        print(f"✶ DEBUG protocol chars: {len(protocol_text)}")
        print(f"✶ Processing {resolved_style}...")

        synapse = EchoSynapse(resolved_style, protocol_text, debug_session_dir)
        orch = VSEncOrchestrator({"ECHO_STUB": StubAgent()})

        processed_content = synapse.ask(raw_data, max_new_tokens=3000)
        save_text(debug_session_dir / "raw_model_output_pass1.txt", processed_content)

        failed_gate, reason = fails_specificity_gate(processed_content, resolved_style)
        if failed_gate and resolved_style == "UBW":
            print(f"⚠️ UBW specificity gate triggered: {reason}")
            print("✶ Running UBW refinement pass...")
            processed_content = synapse.refine_ubw(raw_data, processed_content)
            save_text(debug_session_dir / "raw_model_output_pass2_refined.txt", processed_content)

            failed_gate_2, reason_2 = fails_specificity_gate(processed_content, resolved_style)
            if failed_gate_2:
                save_text(debug_session_dir / "specificity_gate_failure.txt", reason_2)
                raise ValueError(
                    "UBW emission failed specificity gate even after refinement. "
                    f"Reason: {reason_2}"
                )

        elif failed_gate:
            save_text(debug_session_dir / "specificity_gate_failure.txt", reason)
            print(f"⚠️ Specificity gate warning: {reason}")

        is_research = classify_research_title(title)
        rel_dir = f"{ARTIFACT_ROOT}/{'research' if is_research else 'summaries'}"

        payload = orch.run(
            agent_name="ECHO_STUB",
            input_text=processed_content,
            invocation_type="echo_refinery",
            custom_params={
                "title": title,
                "category": "research" if is_research else "summary",
                "style": resolved_style,
                "relative_dir": rel_dir,
                "status": "active",
                "priority": "medium",
                "tags": ["echo", "distillation", resolved_style.lower()],
                "summary": f"Distillation via {resolved_style} protocol.",
                "external_refs": [str(source_path)],
                "grok_ctx_reflection": f"Refinery output: {resolved_style} protocol applied.",
            },
        )

        save_text(debug_session_dir / "payload_preview.txt", repr(payload))
        orch.emit_to_vault(payload)

        print(f"✓ Artifact Emitted under VS-ENC v1.0.0 Law: {payload['filename']}")
        print(f"✓ Refinery Artifact Emitted: {payload['filename']}")

    except KeyboardInterrupt:
        print("\n⚠️ REFINERY ABORTED: user interrupted execution.")
    except Exception as e:
        print(f"❌ REFINERY ERROR: {e}")


if __name__ == "__main__":
    run_refinery()