#!/bin/bash

set -e

SHARD_ID=8  # The default shard ID to wait for
TIMEOUT=120 # seconds
LOG_FILE="/tmp/pm2_restart_$(date +%s).log"

echo "Restarting hb-main..."

if ! pm2 restart hb-main; then
    echo "Error: Failed to restart hb-main"
    exit 1
fi

echo "Waiting for Shard ID ${SHARD_ID} connection (timeout: ${TIMEOUT}s)..."
timeout $TIMEOUT pm2 logs hb-main --lines 0 >"$LOG_FILE" 2>&1 &

LOG_PID=$!

# Monitor for the target message
if timeout $TIMEOUT grep -q "Shard ID ${SHARD_ID} has connected to Gateway" <(tail -f "$LOG_FILE" 2>/dev/null); then
    echo "Shard ID ${SHARD_ID} connected. Restarting hb-sub..."
    kill $LOG_PID 2>/dev/null || true

    if pm2 restart hb-sub; then
        echo "Success: All services restarted"
    else
        echo "Error: Failed to restart hb-sub"
        exit 1
    fi
else
    echo "Error: Timeout waiting for Shard ID ${SHARD_ID} connection"
    kill $LOG_PID 2>/dev/null || true
    exit 1
fi

# Cleanup
rm -f "$LOG_FILE"
