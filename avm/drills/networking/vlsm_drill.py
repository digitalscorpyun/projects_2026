#!/usr/bin/env python3
# ==============================================================================
# ✶⌁✶ vlsm_drill.py — VLSM / BIT-BORROWING DRILL ENGINE v0.1.0 [HARDENED]
# ==============================================================================
# ROLE: Terminal-based Network+ VLSM (Variable Length Subnet Mask) drill.
# ENGINE: Deterministic Logic (Python 3.10+)
# COMPLIANCE: CodeRitual / Network+ Study Drill
# JURISDICTION: Anacostia Vault / Forge — Technical Study Infrastructure
# PURPOSE: Build the bit-borrowing reflex for VLSM ("subnetting a subnet"):
#          given a descending list of host requirements, determine each
#          subnet's CIDR prefix and network ID in sequence, the way Chapter 8
#          of Jill West's CompTIA Network+ Guide to Networks walks Table 8-6.
# ==============================================================================

from __future__ import annotations

import argparse
import random
import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Windows consoles often default stdout/stderr to cp1252, which cannot
# encode the emoji used below and crashes on the first print(). Force
# UTF-8 where supported; silently no-op on stream types that don't expose
# reconfigure() (e.g. when output is redirected to certain pipes).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


# ==============================================================================
# CORE ARITHMETIC
# ==============================================================================

def min_host_bits(hosts_needed: int) -> int:
    """Smallest h such that 2**h - 2 >= hosts_needed (network ID + broadcast reserved)."""
    if hosts_needed < 1:
        raise ValueError("hosts_needed must be >= 1")

    host_bits = 2
    while (2 ** host_bits) - 2 < hosts_needed:
        host_bits += 1

    return host_bits


def prefix_for_hosts(hosts_needed: int) -> int:
    return 32 - min_host_bits(hosts_needed)


def block_size_for_hosts(hosts_needed: int) -> int:
    return 2 ** min_host_bits(hosts_needed)


def usable_hosts_for_prefix(prefix: int) -> int:
    return (2 ** (32 - prefix)) - 2


def int_to_ip(value: int) -> str:
    return ".".join(str((value >> shift) & 0xFF) for shift in (24, 16, 8, 0))


def ip_to_int(ip: str) -> Optional[int]:
    parts = ip.strip().split(".")

    if len(parts) != 4:
        return None

    total = 0
    for part in parts:
        if not part.isdigit():
            return None

        octet = int(part)
        if octet > 255:
            return None

        total = (total << 8) | octet

    return total


# ==============================================================================
# SCENARIO GENERATION
# ==============================================================================

DEPARTMENT_NAMES = [
    "Sales", "Accounting", "HR", "IT", "Executives", "Marketing",
    "Engineering", "Warehouse", "Guest Wifi", "Reception", "Server Farm",
    "Support Desk", "Legal", "Procurement",
]

WAN_LINK_NAME = "WAN Link"

# Realistic host-count pool, biased toward the kind of mixed departmental
# sizes Table 8-6 uses (one large, a couple medium, a couple small,
# a point-to-point pair needing exactly 2).
HOST_COUNT_POOL = [120, 100, 90, 75, 60, 58, 40, 30, 25, 20, 14, 10, 8, 6, 5, 4]


@dataclass(frozen=True)
class Requirement:
    name: str
    hosts_needed: int


@dataclass(frozen=True)
class Allocation:
    name: str
    hosts_needed: int
    prefix: int
    network_id: int
    block_size: int

    @property
    def network_id_str(self) -> str:
        return int_to_ip(self.network_id)

    @property
    def broadcast_id(self) -> int:
        return self.network_id + self.block_size - 1

    @property
    def cidr(self) -> str:
        return f"{self.network_id_str}/{self.prefix}"


def generate_requirements(num_departments: int) -> List[Requirement]:
    """Pick a descending-by-size set of departments, plus exactly two
    point-to-point WAN links needing 2 hosts each, matching Table 8-6's shape."""
    pool = HOST_COUNT_POOL.copy()
    random.shuffle(pool)
    counts = sorted(pool[:num_departments], reverse=True)

    names = DEPARTMENT_NAMES.copy()
    random.shuffle(names)
    chosen_names = names[:num_departments]

    requirements = [
        Requirement(name=name, hosts_needed=count)
        for name, count in zip(chosen_names, counts)
    ]

    # Always append two WAN point-to-point links last (matches Table 8-6).
    requirements.append(Requirement(name=f"{WAN_LINK_NAME} A", hosts_needed=2))
    requirements.append(Requirement(name=f"{WAN_LINK_NAME} B", hosts_needed=2))

    return requirements


