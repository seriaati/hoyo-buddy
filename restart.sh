#!/bin/bash

# A script to restart two Discord bot instances (hb-main and hb-sub) sequentially,
# ensuring the first bot is fully online before restarting the second.

# --- Configuration ---
MAIN_BOT_NAME="hb-main"
SUB_BOT_NAME="hb-sub"
# Set a timeout in seconds to prevent the script from waiting forever if the bot fails.
LOG_TIMEOUT=120

# --- Colors for better output ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# --- Main Bot Restart Logic ---
echo -e "${BLUE}--- Starting restart process for ${MAIN_BOT_NAME} ---${NC}"

# 1. Restart the main bot
echo -e "${YELLOW}Restarting ${MAIN_BOT_NAME}...${NC}"
pm2 restart ${MAIN_BOT_NAME}

# Check if the restart command was successful
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to restart ${MAIN_BOT_NAME}. Aborting.${NC}"
    exit 1
fi

echo -e "${YELLOW}Waiting for bot to initialize and report shard count (Timeout: ${LOG_TIMEOUT}s)...${NC}"

# Initialize variables
shards_total=0
shards_connected=0

# 2. Monitor new logs to wait for all shards to connect
# We pipe the output of 'pm2 logs' into a 'while' loop to process it line-by-line.
# --lines 0: This is the key change. It tails the logs, showing only new lines from this point forward.
# --raw: This flag removes PM2's prefixes, making the logs easier to parse.
# The `timeout` command will kill the `pm2 logs` process if it runs for too long.
timeout ${LOG_TIMEOUT} pm2 logs ${MAIN_BOT_NAME} --raw --lines 0 | while IFS= read -r line; do
    # Check if we have found the total shard count yet
    if [[ $shards_total -eq 0 ]]; then
        # Look for "Spawning X shards" and capture X
        if [[ "$line" =~ Spawning[[:space:]]([0-9]+)[[:space:]]shards ]]; then
            shards_total=${BASH_REMATCH[1]}
            echo -e "${GREEN}Detected a total of ${shards_total} shards to spawn.${NC}"
            # Print an initial status line that we can overwrite later
            printf "Connecting shards: [${shards_connected}/${shards_total}]"
        fi
    fi

    # If we know the total shards, start counting connections
    if [[ $shards_total -gt 0 ]]; then
        # Count how many shards have connected
        if [[ "$line" =~ has[[:space:]]connected[[:space:]]to[[:space:]]Gateway ]]; then
            # Increment the counter
            ((shards_connected++))
            # Update the status line by using \r (carriage return) to move the cursor to the beginning
            printf "\r${YELLOW}Connecting shards: [${shards_connected}/${shards_total}]${NC}"
        fi
    fi

    # Check if all shards are connected
    if [[ $shards_total -gt 0 && $shards_connected -eq $shards_total ]]; then
        echo # Move to a new line after the progress indicator
        echo -e "${GREEN}✔ All ${shards_total} shards for ${MAIN_BOT_NAME} have connected successfully!${NC}"
        # Exit the log-watching loop. This will also terminate the 'pm2 logs' and 'timeout' processes.
        # We need to kill the parent `timeout` process to stop gracefully.
        kill -s TERM $PPID
        exit 0
    fi
done

# Check the exit status of the pipeline.
# A status of 124 means the 'timeout' command was triggered.
if [ $? -eq 124 ]; then
     echo -e "\n${RED}Error: Timed out after ${LOG_TIMEOUT} seconds waiting for shards to connect.${NC}"
     echo -e "${RED}Please check the bot logs manually with 'pm2 logs ${MAIN_BOT_NAME}'. Aborting.${NC}"
     exit 1
fi

# Safety check: If the loop finished but we never found the shard count
if [[ $shards_total -eq 0 ]]; then
    echo -e "\n${RED}Error: Could not determine shard count for ${MAIN_BOT_NAME}. The log 'Spawning X shards' was not found.${NC}"
    echo -e "${RED}Please check the bot logs manually. Aborting.${NC}"
    exit 1
fi


# --- Sub Bot Restart Logic ---
echo -e "\n${BLUE}--- Starting restart process for ${SUB_BOT_NAME} ---${NC}"

# 3. Restart the sub-bot
echo -e "${YELLOW}Restarting ${SUB_BOT_NAME}...${NC}"
pm2 restart ${SUB_BOT_NAME}

# Check if the restart command was successful
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to restart ${SUB_BOT_NAME}.${NC}"
    exit 1
fi

echo -e "${GREEN}✔ ${SUB_BOT_NAME} has been restarted.${NC}"
echo -e "\n${GREEN}======================================"
echo -e "All bot instances restarted successfully."
echo -e "======================================${NC}"

# You can uncomment the line below if you want to see the logs for the sub-bot after it restarts
# pm2 logs ${SUB_BOT_NAME}

exit 0