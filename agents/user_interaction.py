"""User interaction and plan approval utilities."""

import sys
import shlex
from typing import Union, Dict, Any

from .command_validator import validate_command_safety


def _display_plan_step(i: int, step: Dict[str, Any]) -> None:
    """Display a single plan step with safety indicator."""
    cmd = step.get("command", "")
    args_str = " ".join(shlex.quote(arg) for arg in step.get("args", []))
    
    # Check safety
    is_safe, safety_msg = validate_command_safety(cmd, step.get("args", []))
    safety_indicator = "✅" if is_safe else "⚠️"
    
    print(f"  {i+1}. {safety_indicator} {cmd} {args_str}")
    if not is_safe:
        print(f"      └─ {safety_msg}")


def _get_user_approval() -> Union[bool, str]:
    """Get user approval for plan execution."""
    try:
        user_input = input("\n🤔 Approve this plan? [y/N/s(kip)]: ").strip().lower()
        if user_input in ['y', 'yes']:
            return True
        elif user_input in ['s', 'skip']:
            return 'skip'
        else:
            return False
    except (EOFError, KeyboardInterrupt):
        return False


def approve_plan(plan_data: Dict[str, Any], require_approval: bool = False) -> Union[bool, str]:
    """Ask user to approve the execution plan."""
    if not require_approval or not sys.stdin.isatty():
        return True
    
    print("\n🔍 Plan Review:")
    if "plan" in plan_data and isinstance(plan_data["plan"], list):
        for i, step in enumerate(plan_data["plan"]):
            _display_plan_step(i, step)
    
    return _get_user_approval()


def confirm_sudo_execution() -> bool:
    """Confirm sudo command execution with user."""
    if not sys.stdin.isatty():
        return True
    
    print("🔑 Sudo command detected - may require password.")
    try:
        confirm = input("🔒 Confirm sudo execution? [y/N]: ").strip().lower()
        return confirm in ['y', 'yes']
    except (EOFError, KeyboardInterrupt):
        print("\n❌ Sudo command cancelled.")
        return False


def get_user_continuation_choice() -> str:
    """Get user's choice for continuing execution."""
    CONTINUE_PROMPT = "\n\n[Press Enter to continue, 'q' to quit, 'r' to restart context, 'a' to approve plans]: "
    
    try:
        user_input = input(CONTINUE_PROMPT).strip().lower()
        return user_input
    except (EOFError, KeyboardInterrupt):
        return "continue"  # Default to continue in non-interactive mode