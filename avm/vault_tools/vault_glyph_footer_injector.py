#!/usr/bin/env python3
"""
vault_glyph_footer_injector.py

Phase 2 of the Vault Glyph Audit: footer-injection for `safe_auto_candidate`
files only (per the Phase 1 audit report), replicating
`Templates/run_inject_links.md`'s own resolution logic exactly.

DEFAULT MODE IS DRY RUN. No file is ever written unless --apply is passed
explicitly, AND --risk-report is supplied, AND the file is classified
safe_to_apply (with zero non-safe entries) in that risk report. This is
the scoped Phase 2 apply: it only ever touches the intersection of
(safe_auto_candidate per the Phase 1 audit) and (safe_to_apply per the
entry-level risk classifier) -- mismatch, dangling_target, no_frontmatter,
linked_notes_missing_or_empty, exclude_needs_human_judgment, and
dangling_or_wrong_path rows are never written to, regardless of mode.

Resolution logic (must match Templates/run_inject_links.md line for line):
    cleanedPath = raw.replace(/\\.md$/i, "").replace(/^\\/+/, "").replace(/\\/+$/, "")
    fileName    = cleanedPath.split("/").pop()
    file        = app.vault.getAbstractFileByPath(cleanedPath + ".md")
        -- this resolves an EXACT path relative to the vault root, not a
           basename search across folders. For a bare linked_notes entry
           like "domain_mapping" (no slashes), this looks for a file
           literally at <vault_root>/domain_mapping.md -- which almost
           never exists in this vault's nested-folder layout. In that
           common case the script falls through to the filename fallback,
           by design, matching the Templater's own behavior exactly.
    if file found and its frontmatter has a non-empty `title`: use title
    else: use fileName

Boundary:
    - Only touches files where the LATEST audit CSV marked
      safe_auto_candidate == True (footer_missing, linked_notes populated
      and clean, no dangling targets at audit time).
    - Re-validates linked_notes and dangling-target status fresh at
      dry-run time (the audit CSV can go stale -- it already has once
      this session) and SKIPS with a reason if re-validation disagrees
      with the stale report, rather than trusting the CSV blindly.
    - Never touches mismatch, dangling_target, no_frontmatter, or
      linked_notes_missing_or_empty rows -- those require judgment.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from vault_yaml_normalizer import (  # noqa: E402
    TOP_LEVEL_KEY_RE,
    parse_frontmatter_blocks,
    split_frontmatter_raw,
    strip_wrapping_quotes,
    vault_relative_path,
)
from vault_glyph_auditor import (  # noqa: E402
    DEFAULT_EXCLUDED_DIRS,
    build_stem_index,
    extract_linked_notes_items,
    normalize_target_name,
)

MD_SUFFIX_RE = re.compile(r"\.md$", re.IGNORECASE)
LEADING_SLASHES_RE = re.compile(r"^/+")
TRAILING_SLASHES_RE = re.compile(r"/+$")


def load_safe_candidates(report_csv: Path) -> list[dict[str, str]]:
    """Rows from the audit CSV flagged safe_auto_candidate == True."""
    rows: list[dict[str, str]] = []
    with report_csv.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("safe_auto_candidate", "").strip().lower() == "true":
                rows.append(row)
    return rows


def load_safe_to_apply_paths(risk_report_csv: Path) -> set[str]:
    """Entry-level risk-classified CSV -> set of source paths where EVERY
    entry for that file was classified safe_to_apply (worst-entry-wins,
    so a single non-safe entry excludes the whole file)."""
    per_file_classifications: dict[str, set[str]] = {}
    with risk_report_csv.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            path = row["source_path"]
            classification = row.get("recommended_classification", "")
            per_file_classifications.setdefault(path, set()).add(classification)

    return {
        path
        for path, classifications in per_file_classifications.items()
        if classifications == {"safe_to_apply"}
    }


def clean_path_segment(raw: str) -> tuple[str, str]:
    """Replicate run_inject_links.md's cleanedPath/fileName derivation exactly.
    Case is preserved -- this is for display/link text, not comparison."""
    cleaned = MD_SUFFIX_RE.sub("", raw.strip())
    cleaned = LEADING_SLASHES_RE.sub("", cleaned)
    cleaned = TRAILING_SLASHES_RE.sub("", cleaned)
    file_name = cleaned.split("/")[-1] if cleaned else cleaned
    return cleaned, file_name


def get_title_field(file_path: Path) -> str | None:
    """Read a target file's frontmatter `title:` value, or None if absent/empty."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    raw_fm, _body, had_fm = split_frontmatter_raw(text)
    if not had_fm or raw_fm is None:
        return None

    for block in parse_frontmatter_blocks(raw_fm):
        if block.key != "title":
            continue
        match = TOP_LEVEL_KEY_RE.match(block.lines[0])
        value = strip_wrapping_quotes(match.group(2).strip()) if match else ""
        return value or None

    return None


