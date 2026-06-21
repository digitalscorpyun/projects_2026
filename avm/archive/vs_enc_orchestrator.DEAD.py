"""
VS-ENC Orchestrator — Root execution coordinator for the AVM Syndicate.

This class centralizes:
- agent selection
- invocation-type validation (Invocation Law)
- output shaping & JSON enforcement
- tone/rhetorical shaping
- metadata attachment
- fallback logic

All synapse calls must flow through this orchestrator to ensure
consistent structure and safe execution across the system.
"""

import json
import yaml
from datetime import datetime
from typing import Any, Dict


# -------------------------------------------------------------------
# Helper: Load Invocation Law YAML
# -------------------------------------------------------------------
def _load_invocation_law(path: str) -> Dict[str, Any]:
    """Load the VS-ENC Invocation Law YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# -------------------------------------------------------------------
# Main Orchestrator Class
# -------------------------------------------------------------------
class VSEncOrchestrator:
    """
    VS-ENC — Vault Sentinel / Encoding Agent
    The governing orchestrator of the AVM Syndicate.
    """

    def __init__(
        self, agent_registry: Dict[str, Any], law_path: str | None = None
    ) -> None:
        """Initialize orchestrator with registry + optional Invocation Law."""
        self.agent_registry = agent_registry
        self.invocation_law = _load_invocation_law(law_path) if law_path else None

    # -------------------------------------------------------------------
    # Invocation Type Validation
    # -------------------------------------------------------------------
    def _validate_invocation(self, invocation_type: str) -> Dict[str, Any] | None:
        """Return rule block for invocation type or raise error."""
        if not self.invocation_law:
            return None

        rules = self.invocation_law.get("invocation_types", {})
        if invocation_type not in rules:
            global_rules = self.invocation_law.get("global_policies", {})
            if global_rules.get("reject_if_unknown_invocation", True):
                raise ValueError(f"Unknown invocation type: {invocation_type}")
            return None

        return rules[invocation_type]

    def _enforce_agent_permissions(
        self, agent_name: str, rules: Dict[str, Any] | None
    ) -> None:
        """Ensure the selected agent is allowed for this task."""
        if not rules:
            return

        allowed = rules.get("allowed_agents", [])
        if allowed and agent_name not in allowed:
            raise PermissionError(
                f"Agent '{agent_name}' is not permitted for this invocation type."
            )

    # -------------------------------------------------------------------
    # Tone Engine
    # -------------------------------------------------------------------
    def _apply_tone(self, payload: Dict[str, Any], tone: str | None) -> Dict[str, Any]:
        """Apply tone/rhetorical transformation to output."""
        if not tone or tone == "none":
            return payload

        original = payload.get("output")
        if not isinstance(original, str):
            return payload

        if tone == "neutral_analytic":
            payload["output"] = original.strip()
            return payload

        if tone == "structured_summary":
            payload["output"] = f"Summary:\n{original.strip()}"
            return payload

        if tone == "interpretive":
            payload["output"] = "Interpretation:\n" + original.strip()
            return payload

        if tone == "scorpyunstyle":
            payload["output"] = "🔥 ScorpyunStyle Output 🔥\n" + original.strip()
            return payload

        return payload

    # -------------------------------------------------------------------
    # Metadata Attachment
    # -------------------------------------------------------------------
    def _attach_metadata(
        self, payload: Dict[str, Any], agent_name: str, invocation_type: str | None
    ) -> Dict[str, Any]:
        """Attach Invocation Law–defined metadata fields."""

        if not self.invocation_law:
            return payload

        fields = self.invocation_law.get("metadata_fields", [])
        meta: Dict[str, Any] = {}

        timestamp = datetime.utcnow().isoformat()

        if "invocation_type" in fields:
            meta["invocation_type"] = invocation_type

        if "agent_used" in fields:
            meta["agent_used"] = agent_name

        if "timestamp" in fields:
            meta["timestamp"] = timestamp

        payload["_meta"] = meta
        return payload

    # -------------------------------------------------------------------
    # Core Execution
    # -------------------------------------------------------------------
    def run(
        self,
        agent_name: str,
        text: str,
        output_shape: str,
        invocation_type: str | None = None,
    ) -> Dict[str, Any]:
        """
        Execute a request through VS-ENC with Invocation Law enforcement.
        """

        # ---------------------------------------------------------------
        # 1. Validate invocation type & enforce rules
        # ---------------------------------------------------------------
        rules = None
        if invocation_type and self.invocation_law:
            rules = self._validate_invocation(invocation_type)
            self._enforce_agent_permissions(agent_name, rules)

            # Invocation Law may override the output shape
            override_shape = rules.get("output_shape")
            if override_shape:
                output_shape = override_shape

        # ---------------------------------------------------------------
        # 2. Resolve agent
        # ---------------------------------------------------------------
        if agent_name not in self.agent_registry:
            raise ValueError(f"Agent not found: {agent_name}")

        agent = self.agent_registry[agent_name]

        # ---------------------------------------------------------------
        # 3. Execute agent
        # ---------------------------------------------------------------
        raw_output = agent.run(text)

        # ---------------------------------------------------------------
        # 4. JSON parsing or structured wrapping
        # ---------------------------------------------------------------
        if isinstance(raw_output, str):
            try:
                structured = json.loads(raw_output)
            except json.JSONDecodeError:
                structured = {
                    "shape": output_shape,
                    "agent": agent_name,
                    "output": raw_output.strip(),
                }

        elif isinstance(raw_output, dict):
            structured = raw_output

        else:
            structured = {
                "shape": output_shape,
                "agent": agent_name,
                "output": str(raw_output),
            }

        # ---------------------------------------------------------------
        # 5. Attach metadata
        # ---------------------------------------------------------------
        structured = self._attach_metadata(structured, agent_name, invocation_type)

        # ---------------------------------------------------------------
        # 6. Apply Tone / Rhetorical Mode
        # ---------------------------------------------------------------
        tone = rules.get("tone") if rules else None
        structured = self._apply_tone(structured, tone)

        return structured

