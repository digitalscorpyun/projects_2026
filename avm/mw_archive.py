#!/usr/bin/env python3
r"""
mw_archive.py — MW-ARCHIVE (Mnemonic Warden) — Forge-side read-only continuity tool

DOCTRINE (NON-NEGOTIABLE)
- Runs in Forge, reads the Vault (markdown + YAML frontmatter), emits diagnostics to stdout.
- NEVER mutates Vault files.
- NEVER invents memory. It only reports what exists and where.
- Enforces recall integrity: provenance, lineage, drift, phantom references.

USAGE
  python avm_ops/scripts/mw_archive.py lineage
  python avm_ops/scripts/mw_archive.py recall "<query or vault-relative path>"
  python avm_ops/scripts/mw_archive.py diff --scope "<vault-relative folder>" [--max 200]
  python avm_ops/scripts/mw_archive.py continuity [--lookback 10]

CONFIG
  Set VAULT_ROOT to your Anacostia Vault absolute path (recommended).
    Windows (PowerShell):
      $env:VAULT_ROOT="C:\USERS\DIGITALSCORPYUN\SANKOFA_TEMPLE\ANACOSTIA"
  Optionally set HANDOFF_DIR_REL (vault-relative) to override default.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml


DEFAULT_HANDOFF_DIR_REL = "war_council/avm_syndicate/agents/handoffs"
DEFAULT_REQUIRED_KEYS = {
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
    "grok_ctx_reflection",  # note: some legacy notes may use ctx_grok_reflection
    "quotes",
    "adinkra",
    "linked_notes",
    "external_refs",
    "review_date",
}


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass(frozen=True)
class NoteFrontmatter:
    path: Path  # absolute path on disk
    rel_path: str  # vault-relative path
    fm: Dict[str, Any]


def _fatal(msg: str, code: int = 2) -> None:
    print(f"MW-ARCHIVE: ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def _warn(msg: str) -> None:
    print(f"MW-ARCHIVE: WARN: {msg}")


def _info(msg: str) -> None:
    print(f"MW-ARCHIVE: {msg}")


def get_vault_root() -> Path:
    vault_root = os.environ.get("VAULT_ROOT", "").strip()
    if not vault_root:
        _fatal(
            "VAULT_ROOT is not set. Set it to your Anacostia Vault root path.\n"
            'Example (PowerShell): $env:VAULT_ROOT="C:\\USERS\\DIGITALSCORPYUN\\SANKOFA_TEMPLE\\ANACOSTIA"'
        )
    root = Path(vault_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        _fatal(f"VAULT_ROOT does not exist or is not a directory: {root}")
    return root


def vault_abs(vault_root: Path, rel_path: str) -> Path:
    # Normalize slashes but preserve relative semantics
    rel_path = rel_path.strip().lstrip("/\\")
    return (vault_root / rel_path).resolve()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def parse_frontmatter(md_text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Returns (frontmatter_dict_or_none, body_text)
    """
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


def coerce_grok_reflection_key(fm: Dict[str, Any]) -> Dict[str, Any]:
    """
    Some notes use ctx_grok_reflection; the 22-field law uses grok_ctx_reflection.
    We don't mutate; we only normalize for inspection.
    """
    if "grok_ctx_reflection" not in fm and "ctx_grok_reflection" in fm:
        fm = dict(fm)
        fm["grok_ctx_reflection"] = fm.get("ctx_grok_reflection")
    return fm


def load_note(vault_root: Path, rel_path: str) -> NoteFrontmatter:
    abs_path = vault_abs(vault_root, rel_path)
    if not abs_path.exists():
        _fatal(f"Note not found: {rel_path} (resolved: {abs_path})")
    if abs_path.is_dir():
        _fatal(f"Expected a file, got a directory: {rel_path}")

    text = read_text(abs_path)
    fm, _body = parse_frontmatter(text)
    if fm is None:
        _fatal(f"No YAML frontmatter found in: {rel_path}")
    fm = coerce_grok_reflection_key(fm)
    return NoteFrontmatter(path=abs_path, rel_path=rel_path.replace("\\", "/"), fm=fm)


def iter_md_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.md"):
        # Ignore dot dirs if any
        if any(part.startswith(".") for part in p.parts):
            continue
        yield p


def rel_to_vault(vault_root: Path, abs_path: Path) -> str:
    try:
        return abs_path.relative_to(vault_root).as_posix()
    except ValueError:
        return abs_path.as_posix()


