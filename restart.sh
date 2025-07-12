#!/bin/bash

set -e

TIMEOUT=300 # Increased timeout, as waiting for multiple shards might take longer
# Use a temporary file for live log streaming from pm2
LOG_FILE="/tmp/pm2_restart_hb_main_live_logs_$(date +%s).log"

echo "Restarting hb-main..."
if ! pm2 restart hb-main; then
    echo "Error: Failed to restart hb-main"
    exit 1
fi

echo "Monitoring hb-main logs for shard connections (timeout: ${TIMEOUT}s)..."

pm2 logs hb-main --lines 0 --raw | stdbuf -oL tee "$LOG_FILE" >/dev/null &
LIVE_LOG_PID=$!

sleep 2

EXPECTED_SHARDS=0
start_overall_time=$(date +%s)

# --- Determine Expected Number of Shards ---
echo "Attempting to determine total number of shards from logs..."
# Use a sub-timeout for this specific check, so it doesn't wait forever.
if timeout 30 grep -m 1 -E "Spawning ([0-9]+) shards" <(tail -f "$LOG_FILE") &>/dev/null; then
    # Once grep -m 1 finds a match and exits, we can read the line from the file.
    SHARD_COUNT_LINE=$(grep -m 1 -E "Spawning ([0-9]+) shards" "$LOG_FILE")
    if [[ "$SHARD_COUNT_LINE" =~ ([0-9]+)\ shards ]]; then
        EXPECTED_SHARDS=${BASH_REMATCH[1]}
        echo "Detected ${EXPECTED_SHARDS} expected shards from logs."
    fi
fi

if [ $EXPECTED_SHARDS -eq 0 ]; then
    echo "Warning: Could not determine the total number of shards from logs within the timeout."
    echo "Please ensure your bot logs the total shard count during startup (e.g., 'Spawning X shards')."
    echo "Proceeding by waiting for at least one shard to connect. This may not be ideal for multiple shards."
fi

# --- Wait for all shards to connect ---
connected_shards=0
check_interval=5

while [ $(($(date +%s) - start_overall_time)) -lt $TIMEOUT ]; do
    # Count unique "Shard ID X has connected to Gateway" messages from the live log file.
    # The --raw flag simplifies the pattern to just "Shard ID X".
    # awk '{print $3}' gets "X", sort -u for unique IDs, wc -l to count.
    current_connected=$(grep -E "Shard ID ([0-9]+) has connected to Gateway" "$LOG_FILE" | awk '{print $3}' | sort -u | wc -l)

    if [ "$current_connected" -gt "$connected_shards" ]; then
        connected_shards=$current_connected
        echo "Currently ${connected_shards} shard(s) connected."
    fi

    if [ "$EXPECTED_SHARDS" -gt 0 ] && [ "$connected_connected" -ge "$EXPECTED_SHARDS" ]; then
        echo "All ${EXPECTED_SHARDS} shards connected. Restarting hb-sub..."
        break # All shards connected, exit loop
    elif [ "$EXPECTED_SHARDS" -eq 0 ] && [ "$connected_shards" -gt 0 ]; then
        # Fallback: if EXPECTED_SHARDS could not be determined, proceed if at least one shard connects.
        echo "Expected shard count unknown. At least one shard connected. Restarting hb-sub..."
        break
    fi

    sleep "$check_interval"
done

# Kill the background pm2 logs process (the tee process)
kill $LIVE_LOG_PID 2>/dev/null || true

# Check if the loop completed due to timeout or successful connection
if [ "$connected_shards" -ge "$EXPECTED_SHARDS" ] || ([ "$EXPECTED_SHARDS" -eq 0 ] && [ "$connected_shards" -gt 0 ]); then
    if pm2 restart hb-sub; then
        echo "Success: All services restarted"
    else
        echo "Error: Failed to restart hb-sub"
        exit 1
    fi
else
    echo "Error: Timeout waiting for all shards to connect. Only ${connected_shards} connected out of ${EXPECTED_SHARDS} (if known)."
    exit 1
fi

# Cleanup
rm -f "$LOG_FILE"
