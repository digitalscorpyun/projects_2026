# wx_chess_analyst.py — CANONICAL PRODUCTION ARBITER (v3.7)
# ROLE: Engine Arbitration + Verdict Assignment + LLM Pedagogical Synthesis
# FEATURES:
#   - Stockfish quantitative analysis
#   - SAN-normalized move evaluation
#   - Verdict classification (Pristine / Gritty / WIP)
#   - HARD OPENING SILENCE (opening names forbidden)
# STATUS: PRODUCTION / GOVERNANCE-LOCKED

import io
import os
import re
from datetime import datetime
from typing import Tuple, List

import pytz
import yaml
import chess.pgn
import chess.engine

from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference

LOCAL_TZ = pytz.timezone("America/Los_Angeles")
USER_HANDLE = "digitalscorpyun"
DEFAULT_MODEL = "ibm/granite-3-3-8b-instruct"
CP_THRESHOLD = 150


def now_iso() -> str:
    return datetime.now(LOCAL_TZ).isoformat()


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def split_frontmatter(md: str) -> Tuple[str, str]:
    parts = md.split("---", 2)
    if len(parts) < 3:
        raise RuntimeError("No valid YAML frontmatter found.")
    return parts[1].strip(), parts[2].strip()


def extract_raw_pgn(md_content: str) -> str:
    m = re.search(
        r"##\s*Raw PGN\s*.*?```(?:\w+)?\n(.*?)\n```",
        md_content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not m:
        raise RuntimeError("Raw PGN block not found.")
    return m.group(1).strip()


def get_user_perspective(pgn_text: str) -> Tuple[str, str, str]:
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    white_player = game.headers.get("White", "Unknown")
    black_player = game.headers.get("Black", "Unknown")
    result = game.headers.get("Result", "*")
    if USER_HANDLE.lower() in white_player.lower():
        return "White", black_player, result
    return "Black", white_player, result


def run_engine_analysis(
    pgn_text: str, user_color: str
) -> Tuple[List[str], List[str], int]:
    sf_path = os.getenv("STOCKFISH_PATH")
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    board = game.board()
    full_log, blunder_report = [], []
    max_drop, prev_score = 0, 0
    is_user_white = user_color == "White"

    print("Digital Arbiter (Stockfish) generating quantitative truth...")
    with chess.engine.SimpleEngine.popen_uci(sf_path) as engine:
        for i, move in enumerate(game.mainline_moves()):
            san_move = board.san(move)
            move_num = (i // 2) + 1
            full_notation = (
                f"{move_num}. {san_move}" if i % 2 == 0 else f"{move_num}... {san_move}"
            )
            board.push(move)
            info = engine.analyse(board, chess.engine.Limit(time=0.1))
            current_score_obj = info["score"].pov(
                chess.WHITE if is_user_white else chess.BLACK
            )
            current_score = current_score_obj.score(mate_score=10000)

            is_user_turn = (i % 2 == 0 and is_user_white) or (
                i % 2 != 0 and not is_user_white
            )
            if is_user_turn:
                delta = current_score - prev_score
                if delta <= -CP_THRESHOLD:
                    drop_val = abs(delta)
                    max_drop = max(max_drop, drop_val)
                    blunder_report.append(
                        f"CRITICAL ERROR: Move {full_notation} (Score dropped by {drop_val}cp to {current_score}cp)"
                    )
            full_log.append(f"{full_notation} (Score: {current_score})")
            prev_score = current_score
    return full_log, blunder_report, max_drop


def determine_verdict(user_color: str, result: str, max_drop: int) -> str:
    user_won = (user_color == "White" and result == "1-0") or (
        user_color == "Black" and result == "0-1"
    )
    if user_won:
        return "Pristine Mastery" if max_drop < CP_THRESHOLD else "Gritty Recovery"
    elif result == "1/2-1/2":
        return "Solid"
    return "Work-in-Progress"


def build_prompt(
    pgn_text: str,
    full_log: List[str],
    blunders: List[str],
    user_color: str,
    opponent: str,
    verdict: str,
) -> str:
    log_dump = "\n".join(full_log)
    blunder_dump = (
        "\n".join(blunders) if blunders else "No significant blunders detected."
    )
    return f"""
[INST] <<SYS>>
You are the "Maurice Ashley of Altadena" — a pedagogical Chess Logic Processor.
User: {USER_HANDLE} | Color: {user_color} | Target: {opponent}

GOVERNANCE:
1. VERDICT: The official verdict is "{verdict}". You are FORBIDDEN from using any other tag.
2. HARD OPENING SILENCE: You are FORBIDDEN from naming, identifying, or attributing any opening by name (e.g., "Polish Defense", "A40", "Queen's Gambit"). Only describe the start of the game generically as "the opening phase."
3. NOTATION: Use provided SAN notation (e.g. 4. Nb5) exactly.
<</SYS>>

PGN:
{pgn_text}

ENGINE BLUNDER REPORT:
{blunder_dump}

FULL EVAL LOG:
{log_dump}

OUTPUT STRUCTURE:
### Maurice Ashley's Game Breakdown
**Perspective:** {user_color} ({USER_HANDLE})
**Verdict:** {verdict}
**Verdict Logic:** [Justify why "{verdict}" was assigned based on the Engine Blunder Report]

### The Tactical Transition
[Describe the shift in evaluation without naming an opening.]

### Critical Engine-Flagged Errors
[Factual analysis of blunders identified in the report.]

### Altadena Training Protocol
[2 improvement steps based on the blunders.]
[/INST]
""".strip()


def granite_analyze(prompt: str) -> str:
    creds = Credentials(
        api_key=os.getenv("WATSONX_APIKEY"), url=os.getenv("WATSONX_URL")
    )
    model = ModelInference(
        model_id=os.getenv("WX_GRANITE_MODEL_ID", DEFAULT_MODEL),
        credentials=creds,
        project_id=os.getenv("WATSONX_PROJECT_ID"),
        params={
            "max_new_tokens": 1200,
            "decoding_method": "greedy",
            "temperature": 0.0,
        },
    )
    response = model.generate(prompt)
    return response.get("results", [{}])[0].get("generated_text", "").strip()


def main() -> None:
    print("✶⌁✶ MAURICE ASHLEY PROTOCOL (V3.7 - CANONICAL) INITIATED")
    p_input = input("Path to game note (.md): ").strip().strip('"').strip("'")
    md_text = read_text(p_input)
    pgn_text = extract_raw_pgn(md_text)
    user_color, opponent, result = get_user_perspective(pgn_text)
    full_log, blunder_report, max_drop = run_engine_analysis(pgn_text, user_color)
    verdict = determine_verdict(user_color, result, max_drop)
    print(f"Verdict: {verdict}. Synthesizing final analysis...")
    prompt = build_prompt(
        pgn_text, full_log, blunder_report, user_color, opponent, verdict
    )
    analysis = granite_analyze(prompt)
    yml_text, body = split_frontmatter(md_text)
    data = yaml.safe_load(yml_text)
    data["longform_summary"] = f"<<MAURICE ASHLEY>>\n\n{analysis}\n\n[/MAURICE ASHLEY]"
    data["updated"] = now_iso()
    write_text(
        p_input,
        f"---\n{yaml.dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False, width=1000).strip()}\n---\n\n{body}",
    )
    print("✓ Canonical Analysis successfully injected. Production Ready.")


if __name__ == "__main__":
    main()

