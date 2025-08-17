"""Command execution utilities."""

import subprocess
import shlex
import logging
from typing import Tuple

from .command_validator import validate_command_safety


def setup_logging():
    """Setup logging for debugging and audit trail."""
    LOG_FILE = "/tmp/nyx_agent.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def log_command_execution(command: str, args: list, return_code: int, result: str):
    """Log command execution for audit trail."""
    logger = logging.getLogger(__name__)
    cmd_str = f"{command} {' '.join(args)}"
    logger.info(f"EXECUTED: {cmd_str} | EXIT_CODE: {return_code}")
    if return_code != 0:
        logger.warning(f"COMMAND_FAILED: {cmd_str} | ERROR: {result}")


def _format_command_output(result) -> str:
    """Format command output from subprocess result."""
    output = ""
    if result.stdout:
        output += f"--- Output ---\n{result.stdout.strip()}\n"
    if result.stderr:
        output += f"--- Errors ---\n{result.stderr.strip()}\n"
    
    return output if output else "Command executed successfully with no output.\n"


def _run_command_subprocess(command: str, args: list) -> subprocess.CompletedProcess:
    """Run command using subprocess with appropriate shell mode."""
    command_line = f"{command} {' '.join(shlex.quote(arg) for arg in args)}"
    print(f"🤖 Executing: {command_line}")
    
    # Detect if we need shell=True (for pipes, redirections, etc.)
    needs_shell = any(op in ' '.join([command] + args) for op in ['|', '>', '<', '&&', '||'])
    
    if needs_shell:
        # Use shell=True only when necessary and with extra caution
        print("⚠️  Using shell mode for complex command")
        return subprocess.run(command_line, capture_output=True, text=True, check=False, shell=True)
    else:
        # Safer: use argument list (no shell interpretation)
        return subprocess.run([command] + args, capture_output=True, text=True, check=False)


def execute_command(command: str, args: list) -> Tuple[int, str]:
    """Executes a shell command safely and returns its output."""
    # Validate command safety first
    is_safe, safety_msg = validate_command_safety(command, args)
    if not is_safe:
        return 1, f"🚫 Command blocked for safety: {safety_msg}\n"
    
    try:
        result = _run_command_subprocess(command, args)
        final_output = _format_command_output(result)
        
        # Log the execution
        log_command_execution(command, args, result.returncode, final_output)
        
        return result.returncode, final_output

    except FileNotFoundError:
        return 1, f"Error: Command not found: {command}\n"
    except Exception as e:
        return 1, f"An unexpected error occurred: {e}\n"


def detect_os() -> str:
    """Detect the operating system."""
    try:
        # Try to detect Arch Linux
        result = subprocess.run(["which", "pacman"], capture_output=True, text=True)
        if result.returncode == 0:
            return "Arch Linux"
        
        # Try to detect Debian/Ubuntu
        result = subprocess.run(["which", "apt-get"], capture_output=True, text=True)
        if result.returncode == 0:
            return "Debian-based Linux"
        
        # Try generic Linux detection
        result = subprocess.run(["uname", "-a"], capture_output=True, text=True)
        if "Linux" in result.stdout:
            return "Linux"
    except:
        pass
    
    return "Unknown"