import sys
import os

def create_file(path, content=""):
    """Creates a new file with optional content."""
    try:
        with open(path, 'w') as f:
            f.write(content)
        return f"Successfully created file: {path}"
    except Exception as e:
        return f"Error creating file: {e}"

def read_file(path):
    """Reads the content of a file."""
    try:
        with open(path, 'r') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def write_to_file(path, content):
    """Writes content to a file, overwriting existing content."""
    try:
        with open(path, 'w') as f:
            f.write(content)
        return f"Successfully wrote to file: {path}"
    except Exception as e:
        return f"Error writing to file: {e}"

def delete_file(path):
    """Deletes a file."""
    try:
        os.remove(path)
        return f"Successfully deleted file: {path}"
    except Exception as e:
        return f"Error deleting file: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: file.py <action> <path> [content]")
        sys.exit(1)

    action = sys.argv[1]
    path = sys.argv[2]

    if action == "create":
        content = sys.argv[3] if len(sys.argv) > 3 else ""
        print(create_file(path, content))
    elif action == "read":
        print(read_file(path))
    elif action == "write":
        if len(sys.argv) < 4:
            print("Usage: file.py write <path> <content>")
            sys.exit(1)
        content = " ".join(sys.argv[3:])
        print(write_to_file(path, content))
    elif action == "delete":
        print(delete_file(path))
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)
