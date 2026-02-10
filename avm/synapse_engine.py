"""
Synapse Engine — AVM Syndicate
Routes all synaptic execution through the VS-ENC orchestrator.
"""

import argparse
import json
import os
import sys
import yaml

from path_resolver import resolve


# -------------------------------------------------------------------
# 1. Path bootstrap (must run before dynamic imports)
# -------------------------------------------------------------------
def _bootstrap_path() -> None:
    """Ensure avm_ops is available on sys.path."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, ".."))

    if project_root not in sys.path:
        sys.path.insert(0, project_root)


# -------------------------------------------------------------------
# 2. Default synapse file
# -------------------------------------------------------------------
DEFAULT_SYNAPSE = (
    r"C:\Users\digitalscorpyun\projects_2025\avm_ops\qa\synapse"
    r"\proto_synapse_call.yaml"
)

INVOCATION_LAW_PATH = (
    r"C:\Users\digitalscorpyun\projects_2025\avm_ops\config"
    r"\vs_enc_invocation_law.yaml"
)


# -------------------------------------------------------------------
# 3. Synapse execution
# -------------------------------------------------------------------
def run_synapse(yaml_path: str) -> None:
    """Load a synapse YAML file and execute it through VS-ENC."""

    # Ensure paths are set before importing internal modules
    _bootstrap_path()

    # Internal imports must occur *after* bootstrap
    from scripts.ctx_grok_proto import CTXGrokProto
    from avm_ops.scripts.vs_enc_orchestrator import VSEncOrchestrator

    # Build agent registry dynamically
    agent_registry = {
        "ctx_grok_proto": CTXGrokProto(),
    }

    # Instantiate orchestrator WITH Invocation Law
    orchestrator = VSEncOrchestrator(
        agent_registry,
        law_path=INVOCATION_LAW_PATH,
    )

    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"Synapse YAML not found: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    syn = config.get("synapse", {})
    agent_name = syn.get("agent")
    invocation_type = syn.get("invocation_type")
    input_path = resolve(syn.get("input"))
    output_path = resolve(syn.get("writeback"))
    output_shape = syn.get("output_shape", "raw")

    if agent_name not in agent_registry:
        raise ValueError(f"Agent not found: {agent_name}")

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input note not found: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Execute via VS-ENC with Invocation Law + Tone
    result = orchestrator.run(
        agent_name=agent_name,
        text=text,
        output_shape=output_shape,
        invocation_type=invocation_type,
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print("✔ Synapse complete.")
    print(f"→ Output written to: {output_path}")


# -------------------------------------------------------------------
# 4. Entrypoint
# -------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=str, default=DEFAULT_SYNAPSE)
    args = parser.parse_args()
    run_synapse(args.run)


if __name__ == "__main__":
    main()
