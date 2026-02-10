#!/usr/bin/env python3
# ==============================================================================
# vault_yaml_validator.py — Anacostia YAML Schema Sentinel
# Version: 2.0.0  |  22-field law enforced (+daily_journal exception)
# Author: digitalscorpyun x VS-ENC (refactor)
#
# Purpose:
# ==============================================================================
# ✶⌁✶ vault_yaml_validator.py — SCHEMA SENTINEL v2.0.0 [LAW ENFORCEMENT]
# ==============================================================================
# ROLE: Canonical YAML compliance validator for the Anacostia Vault.
# ENGINE: Python (Schema Enforcement, Non-Mutating)
# JURISDICTION: Metadata Law, Frontmatter Validation, Audit Emission
#
# PURPOSE:
#   Validate YAML frontmatter compliance across the Anacostia Vault under the
#   current 22-field Anacostia standard.
#
# KEY GUARANTEES:
#   - Enforces REQUIRED 22 YAML fields for all notes
#   - Flags ILLEGAL extra fields (daily_journal telemetry explicitly exempted)
#   - Validates scalar vs list field typing
#   - Verifies `path` equals vault-relative file path (POSIX form)
#   - Emits CSV audit reports to: war_council/_artifacts/audits/
#
# EXECUTION POSTURE:
#   Read-only. Non-mutating. Enforcement-first.
# ==============================================================================


from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytz
import yaml

LOCAL_TZ = pytz.timezone("America/Los_Angeles")

DEFAULT_VAULT_PATH = Path("C:/Users/digitalscorpyun/sankofa_temple/Anacostia")
AUDIT_DIR_REL = Path("war_council/_artifacts/audits")

# ---- Anacostia 22-field law (canonical) --------------------------------------

REQUIRED_FIELDS: List[str] = [
    "id",
    "title",
    "category",
    "style",
    "path",
    "created",
    "updated",
    "status",
    "priority",
    "summary",
    "longform_summary",
    "tags",
    "cssclasses",
    "synapses",
    "key_themes",
    "bias_analysis",
    "grok_ctx_reflection",
    "quotes",
    "adinkra",
    "linked_notes",
    "external_refs",
    "review_date",
]

# daily_journal exception: allowed to include additional operational fields.
DAILY_JOURNAL_CATEGORY = "daily_journal"

# Expected types (enforced)
LIST_FIELDS = {
    "tags",
    "cssclasses",
    "synapses",
    "key_themes",
    "quotes",
    "adinkra",
    "linked_notes",
    "external_refs",
}
SCALAR_FIELDS = set(REQUIRED_FIELDS) - LIST_FIELDS

# ---- YAML extraction ----------------------------------------------------------

YAML_FM_RE = re.compile(r"(?s)\A---\s*\n(.*?)\n---\s*\n")


def now_stamp() -> str:
    return datetime.now(LOCAL_TZ).strftime("%Y%m%d_%H%M%S")


def extract_yaml_frontmatter(content: str) -> Optional[str]:
    m = YAML_FM_RE.match(content)
    return m.group(1) if m else None


def safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def is_markdown(path: Path) -> bool:
    return path.suffix.lower() == ".md"


def vault_relative_posix(vault_root: Path, file_path: Path) -> str:
    return file_path.relative_to(vault_root).as_posix()


# ---- Validation core ----------------------------------------------------------


@dataclass
class ValidationResult:
    file: str
    status: str  # OK | FAIL
    parse_status: str  # OK | NO_YAML | PARSE_ERROR | MALFORMED
    missing_fields: List[str]
    extra_fields: List[str]
    type_issues: List[str]
    path_mismatch: bool
    expected_path: str
    found_path: str
    category: str


