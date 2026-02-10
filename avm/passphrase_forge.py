import secrets

# -------------------------------
# Curated word pools
# -------------------------------

AFRICANA_WORDS = [
    "Sankofa", "Anacostia", "Douglass", "Griot", "Kemet",
    "Diaspora", "Maroon", "Abolition", "Reconstruction",
    "PanAfrican", "Freedom", "Lineage", "Archive", "Liberation"
]

TECH_WORDS = [
    "Kernel", "Cipher", "Protocol", "Entropy", "Firewall",
    "Algorithm", "Hash", "Token", "Daemon", "Runtime",
    "Virtual", "Packet", "Cloud", "Network", "Secure"
]

SEPARATORS = ["-", "_", ".", ":", "@", "#"]
DIGITS = "0123456789"
SYMBOLS = "!$%&*+="


def generate_passphrase():
    rng = secrets.SystemRandom()

    afr = rng.choice(AFRICANA_WORDS)
    tech = rng.choice(TECH_WORDS)

    sep1 = rng.choice(SEPARATORS)
    sep2 = rng.choice(SEPARATORS)

    digits = "".join(rng.choice(DIGITS) for _ in range(3))
    symbol = rng.choice(SYMBOLS)

    # Capitalization variance
    if rng.choice([True, False]):
        afr = afr.upper()
    if rng.choice([True, False]):
        tech = tech.lower()

    passphrase = f"{afr}{sep1}{tech}{sep2}{digits}{symbol}"

    return passphrase


if __name__ == "__main__":
    print("\nGenerated Passphrase:\n")
    print(generate_passphrase())
    print("\n⚠️  Memorize or store securely. No recovery possible.\n")