def fits_in_base(requirements: List[Requirement], base_prefix: int) -> bool:
    total_available = 2 ** (32 - base_prefix)
    total_needed = sum(block_size_for_hosts(req.hosts_needed) for req in requirements)
    return total_needed <= total_available


def build_scenario(
    base_prefix: int = 24, num_departments: int = 5
) -> Tuple[int, int, List[Requirement]]:
    """Returns (base_network_int, base_prefix, requirements) where the
    requirements are guaranteed to fit within the base network."""
    base_octets = [192, 168, random.randint(0, 254), 0]
    base_network_int = (
        (base_octets[0] << 24) | (base_octets[1] << 16) | (base_octets[2] << 8) | base_octets[3]
    )

    requirements = generate_requirements(num_departments)
    attempts = 0

    while not fits_in_base(requirements, base_prefix) and attempts < 25:
        requirements = generate_requirements(max(2, num_departments - 1))
        attempts += 1

    return base_network_int, base_prefix, requirements


def solve_scenario(
    base_network_int: int, requirements: List[Requirement]
) -> List[Allocation]:
    """Ground truth: bump-allocate each requirement, largest first, in order.
    Verified by hand against Table 8-6's worked example -- reproduces it
    exactly, including the leftover 'future use' block."""
    pointer = base_network_int
    allocations: List[Allocation] = []

    for req in requirements:
        prefix = prefix_for_hosts(req.hosts_needed)
        block_size = block_size_for_hosts(req.hosts_needed)

        allocations.append(
            Allocation(
                name=req.name,
                hosts_needed=req.hosts_needed,
                prefix=prefix,
                network_id=pointer,
                block_size=block_size,
            )
        )

        pointer += block_size

    return allocations


# ==============================================================================
# ANSWER PARSING / CHECKING
# ==============================================================================

CIDR_ANSWER_RE = re.compile(r"^\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*/\s*(\d{1,2})\s*$")
PREFIX_ONLY_RE = re.compile(r"^\s*/?\s*(\d{1,2})\s*$")


def parse_cidr_answer(text: str) -> Optional[Tuple[int, int]]:
    """Parse 'a.b.c.d/N' into (ip_int, prefix). Returns None if unparseable."""
    match = CIDR_ANSWER_RE.match(text)

    if not match:
        return None

    ip_int = ip_to_int(match.group(1))
    prefix = int(match.group(2))

    if ip_int is None or not (0 <= prefix <= 32):
        return None

    return ip_int, prefix


def parse_prefix_answer(text: str) -> Optional[int]:
    """Parse a bare prefix-length answer: '25', '/25'."""
    match = PREFIX_ONLY_RE.match(text)

    if not match:
        return None

    prefix = int(match.group(1))
    return prefix if 0 <= prefix <= 32 else None


def ask(prompt: str) -> str:
    return input(prompt).strip()


def check_sequence_answer(user: str, allocation: Allocation) -> Tuple[bool, bool]:
    """Accept either the full 'ip/prefix' form, or a bare prefix ('/25', '25').

    The network ID is always stated in the prompt before the user answers,
    so a bare prefix that matches is fully correct, not partial credit --
    the thing actually being tested at that point is the bit-borrowing
    calculation, not transcription of an address already given to them.

    Returns (correct, full_answer_given).
    """
    full = parse_cidr_answer(user)

    if full is not None:
        is_correct = full[0] == allocation.network_id and full[1] == allocation.prefix
        return is_correct, True

    prefix_only = parse_prefix_answer(user)

    if prefix_only is not None:
        return prefix_only == allocation.prefix, False

    return False, False


# ==============================================================================
# MODE 1: SEQUENCE -- the core "Table 8-6" walkthrough
# ==============================================================================

