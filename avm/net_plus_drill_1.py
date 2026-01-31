#!/usr/bin/env python3
"""
OSI Drill — terminal flashcards + quizzes
Goal: build OSI reflexes (layer order, purpose, protocols/devices, PDUs).

Usage:
  python osi_drill.py
Optional:
  python osi_drill.py --mode mixed --rounds 25
  python osi_drill.py --mode pdu --rounds 15
  python osi_drill.py --mode protocols --focus 2,3,4
"""

from __future__ import annotations
import argparse
import random
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

# ----------------------------
# Core knowledge base
# ----------------------------

@dataclass(frozen=True)
class Layer:
    num: int
    name: str
    purpose: str
    pdu: str

LAYERS: List[Layer] = [
    Layer(7, "Application",   "User-facing network services",              "Data"),
    Layer(6, "Presentation",  "Encryption, compression, formatting",       "Data"),
    Layer(5, "Session",       "Session setup/management/teardown",         "Data"),
    Layer(4, "Transport",     "End-to-end delivery, ports, reliability",   "Segment/Datagram"),
    Layer(3, "Network",       "Logical addressing and routing",            "Packet"),
    Layer(2, "Data Link",     "MAC addressing, framing, local delivery",   "Frame"),
    Layer(1, "Physical",      "Signals, media, bits on the wire",          "Bits"),
]

# Protocols / technologies / concepts mapped to an OSI layer
# Note: Some items can be debated (e.g., TLS/SSL often sits "between" layers).
# For exam drilling, we anchor to common cert conventions.
ITEM_TO_LAYER: Dict[str, int] = {
    # L7
    "http": 7, "https": 7, "dns": 7, "ftp": 7, "sftp": 7, "smtp": 7, "pop3": 7, "imap4": 7,
    "rdp": 7, "ssh": 7, "telnet": 7, "snmp": 7,
    # L6
    "tls": 6, "ssl": 6,
    # L4
    "tcp": 4, "udp": 4, "port": 4, "ports": 4,
    # L3
    "ip": 3, "icmp": 3, "router": 3, "routing": 3, "ip address": 3,
    # L2
    "mac": 2, "mac address": 2, "ethernet": 2, "802.11": 2, "wifi": 2, "wi-fi": 2,
    "switch": 2, "frame": 2, "arp": 2,
    # L1
    "cable": 1, "fiber": 1, "copper": 1, "radio": 1, "rf": 1, "bits": 1, "hub": 1, "repeater": 1,
}

# Some quick synonyms / accepted answers
ALIASES: Dict[str, str] = {
    "wi fi": "wifi",
    "80211": "802.11",
    "layer1": "1", "layer2": "2", "layer3": "3", "layer4": "4", "layer5": "5", "layer6": "6", "layer7": "7",
    "l1": "1", "l2": "2", "l3": "3", "l4": "4", "l5": "5", "l6": "6", "l7": "7",
}

LAYER_BY_NUM: Dict[int, Layer] = {l.num: l for l in LAYERS}
LAYER_BY_NAME: Dict[str, Layer] = {l.name.lower(): l for l in LAYERS}

MNEMONIC = "All People Seem To Need Data Processing"
MNEMONIC_ORDER = ["Application", "Presentation", "Session", "Transport", "Network", "Data Link", "Physical"]

# ----------------------------
# Helpers
# ----------------------------

