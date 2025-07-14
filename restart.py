from __future__ import annotations

import re
import subprocess
import sys

MAIN_PROCESS_NAME = "hb-main"
SUB_PROCESS_NAME = "hb-sub"


def run_command(command: str, description: str) -> None:
    """A helper function to run a simple command and check for errors."""
    print(description)
    try:
        subprocess.run(command, check=True, shell=True, capture_output=True, text=True)
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
    print("... Done")


def main() -> None:
    """Main function to orchestrate the workflow."""

    # 1. Run `pm2 restart hb-main`
    run_command(f"pm2 restart {MAIN_PROCESS_NAME}", f"1. Restarting '{MAIN_PROCESS_NAME}'...")

    # 2. Run `pm2 logs hb-main --lines 0`
    # We use Popen to start the process and read its output in a non-blocking way.
    # --raw is used to get clean output without pm2's table formatting.
    log_command = ["pm2", "logs", MAIN_PROCESS_NAME, "--lines", "0", "--raw"]
    print(f"\n2. Tailing logs for '{MAIN_PROCESS_NAME}'...")

    # Start the log process
    log_process = subprocess.Popen(
        log_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Redirect stderr to stdout
        text=True,  # Decodes output as text
        encoding="utf-8",
    )

    shard_count = None
    target_shard_id = None

    print("3. Waiting for shard information in logs...")

    try:
        # Read the log output line by line, in real-time
        for line in iter(log_process.stdout.readline, ""):  # pyright: ignore[reportOptionalMemberAccess]
            # Print the log line so you can see the progress
            sys.stdout.write(line)

            # 3. Wait for "Spawning X shards" and 4. Remember the number
            if shard_count is None:
                # Use a regular expression to find the line and capture the number
                match = re.search(r"Spawning (\d+) shards", line)
                if match:
                    shard_count = int(match.group(1))
                    print(f"\n--- Found Shard Count: {shard_count} ---")

                    if shard_count == 0:
                        print("Shard count is 0. No shards to wait for. Proceeding.")
                        break  # Exit the log-checking loop

                    # Shard IDs are 0-indexed, so the last one is count - 1
                    target_shard_id = shard_count - 1
                    print(f"5. Now waiting for Shard ID {target_shard_id} to connect...\n")
                    continue  # Continue to the next log line

            # 5. Wait for the final shard to connect
            if target_shard_id is not None:
                # Construct the exact line we are looking for
                target_log_line = f"Shard ID {target_shard_id} has connected to Gateway"
                if target_log_line in line:
                    print("\n--- Target Shard Connected! ---\n")
                    break  # Success! Exit the log-checking loop

    finally:
        # 6. Ctrl+C to leave the log stream (terminate the process)
        print("6. Terminating log stream...")
        log_process.terminate()
        try:
            # Wait for the process to actually terminate
            log_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("... Log process did not terminate gracefully, killing it.")
            log_process.kill()
        print("... Done")

    # 7. Run `pm2 restart hb-sub`
    run_command(f"pm2 restart {SUB_PROCESS_NAME}", f"\n7. Restarting '{SUB_PROCESS_NAME}'...")

    print("\n✅ Workflow completed successfully!")


if __name__ == "__main__":
    main()
