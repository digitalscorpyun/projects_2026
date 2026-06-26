#!/usr/bin/env python3
"""
vault_glyph_auditor.py

Phase 1 READ-ONLY auditor for the Anacostia Vault's "Connected Glyphs"
footer convention (see Templates/run_inject_links.md) and linked_notes
frontmatter completeness.

This script writes nothing to any Vault note. It produces a CSV report
only, classifying every note into exactly one category:

  ok                            -- footer present, matches linked_notes
  footer_missing                -- linked_notes populated, no footer yet
                                    (safe_auto_candidate for Phase 2)
  mismatch                       -- footer present, but its links don't
                                    match the current linked_notes field
  linked_notes_missing_or_empty -- linked_notes key absent or empty
  dangling_target                -- linked_notes/footer reference a note
                                    that doesn't exist anywhere in the vault
  no_frontmatter / error         -- could not be parsed

Reuses the line-preserving frontmatter block parser from
vault_yaml_normalizer.py rather than reimplementing YAML parsing.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from vault_yaml_normalizer import (  # noqa: E402
    TOP_LEVEL_KEY_RE,
    YAMLBlock,
    iter_markdown_files,
    is_excluded_path,
    parse_frontmatter_blocks,
    split_frontmatter_raw,
    strip_wrapping_quotes,
    vault_relative_path,
)

DEFAULT_EXCLUDED_DIRS = {".obsidian", ".git", "Templates"}

FOOTER_HEADING_RE = re.compile(r"^#+\s*.*Connected Glyphs", re.IGNORECASE | re.MULTILINE)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")
LIST_ITEM_RE = re.compile(r"^\s*-\s+(.*\S)\s*$")
INLINE_LIST_RE = re.compile(r"^\[(.*)\]$")
LEADING_DASH_RE = re.compile(r"^-+\s*")


def extract_linked_notes_items(blocks: list[YAMLBlock]) -> list[str] | None:
    """Return raw linked_notes item strings, or None if the key is entirely absent."""
    for block in blocks:
        if block.key != "linked_notes":
            continue

        first_line = block.lines[0]
        match = TOP_LEVEL_KEY_RE.match(first_line)
        inline_value = match.group(2).strip() if match else ""

        items: list[str] = []

        if inline_value:
            inline_match = INLINE_LIST_RE.match(inline_value)
            if inline_match:
                inner = inline_match.group(1).strip()
                if inner:
                    items.extend(
                        strip_wrapping_quotes(x.strip())
                        for x in inner.split(",")
                        if x.strip()
                    )
            elif inline_value not in {"[]", "{}"}:
                items.append(strip_wrapping_quotes(inline_value))

        for line in block.lines[1:]:
            item_match = LIST_ITEM_RE.match(line)
            if item_match:
                items.append(strip_wrapping_quotes(item_match.group(1).strip()))

        return items

    return None


def normalize_target_name(raw: str) -> str:
    """Reduce a linked_notes/footer entry to a comparable basename, defensively
    stripping a stray leading '-' that indicates malformed single-item YAML
    (e.g. 'linked_notes: - foo' instead of proper list syntax)."""
    cleaned = raw.strip().strip('"').strip("'")
    cleaned = LEADING_DASH_RE.sub("", cleaned).strip()
    cleaned = re.sub(r"\.md$", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip("/").strip()
    return cleaned.split("/")[-1].lower()


def extract_footer_links(content: str) -> list[str] | None:
    """Return normalized link targets in the Connected Glyphs footer, or None
    if no such footer section exists anywhere in the body."""
    match = FOOTER_HEADING_RE.search(content)
    if not match:
        return None
    footer_text = content[match.end():]
    raw_links = WIKILINK_RE.findall(footer_text)
    return [normalize_target_name(x) for x in raw_links]


def build_stem_index(root: Path, excluded_dirs: set[str]) -> set[str]:
    """All note basenames (lowercased, no extension) that exist anywhere
    in the vault, for dangling-reference checks. Obsidian resolves
    [[wikilinks]] by basename across folders, so this matches real behavior."""
    stems: set[str] = set()
    for path in root.rglob("*.md"):
        if path.is_file() and not is_excluded_path(path, excluded_dirs):
            stems.add(path.stem.lower())
    return stems


def categorize(file_path: Path, root: Path, stem_index: set[str]) -> dict[str, object]:
    rel_path = vault_relative_path(file_path, root)
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    raw_fm, _body, had_fm = split_frontmatter_raw(text)

    if not had_fm or raw_fm is None:
        return {
            "path": rel_path,
            "category": "no_frontmatter",
            "linked_notes_count": 0,
            "footer_present": False,
            "footer_link_count": 0,
            "dangling_targets": "",
            "mismatch_detail": "",
            "safe_auto_candidate": False,
            "error": "",
        }

    blocks = parse_frontmatter_blocks(raw_fm)
    ln_items = extract_linked_notes_items(blocks)
    footer_links = extract_footer_links(text)

    footer_present = footer_links is not None
    ln_present = ln_items is not None
    ln_count = len(ln_items) if ln_items else 0

    ln_norm = sorted({normalize_target_name(x) for x in ln_items}) if ln_items else []
    footer_norm = sorted(set(footer_links)) if footer_links else []

    dangling = [t for t in ln_norm if t and t not in stem_index]

    if not ln_present or ln_count == 0:
        category = "linked_notes_missing_or_empty"
    elif not footer_present:
        category = "footer_missing"
    elif ln_norm != footer_norm:
        category = "mismatch"
    elif dangling:
        category = "dangling_target"
    else:
        category = "ok"

    safe_auto_candidate = (
        category == "footer_missing" and ln_present and ln_count > 0 and not dangling
    )

    return {
        "path": rel_path,
        "category": category,
        "linked_notes_count": ln_count,
        "footer_present": footer_present,
        "footer_link_count": len(footer_links) if footer_links else 0,
        "dangling_targets": "; ".join(dangling),
        "mismatch_detail": (
            f"linked_notes={ln_norm} | footer={footer_norm}" if category == "mismatch" else ""
        ),
        "safe_auto_candidate": safe_auto_candidate,
        "error": "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 1 read-only Connected Glyphs / linked_notes auditor. Writes a CSV report only."
    )
    parser.add_argument("vault_root", help="Vault root directory to audit.")
    parser.add_argument("--report", default=None, help="CSV report output path.")
    args = parser.parse_args()

    root = Path(args.vault_root).expanduser().resolve()

    if not root.exists():
        print(f"ERROR: vault root does not exist: {root}", file=sys.stderr)
        return 1

    excluded_dirs = set(DEFAULT_EXCLUDED_DIRS)
    files = iter_markdown_files(root, excluded_dirs=excluded_dirs)
    stem_index = build_stem_index(root, excluded_dirs=excluded_dirs)

    rows: list[dict[str, object]] = []

    for file_path in files:
        try:
            rows.append(categorize(file_path, root, stem_index))
        except Exception as exc:
            rows.append(
                {
                    "path": vault_relative_path(file_path, root),
                    "category": "error",
                    "linked_notes_count": 0,
                    "footer_present": False,
                    "footer_link_count": 0,
                    "dangling_targets": "",
                    "mismatch_detail": "",
                    "safe_auto_candidate": False,
                    "error": str(exc),
                }
            )

    report_path = (
        Path(args.report).expanduser().resolve()
        if args.report
        else Path(__file__).parent / "_reports" / "vault_glyph_audit_report.csv"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "path",
        "category",
        "linked_notes_count",
        "footer_present",
        "footer_link_count",
        "dangling_targets",
        "mismatch_detail",
        "safe_auto_candidate",
        "error",
    ]

    with report_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(row["category"] for row in rows)
    safe_count = sum(1 for row in rows if row["safe_auto_candidate"])

    print(f"Vault root: {root}")
    print(f"Excluded dirs: {', '.join(sorted(excluded_dirs))}")
    print(f"Files scanned: {len(rows)}")
    for category, count in sorted(counts.items(), key=lambda item: -item[1]):
        print(f"  {category}: {count}")
    print(f"safe_auto_candidate (Phase 2 eligible): {safe_count}")
    print(f"Report written: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
