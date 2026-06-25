#!/usr/bin/env python3
# ==============================================================================
# ✶⌁✶ net_plus_drill_1.py — OSI DRILL ENGINE v0.1.1 [HARDENED]
# ==============================================================================
# ROLE: Terminal-based Network+ OSI reflex drill.
# ENGINE: Deterministic Logic (Python 3.10+)
# COMPLIANCE: CodeRitual / Network+ Study Drill
# JURISDICTION: Anacostia Vault / Forge — Technical Study Infrastructure
# PURPOSE: Build OSI reflexes: layer order, purpose, protocols/devices, PDUs.
# ==============================================================================

from __future__ import annotations

import argparse
import random
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# ==============================================================================
# CORE KNOWLEDGE BASE
# ==============================================================================

@dataclass(frozen=True)
class Layer:
    num: int
    name: str
    purpose: str
    pdu: str


LAYERS: List[Layer] = [
    Layer(7, "Application", "User-facing network services", "Data"),
    Layer(6, "Presentation", "Encryption, compression, formatting", "Data"),
    Layer(5, "Session", "Session setup/management/teardown", "Data"),
    Layer(4, "Transport", "End-to-end delivery, ports, reliability", "Segment/Datagram"),
    Layer(3, "Network", "Logical addressing and routing", "Packet"),
    Layer(2, "Data Link", "MAC addressing, framing, local delivery", "Frame"),
    Layer(1, "Physical", "Signals, media, bits on the wire", "Bits"),
]


ITEM_TO_LAYER: Dict[str, int] = {
    # Layer 7 — Application
    "http": 7,
    "https": 7,
    "dns": 7,
    "ftp": 7,
    "sftp": 7,
    "smtp": 7,
    "pop3": 7,
    "imap4": 7,
    "rdp": 7,
    "ssh": 7,
    "telnet": 7,
    "snmp": 7,

    # Layer 6 — Presentation
    "tls": 6,
    "ssl": 6,
    "encryption": 6,
    "compression": 6,
    "formatting": 6,

    # Layer 4 — Transport
    "tcp": 4,
    "udp": 4,
    "port": 4,
    "ports": 4,
    "segment": 4,
    "datagram": 4,

    # Layer 3 — Network
    "ip": 3,
    "icmp": 3,
    "router": 3,
    "routing": 3,
    "ip address": 3,
    "packet": 3,

    # Layer 2 — Data Link
    "mac": 2,
    "mac address": 2,
    "ethernet": 2,
    "802.11": 2,
    "wifi": 2,
    "wi-fi": 2,
    "switch": 2,
    "frame": 2,
    "arp": 2,

    # Layer 1 — Physical
    "cable": 1,
    "fiber": 1,
    "copper": 1,
    "radio": 1,
    "rf": 1,
    "bits": 1,
    "signal": 1,
    "signals": 1,
    "electrical signal": 1,
    "hub": 1,
    "repeater": 1,
}


ALIASES: Dict[str, str] = {
    "wi fi": "wifi",
    "wireless": "wifi",
    "80211": "802.11",

    "layer1": "1",
    "layer 1": "1",
    "l1": "1",

    "layer2": "2",
    "layer 2": "2",
    "l2": "2",

    "layer3": "3",
    "layer 3": "3",
    "l3": "3",

    "layer4": "4",
    "layer 4": "4",
    "l4": "4",

    "layer5": "5",
    "layer 5": "5",
    "l5": "5",

    "layer6": "6",
    "layer 6": "6",
    "l6": "6",

    "layer7": "7",
    "layer 7": "7",
    "l7": "7",

    "portable data unit": "protocol data unit",
    "protocol data units": "protocol data unit",
}


PURPOSE_KEYWORDS: Dict[int, set[str]] = {
    7: {"application", "user", "network", "services", "protocols"},
    6: {"encryption", "compression", "formatting", "translation", "presentation"},
    5: {"session", "setup", "management", "teardown", "dialog"},
    4: {"transport", "ports", "reliability", "delivery", "tcp", "udp"},
    3: {"routing", "logical", "addressing", "ip", "packet"},
    2: {"mac", "framing", "local", "ethernet", "switch", "frame"},
    1: {"signals", "signal", "media", "bits", "wire", "cable", "radio", "electrical", "light"},
}


PDU_ALIASES: Dict[int, set[str]] = {
    7: {"data"},
    6: {"data"},
    5: {"data"},
    4: {"segment", "datagram", "segments", "datagrams", "segment/datagram", "segment or datagram"},
    3: {"packet", "packets"},
    2: {"frame", "frames"},
    1: {"bit", "bits"},
}


LAYER_BY_NUM: Dict[int, Layer] = {layer.num: layer for layer in LAYERS}
LAYER_BY_NAME: Dict[str, Layer] = {layer.name.lower(): layer for layer in LAYERS}

MNEMONIC = "All People Seem To Need Data Processing"
MNEMONIC_ORDER = [
    "Application",
    "Presentation",
    "Session",
    "Transport",
    "Network",
    "Data Link",
    "Physical",
]


# ==============================================================================
# NORMALIZATION HELPERS
# ==============================================================================

