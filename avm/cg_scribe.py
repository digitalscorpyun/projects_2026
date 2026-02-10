#!/usr/bin/env python3
# ==============================================================================
# ✶⌁✶ cg_scribe.py — CIPHER GRIOT (CG-SCRIBE) v0.1.0 [VALIDATION SKELETON]
# ==============================================================================
# ROLE: Eligibility Validation for Ciphered Output (NO GENERATION).
# ENGINE: Deterministic Logic (Python 3.10+)
# EXECUTION ZONE: FORGE (READ-ONLY VAULT ACCESS)
# COMPLIANCE: ANACOSTIA-22-FIELD-LAW / VS-ENC-V1.2.1-INHERITANCE
# LINT-STATUS: RUFF-CLEAN (INTENTIONAL SKELETON)
# ==============================================================================

"""
cg_scribe.py — CG-SCRIBE (Cipher Griot) — Forge-side validate-only skeleton

DOCTRINE (NON-NEGOTIABLE)
- Runs in Forge.
- Reads Vault markdown (YAML + body) in READ-ONLY mode.
- Performs eligibility validation ONLY.
- Emits diagnostics to stdout.
- NEVER mutates the Vault.
- NEVER compresses, encodes, or generates rhetoric (validate-only).

AUTHORIZED COMMANDS (THIS SKELETON)
  cg_scribe.py validate --source <vault-relative-path>

All other commands are intentionally unimplemented.
"""

from __future__ import annotations

import argparse
import os
import sys
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml


# -----------------------------
# Configuration (Law)
# -----------------------------

REQUIRED_FRONTMATTER_KEYS = {
    "id",
    "title",
    "category",
    "style",
    "path",
    "created",
    "updated",
    "status",
    "summary",
    "key_themes",
    "linked_notes",
}

ALLOWED_STATUS = {"active", "canonical"}

FORBIDDEN_BODY_MARKERS = {
    "TODO",
    "TBD",
    "FIXME",
    "???",
}

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# -----------------------------
# Utilities
# -----------------------------


def fatal(msg: str, code: int = 2) -> None:
    print(f"CG-SCRIBE: ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def info(msg: str) -> None:
    print(f"CG-SCRIBE: {msg}")


def warn(msg: str) -> None:
    print(f"CG-SCRIBE: WARN: {msg}")


def get_vault_root() -> Path:
    vault_root = os.environ.get("VAULT_ROOT", "").strip()
    if not vault_root:
        fatal(
            "VAULT_ROOT is not set. "
            'Example (PowerShell): $env:VAULT_ROOT="C:\\USERS\\DIGITALSCORPYUN\\SANKOFA_TEMPLE\\ANACOSTIA"'
        )
    root = Path(vault_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        fatal(f"VAULT_ROOT does not exist or is not a directory: {root}")
    return root


def vault_abs(vault_root: Path, rel_path: str) -> Path:
    rel_path = rel_path.strip().lstrip("/\\")
    return (vault_root / rel_path).resolve()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def parse_frontmatter(md_text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    m = FRONTMATTER_RE.match(md_text)
    if not m:
        return None, md_text
    raw = m.group(1)
    body = md_text[m.end() :]
    try:
        fm = yaml.safe_load(raw) or {}
        if not isinstance(fm, dict):
            return None, body
        return fm, body
    except yaml.YAMLError:
        return None, body


# -----------------------------
# Validation Logic
# -----------------------------


def validate_frontmatter(fm: Dict[str, Any]) -> int:
    errors = 0

    missing = [k for k in sorted(REQUIRED_FRONTMATTER_KEYS) if k not in fm]
    if missing:
        errors += 1
        warn(f"Missing required frontmatter keys: {', '.join(missing)}")

    status = str(fm.get("status", "")).lower()
    if status not in ALLOWED_STATUS:
        errors += 1
        warn(f"Invalid status '{status}'. Must be one of {sorted(ALLOWED_STATUS)}")

    summary = str(fm.get("summary", "")).strip()
    if not summary:
        errors += 1
        warn("summary is empty")

    key_themes = fm.get("key_themes")
    if not isinstance(key_themes, list) or not key_themes:
        errors += 1
        warn("key_themes must be a non-empty list")

    linked_notes = fm.get("linked_notes")
    if not isinstance(linked_notes, list) or not linked_notes:
        errors += 1
        warn("linked_notes must be a non-empty list")

    return errors


def validate_body(body: str) -> int:
    errors = 0
    for marker in FORBIDDEN_BODY_MARKERS:
        if marker in body:
            errors += 1
            warn(f"Forbidden marker found in body: {marker}")
    return errors


# -----------------------------
# Command: validate
# -----------------------------


def cmd_validate(vault_root: Path, source: str) -> int:
    src_abs = vault_abs(vault_root, source)

    if not src_abs.exists():
        fatal(f"Source not found: {source}")
    if not src_abs.is_file():
        fatal(f"Source is not a file: {source}")
    if src_abs.suffix.lower() != ".md":
        fatal("Source must be a Markdown (.md) file")

    text = read_text(src_abs)
    fm, body = parse_frontmatter(text)

    if fm is None:
        fatal("No YAML frontmatter detected")

    errors = 0
    errors += validate_frontmatter(fm)
    errors += validate_body(body)

    if errors == 0:
        info("VALIDATION PASS — source eligible for CG-SCRIBE compression")
        return 0

    warn(f"VALIDATION FAIL — {errors} issue(s) detected")
    return 1


# -----------------------------
# CLI
# -----------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cg_scribe.py",
        description="CG-SCRIBE (Cipher Griot) — validate-only execution skeleton",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser(
        "validate", help="Validate a Vault note for CG-SCRIBE eligibility"
    )
    v.add_argument("--source", required=True, help="Vault-relative path to .md source")

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    vault_root = get_vault_root()

    if args.cmd == "validate":
        return cmd_validate(vault_root, args.source)

    fatal(f"Unsupported command: {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
