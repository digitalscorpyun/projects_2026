# ==============================================================================
# ✶⌁✶ qwen_echo.py — THE CONSOLIDATED ECHO ENGINE v4.2.4 [HARDENED]
# ==============================================================================
# ROLE: Flagship refinery client via VS-ENC v1.0.0.
# COMPLIANCE: WC-DIR-2026-01-11-ENV-HARDENING / SENTINEL-V2.0.0-ALIGN
# ==============================================================================

import os
import sys
import re
from datetime import timedelta, timezone
from pathlib import Path
from watsonx_client import WatsonXClient
from vs_enc import VSEncOrchestrator

# FAIL-FAST GUARD
if not os.getenv("WATSONX_PROJECT_ID"):
    print("❌ ERROR: WATSONX_PROJECT_ID not found in environment.")
    sys.exit(1)

VAULT_ROOT = Path("C:/Users/digitalscorpyun/sankofa_temple/Anacostia")
ARTIFACT_ROOT = "war_council/_artifacts/qwen_echo"
STYLE_GUIDE_PATH = (
    VAULT_ROOT / "war_council/documentation/writing_protocols/summary_styles_guide.md"
)
PST = timezone(timedelta(hours=-8))


class EchoSynapse:
    def __init__(self, style_name: str, protocol_text: str):
        self.client = WatsonXClient()
        self.client.set_agent("QWEN-ECHO")
        self.style_name = style_name
        self.protocol_text = protocol_text

    def ask(self, data: str) -> str:
        prompt = (
            f"INSTRUCTION: Apply the '{self.style_name}' protocol to the text below.\n"
            f"PROTOCOL_RULES:\n{self.protocol_text}\n\n"
            "DO NOT return the raw transcript. DO NOT echo input data.\n"
            f"OUTPUT FORMAT: Provide only the analysis defined by the {self.style_name} standard.\n\n"
            f"RAW_DATA:\n{data}"
        )
        return self.client.ask(prompt, max_new_tokens=3000)


class StubAgent:
    def run(self, text: str):
        return text


def get_available_styles() -> dict:
    if not STYLE_GUIDE_PATH.exists():
        raise FileNotFoundError("Style Guide missing.")
    with open(STYLE_GUIDE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    styles = {}
    pattern = re.compile(
        r"#\s*.*?\d+\.\s*\*\*(.*?)\*\*\n(.*?)(?=\n#\s*.*?\d+\.\s*\*\*|$)", re.DOTALL
    )
    for match in pattern.finditer(content):
        name = (
            match.group(1).split("—")[0].strip().replace("*", "").split("(")[0].strip()
        )
        styles[name] = match.group(2).strip()
    return styles


def run_refinery():
    print("✶⌁✶ QWEN-ECHO REFINERY v4.2.4 [HARDENED] ONLINE")
    try:
        styles = get_available_styles()
        style_names = list(styles.keys())
        for i, name in enumerate(style_names, 1):
            print(f"{i}. {name}")
        choice = int(input("\nSelect Protocol: "))
        style_name = style_names[choice - 1]
        title = input("Target Title: ")
        source_path = Path(input("Source Data Path: ").strip().strip('"'))
        with open(source_path, "r", encoding="utf-8") as f:
            raw_data = f.read()

        synapse = EchoSynapse(style_name, styles[style_name])
        orch = VSEncOrchestrator({"ECHO_STUB": StubAgent()})

        is_research = any(
            k in title.upper() for k in ["ICWC-", "CARR-", "WALKER-", "GWW-"]
        )
        rel_dir = f"{ARTIFACT_ROOT}/{'research' if is_research else 'summaries'}"

        print(f"✶ Processing {style_name}...")
        processed_content = synapse.ask(raw_data)

        payload = orch.run(
            agent_name="ECHO_STUB",
            input_text=processed_content,
            invocation_type="echo_refinery",
            custom_params={
                "title": title,
                "category": "research" if is_research else "summary",
                "style": style_name,
                "relative_dir": rel_dir,
                "status": "active",
                "priority": "medium",
                "tags": ["echo", "distillation", style_name.lower()],
                "summary": f"Distillation via {style_name} protocol.",
                "external_refs": [str(source_path)],
                "grok_ctx_reflection": f"Refinery output: {style_name} protocol applied.",
            },
        )
        orch.emit_to_vault(payload)
        print(f"✓ Refinery Artifact Emitted: {payload['filename']}")
    except Exception as e:
        print(f"❌ REFINERY ERROR: {e}")


if __name__ == "__main__":
    run_refinery()

