# ==============================================================================
# ✶⌁✶ ctx_grok.py — THE UNIFIED DIAGNOSTIC ENGINE v0.2.7.3 [HARDENED]
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
from datetime import datetime
from pathlib import Path

import yaml

# JURISDICTIONAL IMPORT: Kernel v1.0.0
sys.path.append(str(Path(__file__).parent))

try:
    from vs_enc import VSEncOrchestrator
except ImportError:
    VSEncOrchestrator = None

try:
    from ctx_grok_proto import CTXGrokProto
except ImportError:
    CTXGrokProto = None


# CANONICAL CONSTANTS
DEFAULT_VAULT_ROOT = Path(
    r"C:\Users\digitalscorpyun\sankofa_temple\Anacostia"
)

DEFAULT_TAXONOMY = Path(
    r"C:\Users\digitalscorpyun\projects_2026\avm\config\concept_taxonomy.yaml"
)

ARTIFACT_DIR = "war_council/_artifacts/ctx_grok"


class DiagnosticEngine:
    def __init__(self, vault_root: Path, taxonomy: dict):
        self.vault_root = vault_root
        self.taxonomy = taxonomy if isinstance(taxonomy, dict) else {}
        self.classes = self.taxonomy.get("classes", {})
        self.snapshot = {}
        self.timestamp = datetime.now().isoformat()

    def _get_rel_path(self, absolute_path: Path) -> str:
        """Deterministic generation of vault-relative paths."""
        try:
            return absolute_path.relative_to(self.vault_root).as_posix()
        except ValueError:
            return absolute_path.name

    def _discovery(self) -> list[Path]:
        """Pass 1: File Discovery & Metadata Intake."""
        return list(self.vault_root.rglob("*.md"))

    def _read_note(self, path: Path) -> tuple[str, dict]:
        """
        Read Markdown note content and extract YAML frontmatter safely.

        Frontmatter is only parsed when the file begins with '---'.
        Body delimiters later in the note are ignored for frontmatter purposes.
        """
        content = ""

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return content, {}

        meta = {}

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    loaded = yaml.safe_load(parts[1])
                    if isinstance(loaded, dict):
                        meta = loaded
                except Exception:
                    meta = {}

        return content, meta

    def _normalize_tags(self, tags) -> list[str]:
        """Normalize YAML tag values into a deterministic list of strings."""
        if isinstance(tags, str):
            return [tags]

        if isinstance(tags, list):
            return [tag for tag in tags if isinstance(tag, str)]

        return []

    def _classification(self, path: Path) -> None:
        """Pass 2: Taxonomy Enforcement."""
        rel_path = self._get_rel_path(path)
        content, meta = self._read_note(path)

        title = meta.get("title", path.stem)
        if not isinstance(title, str):
            title = path.stem

        stem = path.stem

        align = "unclassified"
        source = "none"

        # Strict taxonomy lookup: concept_taxonomy.yaml's `include` lists
        # are curated note titles/filenames (a declarative, named allowlist
        # per the taxonomy's own "no heuristic promotion permitted" /
        # "exclusion is intentional" principles) -- not tag vocabulary.
        # Match against the note's title or filename stem, both since the
        # lists mix slug-style and Title Case entries.
        for class_name, cfg in self.classes.items():
            include_list = cfg.get("include", [])
            if not isinstance(include_list, list):
                include_list = []

            if title in include_list or stem in include_list:
                align = class_name
                source = "taxonomy_match"
                break

        # Calculate gravity from wikilink density.
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

    def run_pipeline(self) -> str:
        files = self._discovery()

        for file_path in files:
            try:
                rel_parts = file_path.relative_to(self.vault_root).parts
            except ValueError:
                rel_parts = file_path.parts

            if "_artifacts" in rel_parts:
                continue

            self._classification(file_path)

        return self._calculate_drift()

    def _calculate_drift(self) -> str:
        return "Baseline established."


class StubAgent:
    def run(self, text: str) -> str:
        return text


class CTXGrokProtoAdapter:
    """
    Adapts CTXGrokProto's dict-returning .run() to the plain-string
    contract VSEncOrchestrator.run() expects for payload['content'].
    """

    def __init__(self) -> None:
        self._agent = CTXGrokProto()

    def run(self, text: str) -> str:
        result = self._agent.run(text, task="structural_alignment_summary")
        output = result.get("output", {})

        if isinstance(output, dict):
            return "\n".join(f"- **{key}**: {value}" for key, value in output.items())

        return str(output)


def load_taxonomy(path: Path) -> dict:
    """Load taxonomy YAML safely."""
    try:
        with path.open("r", encoding="utf-8") as file:
            loaded = yaml.safe_load(file)
            return loaded if isinstance(loaded, dict) else {}
    except FileNotFoundError:
        raise FileNotFoundError(f"Taxonomy file not found: {path}") from None
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid taxonomy YAML: {path}\n{exc}") from exc


def build_alignment_report(snapshot: dict) -> str:
    """Build the Structural Alignment Map artifact body."""
    report_content = (
        "# 🛰️ STRUCTURAL ALIGNMENT MAP\n\n"
        "| Path | Align | Source |\n"
        "| :--- | :--- | :--- |\n"
    )

    for path, data in sorted(snapshot.items()):
        report_content += (
            f"| {path} | {data['alignment']} | {data['source']} |\n"
        )

    return report_content


def main() -> None:
    parser = argparse.ArgumentParser(description="CTX-GROK v0.2.7.3")
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT_ROOT)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    args = parser.parse_args()

    taxonomy = load_taxonomy(args.taxonomy)

    engine = DiagnosticEngine(args.vault, taxonomy)
    engine.run_pipeline()

    if not VSEncOrchestrator:
        print("VSEncOrchestrator unavailable. Diagnostic scan completed; no Vault emission.")
        return

    agent = CTXGrokProtoAdapter() if CTXGrokProto else StubAgent()
    orch = VSEncOrchestrator(agent_registry={"ctx_grok": agent})

    report_content = build_alignment_report(engine.snapshot)

    payload = orch.run(
        agent_name="ctx_grok",
        input_text=report_content,
        invocation_type="diagnostic",
        custom_params={
            "title": "Structural Alignment Map",
            "relative_dir": ARTIFACT_DIR,
            "priority": "medium",
            "ctx_grok_reflection": "Hardened ingress diagnostic.",
        },
    )

    orch.emit_to_vault(payload)


if __name__ == "__main__":
    main()