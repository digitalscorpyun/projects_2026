# ==============================================================================
# ✶⌁✶ scorpyun_annotator.py — THE ANNOTATION EMITTER v2.1.8 [HARDENED]
# ==============================================================================
# ROLE: Lean annotation client with fail-fast guards and descriptive naming.
# COMPLIANCE: WC-DIR-2026-01-11-ENV-HARDENING / SENTINEL-V2.0.0-ALIGN
# ==============================================================================

import os
import sys
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Standard AVM WatsonX/Kernel imports
from watsonx_client import WatsonXClient
from vs_enc import VSEncOrchestrator

# FAIL-FAST GUARD: Authority of the Execution Layer
if not os.getenv("WATSONX_PROJECT_ID"):
    print("❌ ERROR: WATSONX_PROJECT_ID not found in environment.")
    sys.exit(1)

# PATH CONFIGURATION
VAULT_ROOT = Path("C:/Users/digitalscorpyun/sankofa_temple/Anacostia")
ARTIFACT_DIR = "war_council/_artifacts/scorpyun_annotator"
STYLE_GUIDE_PATH = (
    VAULT_ROOT / "war_council/documentation/writing_protocols/summary_styles_guide.md"
)
PST = timezone(timedelta(hours=-8))

# JURISDICTIONAL BOUNDARIES
SAFE_SYNAPSES = [
    "reading_system",
    "vault_literature",
    "sankofa_cut_corpus",
    "emitted_via_vs_enc",
]
FORBIDDEN_SYNAPSES = {
    "vs_enc_orchestrator",
    "session_context",
    "governance",
    "war_council",
}


def normalize_token(text: str) -> str:
    """Enforces strict snake_case for tags and filenames."""
    clean = re.sub(r"[^a-z0-9]+", "_", text.lower())
    return re.sub(r"_+", "_", clean).strip("_")


class AnnotationSynapse:
    def __init__(self, protocol_text: str, source_context: dict):
        self.client = WatsonXClient()
        self.client.set_agent("QWEN-ECHO")
        self.protocol_text = protocol_text
        self.ctx = source_context

    def ask(self, excerpt: str) -> str:
        prompt = f"""
        INSTRUCTION: Apply the 'SankofaCut' protocol to the text below.
        PROTOCOL_RULES:
        {self.protocol_text}

        SOURCE_CONTEXT: "{self.ctx["title"]}" by {self.ctx["author"]} ({self.ctx["location"]})
        TEXT_TO_ANNOTATE:
        "{excerpt}"

        DO NOT return Raw Metadata.
        OUTPUT FORMAT: Provide only the distilled analysis defined by SankofaCut.
        """
        return self.client.ask(prompt)


class StubAgent:
    def run(self, text: str):
        return text


def get_sankofacut_protocol() -> str:
    if not STYLE_GUIDE_PATH.exists():
        raise FileNotFoundError(f"Protocol Source missing at {STYLE_GUIDE_PATH}")
    with open(STYLE_GUIDE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(
        r"#\s*.*?\d+\.\s*\*\*(.*?)\*\*\n(.*?)(?=\n#\s*.*?\d+\.\s*\*\*|$)", re.DOTALL
    )
    for match in pattern.finditer(content):
        name = (
            match.group(1).split("—")[0].strip().replace("*", "").split("(")[0].strip()
        )
        if name == "SankofaCut":
            return match.group(2).strip()
    raise ValueError("SankofaCut protocol not found.")


def run_annotator():
    print("\n🜃 SCORPYUN ANNOTATOR v2.1.8 [HARDENED] ONLINE")
    excerpt = input("Paste excerpt: ").strip()
    title = input("Title: ").strip()
    author = input("Author: ").strip()
    location = input("Chapter/Section: ").strip()

    try:
        protocol = get_sankofacut_protocol()
        synapse = AnnotationSynapse(
            protocol, {"title": title, "author": author, "location": location}
        )
        registry = {"ANNOTATOR_STUB": StubAgent()}
        orchestrator = VSEncOrchestrator(registry)

        print(f"✶ Processing SankofaCut for '{title}'...")
        processed_content = synapse.ask(excerpt)

        # DETERMINISTIC FILENAMING
        now_pst = datetime.now(PST)
        title_slug = normalize_token(title)
        loc_slug = normalize_token(location)
        filename = (
            f"annotation_{title_slug}_{loc_slug}_{now_pst.strftime('%Y%m%d_%H%M')}.md"
        )

        # Emit via v1.0.0 Orchestrator (Sentinel v2.0.0 Alignment)
        payload = orchestrator.run(
            agent_name="ANNOTATOR_STUB",
            input_text=processed_content,
            invocation_type="annotation_emit",
            custom_params={
                "filename": filename,
                "title": f"{title} Annotation — {location}",
                "category": "annotations",
                "style": "SankofaCut",
                "relative_dir": ARTIFACT_DIR,
                "status": "active",
                "priority": "medium",
                "tags": [
                    "annotation",
                    "sankofa_cut",
                    "vault_lit",
                    normalize_token(author),
                ],
                "synapses": SAFE_SYNAPSES,
                "key_themes": ["symbolism", "resistance", "power_codes"],
                "summary": f"SankofaCut annotation of {title} ({location}) by {author}.",
                "grok_ctx_reflection": "Interpretive literary analysis node.",
                "adinkra": ["fawohodie", "mate_masie"],
                "linked_notes": ["war_council/sankofa_spine.md"],
            },
        )
        orchestrator.emit_to_vault(payload)
        print(f"\n✓ ARTIFACT EMITTED: {filename}")

    except Exception as e:
        print(f"❌ EMISSION FAILED: {e}")


if __name__ == "__main__":
    run_annotator()
