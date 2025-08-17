import requests

def query_ai_service(prompt):
    """
    Queries the AI service for help.
    """
    try:
        response = requests.post("http://127.0.0.1:5000/api/v1/chat", json={"prompt": prompt})
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.RequestException as e:
        return f"Error connecting to AI service: {e}"

def troubleshoot_error(error_message):
    """
    Provides troubleshooting steps for a given error message.
    """
    if "permission denied" in error_message.lower():
        return "It looks like you don't have the necessary permissions. Try running the command with 'sudo'."
    elif "not found" in error_message.lower():
        return "A command or file was not found. Check for typos and ensure the program is installed and in your system's PATH."
    else:
        # If no specific rule matches, consult the AI
        ai_prompt = f"How do I fix this error in my terminal?:\n\n{error_message}"
        return query_ai_service(ai_prompt)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(troubleshoot_error(" ".join(sys.argv[1:])))
