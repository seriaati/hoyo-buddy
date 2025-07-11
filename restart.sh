#!/bin/bash

set -e

TIMEOUT=300
LOG_FILE="/tmp/pm2_restart_$(date +%s).log"
EXPECTED_SHARDS=0

echo "Restarting hb-main..."
if ! pm2 restart hb-main; then
    echo "Error: Failed to restart hb-main"
    exit 1
fi

echo "Monitoring hb-main logs for shard connections (timeout: ${TIMEOUT}s)..."
timeout $TIMEOUT pm2 logs hb-main --lines 0 > "$LOG_FILE" 2>&1 &
LOG_PID=$!

echo "Attempting to determine total number of shards from logs..."
start_time=$(date +%s)
while [ $(($(date +%s) - start_time)) -lt $TIMEOUT ] && [ $EXPECTED_SHARDS -eq 0 ]; do
    # Look for a line indicating the total number of shards
    SHARD_COUNT_LINE=$(grep -m 1 -E "Spawning [0-9]+ shards" "$LOG_FILE" || true)
    if [[ "$SHARD_COUNT_LINE" =~ ([0-9]+)\ shards ]]; then
        EXPECTED_SHARDS=${BASH_REMATCH[1]}
        echo "Detected ${EXPECTED_SHARDS} expected shards from logs."
    fi
    sleep 2 # Check every 2 seconds
done

if [ $EXPECTED_SHARDS -eq 0 ]; then
    echo "Warning: Could not determine the total number of shards from logs within the timeout."
    echo "Please ensure your bot logs the total shard count during startup (e.g., 'Spawning X shards')."
    echo "Falling back to a manual check if only one shard is detected as connected. This may not be ideal for multiple shards."
fi

connected_shards=0
start_time=$(date +%s)

# Monitor the log file for shard connections
while [ $(($(date +%s) - start_time)) -lt $TIMEOUT ]; do
    current_connected=$(grep "has connected to Gateway" "$LOG_FILE" | awk '{print $3}' | sort -u | wc -l)

    if [ "$current_connected" -gt "$connected_shards" ]; then
        connected_shards=$current_connected
        echo "Currently ${connected_shards} shard(s) connected."
    fi

    if [ "$EXPECTED_SHARDS" -gt 0 ] && [ "$connected_shards" -ge "$EXPECTED_SHARDS" ]; then
        echo "All ${EXPECTED_SHARDS} shards connected. Restarting hb-sub..."
        kill $LOG_PID 2>/dev/null || true
        break
    elif [ "$EXPECTED_SHARDS" -eq 0 ] && [ "$connected_shards" -gt 0 ]; then
        echo "Expected shard count unknown. At least one shard connected. Restarting hb-sub..."
        kill $LOG_PID 2>/dev/null || true
        break
    fi

    sleep 5
done

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
    kill $LOG_PID 2>/dev/null || true
    exit 1
fi

# Cleanup
rm -f "$LOG_FILE"