def norm(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    # apply aliases
    if s in ALIASES:
        s = ALIASES[s]
    return s

def parse_focus_list(s: Optional[str]) -> Optional[List[int]]:
    if not s:
        return None
    out = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit():
            raise ValueError("Focus must be comma-separated layer numbers like 2,3,4")
        n = int(part)
        if n < 1 or n > 7:
            raise ValueError("Layer numbers must be 1..7")
        out.append(n)
    return sorted(set(out))

def pick_layer(focus: Optional[List[int]] = None) -> Layer:
    if focus:
        return LAYER_BY_NUM[random.choice(focus)]
    return random.choice(LAYERS)

def ask(prompt: str) -> str:
    return input(prompt).strip()

# ----------------------------
# Quiz modes
# ----------------------------

def q_layer_name_from_num(layer: Layer) -> Tuple[str, str]:
    prompt = f"Layer {layer.num} is called what? "
    answer = layer.name
    return prompt, answer

def q_layer_num_from_name(layer: Layer) -> Tuple[str, str]:
    prompt = f"What layer number is '{layer.name}'? "
    answer = str(layer.num)
    return prompt, answer

def q_purpose_from_layer(layer: Layer) -> Tuple[str, str]:
    prompt = f"What does Layer {layer.num} ({layer.name}) handle? (short) "
    answer = layer.purpose
    return prompt, answer

def q_pdu_from_layer(layer: Layer) -> Tuple[str, str]:
    prompt = f"PDU at Layer {layer.num} ({layer.name}) is called what? "
    answer = layer.pdu
    return prompt, answer

def q_layer_from_item() -> Tuple[str, str]:
    item = random.choice(list(ITEM_TO_LAYER.keys()))
    layer_num = ITEM_TO_LAYER[item]
    layer = LAYER_BY_NUM[layer_num]
    prompt = f"Which OSI layer for: '{item.upper()}'? (name or number) "
    answer = f"{layer.num}|{layer.name}"
    return prompt, answer

def q_item_from_layer(layer: Layer) -> Tuple[str, str]:
    items = [k for k, v in ITEM_TO_LAYER.items() if v == layer.num]
    item = random.choice(items) if items else layer.name.lower()
    prompt = f"Name ONE protocol/device/concept commonly at Layer {layer.num} ({layer.name}): "
    answer = item
    return prompt, answer

def check_answer(user: str, expected: str, mode: str) -> Tuple[bool, str]:
    u = norm(user)

    # expected may be "7|Application" or a literal string
    if "|" in expected:
        parts = expected.split("|")
        exp_num = parts[0]
        exp_name = parts[1].lower()
        if u == exp_num or u == exp_name:
            return True, "OK"
        return False, f"Expected {exp_num} ({parts[1]})"

    # For "purpose" questions, accept keyword-ish matches (not strict)
    if mode == "purpose":
        exp = expected.lower()
        # Require at least two meaningful keywords present
        keywords = [w for w in re.findall(r"[a-z]+", exp) if len(w) >= 5]
        hits = sum(1 for w in set(keywords) if w in u)
        if hits >= 2 or u in exp:
            return True, "OK (fuzzy)"
        return False, f"Expected: {expected}"

    # For "pdu", accept some synonyms
    if mode == "pdu":
        exp = expected.lower()
        if exp == "segment/datagram":
            if u in {"segment", "datagram", "segment/datagram", "segment or datagram"}:
                return True, "OK"
        if u == exp:
            return True, "OK"
        return False, f"Expected: {expected}"

    # For "item_from_layer" accept any correct item for that layer
    if mode == "item_from_layer":
        # user gives an item; validate layer match
        item = u
        if item in ITEM_TO_LAYER and ITEM_TO_LAYER[item] == int(expected):
            return True, "OK"
        return False, f"Expected any item from Layer {expected} (e.g., {example_item_for_layer(int(expected))})"

    # strict otherwise
    if u == norm(expected):
        return True, "OK"
    return False, f"Expected: {expected}"

def example_item_for_layer(layer_num: int) -> str:
    for k, v in ITEM_TO_LAYER.items():
        if v == layer_num:
            return k.upper()
    return "N/A"

# ----------------------------
# Drill runner
# ----------------------------

def run_drill(mode: str, rounds: int, focus: Optional[List[int]]):
    print("\n🛰️  OSI Drill Online")
    print(f"Mnemonic: {MNEMONIC}")
    print("Type 'hint' for help, 'skip' to pass, 'quit' to exit.\n")

    score = 0
    misses: List[str] = []

    # Build question factories per mode
    factories = []
    if mode in ("mixed", "layers"):
        factories += [("layer_name", q_layer_name_from_num), ("layer_num", q_layer_num_from_name)]
    if mode in ("mixed", "purpose"):
        factories += [("purpose", q_purpose_from_layer)]
    if mode in ("mixed", "pdu"):
        factories += [("pdu", q_pdu_from_layer)]
    if mode in ("mixed", "protocols"):
        factories += [("layer_from_item", lambda _=None: q_layer_from_item())]
    if mode in ("mixed", "reverse"):
        factories += [("item_from_layer", q_item_from_layer)]

    if not factories:
        raise ValueError(f"Unknown mode: {mode}")

    for i in range(1, rounds + 1):
        tag, fn = random.choice(factories)

        if tag == "layer_from_item":
            prompt, expected = fn()
            expected_display = expected.replace("|", " ")
        else:
            layer = pick_layer(focus)
            prompt, expected = fn(layer)
            expected_display = expected

        # special expected encoding for item_from_layer: store layer_num
        if tag == "item_from_layer":
            expected = str(layer.num)  # layer number as validator

        while True:
            user = ask(f"[{i}/{rounds}] {prompt}")
            u = norm(user)

            if u in {"quit", "q", "exit"}:
                print("\nExiting drill.")
                rounds = i - 1
                i = rounds
                break

            if u == "hint":
                if tag == "layer_from_item":
                    parts = expected.split("|")
                    print(f"  Hint: It's Layer {parts[0]} ({parts[1]}).")
                elif tag == "pdu":
                    print("  Hint: Think Data / Segment / Packet / Frame / Bits.")
                elif tag == "purpose":
                    print(f"  Hint: {layer.purpose}")
                elif tag in {"layer_name", "layer_num"}:
                    print(f"  Hint: {MNEMONIC_ORDER[7-layer.num]} is not right—remember top→bottom.")
                    print(f"  Mnemonic order: {', '.join(MNEMONIC_ORDER)}")
                elif tag == "item_from_layer":
                    print(f"  Hint: Example item: {example_item_for_layer(layer.num)}")
                continue

            if u == "skip":
                misses.append(f"Q{i} [{tag}] → {expected_display}")
                print(f"  ↪ Skipped. Answer: {expected_display}\n")
                break

            ok, msg = check_answer(user, expected, tag if tag in {"purpose","pdu","item_from_layer"} else tag)
            if ok:
                score += 1
                print("  ✅ Correct.\n")
            else:
                misses.append(f"Q{i} [{tag}] you said '{user}' → {msg}")
                print(f"  ❌ {msg}\n")
            break

    if rounds == 0:
        return

    pct = (score / rounds) * 100
    print("—" * 50)
    print(f"Score: {score}/{rounds} ({pct:.0f}%)")
    if misses:
        print("\nMiss log (review these):")
        for m in misses[:25]:
            print(f" - {m}")
        if len(misses) > 25:
            print(f" ... and {len(misses) - 25} more")
    else:
        print("\nClean run. No misses. 🦂")
    print("—" * 50)

def main():
    parser = argparse.ArgumentParser(description="OSI Drill (terminal quiz)")
    parser.add_argument("--mode", default="mixed",
                        choices=["mixed", "layers", "purpose", "pdu", "protocols", "reverse"],
                        help="Quiz mode")
    parser.add_argument("--rounds", type=int, default=20, help="Number of questions")
    parser.add_argument("--focus", default=None,
                        help="Comma-separated layer numbers to focus on, e.g. 2,3,4")
    args = parser.parse_args()

    focus = parse_focus_list(args.focus)
    run_drill(args.mode, args.rounds, focus)

if __name__ == "__main__":
    main()