def is_handoff_note(fm: Dict[str, Any]) -> bool:
    cat = str(fm.get("category", "")).strip().lower()
    return cat == "session_logs" or "handoff" in str(fm.get("title", "")).lower()


def parse_isoish(ts: Any) -> str:
    """
    We avoid hard parsing; we keep strings stable and compare lexicographically when possible.
    """
    if ts is None:
        return ""
    return str(ts).strip().strip("'").strip('"')


def sort_key_by_updated(note: NoteFrontmatter) -> Tuple[str, str]:
    updated = parse_isoish(note.fm.get("updated"))
    created = parse_isoish(note.fm.get("created"))
    return (updated or created, created)


def validate_required_keys(fm: Dict[str, Any], required: set[str]) -> List[str]:
    missing = [k for k in sorted(required) if k not in fm]
    return missing


def wikilink_targets(body: str) -> List[str]:
    """
    Extract wikilink targets. Keeps alias form "path|alias" but returns raw target before alias.
    """
    out: List[str] = []
    for m in WIKILINK_RE.finditer(body):
        raw = m.group(1).strip()
        target = raw.split("|", 1)[0].strip()
        if target:
            out.append(target)
    return out


def resolve_wikilink_to_path(vault_root: Path, target: str) -> Optional[Path]:
    """
    Resolve a wikilink target to an existing markdown file:
    - If target includes '/', treat as vault-relative path candidate (with or without .md)
    - Else search by filename match under vault root (first hit)
    """
    target = target.strip().lstrip("/\\")
    if not target:
        return None

    # Remove .md if present for resolution logic
    no_ext = target[:-3] if target.lower().endswith(".md") else target

    # Path-like
    if "/" in no_ext or "\\" in no_ext:
        cand = vault_abs(vault_root, no_ext)
        if cand.exists() and cand.is_file():
            return cand
        cand_md = cand.with_suffix(".md")
        if cand_md.exists() and cand_md.is_file():
            return cand_md
        return None

    # Filename-only search (first match)
    # NOTE: This can be ambiguous; MW-ARCHIVE reports ambiguity, does not decide truth.
    needle = f"{no_ext}.md"
    hits = []
    for p in iter_md_files(vault_root):
        if p.name.lower() == needle.lower():
            hits.append(p)
            if len(hits) >= 5:
                break
    if not hits:
        return None
    if len(hits) > 1:
        _warn(
            f"Ambiguous wikilink '{target}' matches multiple files. "
            f"First match used for existence-check only. Hits: "
            + ", ".join(rel_to_vault(vault_root, h) for h in hits)
        )
    return hits[0]


def cmd_lineage(vault_root: Path) -> int:
    handoff_dir_rel = (
        os.environ.get("HANDOFF_DIR_REL", DEFAULT_HANDOFF_DIR_REL).strip()
        or DEFAULT_HANDOFF_DIR_REL
    )
    handoff_dir = vault_abs(vault_root, handoff_dir_rel)
    if not handoff_dir.exists():
        _fatal(
            f"Handoff directory not found: {handoff_dir_rel} (resolved: {handoff_dir})"
        )

    notes: List[NoteFrontmatter] = []
    for p in iter_md_files(handoff_dir):
        text = read_text(p)
        fm, _body = parse_frontmatter(text)
        if not fm:
            continue
        fm = coerce_grok_reflection_key(fm)
        if is_handoff_note(fm):
            notes.append(
                NoteFrontmatter(path=p, rel_path=rel_to_vault(vault_root, p), fm=fm)
            )

    if not notes:
        _fatal(f"No handoff notes detected under: {handoff_dir_rel}")

    notes.sort(key=sort_key_by_updated, reverse=True)
    latest = notes[0]

    _info("LINEAGE — latest terminal handoff (disk-truth):")
    _info(f"  rel_path: {latest.rel_path}")
    _info(f"  title:    {latest.fm.get('title', '')}")
    _info(f"  id:       {latest.fm.get('id', '')}")
    _info(f"  status:   {latest.fm.get('status', '')}")
    _info(f"  updated:  {latest.fm.get('updated', '')}")
    _info(f"  created:  {latest.fm.get('created', '')}")

    missing = validate_required_keys(latest.fm, DEFAULT_REQUIRED_KEYS)
    if missing:
        _warn(f"Frontmatter missing keys ({len(missing)}): {', '.join(missing)}")
    else:
        _info("  frontmatter: 22-field shape present (or normalized)")

    # Extra: check that linked_notes exist on disk (no mutation)
    ln = latest.fm.get("linked_notes", [])
    if isinstance(ln, list) and ln:
        _info("  linked_notes existence check:")
        for item in ln:
            item_s = str(item).strip()
            if not item_s:
                continue
            # strip [[...]] if user stored as wikilinks
            item_s = item_s.strip("[]")
            resolved = resolve_wikilink_to_path(vault_root, item_s)
            if resolved is None:
                _warn(f"    MISSING: {item_s}")
            else:
                _info(f"    OK: {item_s} -> {rel_to_vault(vault_root, resolved)}")
    else:
        _warn("  linked_notes is empty or not a list (continuity risk)")

    return 0


