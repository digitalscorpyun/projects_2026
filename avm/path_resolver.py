import os

# ------------------------------------------------------------
# PATH CONSTANTS — MODIFY ONLY IF YOUR DIRECTORY CHANGES
# ------------------------------------------------------------
FORGE_ROOT = r"C:\Users\digitalscorpyun\projects_2025\avm_ops"
VAULT_ROOT = r"C:\Users\digitalscorpyun\sankofa_temple\Anacostia"


def resolve(path: str) -> str:
    """
    Resolve vault/forge paths into real OS filesystem paths.
    Accepts:
      - vault:operations/tasks/input_note.md
      - forge:scripts/synapse_engine.py
      - operations/tasks/input_note.md (auto-assume vault)
      - relative forge paths (starting with avm_ops/)
      - absolute paths (passed through)
    """

    # --------------------------------------------------------
    # 1. Already absolute → return unchanged
    # --------------------------------------------------------
    if os.path.isabs(path):
        return path

    # --------------------------------------------------------
    # 2. Explicit namespace → vault: or forge:
    # --------------------------------------------------------
    if path.startswith("vault:"):
        rel = path.replace("vault:", "").lstrip("\\/")
        return os.path.join(VAULT_ROOT, rel)

    if path.startswith("forge:"):
        rel = path.replace("forge:", "").lstrip("\\/")
        return os.path.join(FORGE_ROOT, rel)

    # --------------------------------------------------------
    # 3. Implicit vault path (default behavior)
    # --------------------------------------------------------
    if not path.startswith("avm_ops"):
        # treat as vault-relative
        return os.path.join(VAULT_ROOT, path)

    # --------------------------------------------------------
    # 4. Local forge-relative path (avm_ops/…)
    # --------------------------------------------------------
    return os.path.join(os.path.dirname(FORGE_ROOT), path.replace("/", os.sep))