def norm(value: str) -> str:
    """Normalize user input into a stable comparison string."""
    text = value.strip().lower()
    text = text.replace("/", " / ")
    text = re.sub(r"[^a-z0-9. /-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace(" / ", "/")

    return ALIASES.get(text, text)


def extract_layer_number(value: str) -> Optional[str]:
    """Accept '4', 'layer 4', 'Layer 4', 'l4', etc."""
    text = norm(value)

    if text in {"1", "2", "3", "4", "5", "6", "7"}:
        return text

    match = re.fullmatch(r"(?:layer|l)\s*([1-7])", text)
    if match:
        return match.group(1)

    return None


def parse_focus_list(value: Optional[str]) -> Optional[List[int]]:
    if not value:
        return None

    focus: list[int] = []

    for part in value.split(","):
        part = part.strip()

        if not part:
            continue

        if not part.isdigit():
            raise ValueError("Focus must be comma-separated layer numbers like 2,3,4")

        layer_num = int(part)

        if layer_num < 1 or layer_num > 7:
            raise ValueError("Layer numbers must be 1..7")

        focus.append(layer_num)

    return sorted(set(focus))


def pick_layer(focus: Optional[List[int]] = None) -> Layer:
    if focus:
        return LAYER_BY_NUM[random.choice(focus)]

    return random.choice(LAYERS)


def ask(prompt: str) -> str:
    return input(prompt).strip()


def example_item_for_layer(layer_num: int) -> str:
    for item, mapped_layer in ITEM_TO_LAYER.items():
        if mapped_layer == layer_num:
            return item.upper()

    return "N/A"


# ==============================================================================
# QUESTION FACTORIES
# ==============================================================================

def q_layer_name_from_num(layer: Layer) -> Tuple[str, str]:
    return f"Layer {layer.num} is called what? ", layer.name


def q_layer_num_from_name(layer: Layer) -> Tuple[str, str]:
    return f"What layer number is '{layer.name}'? ", str(layer.num)


def q_purpose_from_layer(layer: Layer) -> Tuple[str, str]:
    return f"What does Layer {layer.num} ({layer.name}) handle? (short) ", layer.purpose


def q_pdu_from_layer(layer: Layer) -> Tuple[str, str]:
    return f"PDU at Layer {layer.num} ({layer.name}) is called what? ", layer.pdu


def q_layer_from_item() -> Tuple[str, str]:
    item = random.choice(list(ITEM_TO_LAYER.keys()))
    layer_num = ITEM_TO_LAYER[item]
    layer = LAYER_BY_NUM[layer_num]

    return f"Which OSI layer for: '{item.upper()}'? (name or number) ", f"{layer.num}|{layer.name}"


def q_item_from_layer(layer: Layer) -> Tuple[str, str]:
    items = [item for item, mapped_layer in ITEM_TO_LAYER.items() if mapped_layer == layer.num]
    item = random.choice(items) if items else layer.name.lower()

    return f"Name ONE protocol/device/concept commonly at Layer {layer.num} ({layer.name}): ", item


# ==============================================================================
# ANSWER CHECKING
# ==============================================================================

def check_layer_answer(user: str, expected: str) -> Tuple[bool, str]:
    """Check answers where expected may be '7|Application' or just '4'."""
    user_norm = norm(user)
    user_layer_num = extract_layer_number(user)

    if "|" in expected:
        expected_num, expected_name = expected.split("|", 1)

        if user_layer_num == expected_num:
            return True, "OK"

        if user_norm == norm(expected_name):
            return True, "OK"

        return False, f"Expected {expected_num} ({expected_name})"

    if user_layer_num == expected:
        return True, "OK"

    if user_norm == norm(expected):
        return True, "OK"

    return False, f"Expected: {expected}"


def check_purpose_answer(user: str, layer: Layer) -> Tuple[bool, str]:
    """Fuzzy purpose matcher anchored to the actual layer."""
    user_norm = norm(user)
    tokens = set(re.findall(r"[a-z0-9.]+", user_norm))
    accepted = PURPOSE_KEYWORDS.get(layer.num, set())

    if tokens & accepted:
        return True, "OK (fuzzy)"

    if user_norm in norm(layer.purpose):
        return True, "OK (fuzzy)"

    return False, f"Expected: {layer.purpose}"


def check_pdu_answer(user: str, layer: Layer) -> Tuple[bool, str]:
    user_norm = norm(user)

    if user_norm in PDU_ALIASES.get(layer.num, set()):
        return True, "OK"

    return False, f"Expected: {layer.pdu}"


def check_item_from_layer(user: str, expected_layer_num: int) -> Tuple[bool, str]:
    item = norm(user)

    if item in ITEM_TO_LAYER and ITEM_TO_LAYER[item] == expected_layer_num:
        return True, "OK"

    return (
        False,
        f"Expected any item from Layer {expected_layer_num} "
        f"(e.g., {example_item_for_layer(expected_layer_num)})",
    )


def check_answer(user: str, expected: str, mode: str, layer: Optional[Layer] = None) -> Tuple[bool, str]:
    if mode in {"layer_name", "layer_num", "layer_from_item"}:
        return check_layer_answer(user, expected)

    if mode == "purpose":
        if layer is None:
            return False, "Internal error: missing layer for purpose check"

        return check_purpose_answer(user, layer)

    if mode == "pdu":
        if layer is None:
            return False, "Internal error: missing layer for PDU check"

        return check_pdu_answer(user, layer)

    if mode == "item_from_layer":
        return check_item_from_layer(user, int(expected))

    if norm(user) == norm(expected):
        return True, "OK"

    return False, f"Expected: {expected}"


# ==============================================================================
# DRILL RUNNER
# ==============================================================================

def build_factories(mode: str):
    factories = []

    if mode in ("mixed", "layers"):
        factories += [
            ("layer_name", q_layer_name_from_num),
            ("layer_num", q_layer_num_from_name),
        ]

    if mode in ("mixed", "purpose"):
        factories.append(("purpose", q_purpose_from_layer))

    if mode in ("mixed", "pdu"):
        factories.append(("pdu", q_pdu_from_layer))

    if mode in ("mixed", "protocols"):
        factories.append(("layer_from_item", lambda _layer=None: q_layer_from_item()))

    if mode in ("mixed", "reverse"):
        factories.append(("item_from_layer", q_item_from_layer))

    if not factories:
        raise ValueError(f"Unknown mode: {mode}")

    return factories


def print_hint(tag: str, expected: str, layer: Optional[Layer]) -> None:
    if tag == "layer_from_item":
        expected_num, expected_name = expected.split("|", 1)
        print(f"  Hint: It's Layer {expected_num} ({expected_name}).")
        return

    if tag == "pdu":
        print("  Hint: Data / Data / Data / Segment-or-Datagram / Packet / Frame / Bits.")
        return

    if tag == "purpose" and layer:
        print(f"  Hint: {layer.purpose}")
        return

    if tag in {"layer_name", "layer_num"} and layer:
        print(f"  Hint: Layer {layer.num} = {layer.name}.")
        print(f"  Mnemonic order: {', '.join(MNEMONIC_ORDER)}")
        return

    if tag == "item_from_layer" and layer:
        print(f"  Hint: Example item: {example_item_for_layer(layer.num)}")
        return

    print("  Hint unavailable.")


def run_drill(mode: str, rounds: int, focus: Optional[List[int]]) -> None:
    print("\n🛰️  OSI Drill Online")
    print(f"Mnemonic: {MNEMONIC}")
    print("Type 'hint' for help, 'skip' to pass, 'quit' to exit.\n")

    score = 0
    attempted = 0
    misses: List[str] = []
    factories = build_factories(mode)

    for question_num in range(1, rounds + 1):
        tag, factory = random.choice(factories)
        layer: Optional[Layer] = None

        if tag == "layer_from_item":
            prompt, expected = factory()
            expected_display = expected.replace("|", " ")
        else:
            layer = pick_layer(focus)
            prompt, expected = factory(layer)
            expected_display = expected

        if tag == "item_from_layer" and layer:
            expected = str(layer.num)
            expected_display = f"any Layer {layer.num} item"

        while True:
            user = ask(f"[{question_num}/{rounds}] {prompt}")
            user_norm = norm(user)

            if user_norm in {"quit", "q", "exit"}:
                print("\nExiting drill.")
                rounds = attempted
                break

            if user_norm == "hint":
                print_hint(tag, expected, layer)
                continue

            attempted += 1

            if user_norm == "skip":
                misses.append(f"Q{question_num} [{tag}] → {expected_display}")
                print(f"  ↪ Skipped. Answer: {expected_display}\n")
                break

            ok, message = check_answer(user, expected, tag, layer)

            if ok:
                score += 1
                print("  ✅ Correct.\n")
            else:
                misses.append(f"Q{question_num} [{tag}] you said '{user}' → {message}")
                print(f"  ❌ {message}\n")

            break

        if rounds == attempted and user_norm in {"quit", "q", "exit"}:
            break

    if attempted == 0:
        return

    percent = (score / attempted) * 100

    print("—" * 50)
    print(f"Score: {score}/{attempted} ({percent:.0f}%)")

    if misses:
        print("\nMiss log (review these):")
        for miss in misses[:25]:
            print(f" - {miss}")

        if len(misses) > 25:
            print(f" ... and {len(misses) - 25} more")
    else:
        print("\nClean run. No misses. 🦂")

    print("—" * 50)


# ==============================================================================
# ENTRYPOINT
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="OSI Drill (terminal quiz)")

    parser.add_argument(
        "--mode",
        default="mixed",
        choices=["mixed", "layers", "purpose", "pdu", "protocols", "reverse"],
        help="Quiz mode",
    )

    parser.add_argument(
        "--rounds",
        type=int,
        default=20,
        help="Number of questions",
    )

    parser.add_argument(
        "--focus",
        default=None,
        help="Comma-separated layer numbers to focus on, e.g. 2,3,4",
    )

    args = parser.parse_args()
    focus = parse_focus_list(args.focus)

    run_drill(args.mode, args.rounds, focus)


if __name__ == "__main__":
    main()