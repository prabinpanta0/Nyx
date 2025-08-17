"""Command validation and security utilities."""

import shlex
from typing import List, Tuple, Optional


# Security Configuration
ALLOWED_COMMANDS = {
    # Package managers
    'pacman', 'apt-get', 'apt', 'yum', 'dnf', 'zypper', 'emerge',
    # File operations (safe ones)
    'ls', 'find', 'which', 'whereis', 'file', 'stat', 'du', 'df',
    # System info
    'uname', 'whoami', 'id', 'ps', 'top', 'htop', 'free', 'uptime',
    # Text operations
    'cat', 'head', 'tail', 'grep', 'wc', 'sort', 'uniq',
    # Network (read-only)
    'ping', 'wget', 'curl', 'ssh',
    # Development tools
    'python', 'python3', 'pip', 'pip3', 'node', 'npm', 'git',
    # System services
    'systemctl', 'service', 'sudo'
}

DANGEROUS_COMMANDS = {
    'rm', 'rmdir', 'dd', 'mkfs', 'fdisk', 'parted', 'shred',
    'chmod', 'chown', 'su', 'passwd', 'usermod', 'userdel',
    'iptables', 'firewall-cmd', 'ufw'
}

SAFE_SUDO_COMMANDS = {
    'pacman', 'apt-get', 'apt', 'yum', 'dnf', 'systemctl', 'service'
}


def _check_basic_command_safety(command: str) -> Tuple[bool, str]:
    """Check basic command safety against allow/deny lists."""
    if command in DANGEROUS_COMMANDS:
        return False, f"Command '{command}' is in the dangerous commands list"
    
    if command not in ALLOWED_COMMANDS:
        return False, f"Command '{command}' is not in the allowed commands list"
    
    return True, "Command is safe"


def _validate_sudo_command(args: List[str]) -> Tuple[bool, str]:
    """Validate sudo command arguments."""
    if not args:
        return False, "Sudo command requires arguments"
    
    actual_command = args[0]
    if actual_command not in SAFE_SUDO_COMMANDS:
        return False, f"Sudo with '{actual_command}' is not allowed"
    
    # Check for dangerous flags
    dangerous_flags = {'-rf', '--force', '--no-preserve-root'}
    for arg in args:
        if any(flag in arg for flag in dangerous_flags):
            return False, f"Dangerous flag detected: {arg}"
    
    return True, "Sudo command is safe"


def validate_command_safety(command: str, args: List[str]) -> Tuple[bool, str]:
    """Validates if a command is safe to execute."""
    # Check basic command safety
    is_safe, message = _check_basic_command_safety(command)
    if not is_safe:
        return is_safe, message
    
    # Special sudo validation
    if command == 'sudo':
        return _validate_sudo_command(args)
    
    return True, "Command is safe"


def _normalize_string_step(step: str) -> Tuple[str, List[str]]:
    """Normalize a string step into command and args."""
    parts = shlex.split(step)
    if not parts:
        return "", []
    return parts[0], parts[1:]


def _normalize_dict_step(step: dict) -> Tuple[str, List[str]]:
    """Normalize a dict step into command and args."""
    raw_cmd = step.get("command", "")
    raw_args = step.get("args", [])

    if isinstance(raw_args, str):
        raw_args = shlex.split(raw_args)
    elif not isinstance(raw_args, list):
        raw_args = []

    if raw_cmd and " " in raw_cmd:
        parts = shlex.split(raw_cmd)
        raw_cmd, split_args = parts[0], parts[1:]
        raw_args = split_args + raw_args

    return raw_cmd, raw_args


def _is_step_safe(cmd: str, args: List[str]) -> bool:
    """Check if a step is safe from shell operators."""
    banned = {"&&", "||", ";", "|", ">", "<"}
    tokens = [cmd] + list(args)
    return not any(t in banned for t in tokens)


def _process_single_step(step) -> Optional[Tuple[str, List[str]]]:
    """Process a single step and return command and args if valid."""
    if isinstance(step, str):
        cmd, args = _normalize_string_step(step)
    elif isinstance(step, dict):
        cmd, args = _normalize_dict_step(step)
    else:
        return None

    # Skip unsafe/ambiguous steps
    if not _is_step_safe(cmd, args):
        return None

    return (cmd, args) if cmd else None


def normalize_plan(plan_data: dict) -> dict:
    """Normalize plan steps so each has a single 'command' and a list of 'args'.

    - If a step is a string, split it with shlex.
    - If 'command' contains spaces, split and merge into args.
    - Ensure args is a list of strings.
    - Disallow common shell operators to avoid ambiguous parsing.
    """
    if not isinstance(plan_data, dict) or not isinstance(plan_data.get("plan"), list):
        return plan_data

    normalized = []
    for step in plan_data["plan"]:
        result = _process_single_step(step)
        if result:
            cmd, args = result
            normalized.append({"command": cmd, "args": args})

    plan_data["plan"] = normalized
    return plan_data