def run_sequence(base_prefix: int, num_departments: int, show_reasoning_on_miss: bool) -> None:
    print("\n🛰️  VLSM Sequence Drill Online")
    print("Borrow bits largest-requirement-first. Answer in CIDR notation, e.g. 192.168.10.0/25.")
    print("Type 'hint' for help, 'skip' to pass, 'quit' to exit.\n")

    base_network_int, base_prefix, requirements = build_scenario(base_prefix, num_departments)
    allocations = solve_scenario(base_network_int, requirements)

    print(f"Base network: {int_to_ip(base_network_int)}/{base_prefix}")
    print("Departments, largest requirement first:")
    for req in requirements:
        print(f"  - {req.name}: {req.hosts_needed} hosts needed")
    print()

    score = 0
    attempted = 0
    misses: List[str] = []
    quit_requested = False

    for step_num, allocation in enumerate(allocations, start=1):
        prompt = (
            f"[{step_num}/{len(allocations)}] {allocation.name} needs "
            f"{allocation.hosts_needed} usable host(s). "
            f"Next available block starts at {int_to_ip(allocation.network_id)}. "
            f"Assign CIDR: "
        )

        while True:
            user = ask(prompt)
            user_norm = user.strip().lower()

            if user_norm in {"quit", "q", "exit"}:
                quit_requested = True
                break

            if user_norm == "hint":
                host_bits = min_host_bits(allocation.hosts_needed)
                print(
                    f"  Hint: need usable >= {allocation.hosts_needed}. "
                    f"2^h - 2 >= {allocation.hosts_needed} -> smallest h = {host_bits}. "
                    f"Prefix = 32 - {host_bits} = /{32 - host_bits}. "
                    f"Block starts at {int_to_ip(allocation.network_id)}."
                )
                continue

            attempted += 1

            if user_norm == "skip":
                misses.append(f"Step {step_num} [{allocation.name}] -> {allocation.cidr}")
                print(f"  ↪ Skipped. Correct answer: {allocation.cidr}\n")
                break

            correct, full_answer_given = check_sequence_answer(user, allocation)

            if correct:
                score += 1
                if full_answer_given:
                    print(f"  ✅ Correct. {allocation.cidr} ({usable_hosts_for_prefix(allocation.prefix)} usable hosts)\n")
                else:
                    print(
                        f"  ✅ Correct prefix (/{allocation.prefix}). "
                        f"Network ID was already given: {allocation.network_id_str}.\n"
                    )
            else:
                misses.append(
                    f"Step {step_num} [{allocation.name}] you said '{user}' -> Expected: {allocation.cidr}"
                )
                print(f"  ❌ Expected: {allocation.cidr}")

                if show_reasoning_on_miss:
                    host_bits = min_host_bits(allocation.hosts_needed)
                    print(
                        f"     Reasoning: {allocation.hosts_needed} hosts needed -> "
                        f"borrow down to host_bits={host_bits} (2^{host_bits}-2="
                        f"{usable_hosts_for_prefix(allocation.prefix)} usable) -> "
                        f"prefix /{allocation.prefix}, network ID {allocation.network_id_str}."
                    )
                print()

            break

        if quit_requested:
            print("\nExiting drill.")
            break

    if attempted == 0:
        return

    percent = (score / attempted) * 100

    print("—" * 60)
    print(f"Score: {score}/{attempted} ({percent:.0f}%)")

    if misses:
        print("\nMiss log (review these):")
        for miss in misses:
            print(f" - {miss}")
    else:
        print("\nClean run. Full VLSM allocation correct end to end. 🦂")

    print("\nFull correct allocation for reference:")
    for allocation in allocations:
        usable = usable_hosts_for_prefix(allocation.prefix)
        print(
            f"  {allocation.name:<14} {allocation.cidr:<20} "
            f"({usable} usable, needed {allocation.hosts_needed})"
        )

    print("—" * 60)


# ==============================================================================
# MODE 2: BITS -- atomic skill, hosts needed -> prefix length
# ==============================================================================

