"""
chess_analyze.py — Post-Ingest YAML Enricher (Anacostia Compliant)

Purpose:
- Read an existing game note produced by pgn_ingest.py
- Extract Raw PGN
- Run lightweight heuristic analysis (no engine required)
- Write back YAML fields:
  analysis_status, errors, mistakes, error_patterns, key_moments

Refactor Notes:
- Human-friendly default: if no CLI args are provided, prompt for a note path.
- Accepts quoted/unquoted paths.
- Resolves relative paths safely (relative to current working directory).
- Validates existence of note path and games dir before processing.
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pytz
import yaml
import chess
import chess.pgn

LOCAL_TZ = pytz.timezone("America/Los_Angeles")

DEFAULT_GAMES_DIR = r"C:\Users\digitalscorpyun\sankofa_temple\Anacostia\liberal_arts\personal_development\chess"


# ----------------------------
# Utilities
# ----------------------------


def now_iso() -> str:
    return datetime.now(LOCAL_TZ).isoformat()


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def split_frontmatter(md: str) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Returns (yaml_text, body_text, fence) where fence is '---' or None.
    """
    if not md.startswith("---"):
        return None, md, None
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", md, flags=re.DOTALL)
    if not m:
        return None, md, None
    return m.group(1), m.group(2), "---"


def dump_yaml(data: Dict[str, Any]) -> str:
    # Keep order as inserted; PyYAML preserves dict order in modern Python.
    return yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=88,
    ).strip()


def extract_raw_pgn(md_body: str) -> Optional[str]:
    """
    Extract the PGN inside the '## Raw PGN' fenced block.
    """
    m = re.search(r"##\s*Raw PGN\s*\n```(?:\w+)?\n(.*?)\n```", md_body, flags=re.DOTALL)
    if not m:
        return None
    return m.group(1).strip()


def io_from_text(text: str):
    import io

    return io.StringIO(text)


def normalize_path(p: str) -> str:
    """
    - Strips wrapping quotes
    - Expands ~
    - Normalizes separators
    - Makes absolute if relative (based on current working directory)
    """
    p = p.strip()
    if (p.startswith('"') and p.endswith('"')) or (
        p.startswith("'") and p.endswith("'")
    ):
        p = p[1:-1].strip()

    p = os.path.expanduser(p)
    p = os.path.normpath(p)

    if not os.path.isabs(p):
        p = os.path.abspath(p)

    return p


def prompt_for_note_path() -> str:
    p = input("Path to game note (.md): ").strip()
    return normalize_path(p)


# ----------------------------
# Heuristic Analysis
# ----------------------------


@dataclass
class AnalysisResult:
    errors: List[str]
    mistakes: List[str]
    error_patterns: List[str]
    key_moments: List[Dict[str, Any]]


CANON_ERRORS = {
    "opening drift",
    "premature queen",
    "king exposure",
    "late castling",
    "undeveloped minors",
    "queen trade too early",
}


def _count_developed_minors(board: chess.Board, color: bool) -> int:
    """
    Count minor pieces (N,B) moved off starting squares for given color.
    """
    if color == chess.WHITE:
        start_squares = {chess.B1, chess.G1, chess.C1, chess.F1}
    else:
        start_squares = {chess.B8, chess.G8, chess.C8, chess.F8}

    developed = 0
    for sq in start_squares:
        piece = board.piece_at(sq)
        if piece is None:
            # piece moved away or captured => developed
            developed += 1
    return developed