def resolve_link_text(raw_entry: str, vault_root: Path) -> tuple[str, str]:
    """Returns (link_text, resolution_method) for one linked_notes entry,
    exactly replicating run_inject_links.md's branch logic."""
    cleaned_path, file_name = clean_path_segment(raw_entry)

    candidate = vault_root / f"{cleaned_path}.md"
    if candidate.is_file():
        title = get_title_field(candidate)
        if title:
            return title, "resolved_title"
        return file_name, "resolved_no_title_fallback_filename"

    return file_name, "unresolved_fallback_filename"


def build_proposed_footer(raw_items: list[str], vault_root: Path) -> tuple[str, list[str]]:
    """Returns (footer_text, per_item_resolution_notes)."""
    lines = ["## 🜃 Connected Glyphs", ""]
    notes: list[str] = []

    for raw in raw_items:
        link_text, method = resolve_link_text(raw, vault_root)
        lines.append(f"- [[{link_text}]]")
        notes.append(f"{raw!r} -> [[{link_text}]] ({method})")

    return "\n".join(lines) + "\n", notes


def process_candidate(
    rel_path: str, vault_root: Path, stem_index: set[str]
) -> dict[str, object]:
    """Re-validates one candidate fresh and returns its proposed action.
    Pure read -- never writes. Shared by dry-run and apply."""
    file_path = vault_root / rel_path

    if not file_path.is_file():
        return {
            "path": rel_path,
            "linked_notes_count": 0,
            "proposed_footer": "",
            "action": "skip",
            "skipped_reason": "file no longer exists at audited path",
            "resolution_detail": "",
        }

    text = file_path.read_text(encoding="utf-8", errors="ignore")
    raw_fm, body, had_fm = split_frontmatter_raw(text)

    if not had_fm or raw_fm is None:
        return {
            "path": rel_path,
            "linked_notes_count": 0,
            "proposed_footer": "",
            "action": "skip",
            "skipped_reason": "frontmatter unparseable on re-check (report is stale)",
            "resolution_detail": "",
        }

    if re.search(r"^#+\s*.*Connected Glyphs", body, re.IGNORECASE | re.MULTILINE):
        return {
            "path": rel_path,
            "linked_notes_count": 0,
            "proposed_footer": "",
            "action": "skip",
            "skipped_reason": "footer already present on re-check (report is stale)",
            "resolution_detail": "",
        }

    blocks = parse_frontmatter_blocks(raw_fm)
    raw_items = extract_linked_notes_items(blocks)

    if not raw_items:
        return {
            "path": rel_path,
            "linked_notes_count": 0,
            "proposed_footer": "",
            "action": "skip",
            "skipped_reason": "linked_notes empty/absent on re-check (report is stale)",
            "resolution_detail": "",
        }

    dangling = [item for item in raw_items if normalize_target_name(item) not in stem_index]
    if dangling:
        return {
            "path": rel_path,
            "linked_notes_count": len(raw_items),
            "proposed_footer": "",
            "action": "skip",
            "skipped_reason": f"dangling target(s) found on re-check: {'; '.join(dangling)}",
            "resolution_detail": "",
        }

    footer_text, resolution_notes = build_proposed_footer(raw_items, vault_root)

    return {
        "path": rel_path,
        "linked_notes_count": len(raw_items),
        "proposed_footer": footer_text,
        "action": "append",
        "skipped_reason": "",
        "resolution_detail": " | ".join(resolution_notes),
    }


def write_footer(vault_root: Path, rel_path: str, footer_text: str) -> None:
    """Appends the footer to the end of the file, preserving all existing
    content exactly. One blank line separates body from footer."""
    file_path = vault_root / rel_path
    original = file_path.read_text(encoding="utf-8")
    new_content = original.rstrip("\n") + "\n\n" + footer_text
    file_path.write_text(new_content, encoding="utf-8")


def dry_run(vault_root: Path, audit_report: Path, dry_run_report: Path) -> int:
    excluded_dirs = set(DEFAULT_EXCLUDED_DIRS)
    stem_index = build_stem_index(vault_root, excluded_dirs=excluded_dirs)
    candidates = load_safe_candidates(audit_report)

    out_rows: list[dict[str, object]] = [
        process_candidate(row["path"], vault_root, stem_index) for row in candidates
    ]

    dry_run_report.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "path",
        "linked_notes_count",
        "proposed_footer",
        "action",
        "skipped_reason",
        "resolution_detail",
    ]
    with dry_run_report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in out_rows:
            row.setdefault("resolution_detail", "")
            writer.writerow(row)

    append_count = sum(1 for r in out_rows if r["action"] == "append")
    skip_count = sum(1 for r in out_rows if r["action"] == "skip")

    print(f"Vault root: {vault_root}")
    print(f"Audit report: {audit_report}")
    print(f"Safe candidates loaded: {len(candidates)}")
    print(f"Would append footer: {append_count}")
    print(f"Skipped (re-validation): {skip_count}")
    print(f"Dry-run report written: {dry_run_report}")
    print("NO FILES WERE MODIFIED. This script is dry-run only.")

    return 0


