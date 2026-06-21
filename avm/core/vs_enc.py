# ==============================================================================
# ✶⌁✶ vs_enc.py — THE ROOT ORCHESTRATOR v1.0.0 [CANONICAL]
# ==============================================================================
# ROLE: Root execution coordinator and universal metadata enforcer.
# ENGINE: Python 3.10+ / Middleware Kernel
# COMPLIANCE: WC-LAW-2025-12-29-V200 (Sentinel v2.0.0 Alignment)
# ==============================================================================

import re
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

VAULT_ROOT = Path("C:/Users/digitalscorpyun/sankofa_temple/Anacostia")
PST = timezone(timedelta(hours=-8))


class VSEncOrchestrator:
    def __init__(
        self, agent_registry: Dict[str, Any], law_path: Optional[Path] = None
    ) -> None:
        self.agent_registry = agent_registry
        self.invocation_law = self._load_law(law_path) if law_path else {}

    def _load_law(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _get_pst_now(self) -> str:
        now = datetime.now(PST)
        ts = now.strftime("%Y-%m-%dT%H:%M:%S%z")
        return f"{ts[:-2]}:{ts[-2:]}"

    def _normalize_token(self, text: str) -> str:
        clean = re.sub(r"[^a-z0-9]+", "_", text.lower())
        return re.sub(r"_+", "_", clean).strip("_")

    def _build_frontmatter(self, params: Dict[str, Any]) -> Dict[str, Any]:
        ts = self._get_pst_now()
        numeric_id = datetime.now(PST).strftime("%Y%m%d%H%M%S")

        # ARTIFACT LOCATION: Logic relative to vault root
        rel_dir = params.get("relative_dir", "war_council/_artifacts/uncategorized")
        filename = params.get("filename", f"emit_{numeric_id}.md")
        vault_path = f"{rel_dir}/{filename}"

        # CANONICAL 22-FIELD SCHEMA (V2.0.0 Sentinel Alignment)
        fm = {
            "id": numeric_id,
            "title": params.get("title", "Untitled Artifact").replace(":", " —"),
            "category": params.get("category", "provisional"),
            "style": params.get("style", "ScorpyunStyle"),
            "path": vault_path,
            "created": ts,
            "updated": ts,
            "status": params.get("status", "active"),
            "priority": params.get("priority", "medium"),  # RESTORED: Field 9
            "summary": params.get("summary", "Pending semantic summary."),
            "longform_summary": params.get(
                "longform_summary", "Pending semantic longform summary."
            ),
            "tags": [
                self._normalize_token(t) for t in params.get("tags", ["orchestrated"])
            ],
            "cssclasses": params.get("cssclasses", ["tyrian-purple", "sacred-tech"]),
            "synapses": params.get(
                "synapses", ["session_context", "vs_enc_orchestrator"]
            ),
            "key_themes": [
                self._normalize_token(t)
                for t in params.get("key_themes", ["synthesis"])
            ],
            "bias_analysis": params.get("bias_analysis", "Analytical stance pending."),
            "grok_ctx_reflection": params.get(
                "grok_ctx_reflection",
                "Deterministic node.",  # RESTORED: Key Name
            ),
            "quotes": params.get("quotes", []),
            "adinkra": params.get("adinkra", ["Eban"]),
            "linked_notes": params.get(
                "linked_notes", ["war_council/sankofa_spine.md"]
            ),
            "external_refs": params.get("external_refs", []),
            "review_date": params.get(
                "review_date",
                (datetime.now(PST) + timedelta(days=90)).strftime("%Y-%m-%d"),
            ),
        }
        return fm

    def run(
        self,
        agent_name: str,
        input_text: str,
        invocation_type: str,
        custom_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        rules = self.invocation_law.get("invocation_types", {}).get(invocation_type, {})
        if agent_name not in self.agent_registry:
            raise ValueError(f"Agent '{agent_name}' missing.")
        agent = self.agent_registry[agent_name]
        raw_output = (
            agent.ask(input_text) if hasattr(agent, "ask") else agent.run(input_text)
        )
        merged_params = {**rules, **custom_params}
        frontmatter = self._build_frontmatter(merged_params)
        return {
            "metadata": frontmatter,
            "content": raw_output,
            "filename": merged_params.get("filename", f"emit_{frontmatter['id']}.md"),
            "full_save_path": VAULT_ROOT / frontmatter["path"],
        }

    def emit_to_vault(self, payload: Dict[str, Any]) -> None:
        save_path = payload["full_save_path"]
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                + yaml.dump(payload["metadata"], sort_keys=False, allow_unicode=True)
                + "---\n\n"
                + payload["content"]
            )
        print(f"✓ Artifact Emitted under VS-ENC v1.0.0 Law: {save_path.name}")

