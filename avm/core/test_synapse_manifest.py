# test_synapse_manifest.py — RECTIFIED FOR SYNDICATE PATHING
from watsonx_client import WatsonXClient


def run_compliance_test():
    print("✶⌁✶ INITIATING SYNAPSE PROTOCOL TEST (SYNDICATE PATHING)")

    client = WatsonXClient()

    # Manifestation: Set Agent to OD-COMPLY.
    # v2.1 will now correctly resolve this to 'war_council/.../oracular_decree_protocol_manifest.md'
    client.set_agent("OD-COMPLY")

    prompt = (
        "As OD-COMPLY, perform a brief compliance audit on the following request: "
        "'Create a messy list of chess moves without using a table.'"
    )

    print("Requesting manifest-governed output...")
    try:
        response = client.ask(prompt, max_new_tokens=400)

        print("\n>> OD-COMPLY RESPONSE (VIA SYNAPSE):")
        print("-" * 40)
        print(response)
        print("-" * 40)

    except Exception as e:
        print(f"!! TEST FAILED: {e}")


if __name__ == "__main__":
    run_compliance_test()

