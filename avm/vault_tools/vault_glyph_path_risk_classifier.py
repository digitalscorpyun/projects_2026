#!/usr/bin/env python3
"""
vault_glyph_path_risk_classifier.py

READ-ONLY. Re-examines every safe_auto_candidate row from the Phase 1
audit, entry by entry, to catch the failure mode found in kwanzaa.md: a
linked_notes entry that explicitly specifies a subpath (contains "/")
which does NOT resolve at that exact location, but which the original
auditor's basename-only dangling check let through as "not dangling"
because SOME unrelated file elsewhere in the vault happens to share that
basename.

This script writes nothing to any Vault note. Output is a single CSV,
one row per (source file, linked_notes entry) pair.

Per-entry logic:

  Path entry (contains "/"): check the exact vault-root-relative path
  (replicates run_inject_links.md's getAbstractFileByPath check).
    - exists      -> safe
    - missing     -> dangling_or_wrong_path, REGARDLESS of whether some
                      unrelated file elsewhere shares the basename --
                      the specified path itself is what's wrong.

  Bare entry (no "/"): vault's normal convention (Obsidian resolves by
  basename, not by exact path).
    - 0 basename matches anywhere -> dangling_or_wrong_path (defensive;
                                       Phase 1 should already exclude this)
    - basename is in the high-risk generic list (index, overview, readme,
      _meta, hub, notes, map) -> exclude_needs_human_judgment, regardless
      of current match count -- these names are too generic to trust even
      when currently unique, since the vault keeps growing
    - 1 basename match, not generic -> safe_to_apply
    - 2+ basename matches, not generic -> exclude_needs_human_judgment

File-level recommended classification = worst entry's classification
(dangling_or_wrong_path > exclude_needs_human_judgment > safe_to_apply).
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from vault_yaml_normalizer import (  # noqa: E402
    parse_frontmatter_blocks,
    split_frontmatter_raw,
)
from vault_glyph_auditor import (  # noqa: E402
    DEFAULT_EXCLUDED_DIRS,
    extract_linked_notes_items,
)
from vault_glyph_footer_injector import (  # noqa: E402
    load_safe_candidates,
    clean_path_segment,
)

RISKY_BARE_BASENAMES = {"index", "overview", "readme", "_meta", "hub", "notes", "map"}

VERDICT_RANK = {"safe_to_apply": 0, "exclude_needs_human_judgment": 1, "dangling_or_wrong_path": 2}


def build_basename_map(root: Path, excluded_dirs: set[str]) -> dict[str, list[str]]:
    """basename (lowercase, no extension) -> list of vault-relative paths."""
    mapping: dict[str, list[str]] = defaultdict(list)
    for path in root.rglob("*.md"):
        if not path.is_file():
            continue
        if any(part.lower() in {d.lower() for d in excluded_dirs} for part in path.parts):
            continue
        mapping[path.stem.lower()].append(path.relative_to(root).as_posix())
    return mapping


def classify_entry(
    raw_entry: str,
    vault_root: Path,
    basename_map: dict[str, list[str]],
) -> dict[str, object]:
    cleaned_path, file_name = clean_path_segment(raw_entry)
    has_explicit_subpath = "/" in cleaned_path
    exact_candidate_rel = f"{cleaned_path}.md"
    exact_exists = (vault_root / exact_candidate_rel).is_file()
    matches = basename_map.get(file_name.lower(), [])

    if has_explicit_subpath:
        exact_checked = exact_candidate_rel
        if exact_exists:
            return {
                "exact_path_checked": exact_checked,
                "exact_path_exists": True,
                "basename_matches_elsewhere": "",
                "risk_reason": "exact path resolved",
                "classification": "safe_to_apply",
            }
        return {
            "exact_path_checked": exact_checked,
            "exact_path_exists": False,
            "basename_matches_elsewhere": "; ".join(matches),
            "risk_reason": (
                "specified path does not exist"
                + (f" (basename coincidentally matches {len(matches)} unrelated file(s))" if matches else " (no basename match at all)")
            ),
            "classification": "dangling_or_wrong_path",
        }

    # Bare entry -- normal vault convention, not checked against exact path.
    if not matches:
        return {
            "exact_path_checked": "",
            "exact_path_exists": False,
            "basename_matches_elsewhere": "",
            "risk_reason": "bare name matches no file anywhere in vault",
            "classification": "dangling_or_wrong_path",
        }

    if file_name.lower() in RISKY_BARE_BASENAMES:
        return {
            "exact_path_checked": "",
            "exact_path_exists": "",
            "basename_matches_elsewhere": "; ".join(matches),
            "risk_reason": f"generic/high-risk basename '{file_name}' -- flagged regardless of current match count ({len(matches)})",
            "classification": "exclude_needs_human_judgment",
        }

    if len(matches) == 1:
        return {
            "exact_path_checked": "",
            "exact_path_exists": "",
            "basename_matches_elsewhere": matches[0],
            "risk_reason": "bare name uniquely resolves, not a generic name",
            "classification": "safe_to_apply",
        }

    return {
        "exact_path_checked": "",
        "exact_path_exists": "",
        "basename_matches_elsewhere": "; ".join(matches),
        "risk_reason": f"bare name matches {len(matches)} files -- ambiguous resolution",
        "classification": "exclude_needs_human_judgment",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="READ-ONLY entry-level risk re-classification of Phase 1 safe_auto_candidate rows."
    )
    parser.add_argument("vault_root")
    parser.add_argument("--audit-report", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    root = Path(args.vault_root).expanduser().resolve()
    audit_report = Path(args.audit_report).expanduser().resolve()
    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else Path(__file__).parent / "_reports" / "vault_glyph_phase2_risk_classified.csv"
    )

    excluded_dirs = set(DEFAULT_EXCLUDED_DIRS)
    basename_map = build_basename_map(root, excluded_dirs)
    candidates = load_safe_candidates(audit_report)

    entry_rows: list[dict[str, object]] = []
    file_verdicts: dict[str, str] = {}

    for cand in candidates:
        rel_path = cand["path"]
        file_path = root / rel_path
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        raw_fm, _body, had_fm = split_frontmatter_raw(text)

        if not had_fm or raw_fm is None:
            entry_rows.append(
                {
                    "source_path": rel_path,
                    "raw_linked_notes_entry": "",
                    "exact_path_checked": "",
                    "exact_path_exists": "",
                    "basename_matches_elsewhere": "",
                    "risk_reason": "frontmatter unparseable on re-check",
                    "recommended_classification": "exclude_needs_human_judgment",
                }
            )
            file_verdicts[rel_path] = "exclude_needs_human_judgment"
            continue

        blocks = parse_frontmatter_blocks(raw_fm)
        raw_items = extract_linked_notes_items(blocks) or []

        worst_rank = -1
        worst_verdict = "safe_to_apply"

        for raw in raw_items:
            result = classify_entry(raw, root, basename_map)
            entry_rows.append(
                {
                    "source_path": rel_path,
                    "raw_linked_notes_entry": raw,
                    **result,
                }
            )
            rank = VERDICT_RANK[result["classification"]]
            if rank > worst_rank:
                worst_rank = rank
                worst_verdict = result["classification"]

        file_verdicts[rel_path] = worst_verdict if raw_items else "exclude_needs_human_judgment"

    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_path",
        "raw_linked_notes_entry",
        "exact_path_checked",
        "exact_path_exists",
        "basename_matches_elsewhere",
        "risk_reason",
        "recommended_classification",
    ]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in entry_rows:
            row.setdefault("recommended_classification", row.get("classification", ""))
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    file_counts = Counter(file_verdicts.values())
    print(f"Vault root: {root}")
    print(f"Source files re-examined: {len(file_verdicts)}")
    print(f"Total linked_notes entries examined: {len(entry_rows)}")
    for verdict in ("safe_to_apply", "exclude_needs_human_judgment", "dangling_or_wrong_path"):
        print(f"  {verdict}: {file_counts.get(verdict, 0)} files")
    print(f"Report written: {output}")
    print("NO FILES WERE MODIFIED. No footer injection. No deletion.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
