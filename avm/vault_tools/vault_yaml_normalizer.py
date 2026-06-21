#!/usr/bin/env python3
"""
vault_yaml_normalizer.py

Line-preserving YAML frontmatter normalizer for the Anacostia Vault.

Default mode is DRY RUN.
Use --apply to write changes.

This script avoids full YAML reserialization. It edits only targeted
frontmatter lines and blocks so existing formatting is preserved.

Operations:
- Skip Templates by default
- Preserve Markdown body exactly
- Fix top-level path field
- Rename top-level grok_ctx_reflection -> ctx_grok_reflection
- Convert scalar top-level list fields into flush-left YAML lists
- Reorder known AVM fields as whole preserved blocks
- Emit CSV report
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path


FIELD_ORDER = [
    "id",
    "title",
    "subtitle",
    "category",
    "style",
    "created",
    "updated",
    "status",
    "priority",
    "path",
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

DEFAULT_EXCLUDED_DIRS = {
    ".obsidian",
    ".git",
    "Templates",
}

TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$")


@dataclass
class YAMLBlock:
    key: str
    lines: list[str]


def split_frontmatter_raw(text: str) -> tuple[str | None, str, bool]:
    """
    Return raw frontmatter, body, and whether frontmatter exists.

    raw_frontmatter excludes the opening and closing --- fences.
    body is preserved exactly after the closing fence.
    """
    if not text.startswith("---\n"):
        return None, text, False

    end_marker = "\n---\n"
    end_index = text.find(end_marker, 4)

    if end_index == -1:
        raise ValueError("Opening YAML fence found, but closing YAML fence is missing.")

    raw_frontmatter = text[4:end_index]
    body = text[end_index + len(end_marker):]

    return raw_frontmatter, body, True


def rebuild_markdown(raw_frontmatter: str, body: str) -> str:
    return f"---\n{raw_frontmatter}\n---\n{body}"


def is_excluded_path(path: Path, excluded_dirs: set[str]) -> bool:
    excluded_lower = {item.lower() for item in excluded_dirs}
    return any(part.lower() in excluded_lower for part in path.parts)


def iter_markdown_files(target: Path, excluded_dirs: set[str]) -> list[Path]:
    if target.is_file():
        if target.suffix.lower() == ".md" and not is_excluded_path(target, excluded_dirs):
            return [target]
        return []

    return sorted(
        path
        for path in target.rglob("*.md")
        if path.is_file()
        and not is_excluded_path(path, excluded_dirs)
    )


def vault_relative_path(file_path: Path, root: Path) -> str:
    return file_path.relative_to(root).as_posix()


def parse_frontmatter_blocks(raw_frontmatter: str) -> list[YAMLBlock]:
    """
    Parse top-level YAML into preserved blocks.

    A block begins at a flush-left top-level key:
        key: value

    All following lines belong to that key until the next flush-left key.
    """
    lines = raw_frontmatter.splitlines()
    blocks: list[YAMLBlock] = []
    current_key: str | None = None
    current_lines: list[str] = []

    for line in lines:
        match = TOP_LEVEL_KEY_RE.match(line)

        if match:
            if current_key is not None:
                blocks.append(YAMLBlock(key=current_key, lines=current_lines))

            current_key = match.group(1)
            current_lines = [line]
        else:
            if current_key is None:
                current_key = "__preamble__"
                current_lines = [line]
            else:
                current_lines.append(line)

    if current_key is not None:
        blocks.append(YAMLBlock(key=current_key, lines=current_lines))

    return blocks


def serialize_blocks(blocks: list[YAMLBlock]) -> str:
    all_lines: list[str] = []

    for block in blocks:
        all_lines.extend(block.lines)

    return "\n".join(all_lines)


def replace_block_key(block: YAMLBlock, new_key: str) -> YAMLBlock:
    first_line = block.lines[0]
    match = TOP_LEVEL_KEY_RE.match(first_line)

    if not match:
        return block

    rest = match.group(2)
    new_lines = list(block.lines)
    new_lines[0] = f"{new_key}:{rest}"

    return YAMLBlock(key=new_key, lines=new_lines)


def set_simple_scalar_block(key: str, value: str) -> YAMLBlock:
    return YAMLBlock(key=key, lines=[f"{key}: {value}"])


def is_single_line_scalar_block(block: YAMLBlock) -> bool:
    if len(block.lines) != 1:
        return False

    line = block.lines[0]
    match = TOP_LEVEL_KEY_RE.match(line)

    if not match:
        return False

    value = match.group(2).strip()

    if value == "":
        return False

    if value in {"[]", "{}"}:
        return False

    if value.startswith("[") or value.startswith("{"):
        return False

    if value.startswith("|") or value.startswith(">"):
        return False

    return True


def scalar_value_from_block(block: YAMLBlock) -> str:
    line = block.lines[0]
    match = TOP_LEVEL_KEY_RE.match(line)

    if not match:
        return ""

    return match.group(2).strip()


def strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2:
        if value[0] == value[-1] and value[0] in {"'", '"'}:
            return value[1:-1]

    return value


def convert_scalar_list_block(block: YAMLBlock) -> YAMLBlock:
    """
    Convert:
        adinkra: Sankofa

    To:
        adinkra:
        - Sankofa

    Also handles comma-separated scalar values.
    """
    value = strip_wrapping_quotes(scalar_value_from_block(block)).strip()

    if not value:
        return block

    if "," in value:
        items = [item.strip() for item in value.split(",") if item.strip()]
    else:
        items = [value]

    lines = [f"{block.key}:"]

    for item in items:
        lines.append(f"- {item}")

    return YAMLBlock(key=block.key, lines=lines)


def dedupe_blocks_keep_first(blocks: list[YAMLBlock]) -> tuple[list[YAMLBlock], list[str]]:
    seen: set[str] = set()
    result: list[YAMLBlock] = []
    changes: list[str] = []

    for block in blocks:
        if block.key == "__preamble__":
            result.append(block)
            continue

        if block.key in seen:
            changes.append(f"dropped duplicate {block.key}")
            continue

        seen.add(block.key)
        result.append(block)

    return result, changes


def reorder_blocks(blocks: list[YAMLBlock]) -> tuple[list[YAMLBlock], bool]:
    original_keys = [block.key for block in blocks]

    preamble_blocks = [block for block in blocks if block.key == "__preamble__"]
    real_blocks = [block for block in blocks if block.key != "__preamble__"]

    by_key: dict[str, YAMLBlock] = {}

    for block in real_blocks:
        if block.key not in by_key:
            by_key[block.key] = block

    ordered: list[YAMLBlock] = []
    ordered.extend(preamble_blocks)

    for key in FIELD_ORDER:
        if key in by_key:
            ordered.append(by_key[key])

    for block in real_blocks:
        if block.key not in FIELD_ORDER and block.key in by_key:
            ordered.append(block)

    new_keys = [block.key for block in ordered]

    return ordered, original_keys != new_keys


def normalize_frontmatter_raw(
    raw_frontmatter: str,
    file_path: Path,
    root: Path,
) -> tuple[str, list[str]]:
    changes: list[str] = []
    blocks = parse_frontmatter_blocks(raw_frontmatter)

    new_blocks: list[YAMLBlock] = []
    has_ctx_grok_reflection = any(block.key == "ctx_grok_reflection" for block in blocks)

    for block in blocks:
        if block.key == "grok_ctx_reflection":
            if has_ctx_grok_reflection:
                changes.append("dropped grok_ctx_reflection because ctx_grok_reflection already exists")
                continue

            block = replace_block_key(block, "ctx_grok_reflection")
            changes.append("renamed grok_ctx_reflection -> ctx_grok_reflection")

        new_blocks.append(block)

    blocks = new_blocks

    expected_path = vault_relative_path(file_path, root)
    path_found = False
    new_blocks = []

    for block in blocks:
        if block.key == "path":
            path_found = True
            current_value = scalar_value_from_block(block)
            current_value_unquoted = strip_wrapping_quotes(current_value)

            if current_value_unquoted != expected_path:
                block = set_simple_scalar_block("path", expected_path)
                changes.append(f"fixed path -> {expected_path}")

        new_blocks.append(block)

    blocks = new_blocks

    if not path_found:
        insert_index = 0

        preferred_before_path = {
            "id",
            "title",
            "subtitle",
            "category",
            "style",
            "created",
            "updated",
            "status",
            "priority",
        }

        for index, block in enumerate(blocks):
            if block.key in preferred_before_path:
                insert_index = index + 1

        blocks.insert(insert_index, set_simple_scalar_block("path", expected_path))
        changes.append(f"added path -> {expected_path}")

    new_blocks = []

    for block in blocks:
        if block.key in LIST_FIELDS and is_single_line_scalar_block(block):
            old_lines = list(block.lines)
            block = convert_scalar_list_block(block)

            if block.lines != old_lines:
                changes.append(f"converted {block.key} to list")

        new_blocks.append(block)

    blocks = new_blocks

    blocks, dedupe_changes = dedupe_blocks_keep_first(blocks)
    changes.extend(dedupe_changes)

    blocks, reordered = reorder_blocks(blocks)

    if reordered:
        changes.append("reordered known AVM fields")

    new_raw_frontmatter = serialize_blocks(blocks)

    return new_raw_frontmatter, changes


def process_file(
    file_path: Path,
    root: Path,
    apply_changes: bool,
) -> dict[str, str]:
    try:
        original_text = file_path.read_text(encoding="utf-8")
        raw_frontmatter, body, had_frontmatter = split_frontmatter_raw(original_text)

        if not had_frontmatter or raw_frontmatter is None:
            return {
                "file": str(file_path),
                "status": "skipped",
                "applied": "no",
                "had_frontmatter": "no",
                "changes": "missing frontmatter; skipped",
                "error": "",
            }

        new_raw_frontmatter, changes = normalize_frontmatter_raw(
            raw_frontmatter=raw_frontmatter,
            file_path=file_path,
            root=root,
        )

        new_text = rebuild_markdown(new_raw_frontmatter, body)
        changed = new_text != original_text

        if apply_changes and changed:
            file_path.write_text(new_text, encoding="utf-8")

        return {
            "file": str(file_path),
            "status": "changed" if changed else "ok",
            "applied": "yes" if apply_changes and changed else "no",
            "had_frontmatter": "yes",
            "changes": "; ".join(changes),
            "error": "",
        }

    except Exception as exc:
        return {
            "file": str(file_path),
            "status": "error",
            "applied": "no",
            "had_frontmatter": "",
            "changes": "",
            "error": str(exc),
        }


def write_report(rows: list[dict[str, str]], report_path: Path) -> None:
    fieldnames = [
        "file",
        "status",
        "applied",
        "had_frontmatter",
        "changes",
        "error",
    ]

    report_path.parent.mkdir(parents=True, exist_ok=True)

    with report_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Line-preserving Anacostia Vault YAML frontmatter normalizer."
    )

    parser.add_argument(
        "target",
        help="Markdown file or vault directory to normalize.",
    )

    parser.add_argument(
        "--root",
        default=None,
        help="Vault root. Defaults to target if target is directory, otherwise parent of target.",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes. Default is dry-run.",
    )

    parser.add_argument(
        "--include-templates",
        action="store_true",
        help="Include Templates directory. Default is to skip it.",
    )

    parser.add_argument(
        "--report",
        default="vault_yaml_normalizer_report.csv",
        help="CSV report path.",
    )

    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve()

    if not target.exists():
        print(f"ERROR: target does not exist: {target}", file=sys.stderr)
        return 1

    if args.root:
        root = Path(args.root).expanduser().resolve()
    else:
        root = target if target.is_dir() else target.parent

    if not root.exists():
        print(f"ERROR: root does not exist: {root}", file=sys.stderr)
        return 1

    excluded_dirs = set(DEFAULT_EXCLUDED_DIRS)

    if args.include_templates:
        excluded_dirs.discard("Templates")

    markdown_files = iter_markdown_files(target, excluded_dirs=excluded_dirs)

    rows: list[dict[str, str]] = []

    for file_path in markdown_files:
        try:
            file_path.relative_to(root)
        except ValueError:
            rows.append(
                {
                    "file": str(file_path),
                    "status": "error",
                    "applied": "no",
                    "had_frontmatter": "",
                    "changes": "",
                    "error": f"file is not under root: {root}",
                }
            )
            continue

        rows.append(
            process_file(
                file_path=file_path,
                root=root,
                apply_changes=args.apply,
            )
        )

    report_path = Path(args.report).expanduser().resolve()
    write_report(rows, report_path)

    ok_count = sum(1 for row in rows if row["status"] == "ok")
    changed_count = sum(1 for row in rows if row["status"] == "changed")
    skipped_count = sum(1 for row in rows if row["status"] == "skipped")
    error_count = sum(1 for row in rows if row["status"] == "error")

    mode = "APPLY" if args.apply else "DRY RUN"

    print(f"Mode: {mode}")
    print(f"Files scanned: {len(rows)}")
    print(f"OK: {ok_count}")
    print(f"Changed: {changed_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Errors: {error_count}")
    print(f"Report: {report_path}")
    print(f"Excluded dirs: {', '.join(sorted(excluded_dirs))}")

    if not args.apply and changed_count:
        print("Dry run only. Re-run with --apply to write changes.")

    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
