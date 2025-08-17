import sys
import json
import shlex
from typing import List, Dict, Any, Tuple

# Local imports
from .history_manager import (
    load_history, save_history, estimate_context_size, 
    summarize_old_history, MAX_CONTEXT_SIZE
)
from .ai_client import (
    stream_and_extract_plan, extract_json_with_retry,
    check_if_task_complete, stream_ai_response
)
from .command_executor import setup_logging, execute_command
from .command_validator import normalize_plan, validate_command_safety
from .user_interaction import (
    approve_plan, confirm_sudo_execution, get_user_continuation_choice
)
from .plan_generator import create_plan_generation_prompt

# Global settings
REQUIRE_PLAN_APPROVAL = False  # Can be toggled by user
LOG_FILE = "/tmp/nyx_agent.log"


def _show_usage_and_exit():
    """Show usage information and exit."""
    print("Usage: main_agent.py [--approve] [--model MODEL] <prompt>")
    print("  --approve: Require manual approval for each plan")
    print("  --model MODEL: Specify AI model (default: smollm2:1.7b)")
    print(f"  Logs are written to: {LOG_FILE}")
    sys.exit(1)


def _process_flags(args: List[str]) -> tuple:
    """Process command line flags and return model, require_approval, and remaining args."""
    model = "smollm2:1.7b"
    require_approval = False
    
    while args and args[0].startswith('--'):
        if args[0] == '--approve':
            require_approval = True
            args = args[1:]
        elif args[0] == '--model' and len(args) > 1:
            model = args[1]
            args = args[2:]
        else:
            print(f"Unknown flag: {args[0]}")
            sys.exit(1)
    
    return model, require_approval, args


def parse_command_line_args() -> tuple:
    """Parse command line arguments and return processed args and flags."""
    if len(sys.argv) < 2:
        _show_usage_and_exit()

    args = sys.argv[1:]
    model, require_approval, remaining_args = _process_flags(args)
    
    if not remaining_args:
        print("Error: No prompt provided")
        sys.exit(1)
    
    user_prompt = " ".join(remaining_args)
    return user_prompt, model, require_approval


def print_session_info(model: str, require_approval: bool):
    """Print session initialization information."""
    print(f"🔐 Security: Command validation enabled")
    print(f"📝 Logging: {LOG_FILE}")
    print(f"🤖 Model: {model}")
    if require_approval:
        print(f"🔒 Plan approval: Required")
    print()


def execute_plan_steps(plan_data: Dict[str, Any], history: List[Dict[str, Any]]) -> bool:
    """Execute all steps in a plan and return whether all succeeded."""
    all_steps_succeeded = True
    
    for step in plan_data["plan"]:
        command = step.get("command")
        args = step.get("args", [])
        
        if not command:
            history.append({"role": "system", "content": "Skipped invalid step in plan."})
            continue
        
        # Enhanced sudo handling
        if command == "sudo" and not confirm_sudo_execution():
            history.append({
                "role": "system", 
                "content": f"Cancelled '{command} {' '.join(args)}'. User declined sudo."
            })
            all_steps_succeeded = False
            break
        
        return_code, result = execute_command(command, args)
        history.append({
            "role": "system", 
            "content": f"Executed '{command} {' '.join(args)}'. Exit code: {return_code}. Result:\n{result}"
        })
        print(result)
        
        if return_code != 0:
            all_steps_succeeded = False
            print("⚠️  Command failed, will re-plan...")
            break
    
    return all_steps_succeeded


def handle_plan_execution(plan_data: Dict[str, Any], history: List[Dict[str, Any]], require_approval: bool) -> bool:
    """Handle the complete plan execution process."""
    if "error" in plan_data:
        print(f"❌ Error from AI service: {plan_data['error']}")
        history.append({"role": "system", "content": f"AI service error: {plan_data['error']}"})
        return False

    if not ("plan" in plan_data and isinstance(plan_data["plan"], list)):
        history.append({"role": "system", "content": f"AI returned an invalid plan: {plan_data}"})
        print(f"⚠️  Invalid plan received, retrying...")
        return False

    # Display plan
    print("📋 Execution Plan:")
    for i, step in enumerate(plan_data["plan"]):
        cmd = step.get("command", "")
        args_str = " ".join(shlex.quote(arg) for arg in step.get("args", []))
        
        # Show safety status
        is_safe, _ = validate_command_safety(cmd, step.get("args", []))
        safety_indicator = "✅" if is_safe else "⚠️"
        print(f"  {i+1}. {safety_indicator} {cmd} {args_str}")
    print()

    # Get plan approval if required
    approval = approve_plan(plan_data, require_approval)
    if approval == False:
        print("❌ Plan rejected by user. Re-planning...")
        history.append({"role": "system", "content": "User rejected the execution plan. Please create a different approach."})
        return False
    elif approval == 'skip':
        print("⏭️  Plan skipped by user.")
        return True  # Consider this as completion

    return execute_plan_steps(plan_data, history)


def _handle_user_choice(user_input: str, history: List[Dict[str, Any]], model: str, iteration: int) -> tuple:
    """Handle specific user choice and return appropriate response."""
    global REQUIRE_PLAN_APPROVAL
    
    if user_input == 'q':
        print("🛑 Stopping execution.")
        return False, history, 0
    elif user_input == 'r':
        print("🔄 Restarting with compressed context...")
        history = summarize_old_history(history, model=model)
        return True, history, 0
    elif user_input == 'a':
        REQUIRE_PLAN_APPROVAL = not REQUIRE_PLAN_APPROVAL
        status = "enabled" if REQUIRE_PLAN_APPROVAL else "disabled"
        print(f"🔒 Plan approval {status}")
        return True, history, iteration
    
    return True, history, iteration


