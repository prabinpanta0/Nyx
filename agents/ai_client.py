"""AI communication and response handling utilities."""

import json
import re
import requests
from typing import Tuple, Optional

# Constants
OLLAMA_API_URL = "http://localhost:11434/api/generate"


def stream_ai_response(prompt: str, model: str = "smollm2:1.7b") -> str:
    """Streams a simple text response from the AI."""
    try:
        response = requests.post(OLLAMA_API_URL, json={"model": model, "prompt": prompt, "stream": True}, stream=True)
        response.raise_for_status()

        full_response = ""
        for chunk in response.iter_lines():
            if not chunk:
                continue
            decoded_chunk = json.loads(chunk.decode("utf-8"))
            token = decoded_chunk.get("response", "")
            print(token, end="", flush=True)
            full_response += token
            if decoded_chunk.get("done"):
                break
        return full_response
    except requests.exceptions.RequestException as e:
        print(f"\nError connecting to Ollama: {e}")
        return ""


def _extract_from_fenced_block(text: str) -> Optional[str]:
    """Extract JSON from fenced code blocks."""
    # Try fenced code block first
    code_block = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if code_block:
        return code_block.group(1)

    # Generic fenced block (no language)
    code_block_generic = re.search(r"```\s*(\{[\s\S]*?\})\s*```", text)
    if code_block_generic:
        return code_block_generic.group(1)
    
    return None


def _should_skip_char(ch: str, esc: bool, in_str: bool) -> Tuple[bool, bool]:
    """Determine if character should be skipped and update escape/string state."""
    if esc:
        return True, False
    if ch == "\\":
        return True, True
    if ch == '"':
        return True, not in_str
    if in_str:
        return True, in_str
    return False, in_str


def _handle_opening_brace(i: int, depth: int) -> Tuple[int, int]:
    """Handle opening brace logic."""
    start = i if depth == 0 else -1
    return start, depth + 1


def _handle_closing_brace(text: str, i: int, depth: int, start: int) -> Tuple[Optional[str], int]:
    """Handle closing brace logic."""
    new_depth = depth - 1
    if new_depth == 0 and start != -1:
        return text[start : i + 1], new_depth
    return None, new_depth


def _update_string_state(ch: str, esc: bool, in_str: bool) -> Tuple[bool, bool]:
    """Update string parsing state based on current character."""
    if ch == '"' and not esc:
        return False, not in_str
    if ch == "\\":
        return not esc, in_str
    return False, in_str


from typing import Tuple, Optional, NamedTuple


class BraceState(NamedTuple):
    """State for brace tracking during JSON parsing."""
    depth: int
    start: int


def _process_brace_character(ch: str, i: int, state: BraceState, text: str) -> Tuple[Optional[str], BraceState]:
    """Process opening and closing braces, returning result if complete."""
    if ch == "{":
        new_start, new_depth = _handle_opening_brace(i, state.depth)
        return None, BraceState(new_depth, new_start)
    elif ch == "}":
        result, new_depth = _handle_closing_brace(text, i, state.depth, state.start)
        return result, BraceState(new_depth, state.start)
    return None, state


def _extract_with_balanced_braces(text: str) -> Optional[str]:
    """Extract JSON using balanced brace scanning."""
    in_str = False
    esc = False
    state = BraceState(depth=0, start=-1)
    
    for i, ch in enumerate(text):
        # Update string parsing state
        esc, in_str = _update_string_state(ch, esc, in_str)
        
        # Skip characters inside strings
        should_skip, _ = _should_skip_char(ch, esc, in_str)
        if should_skip:
            continue
            
        # Process braces
        result, state = _process_brace_character(ch, i, state, text)
        if result:
            return result
    
    return None


def extract_json_object(text: str) -> str:
    """Extract the first valid top-level JSON object from text.

    - Prefer content inside a fenced ```json code block
    - Otherwise scan for balanced braces outside of strings
    Returns the JSON string if found; else an error JSON string.
    """
    # Try fenced code blocks first
    result = _extract_from_fenced_block(text)
    if result:
        return result
    
    # Fall back to balanced brace scanning
    result = _extract_with_balanced_braces(text)
    if result:
        return result

    return '{"error": "Failed to extract JSON from AI response."}'


def extract_json_with_retry(text: str, max_retries: int = 2, model: str = "smollm2:1.7b") -> str:
    """Enhanced JSON extraction with retry mechanism."""
    # Try standard extraction first
    json_str = extract_json_object(text)
    
    # If it failed, try to get a better response
    if '"error"' in json_str and max_retries > 0:
        retry_prompt = f"""
The previous response contained invalid JSON. Please provide ONLY a valid JSON object in this exact format:

```json
{{
  "plan": [
    {{"command": "command_name", "args": ["arg1", "arg2"]}}
  ]
}}
```

No other text, explanations, or formatting. Just the JSON object.
"""
        try:
            response = requests.post(OLLAMA_API_URL, json={"model": model, "prompt": retry_prompt, "stream": False})
            response.raise_for_status()
            retry_text = response.json().get("response", "")
            return extract_json_object(retry_text)
        except:
            pass
    
    return json_str


