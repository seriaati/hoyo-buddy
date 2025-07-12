#!/bin/bash

set -e

TIMEOUT=120 # seconds
LOG_FILE="/tmp/pm2_restart_$(date +%s).log"

echo "Restarting hb-main..."

if ! pm2 restart hb-main; then
    echo "Error: Failed to restart hb-main"
    exit 1
fi

echo "Determining shard count and waiting for last shard connection (timeout: ${TIMEOUT}s)..."

timeout $TIMEOUT pm2 logs hb-main --lines 0 >"$LOG_FILE" 2>&1 &

LOG_PID=$!

# Wait for spawning message and determine shard count
SHARD_COUNT=""
LAST_SHARD_ID=""

# Monitor for spawning message first
if timeout 30 grep -q "Spawning [0-9]* shards" <(tail -f "$LOG_FILE" 2>/dev/null); then
    # Extract shard count from the log
    SHARD_COUNT=$(grep "Spawning [0-9]* shards" "$LOG_FILE" | head -1 | grep -o '[0-9]*')
    LAST_SHARD_ID=$((SHARD_COUNT - 1))
    echo "Found $SHARD_COUNT shards, waiting for Shard ID $LAST_SHARD_ID to connect..."
else
    echo "Warning: Could not find spawning message, defaulting to Shard ID 8"
    LAST_SHARD_ID=8
fi

# Monitor for the target message
if timeout $TIMEOUT grep -q "Shard ID $LAST_SHARD_ID has connected to Gateway" <(tail -f "$LOG_FILE" 2>/dev/null); then
    echo "Shard ID $LAST_SHARD_ID connected. Restarting hb-sub..."
    kill $LOG_PID 2>/dev/null || true

    if pm2 restart hb-sub; then
        echo "Success: All services restarted"
    else
        echo "Error: Failed to restart hb-sub"
        exit 1
    fi
else
    echo "Error: Timeout waiting for Shard ID $LAST_SHARD_ID connection"
    kill $LOG_PID 2>/dev/null || true
    exit 1
fi

# Cleanup
rm -f "$LOG_FILE"