def cmd_recall(vault_root: Path, query: str, max_hits: int) -> int:
    query = query.strip()
    if not query:
        _fatal("Recall requires a non-empty query string.")

    # If user passed a vault-relative path, try direct load first
    if query.endswith(".md") and ("/" in query or "\\" in query):
        try:
            note = load_note(vault_root, query)
            _info("RECALL — direct path resolved:")
            _info(f"  rel_path: {note.rel_path}")
            _info(f"  title:    {note.fm.get('title', '')}")
            _info(f"  id:       {note.fm.get('id', '')}")
            _info(f"  status:   {note.fm.get('status', '')}")
            return 0
        except SystemExit:
            # fall through to search mode
            pass

    # Search by filename or title substring in frontmatter
    hits: List[Tuple[int, str, str]] = []  # score, rel_path, title
    q = query.lower()

    for p in iter_md_files(vault_root):
        rp = rel_to_vault(vault_root, p)
        score = 0

        # filename signal
        if q in p.stem.lower():
            score += 3
        if q in p.name.lower():
            score += 2

        # frontmatter title signal
        text = read_text(p)
        fm, _body = parse_frontmatter(text)
        if fm:
            fm = coerce_grok_reflection_key(fm)
            title = str(fm.get("title", "")).lower()
            if q in title:
                score += 5
        else:
            title = ""

        if score > 0:
            hits.append((score, rp, str(fm.get("title", "")) if fm else ""))

    if not hits:
        _info(f"RECALL — no matches for: {query}")
        return 0

    hits.sort(key=lambda t: t[0], reverse=True)
    _info(f"RECALL — top matches for: {query}")
    for score, rp, title in hits[:max_hits]:
        label = f"{rp}"
        if title:
            label += f"  |  title: {title}"
        _info(f"  [{score}] {label}")

    return 0


def cmd_diff(vault_root: Path, scope_rel: str, max_files: int) -> int:
    """
    Drift/phantom scan across a folder:
    - missing frontmatter
    - missing required keys
    - broken wikilinks
    """
    scope_rel = scope_rel.strip().lstrip("/\\")
    scope_abs = vault_abs(vault_root, scope_rel)
    if not scope_abs.exists() or not scope_abs.is_dir():
        _fatal(f"Scope folder not found: {scope_rel} (resolved: {scope_abs})")

    files = list(iter_md_files(scope_abs))
    if not files:
        _info(f"DIFF — no markdown files under scope: {scope_rel}")
        return 0

    files = files[:max_files]
    _info(f"DIFF — scanning scope: {scope_rel} (files scanned: {len(files)})")

    missing_frontmatter = 0
    missing_keys_total = 0
    broken_links_total = 0

    for p in files:
        rp = rel_to_vault(vault_root, p)
        text = read_text(p)
        fm, body = parse_frontmatter(text)

        if fm is None:
            missing_frontmatter += 1
            _warn(f"{rp}: missing YAML frontmatter")
            continue

        fm = coerce_grok_reflection_key(fm)
        missing = validate_required_keys(fm, DEFAULT_REQUIRED_KEYS)
        if missing:
            missing_keys_total += 1
            _warn(f"{rp}: missing keys -> {', '.join(missing)}")

        # broken wikilinks in body
        targets = wikilink_targets(body)
        for t in targets:
            resolved = resolve_wikilink_to_path(vault_root, t)
            if resolved is None:
                broken_links_total += 1
                _warn(f"{rp}: broken wikilink -> [[{t}]]")

    _info("DIFF — summary")
    _info(f"  missing_frontmatter_files: {missing_frontmatter}")
    _info(f"  files_missing_required_keys: {missing_keys_total}")
    _info(f"  broken_wikilinks_found: {broken_links_total}")

    return 0