def analyze_game(game: chess.pgn.Game) -> AnalysisResult:
    board = game.board()

    errors: List[str] = []
    mistakes: List[str] = []
    patterns: List[str] = []
    key_moments: List[Dict[str, Any]] = []

    queen_moves_white = 0
    queen_moves_black = 0
    early_queen_trade = False
    king_moved_early = False

    OPENING_PLIES = 16  # 8 moves each side

    move_index = 0

    for move in game.mainline_moves():
        move_index += 1
        san = board.san(move)
        is_capture = board.is_capture(move)
        gives_check = board.gives_check(move)

        captured_piece = None
        if is_capture:
            cap_sq = move.to_square
            captured_piece = board.piece_at(cap_sq)

        mover = board.piece_at(move.from_square)
        if mover and mover.piece_type == chess.QUEEN:
            if mover.color == chess.WHITE:
                queen_moves_white += 1
            else:
                queen_moves_black += 1

        # Detect castling (note: board.turn is the side to move BEFORE push)
        if board.is_castling(move):
            if board.turn == chess.WHITE:
                key_moments.append(
                    {"ply": move_index, "san": san, "note": "White castled"}
                )
            else:
                key_moments.append(
                    {"ply": move_index, "san": san, "note": "Black castled"}
                )

        # Detect early king move (non-castle)
        if mover and mover.piece_type == chess.KING and not board.is_castling(move):
            if move_index <= OPENING_PLIES:
                king_moved_early = True
                key_moments.append(
                    {"ply": move_index, "san": san, "note": "King moved early"}
                )

        # Detect early queen trade (simplified): queen captured in opening window
        if (
            is_capture
            and captured_piece
            and captured_piece.piece_type == chess.QUEEN
            and move_index <= OPENING_PLIES
        ):
            early_queen_trade = True
            key_moments.append(
                {"ply": move_index, "san": san, "note": "Queen traded early"}
            )

        if gives_check:
            key_moments.append({"ply": move_index, "san": san, "note": "Check"})

        board.push(move)

    # Mate key moment
    end_board = game.end().board()
    if end_board.is_checkmate():
        key_moments.append(
            {"ply": move_index, "san": "(checkmate)", "note": "Game ended in mate"}
        )

    # Opening heuristics: evaluate at ply OPENING_PLIES (replay to that point)
    board2 = game.board()
    ply = 0
    castled_white_opening = False
    castled_black_opening = False

    for mv in game.mainline_moves():
        ply += 1
        if board2.is_castling(mv):
            if board2.turn == chess.WHITE:
                castled_white_opening = True
            else:
                castled_black_opening = True
        board2.push(mv)
        if ply >= OPENING_PLIES:
            break

    dev_white = _count_developed_minors(board2, chess.WHITE)
    dev_black = _count_developed_minors(board2, chess.BLACK)

    # Rules (lightweight, explainable)
    if queen_moves_white >= 2 or queen_moves_black >= 2:
        errors.append("premature queen")
        patterns.append("early queen activation")
        mistakes.append("Multiple queen moves in the opening window (tempo risk).")

    if early_queen_trade:
        errors.append("queen trade too early")
        patterns.append("early simplification")
        mistakes.append(
            "Early queen trade detected in the opening window; verify it served development/king safety."
        )

    if (queen_moves_white >= 1 or queen_moves_black >= 1) and (
        dev_white <= 1 or dev_black <= 1
    ):
        errors.append("opening drift")
        patterns.append("development lag")
        mistakes.append(
            "Opening showed early queen involvement + low minor-piece development."
        )

    if not castled_white_opening:
        errors.append("late castling")
        patterns.append("king safety delayed")
        mistakes.append(
            "White did not castle within the opening window; ensure king safety plan is explicit."
        )
    if not castled_black_opening:
        errors.append("late castling")
        patterns.append("king safety delayed")
        mistakes.append(
            "Black did not castle within the opening window; ensure king safety plan is explicit."
        )

    if king_moved_early:
        errors.append("king exposure")
        patterns.append("king moved early")
        mistakes.append(
            "King moved early (non-castle) in the opening window; treat as risk unless forced."
        )

    if dev_white <= 1:
        errors.append("undeveloped minors")
        patterns.append("slow development")
        mistakes.append(
            "White minor-piece development is low by end of opening window."
        )
    if dev_black <= 1:
        errors.append("undeveloped minors")
        patterns.append("slow development")
        mistakes.append(
            "Black minor-piece development is low by end of opening window."
        )

    errors = sorted(set([e for e in errors if e in CANON_ERRORS]))
    patterns = sorted(set(patterns))
    mistakes = list(dict.fromkeys(mistakes))

    return AnalysisResult(
        errors=errors,
        mistakes=mistakes,
        error_patterns=patterns,
        key_moments=key_moments,
    )


# ----------------------------
# YAML Update Logic
# ----------------------------


def ensure_list_field(d: Dict[str, Any], key: str) -> None:
    if key not in d or d[key] is None:
        d[key] = []
    if not isinstance(d[key], list):
        d[key] = [d[key]]


def merge_unique(existing: List[Any], incoming: List[Any]) -> List[Any]:
    out = list(existing)
    for x in incoming:
        if x not in out:
            out.append(x)
    return out


