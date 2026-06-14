#!/usr/bin/env python3
"""
vault_yaml_normalizer.py

Normalize Anacostia Vault Markdown YAML frontmatter.

Default mode is DRY RUN.
Use --apply to write changes.

Core behaviors:
- Preserve Markdown body exactly.
- Rewrite YAML frontmatter in AVM-style field order.
- Rename grok_ctx_reflection -> ctx_grok_reflection.
- Move ctx_grok_reflection after bias_analysis.
- Keep review_date last.
- Fix path field from file location relative to vault root.
- Convert scalar list fields into YAML lists.
- Optionally fill missing required fields.
- Optionally drop extra YAML fields.
- Emit CSV report.

Usage examples:

python vault_yaml_normalizer.py C:\\Users\\digitalscorpyun\\sankofa_temple\\Anacostia

python vault_yaml_normalizer.py C:\\Users\\digitalscorpyun\\sankofa_temple\\Anacostia --apply

python vault_yaml_normalizer.py C:\\Users\\digitalscorpyun\\sankofa_temple\\Anacostia --apply --fill-missing

python vault_yaml_normalizer.py C:\\Users\\digitalscorpyun\\sankofa_temple\\Anacostia --apply --drop-extras
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


FIELD_ORDER = [
    "title",
    "subtitle",
    "created",
    "updated",
    "status",
    "priority",
    "category",
    "path",
    "summary",
    "longform_summary",
    "tags",
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
    "synapses",
    "key_themes",
    "quotes",
    "adinkra",
    "linked_notes",
    "external_refs",
}

DEFAULTS = {
    "title": "",
    "subtitle": "",
    "created": "",
    "updated": "",
    "status": "draft",
    "priority": "normal",
    "category": "",
    "path": "",
    "summary": "",
    "longform_summary": "",
    "tags": [],
    "synapses": [],
    "key_themes": [],
    "bias_analysis": "",
    "ctx_grok_reflection": "",
    "quotes": [],
    "adinkra": [],
    "linked_notes": [],
    "external_refs": [],
    "review_date": "",
}


def today() -> str:
    return dt.date.today().isoformat()


def split_frontmatter(text: str) -> tuple[dict[str, Any], str, bool]:
    """
    Return (frontmatter_dict, body, had_frontmatter).
    Body is preserved exactly after the closing YAML fence.
    """
    if not text.startswith("---\n"):
        return {}, text, False

    end_marker = "\n---\n"
    end_index = text.find(end_marker, 4)

    if end_index == -1:
        return {}, text, False

    raw_yaml = text[4:end_index]
    body = text[end_index + len(end_marker):]

    if not raw_yaml.strip():
        return {}, body, True

    loaded = yaml.safe_load(raw_yaml)

    if loaded is None:
        return {}, body, True

    if not isinstance(loaded, dict):
        raise ValueError("YAML frontmatter must be a mapping/dictionary.")

    return dict(loaded), body, True


def normalize_list_value(value: Any) -> list[Any]:
    """
    Convert scalar values into list form.
    Preserve lists.
    Convert None/empty string to [].
    """
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []

        # If user wrote comma-separated inline scalar, split gently.
        if "," in stripped and not stripped.startswith("["):
            return [item.strip() for item in stripped.split(",") if item.strip()]

        return [stripped]

    return [value]


def infer_title_from_filename(path: Path) -> str:
    stem = path.stem.replace("_", " ").replace("-", " ")
    return " ".join(word.capitalize() for word in stem.split())


def infer_category_from_relative_path(relative_path: Path) -> str:
    parts = relative_path.parts
    if len(parts) <= 1:
        return ""

    return parts[0]


def vault_relative_path(file_path: Path, root: Path) -> str:
    rel = file_path.relative_to(root)
    return rel.as_posix()


def normalize_frontmatter(
    data: dict[str, Any],
    file_path: Path,
    root: Path,
    fill_missing: bool = False,
    drop_extras: bool = False,
) -> tuple[OrderedDict[str, Any], list[str]]:
    changes: list[str] = []
    normalized: dict[str, Any] = dict(data)

    if "grok_ctx_reflection" in normalized:
        old_value = normalized.pop("grok_ctx_reflection")

        if "ctx_grok_reflection" not in normalized or normalized.get("ctx_grok_reflection") in (None, ""):
            normalized["ctx_grok_reflection"] = old_value

        changes.append("renamed grok_ctx_reflection -> ctx_grok_reflection")

    expected_path = vault_relative_path(file_path, root)

    if normalized.get("path") != expected_path:
        normalized["path"] = expected_path
        changes.append(f"fixed path -> {expected_path}")

    if fill_missing:
        for key, default_value in DEFAULTS.items():
            if key not in normalized or normalized[key] is None:
                if key == "title":
                    normalized[key] = infer_title_from_filename(file_path)
                elif key == "created":
                    normalized[key] = today()
                elif key == "updated":
                    normalized[key] = today()
                elif key == "review_date":
                    normalized[key] = today()
                elif key == "category":
                    normalized[key] = infer_category_from_relative_path(file_path.relative_to(root))
                else:
                    normalized[key] = default_value.copy() if isinstance(default_value, list) else default_value

                changes.append(f"filled missing {key}")

    for key in LIST_FIELDS:
        if key in normalized:
            old_value = normalized[key]
            new_value = normalize_list_value(old_value)

            if old_value != new_value:
                normalized[key] = new_value
                changes.append(f"converted {key} to list")

    ordered: OrderedDict[str, Any] = OrderedDict()

    for key in FIELD_ORDER:
        if key in normalized:
            ordered[key] = normalized[key]

    if not drop_extras:
        for key, value in normalized.items():
            if key not in ordered:
                ordered[key] = value
    else:
        extras = [key for key in normalized if key not in FIELD_ORDER]
        if extras:
            changes.append(f"dropped extras: {', '.join(extras)}")

    # Force review_date to the end if present.
    if "review_date" in ordered:
        review_date_value = ordered.pop("review_date")
        ordered["review_date"] = review_date_value

    return ordered, changes


class AVMYAMLDumper(yaml.SafeDumper):
    pass


def represent_ordered_dict(dumper: yaml.Dumper, data: OrderedDict) -> yaml.nodes.MappingNode:
    return dumper.represent_mapping("tag:yaml.org,2002:map", data.items())


AVMYAMLDumper.add_representer(OrderedDict, represent_ordered_dict)


def dump_frontmatter(data: OrderedDict[str, Any]) -> str:
    return yaml.dump(
        data,
        Dumper=AVMYAMLDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,
    ).strip()


def rebuild_markdown(frontmatter: OrderedDict[str, Any], body: str) -> str:
    yaml_text = dump_frontmatter(frontmatter)
    return f"---\n{yaml_text}\n---\n{body}"


def iter_markdown_files(target: Path) -> list[Path]:
    if target.is_file():
        if target.suffix.lower() == ".md":
            return [target]
        return []

    return sorted(
        path
        for path in target.rglob("*.md")
        if path.is_file()
        and ".obsidian" not in path.parts
        and ".git" not in path.parts
    )


def process_file(
    file_path: Path,
    root: Path,
    apply: bool,
    fill_missing: bool,
    drop_extras: bool,
) -> dict[str, str]:
    original_text = file_path.read_text(encoding="utf-8")

    try:
        frontmatter, body, had_frontmatter = split_frontmatter(original_text)

        normalized, changes = normalize_frontmatter(
            frontmatter,
            file_path=file_path,
            root=root,
            fill_missing=fill_missing,
            drop_extras=drop_extras,
        )

        new_text = rebuild_markdown(normalized, body)

        changed = new_text != original_text

        if apply and changed:
            file_path.write_text(new_text, encoding="utf-8")

        return {
            "file": str(file_path),
            "status": "changed" if changed else "ok",
            "applied": "yes" if apply and changed else "no",
            "had_frontmatter": "yes" if had_frontmatter else "no",
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
    report_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "file",
        "status",
        "applied",
        "had_frontmatter",
        "changes",
        "error",
    ]

    with report_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize Anacostia Vault YAML frontmatter."
    )

    parser.add_argument(
        "target",
        help="Markdown file or vault directory to normalize.",
    )

    parser.add_argument(
        "--root",
        help="Vault root. Defaults to target if target is directory, otherwise parent of target.",
        default=None,
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes. Default is dry-run.",
    )

    parser.add_argument(
        "--fill-missing",
        action="store_true",
        help="Fill missing AVM fields with safe defaults.",
    )

    parser.add_argument(
        "--drop-extras",
        action="store_true",
        help="Drop YAML keys not in FIELD_ORDER.",
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

    markdown_files = iter_markdown_files(target)

    if not markdown_files:
        print("No Markdown files found.")
        return 0

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

        row = process_file(
            file_path=file_path,
            root=root,
            apply=args.apply,
            fill_missing=args.fill_missing,
            drop_extras=args.drop_extras,
        )
        rows.append(row)

    report_path = Path(args.report).expanduser().resolve()
    write_report(rows, report_path)

    changed_count = sum(1 for row in rows if row["status"] == "changed")
    error_count = sum(1 for row in rows if row["status"] == "error")

    mode = "APPLY" if args.apply else "DRY RUN"

    print(f"Mode: {mode}")
    print(f"Files scanned: {len(rows)}")
    print(f"Changed: {changed_count}")
    print(f"Errors: {error_count}")
    print(f"Report: {report_path}")

    if not args.apply and changed_count:
        print("Dry run only. Re-run with --apply to write changes.")

    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())