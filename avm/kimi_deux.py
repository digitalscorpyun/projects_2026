# ==============================================================================
# ✶⌁✶ kimi_deux.py — THE SYNDICATE STUDY STUDIO v4.4.1 [HARDENED]
# ==============================================================================
# ROLE: Lean training client via VS-ENC Orchestrator.
# ENGINE: QWEN-ECHO via VS-ENC v1.2.1
# COMPLIANCE: ANACOSTIA-22-FIELD-LAW / VS-ENC-V1.2.1-INHERITANCE
# LINT-STATUS: RUFF-CLEAN
# ==============================================================================

import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from watsonx_client import WatsonXClient
from vs_enc import VSEncOrchestrator

# PATH CONFIGURATION (RATIFIED PATH LAW)
VAULT_ROOT = Path("C:/Users/digitalscorpyun/sankofa_temple/Anacostia")
EMISSION_DIR = "war_council/_artifacts/kimi_deux"
LOG_PATH = VAULT_ROOT / EMISSION_DIR / "kimi_deux_training_log.md"
PST = timezone(timedelta(hours=-8))


class KimiSynapse:
    """Cognitive wrapper for KIMI-DEUX maintaining narrative/math logic."""

    def __init__(self):
        self.client = WatsonXClient()
        self.client.set_agent("KIMI-DEUX")

    def format_math(self, content: str) -> str:
        """Enforces block MathJax for Obsidian rendering."""
        content = re.sub(r"\\\((.*?)\\\)", r"\n\n$$\n\1\n$$\n\n", content)
        content = re.sub(
            r"(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)", r"\n\n$$\n\1\n$$\n\n", content
        )
        return re.sub(r"\n{3,}", "\n\n", content)

    def enforce_ceiling(self, content: str) -> str:
        """Hard truncation at Section XI (inclusive)."""
        match = re.search(r"\n#+\s*(XII|12)\.", content, re.IGNORECASE)
        return content[: match.start()].strip() if match else content

    def ask(self, prompt: str) -> str:
        raw = self.client.ask(prompt, max_new_tokens=2500)
        processed = self.format_math(raw)
        return self.enforce_ceiling(processed)


class StubAgent:
    """Satisfies Orchestrator registry while preserving pre-processed content."""

    def run(self, text: str):
        return text


def update_studio_log(topic, domain, filename, result="UNTESTED"):
    """Maintains training history without altering core log structure."""
    ts = datetime.now(PST).strftime("%Y-%m-%d %H:%M:%S")
    link = f"[[{filename[:-3]}]]"
    entry = f"| {ts} | {topic} | {domain} | {link} | {result} |\n"
    if not LOG_PATH.exists():
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write(
                "---\ntitle: KIMI-DEUX Studio Log\nstatus: active\n---\n\n"
                "# ⚖️✶🜂 KIMI-DEUX LOG\n\n"
                "| TS | Topic | Domain | Link | Result |\n"
                "| :--- | :--- | :--- | :--- | :--- |\n"
            )
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)


def run_studio():
    print("✶⌁✶ KIMI-DEUX STUDIO v4.4.1 [HARDENED] ONLINE")
    mode = input("1. FORGE DRILL\n2. LOG ASSESSMENT\nSelect: ").strip()

    # Initialize Middleware
    synapse = KimiSynapse()
    registry = {"KIMI_STUB": StubAgent()}
    orchestrator = VSEncOrchestrator(registry)

    try:
        if mode == "1":
            skill, domain = input("Core Skill: ").strip(), input("Domain: ").strip()
            print("✶ Generating pre-processed drill content...")

            # Execute logic through local synapse first
            drill_prompt = f"Generate a Repetition Drill for: '{skill}' in '{domain}'. Headers: I-XI."
            processed_content = synapse.ask(drill_prompt)

            # Emit via v1.2.1 Orchestrator
            payload = orchestrator.run(
                agent_name="KIMI_STUB",
                input_text=processed_content,
                invocation_type="forge_drill",
                custom_params={
                    "title": f"Drill — {skill}",
                    "category": "drills",
                    "relative_dir": EMISSION_DIR,
                    "tags": [domain.lower().replace(" ", "_"), "drills"],
                    "key_themes": [
                        "skill_acquisition",
                        domain.lower().replace(" ", "_"),
                    ],
                    "ctx_grok_reflection": "Repetition drill for structural skill hardening.",
                },
            )
            orchestrator.emit_to_vault(payload)
            update_studio_log(skill, domain, payload["filename"])

        elif mode == "2":
            topic, domain, score = (
                input("Topic: ").strip(),
                input("Domain: ").strip(),
                input("Score: ").strip(),
            )
            notes = input("Notes: ").strip()
            content = (
                f"# Assessment: {topic}\n\n**Score:** {score}\n\n**Notes:**\n{notes}"
            )

            payload = orchestrator.run(
                agent_name="KIMI_STUB",
                input_text=content,
                invocation_type="log_assessment",
                custom_params={
                    "title": f"Assessment — {topic}",
                    "category": "assessments",
                    "relative_dir": EMISSION_DIR,
                    "tags": [domain.lower().replace(" ", "_"), "results"],
                    "ctx_grok_reflection": "Log assessment for metric evaluation.",
                },
            )
            orchestrator.emit_to_vault(payload)
            update_studio_log(topic, domain, payload["filename"], result=score)

    except Exception as e:
        print(f"❌ MIGRATION ERROR: {e}")


if __name__ == "__main__":
    run_studio()

