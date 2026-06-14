#!/usr/bin/env python3
# ==============================================================================
# ✶⌁✶ vault_yaml_validator.py — ANACOSTIA YAML SCHEMA SENTINEL v2.1.0 [ORDER ENFORCED]
# ==============================================================================
# ROLE: Canonical YAML compliance validator for the Anacostia Vault.
# COMPLIANCE: WC-DIR-2026-01-11-ENV-HARDENING / SENTINEL-V2.0.0-ALIGN
# PURPOSE:
#   - Validate YAML frontmatter compliance across the Anacostia Vault
#   - Enforce the canonical 22-field Anacostia frontmatter law
#   - Enforce canonical field name: ctx_grok_reflection
#   - Flag missing fields, illegal extra fields, type violations, and path drift
#   - Enforce canonical YAML field order, with review_date last
#   - Survive malformed YAML keys and emit audit receipts instead of crashing
#   - Preserve CSV audit reports for War Council review
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

# ---- Anacostia 22-field law: canonical order ---------------------------------
#
# RULES:
#   - id is a numeric string-style identifier, not a slug.
#   - path is the vault-relative POSIX file path.
#   - ctx_grok_reflection is the canonical field name.
#   - review_date MUST remain the final YAML field.
#   - No schema improvisation.
#
# NOTE:
#   The previous validator drifted to grok_ctx_reflection.
#   That is now invalid and will be flagged as:
#     missing ctx_grok_reflection
#     extra grok_ctx_reflection

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
    "ctx_grok_reflection",
    "quotes",
    "adinkra",
    "linked_notes",
    "external_refs",
    "review_date",
]

REQUIRED_FIELD_SET = set(REQUIRED_FIELDS)

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

SCALAR_FIELDS = REQUIRED_FIELD_SET - LIST_FIELDS

DAILY_JOURNAL_CATEGORY = "daily_journal"

YAML_FM_RE = re.compile(r"(?s)\A---\s*\n(.*?)\n---\s*\n")


# ---- Utility -----------------------------------------------------------------


def now_stamp() -> str:
    return datetime.now(LOCAL_TZ).strftime("%Y%m%d_%H%M%S")


def stringify_item(item: Any) -> str:
    return str(item)


def stringify_items(items: List[Any]) -> str:
    return ", ".join(stringify_item(item) for item in items)


def extract_yaml_frontmatter(content: str) -> Optional[str]:
    match = YAML_FM_RE.match(content)
    return match.group(1) if match else None


def safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def vault_relative_posix(vault_root: Path, file_path: Path) -> str:
    return file_path.relative_to(vault_root).as_posix()


def as_string_key(key: Any) -> str:
    """
    PyYAML can parse unquoted date-like keys as datetime.date.
    This function prevents the validator from crashing when reporting malformed keys.
    """
    return str(key)


def parsed_keys_as_strings(parsed: Dict[Any, Any]) -> List[str]:
    return [as_string_key(key) for key in parsed.keys()]


# ---- Validation model ---------------------------------------------------------


@dataclass
class ValidationResult:
    file: str
    status: str  # OK | FAIL
    parse_status: str  # OK | NO_YAML | PARSE_ERROR | MALFORMED
    missing_fields: List[str]
    extra_fields: List[Any]
    type_issues: List[str]
    order_issues: List[str]
    path_mismatch: bool
    expected_path: str
    found_path: str
    category: str


# ---- YAML parse ---------------------------------------------------------------


def parse_yaml(yaml_text: str) -> Tuple[str, Optional[Dict[Any, Any]]]:
    try:
        parsed = yaml.safe_load(yaml_text)
        if not isinstance(parsed, dict) or not parsed:
            return "MALFORMED", None
        return "OK", parsed
    except yaml.YAMLError:
        return "PARSE_ERROR", None


# ---- Validation functions -----------------------------------------------------


def validate_required_fields(parsed: Dict[Any, Any]) -> List[str]:
    keys = set(parsed_keys_as_strings(parsed))
    return [field for field in REQUIRED_FIELDS if field not in keys]


def validate_extra_fields(parsed: Dict[Any, Any]) -> List[Any]:
    extras: List[Any] = []

    for key in parsed.keys():
        key_string = as_string_key(key)
        if key_string not in REQUIRED_FIELD_SET:
            extras.append(key)

    return extras


def validate_types(parsed: Dict[Any, Any]) -> List[str]:
    issues: List[str] = []

    for key, value in parsed.items():
        key_string = as_string_key(key)

        if key_string in LIST_FIELDS:
            if not isinstance(value, list):
                issues.append(f"{key_string}:expected_list")
            else:
                for index, item in enumerate(value):
                    if isinstance(item, (dict, list)):
                        issues.append(f"{key_string}[{index}]:invalid_item_type")

        if key_string in SCALAR_FIELDS:
            if isinstance(value, (dict, list)):
                issues.append(f"{key_string}:expected_scalar")

    return issues