def cmd_continuity(vault_root: Path, lookback: int) -> int:
    """
    Continuity check over last N handoffs:
    - ordering sanity
    - terminal status
    - required keys present
    """
    handoff_dir_rel = (
        os.environ.get("HANDOFF_DIR_REL", DEFAULT_HANDOFF_DIR_REL).strip()
        or DEFAULT_HANDOFF_DIR_REL
    )
    handoff_dir = vault_abs(vault_root, handoff_dir_rel)
    if not handoff_dir.exists():
        _fatal(
            f"Handoff directory not found: {handoff_dir_rel} (resolved: {handoff_dir})"
        )

    notes: List[NoteFrontmatter] = []
    for p in iter_md_files(handoff_dir):
        text = read_text(p)
        fm, _body = parse_frontmatter(text)
        if not fm:
            continue
        fm = coerce_grok_reflection_key(fm)
        if is_handoff_note(fm):
            notes.append(
                NoteFrontmatter(path=p, rel_path=rel_to_vault(vault_root, p), fm=fm)
            )

    if not notes:
        _fatal("No handoff notes found for continuity scan.")

    notes.sort(key=sort_key_by_updated, reverse=True)
    window = notes[: max(1, lookback)]

    _info(f"CONTINUITY — last {len(window)} handoffs (newest → oldest):")
    problems = 0

    prev_key: Optional[Tuple[str, str]] = None
    for n in window:
        key = sort_key_by_updated(n)
        title = str(n.fm.get("title", ""))
        status = str(n.fm.get("status", ""))
        updated = str(n.fm.get("updated", ""))
        rp = n.rel_path

        line = f"- {updated} | {status} | {rp} | {title}"
        _info(line)

        missing = validate_required_keys(n.fm, DEFAULT_REQUIRED_KEYS)
        if missing:
            problems += 1
            _warn(f"  -> missing keys: {', '.join(missing)}")

        if status.lower() != "terminal" and status.lower() != "active":
            problems += 1
            _warn(f"  -> unusual status value: {status}")

        if prev_key is not None:
            # Lexicographic compare; if timestamps are consistent ISO-ish this holds.
            if key > prev_key:
                problems += 1
                _warn(
                    "  -> ordering anomaly (timestamp sort inconsistency). Check updated/created formatting."
                )
        prev_key = key

    if problems == 0:
        _info(
            "CONTINUITY — GREEN: no structural continuity breaches detected in scan window."
        )
    else:
        _warn(
            f"CONTINUITY — AMBER: {problems} issues detected. MW-ARCHIVE recommends reconciliation before expansion."
        )

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mw_archive.py",
        description="MW-ARCHIVE (Mnemonic Warden) — read-only continuity + recall diagnostics",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser(
        "lineage", help="Show latest handoff + basic schema/linked_notes checks"
    )

    recall = sub.add_parser(
        "recall", help="Search by title/filename, or load a vault-relative path"
    )
    recall.add_argument(
        "query", type=str, help="Query string or vault-relative path to a note"
    )
    recall.add_argument(
        "--max", type=int, default=10, help="Max hits to display (default 10)"
    )

    diff = sub.add_parser(
        "diff", help="Drift/phantom scan across a vault folder (read-only)"
    )
    diff.add_argument(
        "--scope", type=str, required=True, help="Vault-relative folder path to scan"
    )
    diff.add_argument(
        "--max", type=int, default=200, help="Max files scanned (default 200)"
    )

    cont = sub.add_parser("continuity", help="Continuity scan across last N handoffs")
    cont.add_argument(
        "--lookback",
        type=int,
        default=10,
        help="How many handoffs to scan (default 10)",
    )

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    vault_root = get_vault_root()

    if args.cmd == "lineage":
        return cmd_lineage(vault_root)
    if args.cmd == "recall":
        return cmd_recall(vault_root, args.query, args.max)
    if args.cmd == "diff":
        return cmd_diff(vault_root, args.scope, args.max)
    if args.cmd == "continuity":
        return cmd_continuity(vault_root, args.lookback)

    _fatal(f"Unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