def update_note_yaml(
    md_path: str, result: AnalysisResult, mark_complete: bool, overwrite: bool
) -> Dict[str, Any]:
    md = read_text(md_path)
    yml_text, body, fence = split_frontmatter(md)
    if not yml_text or fence != "---":
        raise RuntimeError("No YAML frontmatter found at top of note.")

    data = yaml.safe_load(yml_text) or {}
    if not isinstance(data, dict):
        raise RuntimeError("Frontmatter YAML is not a mapping/dict.")

    data["analysis_status"] = (
        "complete" if mark_complete else data.get("analysis_status", "pending")
    )
    data["updated"] = now_iso()

    for k in ["errors", "mistakes", "error_patterns", "key_moments"]:
        ensure_list_field(data, k)

    if overwrite:
        data["errors"] = result.errors
        data["mistakes"] = result.mistakes
        data["error_patterns"] = result.error_patterns
        data["key_moments"] = result.key_moments
    else:
        data["errors"] = merge_unique(data["errors"], result.errors)
        data["mistakes"] = merge_unique(data["mistakes"], result.mistakes)
        data["error_patterns"] = merge_unique(
            data["error_patterns"], result.error_patterns
        )
        data["key_moments"] = merge_unique(data["key_moments"], result.key_moments)

    new_front = dump_yaml(data)
    new_md = f"---\n{new_front}\n---\n\n{body}"
    write_text(md_path, new_md)
    return data


# ----------------------------
# CLI / Target Resolution
# ----------------------------


def iter_game_notes(games_dir: str) -> List[str]:
    paths: List[str] = []
    for name in os.listdir(games_dir):
        if name.lower().endswith(".md"):
            paths.append(os.path.join(games_dir, name))
    return sorted(paths)


def resolve_targets(args: argparse.Namespace) -> List[str]:
    """
    Priority:
    1) --note
    2) --all (uses --games-dir)
    3) interactive prompt for a .md path
    """
    if args.note:
        p = normalize_path(args.note)
        if not os.path.exists(p):
            raise FileNotFoundError(f"Note not found: {p}")
        return [p]

    if args.all:
        games_dir = normalize_path(args.games_dir)
        if not os.path.isdir(games_dir):
            raise FileNotFoundError(f"Games directory not found: {games_dir}")
        return iter_game_notes(games_dir)

    p = prompt_for_note_path()
    if not os.path.exists(p):
        raise FileNotFoundError(f"Note not found: {p}")
    return [p]


# ----------------------------
# Main
# ----------------------------


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Analyze chess game notes and write back YAML fields."
    )
    ap.add_argument("--note", help="Path to a single game note .md")
    ap.add_argument(
        "--games-dir", default=DEFAULT_GAMES_DIR, help="Directory containing game notes"
    )
    ap.add_argument(
        "--all", action="store_true", help="Analyze all notes in --games-dir"
    )
    ap.add_argument(
        "--complete", action="store_true", help="Set analysis_status to complete"
    )
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing fields instead of merging",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Print changes but do not write files"
    )
    args = ap.parse_args()

    targets = resolve_targets(args)

    for md_path in targets:
        md = read_text(md_path)
        yml_text, body, _fence = split_frontmatter(md)
        if not yml_text:
            print(f"SKIP (no YAML): {md_path}")
            continue

        pgn_text = extract_raw_pgn(body)
        if not pgn_text:
            print(f"SKIP (no Raw PGN block): {md_path}")
            continue

        game = chess.pgn.read_game(io_from_text(pgn_text))
        if not game:
            print(f"SKIP (PGN parse failed): {md_path}")
            continue

        res = analyze_game(game)

        if args.dry_run:
            print(f"\n== {os.path.basename(md_path)} ==")
            print("errors:", res.errors)
            print(
                "mistakes:", res.mistakes[:3], ("..." if len(res.mistakes) > 3 else "")
            )
            print("error_patterns:", res.error_patterns)
            print("key_moments:", len(res.key_moments))
            continue

        updated = update_note_yaml(
            md_path, res, mark_complete=args.complete, overwrite=args.overwrite
        )
        print(
            f"UPDATED: {md_path}  (errors={len(updated.get('errors', []))}, status={updated.get('analysis_status')})"
        )


if __name__ == "__main__":
    main()