def get_ai_json(prompt: str, model: str = "smollm2:1.7b") -> str:
    """Gets a clean JSON response from the AI."""
    try:
        response = requests.post(OLLAMA_API_URL, json={"model": model, "prompt": prompt, "stream": False})
        response.raise_for_status()
        raw = response.json().get("response", "")
        return extract_json_object(raw)
    except requests.exceptions.RequestException as e:
        return f'{{"error": "Error connecting to Ollama: {e}"}}'


def _handle_think_block_start(full_response: str) -> bool:
    """Handle entering a think block and print initial content."""
    if "<think>" not in full_response:
        return False
    
    # Extract and print content after <think>
    think_start = full_response.rfind("<think>") + len("<think>")
    content_after_think = full_response[think_start:]
    if content_after_think:
        print(content_after_think, end="", flush=True)
    return True


def _handle_think_block_end(token: str) -> bool:
    """Handle exiting a think block."""
    if "</think>" not in token:
        return False
    
    # Print everything before </think>
    before_end_think = token.split("</think>", 1)[0]
    if before_end_think:
        print(before_end_think, end="", flush=True)
    print("\n")  # Add newline after thinking
    return True


def _process_chunk(chunk, full_response: str) -> Tuple[str, str, bool]:
    """Process a single chunk and return updated response, token, and done status."""
    if not chunk:
        return full_response, "", False
    
    decoded_chunk = json.loads(chunk.decode("utf-8"))
    token = decoded_chunk.get("response", "")
    full_response += token
    done = decoded_chunk.get("done", False)
    
    return full_response, token, done


def _handle_think_blocks(token: str, full_response: str, in_think_block: bool) -> Tuple[bool, bool]:
    """Handle think block start/end detection. Returns (new_state, should_continue)."""
    if not in_think_block and _handle_think_block_start(full_response):
        return True, True  # Entered think block, continue processing
    if in_think_block and _handle_think_block_end(token):
        return False, True  # Exited think block, continue processing
    return in_think_block, False  # No state change, process normally


def _process_token_output(token: str, in_think_block: bool) -> None:
    """Process token output for think blocks."""
    if in_think_block:
        print(token, end="", flush=True)


def stream_thinking_process(response, full_response: str) -> Tuple[str, bool]:
    """Process streaming response to show thinking and return updated response."""
    in_think_block = False
    
    for chunk in response.iter_lines():
        full_response, token, done = _process_chunk(chunk, full_response)
        if not token:
            continue

        # Handle think block transitions
        in_think_block, should_continue = _handle_think_blocks(token, full_response, in_think_block)
        if should_continue:
            continue
        
        # Process token output
        _process_token_output(token, in_think_block)
        
        # If we encounter the done signal, break
        if done:
            break
    
    return full_response, in_think_block


def stream_and_extract_plan(prompt: str, model: str = "smollm2:1.7b") -> Tuple[str, str]:
    """
    Streams the AI's thinking process and then extracts the JSON plan.
    The thinking part is printed to stdout in real-time.
    """
    print("🤔 Thinking: ", end="", flush=True)
    
    try:
        response = requests.post(OLLAMA_API_URL, json={"model": model, "prompt": prompt, "stream": True}, stream=True)
        response.raise_for_status()

        full_response = ""
        full_response, in_think_block = stream_thinking_process(response, full_response)
        
        # Ensure we end with a newline if we were in a think block
        if in_think_block:
            print("\n")
            
        plan_json_str = extract_json_object(full_response)
        return plan_json_str, full_response

    except requests.exceptions.RequestException as e:
        error_msg = f"Error connecting to Ollama: {e}"
        print(f"\n{error_msg}")
        return f'{{"error": "{error_msg}"}}', ""


def check_if_task_complete(history, user_prompt: str, model: str = "smollm2:1.7b") -> bool:
    """Ask AI if the task is complete based on execution history."""
    # A simplified check. If the last command failed, the task is not complete.
    last_system_message = history[-1] if history and history[-1].get("role") == "system" else {}
    last_result = last_system_message.get("content", "")
    if "Exit code: 0" not in last_result and "success" not in last_result.lower():
         # If the last command failed, we are definitely not done.
        if "which" in last_result and "Exit code: 1" in last_result:
             # Special case: `which` failing after an uninstall is a SUCCESS condition.
             pass
        else:
            return False

    completion_prompt = f"""
You are an expert AI assistant that determines task completion status.

**Task Analysis:**
Based on the execution history, determine if the user's request has been fully completed.

User request: "{user_prompt}"
Recent execution history: {json.dumps(history[-5:], indent=2)}

**Completion Rules:**
- A task is COMPLETE when the requested action has been successfully executed
- Failed commands indicate the task is NOT complete, unless the failure is expected
- Special case: A failed `which` command after an uninstall indicates SUCCESS (program was successfully removed)
- Exit code 0 generally indicates success
- Consider the specific nature of the user's request

**Response Format:**
Respond with only "COMPLETE" if the task is done, or "CONTINUE" if more work is needed.
"""
    try:
        response = requests.post(OLLAMA_API_URL, json={"model": model, "prompt": completion_prompt, "stream": False})
        response.raise_for_status()
        result = response.json()["response"].strip().upper()
        return "COMPLETE" in result
    except:
        return False