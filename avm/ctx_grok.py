# ==============================================================================
# ✶⌁✶ ctx_grok.py — THE UNIFIED DIAGNOSTIC ENGINE v0.2.7.2 [HARDENED]
# ==============================================================================
# ROLE: Unified Full-Spectrum Diagnostic Emission (Structural/Semantic/Drift).
# ENGINE: Deterministic Logic (Python 3.10+)
# COMPLIANCE: WC-DIR-2026-01-08-V117 / SENTINEL-V2.0.0-ALIGN
# JURISDICTION: Anacostia Vault — Structural Governance
# ==============================================================================

import argparse
import math
import re
import sys
from pathlib import Path
from datetime import datetime
import yaml

# JURISDICTIONAL IMPORT: Kernel v1.0.0
sys.path.append(str(Path(__file__).parent))
try:
    from vs_enc import VSEncOrchestrator
except ImportError:
    VSEncOrchestrator = None

# CANONICAL CONSTANTS
DEFAULT_VAULT_ROOT = r"C:\Users\digitalscorpyun\sankofa_temple\Anacostia"
DEFAULT_TAXONOMY = (
    r"C:\Users\digitalscorpyun\projects_2025\avm_ops\config\concept_taxonomy.yaml"
)
ARTIFACT_DIR = "war_council/_artifacts/ctx_grok"


class DiagnosticEngine:
    def __init__(self, vault_root: Path, taxonomy: dict):
        self.vault_root = vault_root
        self.taxonomy = taxonomy
        self.classes = taxonomy.get("classes", {})
        self.snapshot = {}
        self.timestamp = datetime.now().isoformat()

    def _get_rel_path(self, absolute_path: Path) -> str:
        """Deterministic generation of vault-relative paths."""
        try:
            return absolute_path.relative_to(self.vault_root).as_posix()
        except ValueError:
            return absolute_path.name

    def _discovery(self):
        """Pass 1: File Discovery & Metadata Intake."""
        return list(self.vault_root.rglob("*.md"))

    def _classification(self, path: Path):
        """Pass 2: Taxonomy Enforcement (No Heuristics)."""
        rel_path = self._get_rel_path(path)

        # Metadata Extraction (HARDENED via WC-DIR-2026-01-08-V117)
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            parts = content.split("---")
            meta = yaml.safe_load(parts[1]) if len(parts) >= 3 else {}
            # AUTHORIZED BOUNDARY: Type validation to prevent list-attribute error
            if not isinstance(meta, dict):
                meta = {}
        except Exception:
            meta = {}

        title = meta.get("title", path.stem)
        tags = meta.get("tags", [])

        align = "unclassified"
        source = "none"

        # Strict Taxonomy Lookup
        for class_name, cfg in self.classes.items():
            if any(tag in tags for tag in cfg.get("include_tags", [])):
                align, source = class_name, "taxonomy_match"
                break

        # Calculate Gravity (v0.2.3 Logic)
        links = re.findall(r"\[\[(.*?)\]\]", content)
        raw_gravity = len(links) * 1.0
        norm_gravity = (
            round(raw_gravity / math.log(len(content) + 1.1), 4)
            if len(content) > 0
            else 0
        )

        self.snapshot[rel_path] = {
            "title": title,
            "alignment": align,
            "source": source,
            "gravity": round(raw_gravity, 2),
            "norm_gravity": norm_gravity,
        }

    def run_pipeline(self):
        files = self._discovery()
        for f in files:
            if "_artifacts" in str(f):
                continue
            self._classification(f)
        return self._calculate_drift()

    def _calculate_drift(self):
        return "Baseline established."


class StubAgent:
    def run(self, text: str):
        return text


def main():
    parser = argparse.ArgumentParser(description="CTX-GROK v0.2.7.2")
    parser.add_argument("--vault", type=Path, default=Path(DEFAULT_VAULT_ROOT))
    args = parser.parse_args()

    with open(DEFAULT_TAXONOMY, "r", encoding="utf-8") as f:
        tax = yaml.safe_load(f)

    engine = DiagnosticEngine(args.vault, tax)
    engine.run_pipeline()

    if VSEncOrchestrator:
        orch = VSEncOrchestrator(agent_registry={"ctx_grok": StubAgent()})

        # EMISSION: Structural Alignment Map
        report_content = "# 🛰️ STRUCTURAL ALIGNMENT MAP\n\n| Path | Align | Source |\n| :--- | :--- | :--- |\n"
        for path, data in engine.snapshot.items():
            report_content += f"| {path} | {data['alignment']} | {data['source']} |\n"

        payload = orch.run(
            agent_name="ctx_grok",
            input_text=report_content,
            invocation_type="diagnostic",
            custom_params={
                "title": "Structural Alignment Map",
                "relative_dir": ARTIFACT_DIR,
                "priority": "medium",
                "grok_ctx_reflection": "Hardened ingress diagnostic.",
            },
        )
        orch.emit_to_vault(payload)


if __name__ == "__main__":
    main()