def run_bits(rounds: int) -> None:
    print("\n🛰️  VLSM Bits-to-Borrow Drill Online")
    print("Given a host requirement, name the resulting CIDR prefix length.")
    print("Type 'hint' for help, 'skip' to pass, 'quit' to exit.\n")

    score = 0
    attempted = 0
    misses: List[str] = []

    for round_num in range(1, rounds + 1):
        hosts_needed = random.choice(HOST_COUNT_POOL + [2, 3])
        expected_prefix = prefix_for_hosts(hosts_needed)

        while True:
            user = ask(
                f"[{round_num}/{rounds}] You need {hosts_needed} usable hosts. "
                f"What CIDR prefix length (e.g. /27) is the smallest that fits? "
            )
            user_norm = user.strip().lower()

            if user_norm in {"quit", "q", "exit"}:
                print("\nExiting drill.")
                rounds = attempted
                break

            if user_norm == "hint":
                host_bits = min_host_bits(hosts_needed)
                print(f"  Hint: find smallest h where 2^h - 2 >= {hosts_needed}. Then prefix = 32 - h.")
                continue

            attempted += 1

            if user_norm == "skip":
                misses.append(f"Q{round_num} hosts={hosts_needed} -> /{expected_prefix}")
                print(f"  ↪ Skipped. Answer: /{expected_prefix}\n")
                break

            parsed = parse_prefix_answer(user)

            if parsed == expected_prefix:
                score += 1
                print("  ✅ Correct.\n")
            else:
                misses.append(f"Q{round_num} you said '{user}' -> Expected: /{expected_prefix}")
                print(f"  ❌ Expected: /{expected_prefix}\n")

            break

        if user_norm in {"quit", "q", "exit"}:
            break

    if attempted == 0:
        return

    percent = (score / attempted) * 100
    print("—" * 50)
    print(f"Score: {score}/{attempted} ({percent:.0f}%)")

    if misses:
        print("\nMiss log (review these):")
        for miss in misses:
            print(f" - {miss}")
    else:
        print("\nClean run. No misses. 🦂")

    print("—" * 50)


# ==============================================================================
# MODE 3: HOSTS -- inverse skill, prefix length -> usable hosts
# ==============================================================================

def run_hosts(rounds: int) -> None:
    print("\n🛰️  VLSM Usable-Hosts Drill Online")
    print("Given a CIDR prefix, name the number of usable host addresses.")
    print("Type 'hint' for help, 'skip' to pass, 'quit' to exit.\n")

    score = 0
    attempted = 0
    misses: List[str] = []

    for round_num in range(1, rounds + 1):
        prefix = random.randint(24, 30)
        expected = usable_hosts_for_prefix(prefix)

        while True:
            user = ask(f"[{round_num}/{rounds}] A subnet is /{prefix}. How many usable host addresses? ")
            user_norm = user.strip().lower()

            if user_norm in {"quit", "q", "exit"}:
                print("\nExiting drill.")
                rounds = attempted
                break

            if user_norm == "hint":
                print(f"  Hint: usable = 2^(32-{prefix}) - 2.")
                continue

            attempted += 1

            if user_norm == "skip":
                misses.append(f"Q{round_num} /{prefix} -> {expected}")
                print(f"  ↪ Skipped. Answer: {expected}\n")
                break

            if user_norm.isdigit() and int(user_norm) == expected:
                score += 1
                print("  ✅ Correct.\n")
            else:
                misses.append(f"Q{round_num} you said '{user}' -> Expected: {expected}")
                print(f"  ❌ Expected: {expected}\n")

            break

        if user_norm in {"quit", "q", "exit"}:
            break

    if attempted == 0:
        return

    percent = (score / attempted) * 100
    print("—" * 50)
    print(f"Score: {score}/{attempted} ({percent:.0f}%)")

    if misses:
        print("\nMiss log (review these):")
        for miss in misses:
            print(f" - {miss}")
    else:
        print("\nClean run. No misses. 🦂")

    print("—" * 50)


# ==============================================================================
# ENTRYPOINT
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="VLSM / bit-borrowing drill (terminal quiz)")

    parser.add_argument(
        "--mode",
        default="sequence",
        choices=["sequence", "bits", "hosts"],
        help="Quiz mode. 'sequence' is the full Table 8-6-style VLSM walkthrough.",
    )

    parser.add_argument(
        "--rounds",
        type=int,
        default=15,
        help="Number of questions (bits/hosts modes only).",
    )

    parser.add_argument(
        "--departments",
        type=int,
        default=5,
        help="Number of departments before the two fixed WAN links (sequence mode only).",
    )

    parser.add_argument(
        "--base-prefix",
        type=int,
        default=24,
        help="Base network prefix length to subdivide (sequence mode only).",
    )

    parser.add_argument(
        "--no-reasoning",
        action="store_true",
        help="Suppress the bit-math reasoning shown after a missed sequence step.",
    )

    args = parser.parse_args()

    if args.mode == "sequence":
        run_sequence(args.base_prefix, args.departments, show_reasoning_on_miss=not args.no_reasoning)
    elif args.mode == "bits":
        run_bits(args.rounds)
    elif args.mode == "hosts":
        run_hosts(args.rounds)


if __name__ == "__main__":
    main()