def validate_field_order(parsed: Dict[Any, Any], category: str) -> List[str]:
    """
    Enforces canonical relative order for the required 22 fields.

    Normal notes:
      - required fields must appear in exact REQUIRED_FIELDS order
      - review_date must be the final key in the YAML block
      - extras are illegal and handled separately

    daily_journal:
      - extra operational telemetry fields are allowed
      - required fields must still appear in canonical relative order
      - review_date must still be the final key
    """
    issues: List[str] = []

    keys = parsed_keys_as_strings(parsed)

    present_required = [key for key in keys if key in REQUIRED_FIELD_SET]
    expected_present = [field for field in REQUIRED_FIELDS if field in keys]

    if present_required != expected_present:
        issues.append(
            "required_field_order_mismatch:"
            f"expected={'|'.join(expected_present)};"
            f"found={'|'.join(present_required)}"
        )

    if "review_date" in keys and keys[-1] != "review_date":
        issues.append("review_date:not_last")

    if "ctx_grok_reflection" in keys:
        ctx_index = keys.index("ctx_grok_reflection")
        bias_index = keys.index("bias_analysis") if "bias_analysis" in keys else None
        quotes_index = keys.index("quotes") if "quotes" in keys else None

        if bias_index is not None and ctx_index < bias_index:
            issues.append("ctx_grok_reflection:before_bias_analysis")

        if quotes_index is not None and ctx_index > quotes_index:
            issues.append("ctx_grok_reflection:after_quotes")

    return issues


def validate_path_field(
    vault_root: Path,
    file_path: Path,
    parsed: Dict[Any, Any],
) -> Tuple[bool, str, str]:
    expected = vault_relative_posix(vault_root, file_path)

    found = ""
    for key, value in parsed.items():
        if as_string_key(key) == "path":
            found = "" if value is None else str(value)
            break

    return found != expected, expected, found


def get_category(parsed: Dict[Any, Any]) -> str:
    for key, value in parsed.items():
        if as_string_key(key) == "category":
            return "" if value is None else str(value)

    return ""


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
            order_issues=[],
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
            order_issues=[],
            path_mismatch=False,
            expected_path=rel_file,
            found_path="",
            category="",
        )

    category = get_category(parsed)

    missing = validate_required_fields(parsed)

    extras = validate_extra_fields(parsed)
    if category == DAILY_JOURNAL_CATEGORY:
        extras = []

    type_issues = validate_types(parsed)
    order_issues = validate_field_order(parsed, category)

    path_mismatch, expected_path, found_path = validate_path_field(
        vault_root=vault_root,
        file_path=file_path,
        parsed=parsed,
    )

    status = "OK"
    if missing or extras or type_issues or order_issues or path_mismatch:
        status = "FAIL"

    return ValidationResult(
        file=rel_file,
        status=status,
        parse_status="OK",
        missing_fields=missing,
        extra_fields=extras,
        type_issues=type_issues,
        order_issues=order_issues,
        path_mismatch=path_mismatch,
        expected_path=expected_path,
        found_path=found_path,
        category=category,
    )


# ---- Vault scan ---------------------------------------------------------------


def should_skip_file(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}

    if ".obsidian" in parts:
        return True

    if ".git" in parts:
        return True

    return False


def scan_vault(vault_root: Path, include_ok: bool = False) -> List[ValidationResult]:
    results: List[ValidationResult] = []

    for md_file in vault_root.rglob("*.md"):
        if should_skip_file(md_file):
            continue

        result = validate_file(vault_root, md_file)

        if include_ok or result.status != "OK":
            results.append(result)

    return results


# ---- CSV audit emission -------------------------------------------------------


def write_csv_report(results: List[ValidationResult], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "file",
                "status",
                "parse_status",
                "category",
                "missing_fields",
                "extra_fields",
                "type_issues",
                "order_issues",
                "path_mismatch",
                "expected_path",
                "found_path",
            ],
        )

        writer.writeheader()

        for result in results:
            writer.writerow(
                {
                    "file": result.file,
                    "status": result.status,
                    "parse_status": result.parse_status,
                    "category": result.category,
                    "missing_fields": stringify_items(result.missing_fields),
                    "extra_fields": stringify_items(result.extra_fields),
                    "type_issues": stringify_items(result.type_issues),
                    "order_issues": stringify_items(result.order_issues),
                    "path_mismatch": "true" if result.path_mismatch else "false",
                    "expected_path": result.expected_path,
                    "found_path": result.found_path,
                }
            )


def summarize(results: List[ValidationResult]) -> Tuple[int, int]:
    total = len(results)
    failures = sum(1 for result in results if result.status != "OK")
    return total, failures


# ---- CLI ----------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Anacostia YAML Schema Sentinel v2.1.0 — "
            "22-field law + order enforcement."
        )
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
        help="Include OK files in the CSV report. Default reports only failures.",
    )

    parser.add_argument(
        "--out",
        type=str,
        default="",
        help=(
            "Optional explicit output CSV path. "
            "Default writes to war_council/_artifacts/audits/."
        ),
    )

    args = parser.parse_args()

    vault_root = Path(args.vault)

    if not vault_root.exists():
        print(f"❌ Vault path not found: {vault_root}")
        return 2

    results = scan_vault(vault_root=vault_root, include_ok=args.include_ok)
    total, failures = summarize(results)

    if args.out.strip():
        out_path = Path(args.out)
    else:
        out_path = (
            vault_root
            / AUDIT_DIR_REL
            / f"yaml_validation_report_{now_stamp()}.csv"
        )

    write_csv_report(results=results, out_path=out_path)

    print(f"🔍 Vault: {vault_root}")
    print(f"📄 Report: {out_path}")
    print(f"📦 Files reported: {total}  |  ❌ Fails: {failures}")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())