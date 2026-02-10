import os
import json
import sys

VAULT_ROOT = r"C:\Users\digitalscorpyun\sankofa_temple\Anacostia"
MANIFEST_PATH = (
    r"C:\Users\digitalscorpyun\projects_2025\avm_ops\anacostia_library_batch.json"
)

# The full 21-field schema
YAML_FIELDS = {
    "id": "no_id_provided",
    "title": "no_title_provided",
    "category": "anacostia_library",
    "style": "ScorpyunStyle",
    "path": "",
    "created": "",
    "updated": "",
    "status": "active",
    "priority": "normal",
    "summary": "Summary not yet generated.",
    "longform_summary": "Longform summary not yet generated.",
    "tags": ["reading_system", "library"],
    "cssclasses": ["tyrian-purple"],
    "synapses": ["no_synapses_added"],
    "key_themes": ["theme_not_identified"],
    "bias_analysis": "Bias analysis not yet generated.",
    "grok_ctx_reflection": "Context reflection not yet generated.",
    "quotes": ["No quotes captured yet."],
    "adinkra": "duafe",
    "linked_notes": ["none_linked_yet"],
    "review_date": "not_scheduled",
}


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def merge_yaml(json_yaml):
    """Ensure all 21 fields exist and contain text."""
    merged = {}

    for key, default in YAML_FIELDS.items():
        if key in json_yaml:
            val = json_yaml[key]

            # convert empty lists to list with text
            if isinstance(val, list) and len(val) == 0:
                merged[key] = default
            elif isinstance(val, str) and val.strip() == "":
                merged[key] = default
            else:
                merged[key] = val
        else:
            merged[key] = default

    return merged


def write_note(note_obj):
    relative_path = note_obj["path"]
    filename = note_obj["filename"]

    full_dir = os.path.join(VAULT_ROOT, os.path.dirname(relative_path))
    full_path = os.path.join(full_dir, filename)

    ensure_dir(full_dir)

    yaml_source = note_obj["yaml"]
    merged_yaml = merge_yaml(yaml_source)

    yaml_lines = ["---"]
    for key, value in merged_yaml.items():
        if isinstance(value, list):
            yaml_lines.append(f"{key}:")
            for item in value:
                yaml_lines.append(f"  - {item}")
        else:
            yaml_lines.append(f'{key}: "{value}"')
    yaml_lines.append("---\n")

    yaml_block = "\n".join(yaml_lines)

    body = note_obj["body"]

    if os.path.exists(full_path):
        print(f"[SKIPPED] Already exists: {full_path}")
        return

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(yaml_block)
        f.write(body)

    print(f"[OK] Created: {full_path}")


def main():
    if not os.path.exists(MANIFEST_PATH):
        print(f"ERROR: Manifest not found: {MANIFEST_PATH}")
        sys.exit(1)

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        notes = json.load(f)

    print(f"Loaded {len(notes)} notes.")
    print("Writing…\n")

    for note in notes:
        write_note(note)

    print("\nDone. All notes processed.\n")


if __name__ == "__main__":
    main()
