def generate_note(title, content):
    # Define the file path to your vault's root
    file_path = f"C:/Users/digitalscorpyun/sankofa_temple/Anacostia/{title.lower().replace(' ', '_')}.md"
    note = f"# {title}\n\n{content}\n"
    with open(file_path, "w") as f:
        f.write(note)
    return f"Note '{title}' created successfully."

# Example usage
print(generate_note("Sample Note", "This is a test note for AVM Syndicate."))