def apply_footers(
    vault_root: Path,
    audit_report: Path,
    risk_report: Path,
    apply_log: Path,
) -> int:
    excluded_dirs = set(DEFAULT_EXCLUDED_DIRS)
    stem_index = build_stem_index(vault_root, excluded_dirs=excluded_dirs)
    candidates = load_safe_candidates(audit_report)
    safe_to_apply_paths = load_safe_to_apply_paths(risk_report)

    to_modify: list[dict[str, object]] = []
    excluded: list[dict[str, object]] = []

    for row in candidates:
        rel_path = row["path"]

        if rel_path not in safe_to_apply_paths:
            excluded.append({"path": rel_path, "reason": "not safe_to_apply per risk report"})
            continue

        result = process_candidate(rel_path, vault_root, stem_index)

        if result["action"] != "append":
            excluded.append(
                {"path": rel_path, "reason": f"re-validation skip: {result['skipped_reason']}"}
            )
            continue

        to_modify.append(result)

    print(f"Report path used (audit): {audit_report}")
    print(f"Report path used (risk classification): {risk_report}")
    print(f"Files to modify: {len(to_modify)}")
    print(f"Files excluded: {len(excluded)}")
    print()

    log_rows: list[dict[str, object]] = []

    for item in to_modify:
        rel_path = item["path"]
        footer_text = item["proposed_footer"]
        write_footer(vault_root, rel_path, footer_text)
        log_rows.append(
            {
                "path": rel_path,
                "linked_notes_count": item["linked_notes_count"],
                "action": "footer_appended",
                "resolution_detail": item["resolution_detail"],
            }
        )

    for item in excluded:
        log_rows.append(
            {
                "path": item["path"],
                "linked_notes_count": "",
                "action": "excluded",
                "resolution_detail": item["reason"],
            }
        )

    apply_log.parent.mkdir(parents=True, exist_ok=True)
    with apply_log.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["path", "linked_notes_count", "action", "resolution_detail"]
        )
        writer.writeheader()
        writer.writerows(log_rows)

    print(f"Footers appended: {len(to_modify)}")
    print(f"Apply log written: {apply_log}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 2 Connected Glyphs footer injector -- DRY RUN ONLY. "
            "Reports what would be written for safe_auto_candidate files; writes nothing."
        )
    )
    parser.add_argument("vault_root", help="Vault root directory.")
    parser.add_argument(
        "--audit-report",
        required=True,
        help="Path to the Phase 1 audit CSV (vault_glyph_audit_report.csv).",
    )
    parser.add_argument(
        "--dry-run-report",
        default=None,
        help="Output CSV path for the dry-run proposal report.",
    )
    parser.add_argument(
        "--risk-report",
        default=None,
        help=(
            "Path to the entry-level risk-classified CSV "
            "(vault_glyph_phase2_risk_classified.csv). Required for --apply."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Actually write footers, scoped to files marked safe_to_apply "
            "in --risk-report. Without this flag, the script only ever dry-runs."
        ),
    )
    parser.add_argument(
        "--apply-log",
        default=None,
        help="Output CSV path for the apply-pass log.",
    )
    args = parser.parse_args()

    root = Path(args.vault_root).expanduser().resolve()
    if not root.exists():
        print(f"ERROR: vault root does not exist: {root}", file=sys.stderr)
        return 1

    audit_report = Path(args.audit_report).expanduser().resolve()
    if not audit_report.exists():
        print(f"ERROR: audit report does not exist: {audit_report}", file=sys.stderr)
        return 1

    if args.apply:
        if not args.risk_report:
            print("ERROR: --apply requires --risk-report.", file=sys.stderr)
            return 1

        risk_report = Path(args.risk_report).expanduser().resolve()
        if not risk_report.exists():
            print(f"ERROR: risk report does not exist: {risk_report}", file=sys.stderr)
            return 1

        apply_log = (
            Path(args.apply_log).expanduser().resolve()
            if args.apply_log
            else Path(__file__).parent / "_reports" / "vault_glyph_phase2_apply_log.csv"
        )

        return apply_footers(root, audit_report, risk_report, apply_log)

    dry_run_report = (
        Path(args.dry_run_report).expanduser().resolve()
        if args.dry_run_report
        else Path(__file__).parent / "_reports" / "vault_glyph_phase2_dry_run.csv"
    )

    return dry_run(root, audit_report, dry_run_report)


if __name__ == "__main__":
    raise SystemExit(main())
