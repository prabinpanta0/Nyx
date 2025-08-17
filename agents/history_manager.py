"""History management and context handling utilities."""

import json
import os
import requests
from typing import List, Dict, Any

# Constants
HISTORY_FILE = "/tmp/nyx_history.json"
MAX_CONTEXT_SIZE = 4000  # Rough token limit
OLLAMA_API_URL = "http://localhost:11434/api/generate"


def load_history() -> List[Dict[str, Any]]:
    """Loads conversation history from a file."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save_history(history: List[Dict[str, Any]]) -> None:
    """Saves conversation history to a file."""
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)


def estimate_context_size(history: List[Dict[str, Any]]) -> int:
    """Rough estimation of context size in characters."""
    return len(json.dumps(history))


def summarize_old_history(history: List[Dict[str, Any]], max_summary_length: int = 500, model: str = "smollm2:1.7b") -> List[Dict[str, Any]]:
    """Summarizes old history instead of dropping it."""
    if len(history) <= 5:
        return history
    
    # Keep first user request and last 3 entries
    to_summarize = history[1:-3]
    if not to_summarize:
        return history

    summary_prompt = f"""
Summarize the following conversation history into a concise summary that preserves important context:

{json.dumps(to_summarize, indent=2)}

Provide a brief summary (max {max_summary_length} chars) that captures:
- What commands were attempted
- Any important failures or successes
- Current system state relevant to future commands

Summary:
"""
    
    try:
        response = requests.post(OLLAMA_API_URL, json={"model": model, "prompt": summary_prompt, "stream": False})
        response.raise_for_status()
        summary = response.json().get("response", "").strip()
        
        # Create new compressed history
        compressed = [history[0]]  # Keep original user request
        compressed.append({"role": "system", "content": f"Previous session summary: {summary}"})
        compressed.extend(history[-3:])  # Keep recent entries
        
        return compressed
    except:
        # Fallback to old compression method
        return compress_history(history)


def compress_history(history: List[Dict[str, Any]], max_size: int = MAX_CONTEXT_SIZE) -> List[Dict[str, Any]]:
    """Compresses history by summarizing old entries instead of dropping them."""
    if estimate_context_size(history) <= max_size:
        return history
    
    # Use the new summarization method
    return summarize_old_history(history)


def get_failure_context(history: List[Dict[str, Any]]) -> str:
    """Extract failure context from recent history entries."""
    recent_failures = [
        h for h in history[-3:] 
        if h.get("role") == "system" and ("Error" in h.get("content", "") or "failed" in h.get("content", ""))
    ]
    
    if recent_failures:
        return (f"You have recently failed with the following errors. Do not repeat these mistakes. "
                f"Analyze the errors and create a new, different plan.\n"
                f"Recent failures:\n{json.dumps(recent_failures, indent=2)}")
    
    return ""