def handle_iteration_control(iteration: int, history: List[Dict[str, Any]], model: str) -> tuple:
    """Handle iteration control and user input."""
    if iteration >= 3 and sys.stdin.isatty():
        user_input = get_user_continuation_choice()
        return _handle_user_choice(user_input, history, model, iteration)
            
    elif iteration >= 5:
        print("🔄 Auto-compressing context to continue...")
        history = summarize_old_history(history, model=model)
        return True, history, 0
    
    return True, history, iteration


def generate_task_summary(user_prompt: str, history: List[Dict[str, Any]], model: str):
    """Generate and display task completion summary."""
    summary_prompt = f"""
You are an expert AI assistant that provides clear, concise summaries of completed technical tasks.

The user requested: "{user_prompt}"

Based on the commands executed in this session, provide a brief, clear summary of what was accomplished.
Focus only on this current request and what was done to fulfill it.

**Guidelines:**
- Be specific about what was actually done
- Use technical language appropriately 
- Confirm the outcome of the user's request
- Keep it concise but informative

Recent commands executed: {json.dumps(history[-3:], indent=2)}

Provide a professional summary in 1-2 sentences.
"""
    print("📝 Summary: ", end='', flush=True)
    summary = stream_ai_response(summary_prompt, model)
    history.append({"role": "assistant", "content": f"Summary: {summary}"})
    print("\n")

def _is_command_successful(last_command: str) -> bool:
    """Check if the last command was successful."""
    if "Exit code: 0" in last_command:
        return True
    # Special case: 'which' failing after uninstall is success
    if "which" in last_command and "Exit code: 1" in last_command:
        return True
    return False


def _check_task_completion(history: List[Dict[str, Any]], user_prompt: str, model: str) -> bool:
    """Check if task is complete and handle completion."""
    last_command = history[-1].get("content", "") if history else ""
    
    if _is_command_successful(last_command):
        if check_if_task_complete(history, user_prompt, model):
            print("\n✅ Task complete! Generating summary...")
            generate_task_summary(user_prompt, history, model)
            return True
        else:
            print("\n🔄 Commands succeeded but task may not be complete. Continuing...")
    
    return False


def _setup_session(logger) -> Tuple[str, str, bool, List[Dict]]:
    """Setup the agent session with logging, arguments, and initial history."""
    logger.info("=== NYX AGENT SESSION STARTED ===")
    
    # Parse command line arguments
    user_prompt, model, require_approval = parse_command_line_args()
    
    logger.info(f"User prompt: {user_prompt}")
    logger.info(f"Using model: {model}")
    if require_approval:
        logger.info("Plan approval mode enabled")
    
    print_session_info(model, require_approval)

    # Start with fresh history for each request to avoid prompt injection
    history = [{"role": "user", "content": user_prompt}]
    
    return user_prompt, model, require_approval, history


def _handle_planning_phase(user_prompt: str, history: List[Dict], model: str) -> Tuple[str, str, List[Dict]]:
    """Handle the AI planning phase."""
    # Context management
    if estimate_context_size(history) > MAX_CONTEXT_SIZE:
        print(f"\n💾 Context getting large, compressing history...")
        history = summarize_old_history(history, model=model)

    # 1. THINK and PLAN (Combined Step)
    generate_plan_prompt = create_plan_generation_prompt(user_prompt, history)
    plan_json_str, full_ai_response = stream_and_extract_plan(generate_plan_prompt, model)
    
    # Try improved JSON extraction if initial attempt failed
    if '"error"' in plan_json_str:
        plan_json_str = extract_json_with_retry(full_ai_response, model=model)
    
    history.append({"role": "assistant", "content": full_ai_response})
    return plan_json_str, full_ai_response, history


def _handle_execution_phase(plan_json_str: str, history: List[Dict], require_approval: bool) -> Tuple[bool, List[Dict]]:
    """Handle the plan execution phase."""
    try:
        plan_data = json.loads(plan_json_str)
        plan_data = normalize_plan(plan_data)

        execution_success = handle_plan_execution(plan_data, history, require_approval)
        return execution_success, history

    except json.JSONDecodeError:
        history.append({"role": "system", "content": f"AI returned invalid JSON: {plan_json_str}"})
        print(f"⚠️  Invalid JSON received, retrying...")
        return False, history


def main():
    global REQUIRE_PLAN_APPROVAL
    
    # Setup logging
    logger = setup_logging()
    user_prompt, model, require_approval, history = _setup_session(logger)
    REQUIRE_PLAN_APPROVAL = require_approval

    iteration = 0

    while True:
        iteration += 1

        # Planning phase
        plan_json_str, full_ai_response, history = _handle_planning_phase(user_prompt, history, model)

        # Execution phase
        execution_success, history = _handle_execution_phase(plan_json_str, history, REQUIRE_PLAN_APPROVAL)
        
        if not execution_success:
            # Continue to next iteration if execution failed
            continue

        # 3. CHECK COMPLETION
        if _check_task_completion(history, user_prompt, model):
            return
            
        # Loop control
        should_continue, history, iteration = handle_iteration_control(iteration, history, model)
        if not should_continue:
            return

        if iteration > 10:
            print(f"\n🛑 Reached maximum iterations ({iteration}). Stopping.")
            break


if __name__ == "__main__":
    main()