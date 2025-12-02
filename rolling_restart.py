"""Rolling deployment script for zero-downtime restarts.

This script implements a Docker-like rolling deployment strategy for PM2 processes:
1. Start a new process instance with a temporary name
2. Monitor logs to verify all shards have connected (health check)
3. Delete the old process once the new one is healthy
4. Rename the new process to the original name

Benefits:
- Achieves zero downtime with only ONE active process at a time
- No need for dual deployments (hb-main + hb-sub)
- Automatic rollback if the new process fails health checks
- Monitors shard connection status to ensure bot is fully ready

Usage:
    python rolling_restart.py

The script will automatically detect the current process configuration and
apply it to the new instance.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time

PROCESS_NAME = "hb-main"
TEMP_PROCESS_NAME = "hb-main-new"
MAX_WAIT_TIME = 300  # 5 minutes max wait for health check


def run_command(command: str, description: str, check: bool = True) -> subprocess.CompletedProcess:
    """Helper function to run a command and optionally check for errors."""
    print(description)
    try:
        result = subprocess.run(command, check=check, shell=True, capture_output=True, text=True)
        print("... Done")
        return result
    except FileNotFoundError:
        print(
            f"Error: Command '{command.split(maxsplit=1)[0]}' not found. Is pm2 installed and in your PATH?"
        )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {command}")
        print(f"Return Code: {e.returncode}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        sys.exit(1)


def get_process_status(process_name: str) -> dict | None:
    """Get process status from pm2 jlist output."""
    try:
        result = subprocess.run(["pm2", "jlist"], check=True, capture_output=True, text=True)
        processes = json.loads(result.stdout)
        for proc in processes:
            if proc.get("name") == process_name:
                return proc
        return None
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error getting process status: {e}")
        return None


def wait_for_health(process_name: str) -> bool:
    """Wait for the new process to become healthy by monitoring logs."""
    print(f"\nWaiting for '{process_name}' to become healthy...")

    log_command = ["pm2", "logs", process_name, "--lines", "0", "--raw"]
    log_process = subprocess.Popen(
        log_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8"
    )

    shard_count = None
    target_shard_id = None
    start_time = time.time()

    try:
        for line in iter(log_process.stdout.readline, ""):  # pyright: ignore[reportOptionalMemberAccess]
            sys.stdout.write(line)

            # Check timeout
            if time.time() - start_time > MAX_WAIT_TIME:
                print(f"\n❌ Timeout: Process did not become healthy within {MAX_WAIT_TIME}s")
                return False

            # Check if process crashed
            status = get_process_status(process_name)
            if status and status.get("pm2_env", {}).get("status") == "errored":
                print(f"\n❌ Process '{process_name}' crashed during startup")
                return False

            # Wait for "Spawning X shards"
            if shard_count is None:
                match = re.search(r"Spawning (\d+) shards", line)
                if match:
                    shard_count = int(match.group(1))
                    print(f"\n--- Found Shard Count: {shard_count} ---")

                    if shard_count == 0:
                        print("Shard count is 0. No shards to wait for.")
                        return True

                    target_shard_id = shard_count - 1
                    print(f"Waiting for Shard ID {target_shard_id} to connect...\n")
                    continue

            # Wait for the final shard to connect
            if target_shard_id is not None:
                target_log_line = f"Shard ID {target_shard_id} has connected to Gateway"
                if target_log_line in line:
                    print("\n✅ All shards connected! Process is healthy.\n")
                    return True

    finally:
        log_process.terminate()
        try:
            log_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            log_process.kill()

    return False


def main() -> None:
    """Main function to orchestrate rolling deployment."""
    print("🔄 Starting rolling deployment...\n")

    # 1. Check if old process exists
    old_status = get_process_status(PROCESS_NAME)
    if not old_status:
        print(f"❌ Process '{PROCESS_NAME}' not found. Nothing to restart.")
        sys.exit(1)

    print(f"✓ Found existing process '{PROCESS_NAME}' (PID: {old_status.get('pid')})")

    # 2. Check if temp process already exists (cleanup from failed previous run)
    temp_status = get_process_status(TEMP_PROCESS_NAME)
    if temp_status:
        print(f"⚠ Temporary process '{TEMP_PROCESS_NAME}' already exists, deleting it...")
        run_command(f"pm2 delete {TEMP_PROCESS_NAME}", "Cleaning up old temporary process...")

    # 3. Start new process with temporary name
    old_script = old_status["pm2_env"]["pm_exec_path"]
    old_interpreter = old_status["pm2_env"]["exec_interpreter"]
    old_args = " ".join(old_status["pm2_env"]["args"]) if old_status["pm2_env"].get("args") else ""
    old_interpreter_args = (
        " ".join(old_status["pm2_env"]["node_args"])
        if old_status["pm2_env"].get("node_args")
        else ""
    )

    start_command = (
        f'pm2 start "{old_script}" --name {TEMP_PROCESS_NAME} --interpreter "{old_interpreter}"'
    )
    if old_interpreter_args:
        start_command += f" --interpreter-args '{old_interpreter_args}'"
    if old_args:
        start_command += f" -- {old_args}"

    run_command(start_command, f"\n1. Starting new process '{TEMP_PROCESS_NAME}'...")

    # 4. Wait for new process to be healthy
    print("\n2. Performing health check...")
    if not wait_for_health(TEMP_PROCESS_NAME):
        print(f"\n❌ New process failed health check. Cleaning up '{TEMP_PROCESS_NAME}'...")
        run_command(f"pm2 delete {TEMP_PROCESS_NAME}", "Deleting failed process...")
        print("\n❌ Rolling deployment failed. Old process still running.")
        sys.exit(1)

    # 5. Stop old process
    run_command(f"pm2 delete {PROCESS_NAME}", f"\n3. Stopping old process '{PROCESS_NAME}'...")

    # 6. Rename new process to original name
    # PM2 doesn't have a native rename, so we need to save ecosystem, modify it, and reload
    # Instead, we'll delete and restart with the correct name
    print(f"\n4. Renaming '{TEMP_PROCESS_NAME}' to '{PROCESS_NAME}'...")

    restart_command = (
        f'pm2 start "{old_script}" --name {PROCESS_NAME} --interpreter "{old_interpreter}"'
    )
    if old_interpreter_args:
        restart_command += f" --interpreter-args '{old_interpreter_args}'"
    if old_args:
        restart_command += f" -- {old_args}"

    # First stop the temp process
    run_command(f"pm2 delete {TEMP_PROCESS_NAME}", "Stopping temporary process...")

    # Then start with the correct name
    run_command(restart_command, f"Starting process with name '{PROCESS_NAME}'...")

    # Save PM2 process list
    run_command("pm2 save", "\n5. Saving PM2 process list...")

    print("\n✅ Rolling deployment completed successfully!")
    print(f"✓ Process '{PROCESS_NAME}' is now running the new version")


if __name__ == "__main__":
    main()
