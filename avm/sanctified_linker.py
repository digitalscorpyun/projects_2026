#!/usr/bin/env python3
"""

sanctified_linker.py – v1.1.0
AVM Ops: Sacred-Tech Linking Ritual CLI
Adds scanning and suggestion logic without modifying .md files.
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime
from rapidfuzz import fuzz

__version__ = "1.1.0"


def parse_args():
    parser = argparse.ArgumentParser(
        prog="sanctified_linker",
        description="Sanctified Linker Ritual – Suggest Obsidian links without writing changes"
    )
    parser.add_argument(
        "--version", action="version", version=__version__,
        help="Show program version and exit"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        required=True,
        help="Similarity threshold for conceptual linking (0.0–1.0)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (verbose logging)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry-run; generate suggestion log without writing changes"
    )
    parser.add_argument(
        "--vault-path",
        type=str,
        required=True,
        help="Path to the Anacostia Vault folder"
    )
    return parser.parse_args()


def setup_logging(debug: bool):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def gather_notes(vault: Path):
    notes = list(vault.rglob('*.md'))
    titles = {note.stem: note for note in notes}
    return notes, titles


def suggest_links(notes, titles, threshold):
    suggestions = []
    for note in notes:
        content = note.read_text(encoding='utf-8')
        for title, path in titles.items():
            if path == note:
                continue
            score = fuzz.token_set_ratio(title, content) / 100.0
            if score >= threshold:
                suggestions.append((note, title, score))
            else:
                logging.debug(f"LINK_SKIP: {note.name} -> {title} (score {score:.2f})")
    return suggestions


def write_log(vault: Path, suggestions):
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = vault / f"link_suggestions_{timestamp}.log"
    with log_file.open('w', encoding='utf-8') as f:
        for note, title, score in suggestions:
            f.write(f"SUGGEST: {note.name} -> [[{title}]] (score {score:.2f})\n")
    logging.info(f"Suggestion log written to {log_file}")


def main():
    args = parse_args()
    setup_logging(args.debug)
    logging.info(f"Sanctified Linker v{__version__} starting...")

    vault = Path(args.vault_path)
    if not vault.exists() or not vault.is_dir():
        logging.error(f"Vault path invalid: {vault}")
        sys.exit(1)

    notes, titles = gather_notes(vault)
    logging.info(f"Found {len(notes)} markdown notes for analysis.")

    suggestions = suggest_links(notes, titles, args.threshold)
    logging.info(f"Generated {len(suggestions)} link suggestions.")

    write_log(vault, suggestions)

    logging.info("Sanctified Linker completed (no files modified).")

if __name__ == "__main__":
    main()