def parse_yaml(yaml_text: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    try:
        parsed = yaml.safe_load(yaml_text)
        if not isinstance(parsed, dict) or not parsed:
            return "MALFORMED", None
        return "OK", parsed
    except yaml.YAMLError:
        return "PARSE_ERROR", None


def validate_types(parsed: Dict[str, Any]) -> List[str]:
    issues: List[str] = []

    # Lists
    for k in LIST_FIELDS:
        if k in parsed:
            v = parsed[k]
            if not isinstance(v, list):
                issues.append(f"{k}:expected_list")
            else:
                # ensure list items are scalars (strings/numbers), not dicts
                for i, item in enumerate(v):
                    if isinstance(item, (dict, list)):
                        issues.append(f"{k}[{i}]:invalid_item_type")

    # Scalars
    for k in SCALAR_FIELDS:
        if k in parsed:
            v = parsed[k]
            # YAML may parse dates as datetime/date depending; accept str/number/bool as "scalar"
            if isinstance(v, (dict, list)):
                issues.append(f"{k}:expected_scalar")

    return issues


def validate_required_fields(parsed: Dict[str, Any]) -> List[str]:
    return [f for f in REQUIRED_FIELDS if f not in parsed]


def validate_extra_fields(parsed: Dict[str, Any]) -> List[str]:
    return [k for k in parsed.keys() if k not in REQUIRED_FIELDS]


def validate_path_field(
    vault_root: Path, file_path: Path, parsed: Dict[str, Any]
) -> Tuple[bool, str, str]:
    expected = vault_relative_posix(vault_root, file_path)
    found = parsed.get("path", "")
    # Normalize found to string
    found_str = str(found) if found is not None else ""
    return (found_str != expected), expected, found_str


def validate_file(vault_root: Path, file_path: Path) -> ValidationResult:
    rel_file = vault_relative_posix(vault_root, file_path)

    content = safe_read_text(file_path)
    yaml_text = extract_yaml_frontmatter(content)

    if yaml_text is None:
        return ValidationResult(
            file=rel_file,
            status="FAIL",
            parse_status="NO_YAML",
            missing_fields=REQUIRED_FIELDS.copy(),
            extra_fields=[],
            type_issues=[],
            path_mismatch=False,
            expected_path=rel_file,
            found_path="",
            category="",
        )

    parse_status, parsed = parse_yaml(yaml_text)
    if parse_status != "OK" or parsed is None:
        return ValidationResult(
            file=rel_file,
            status="FAIL",
            parse_status=parse_status,
            missing_fields=REQUIRED_FIELDS.copy(),
            extra_fields=[],
            type_issues=[],
            path_mismatch=False,
            expected_path=rel_file,
            found_path="",
            category="",
        )

    # Required fields
    missing = validate_required_fields(parsed)

    # Category for exception logic
    category_val = parsed.get("category", "")
    category_str = str(category_val) if category_val is not None else ""

    # Extra fields (illegal unless daily_journal)
    extras = validate_extra_fields(parsed)
    if category_str == DAILY_JOURNAL_CATEGORY:
        # daily_journal may include additional telemetry fields: allow extras
        extras = []

    # Types
    type_issues = validate_types(parsed)

    # Path
    path_mismatch, expected_path, found_path = validate_path_field(
        vault_root, file_path, parsed
    )

    status = "OK"
    if missing or extras or type_issues or path_mismatch:
        status = "FAIL"

    return ValidationResult(
        file=rel_file,
        status=status,
        parse_status="OK",
        missing_fields=missing,
        extra_fields=extras,
        type_issues=type_issues,
        path_mismatch=path_mismatch,
        expected_path=expected_path,
        found_path=found_path,
        category=category_str,
    )


def scan_vault(vault_root: Path, include_ok: bool = False) -> List[ValidationResult]:
    results: List[ValidationResult] = []
    for md_file in vault_root.rglob("*.md"):
        # Skip common hidden/system folders if present
        parts = {p.lower() for p in md_file.parts}
        if ".obsidian" in parts:
            continue

        r = validate_file(vault_root, md_file)
        if include_ok or r.status != "OK":
            results.append(r)
    return results


def write_csv_report(
    vault_root: Path, results: List[ValidationResult], out_path: Path
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "file",
                "status",
                "parse_status",
                "category",
                "missing_fields",
                "extra_fields",
                "type_issues",
                "path_mismatch",
                "expected_path",
                "found_path",
            ],
        )
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "file": r.file,
                    "status": r.status,
                    "parse_status": r.parse_status,
                    "category": r.category,
                    "missing_fields": ", ".join(r.missing_fields),
                    "extra_fields": ", ".join(r.extra_fields),
                    "type_issues": ", ".join(r.type_issues),
                    "path_mismatch": "true" if r.path_mismatch else "false",
                    "expected_path": r.expected_path,
                    "found_path": r.found_path,
                }
            )


def summarize(results: List[ValidationResult]) -> Tuple[int, int]:
    total = len(results)
    fails = sum(1 for r in results if r.status != "OK")
    return total, fails


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Anacostia YAML Schema Sentinel (22-field law)."
    )
    parser.add_argument(
        "--vault",
        type=str,
        default=str(DEFAULT_VAULT_PATH),
        help="Absolute path to Anacostia vault root.",
    )
    parser.add_argument(
        "--include-ok",
        action="store_true",
        help="Include OK files in the CSV report (default: only FAIL).",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="",
        help="Optional explicit output CSV path. Default writes to war_council/_artifacts/audits/.",
    )
    args = parser.parse_args()

    vault_root = Path(args.vault)
    if not vault_root.exists():
        print(f"❌ Vault path not found: {vault_root}")
        return 2

    results = scan_vault(vault_root, include_ok=args.include_ok)
    total, fails = summarize(results)

    if args.out.strip():
        out_path = Path(args.out)
    else:
        out_dir = vault_root / AUDIT_DIR_REL
        out_path = out_dir / f"yaml_validation_report_{now_stamp()}.csv"

    write_csv_report(vault_root, results, out_path)

    print(f"🔍 Vault: {vault_root}")
    print(f"📄 Report: {out_path}")
    print(f"📦 Files reported: {total}  |  ❌ Fails: {fails}")

    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
