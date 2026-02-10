#!/usr/bin/env python3
# ==============================================================================
# ✶⌁✶ pgn_ingest.py — SAN FIGURINE ENGINE v0.1.0 [ARTIFACT LAW]
# ==============================================================================
# ROLE: PGN → Vault Game Ingestion (Figurine SAN + Raw PGN Preservation)
# ENGINE: Deterministic Logic (Python 3.10+)
# DOMAIN: Anacostia Chess / War Council
# COMPLIANCE: ANACOSTIA-22-FIELD-LAW / VS-ENC-V1.2.1-INHERITANCE
# LINT-STATUS: OPERATOR-VERIFIED
#
# DOCTRINE (NON-NEGOTIABLE)
# - Runs in Forge.
# - Reads PGN input.
# - Emits Markdown artifacts into the Vault.
# - Does NOT analyze, judge, or evaluate moves.
# - Preserves both figurine SAN and raw PGN as historical record.
# ==============================================================================

import os
import re
import io
from datetime import datetime

import pytz
import chess
import chess.pgn

VAULT = r"C:\Users\digitalscorpyun\sankofa_temple\Anacostia\liberal_arts\personal_development\chess\games"
LOCAL_TZ = pytz.timezone("America/Los_Angeles")

# --------------------------------------------------------
# Helpers
# --------------------------------------------------------


def snake(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def parse_pgn(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_field(tag: str, pgn: str, default=None):
    m = re.search(rf'\[{tag} "([^"]+)"\]', pgn)
    return m.group(1) if m else default


def extract_eco(pgn: str) -> str:
    eco = extract_field("ECO", pgn, "unknown")
    return eco.lower() if eco else "unknown"


def next_sequence(date_str: str) -> str:
    existing = [
        f for f in os.listdir(VAULT) if f.startswith(date_str) and f.endswith(".md")
    ]

    nums = []
    for f in existing:
        parts = f.split("_")
        if len(parts) > 1 and parts[1].isdigit():
            nums.append(int(parts[1]))

    nxt = max(nums) + 1 if nums else 1
    return f"{nxt:03d}"


def iso_timestamp() -> str:
    return datetime.now(LOCAL_TZ).isoformat()


# --------------------------------------------------------
# Figurine Map
# --------------------------------------------------------

FIGS = {
    "K": "♔",
    "Q": "♕",
    "R": "♖",
    "B": "♗",
    "N": "♘",
    "P": "♙",
    "k": "♚",
    "q": "♛",
    "r": "♜",
    "b": "♝",
    "n": "♞",
    "p": "♟",
}


def to_figurines(san: str) -> str:
    return "".join(FIGS.get(ch, ch) for ch in san)


# --------------------------------------------------------
# SAN + Figurine Movetext Builder
# --------------------------------------------------------


def convert_movetext_to_san_figurines(pgn_text: str) -> str:
    cleaned = re.sub(r"\{\[%emt.*?\]\}", "", pgn_text)

    game = chess.pgn.read_game(io.StringIO(cleaned))
    if not game:
        return "Could not parse PGN."

    board = game.board()
    san_lines = []
    move_number = 1
    pair = []

    for move in game.mainline_moves():
        san = board.san(move)
        san = to_figurines(san)
        pair.append(san)

        if len(pair) == 2:
            san_lines.append(f"{move_number}. {pair[0]}  {pair[1]}")
            move_number += 1
            pair = []

        board.push(move)

    if pair:
        san_lines.append(f"{move_number}. {pair[0]}")

    return "\n".join(san_lines)


# --------------------------------------------------------
# Main Ingestion
# --------------------------------------------------------


def ingest_pgn(path: str) -> str:
    pgn = parse_pgn(path)

    date_raw = extract_field("Date", pgn)
    year, month, day = date_raw.split(".")
    date_str = f"{year}{month}{day}"
    date_iso = f"{year}-{month}-{day}"

    opponent_raw = extract_field("Black", pgn, "opponent")
    opponent = snake(opponent_raw)

    result_tag = extract_field("Result", pgn, "*")
    if result_tag == "1-0":
        result = "win"
    elif result_tag == "0-1":
        result = "loss"
    else:
        result = "draw"

    eco = extract_eco(pgn)
    opening = extract_field("Opening", pgn, "unknown")

    seq = next_sequence(date_str)
    filename = f"{date_str}_{seq}_{opponent}_{result}_{eco}.md"
    out_path = os.path.join(VAULT, filename)

    yaml_block = f"""---
id: "{date_str}_{seq}"
title: "{filename[:-3]}"
category: war_council
style: ScorpyunStyle
path: war_council/chess/games/{filename}
created: {iso_timestamp()}
updated: {iso_timestamp()}
status: active
priority: normal

summary: |
  Game played on {date_iso} vs {opponent_raw} ({result.upper()}). ECO: {eco.upper()}.

longform_summary: |
  Placeholder for full engine-assisted analysis once agentic routines activate.

analysis_status: pending
errors: []
mistakes: []
error_patterns: []
key_moments: []

tags:
  - chess
  - games
  - {eco}
  - {opponent}

cssclasses:
  - tyrian-purple

synapses:
  - chess_index
  - chess_error_taxonomy

opponent: "{opponent_raw}"
color: "white"
eco: "{eco.upper()}"
opening: "{opening}"
result: "{result}"
date: "{date_iso}"
sequence: "{seq}"

linked_notes:
  - chess_error_taxonomy
  - chess_training_rituals
  - chess_opening_repertoire
  - chess_tactical_archive

review_date: 2026-06-09
---
"""

    readable = convert_movetext_to_san_figurines(pgn)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(yaml_block)
        f.write("\n## Movetext (Figurine SAN)\n```\n")
        f.write(readable)
        f.write("\n```\n\n")
        f.write("## Raw PGN\n```\n")
        f.write(pgn)
        f.write("\n```\n")

    return out_path


# --------------------------------------------------------
# Quoted / Unquoted Path Support
# --------------------------------------------------------

if __name__ == "__main__":
    p = input("Path to PGN: ").strip()
    if (p.startswith('"') and p.endswith('"')) or (
        p.startswith("'") and p.endswith("'")
    ):
        p = p[1:-1]

    print("Created:", ingest_pgn(p))
