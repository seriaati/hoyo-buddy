# Deployment Guide

This document explains the deployment strategies available for Hoyo Buddy.

## Overview

Hoyo Buddy uses PM2 for process management in production. The project includes multiple deployment strategies to suit different needs.

## PM2 Configuration

The `pm2.json` file defines 5 processes:

- `hb-main`: Main bot instance
- `hb-sub`: Secondary bot instance (for dual deployment)
- `hb-app`: Web authentication app
- `hb-scheduler`: Background task scheduler
- `hb-web-server`: Web server for static content

## Deployment Strategies

### 1. Rolling Deployment (Recommended)

**Script:** `rolling_restart.py`

**Strategy:** Docker-like rolling deployment with zero downtime using a single bot instance.

**How it works:**

1. Starts a new process instance with a temporary name (`hb-main-new`)
2. Monitors the new instance's logs to verify all shards have connected
3. Once healthy, deletes the old process
4. Renames the new process to the original name (`hb-main`)

**Advantages:**

- ✅ Zero downtime deployment
- ✅ Only one bot instance online at a time (saves resources)
- ✅ Automatic rollback if health checks fail
- ✅ No need for dual deployments

**Usage:**

```bash
python rolling_restart.py
```

**Health Check:**
The script monitors Discord bot logs for the message:

```
Shard ID {N} has connected to Gateway
```

where N is the last shard ID (shard count - 1). This ensures all shards are fully connected before switching over.

**Timeout:** 5 minutes (configurable via `MAX_WAIT_TIME`)

**Rollback:** If the new instance fails to become healthy within the timeout or crashes during startup, the script automatically cleans up and keeps the old instance running.

---

### 2. Dual Deployment (Legacy)

**Script:** `restart.py`

**Strategy:** Maintains two bot instances (`hb-main` and `hb-sub`) for zero downtime.

**How it works:**

1. Restarts `hb-main`
2. Waits for all shards to connect on `hb-main`
3. Restarts `hb-sub`

**Advantages:**

- ✅ Zero downtime deployment
- ✅ Proven strategy, already in production

**Disadvantages:**

- ❌ Requires two bot instances to be online simultaneously
- ❌ Uses 2x resources (memory, CPU)
- ❌ More complex setup

**Usage:**

```bash
python restart.py
```

---

### 3. Standard PM2 Restart

**Command:** `pm2 restart <process-name>`

**Strategy:** Simple restart with brief downtime.

**Usage:**

```bash
pm2 restart hb-main
```

**Disadvantages:**

- ❌ Brief downtime during restart (~10-30 seconds depending on shard count)

---

## Deployment Workflow

### Initial Setup

1. **Install dependencies:**

   ```bash
   uv sync --frozen
   ```

2. **Configure environment:**
   Create `.env` file with required variables:
   - `discord_token`
   - `discord_client_id`
   - `discord_client_secret`
   - `db_url`
   - `fernet_key`

3. **Start processes:**

   ```bash
   pm2 start pm2.json
   pm2 save
   ```

### Regular Updates

**For zero downtime with minimal resources (recommended):**

```bash
git pull
uv sync --frozen
aerich upgrade  # If database migrations exist
python rolling_restart.py
```

**For dual deployment:**

```bash
git pull
uv sync --frozen
aerich upgrade  # If database migrations exist
python restart.py
```

**Quick restart (with brief downtime):**

```bash
git pull
uv sync --frozen
aerich upgrade  # If database migrations exist
pm2 restart hb-main
```

## Monitoring

### PM2 Commands

```bash
pm2 status              # View all processes
pm2 logs hb-main        # View logs for main bot
pm2 monit               # Real-time monitoring dashboard
pm2 restart all         # Restart all processes
pm2 reload all          # Graceful reload (zero downtime)
```

### Health Checks

The bot exposes Prometheus metrics (if `--prometheus` flag is enabled):

- `discordbot_connected`: Whether the bot is connected to Discord
- `discordbot_latency_seconds`: Latency to Discord gateway
- `discordbot_guilds_total`: Number of guilds

### Logs

Logs are stored in:

- PM2 logs: `~/.pm2/logs/`
- Application logs: `logs/` directory (if configured)

## Troubleshooting

### Rolling Restart Fails

**Symptom:** Script exits with "❌ New process failed health check"

**Solutions:**

1. Check logs: `pm2 logs hb-main-new`
2. Verify environment variables are correct
3. Check database connectivity
4. Increase `MAX_WAIT_TIME` if shards take longer to connect
5. Ensure no port conflicts

### Process Crashes on Startup

**Symptom:** Process shows status "errored" in `pm2 status`

**Solutions:**

1. Check error logs: `pm2 logs hb-main --err --lines 100`
2. Verify Python environment: `.venv/bin/python --version`
3. Check database migrations: `aerich history`
4. Verify all dependencies installed: `uv sync --frozen`

### Memory Issues

**Symptom:** Process killed by system (OOM)

**Solutions:**

1. Check memory usage: `pm2 status` (look at memory column)
2. Use only rolling deployment (single instance)
3. Adjust PM2 memory limits in `pm2.json`:

   ```json
   {
     "max_memory_restart": "1G"
   }
   ```

## Best Practices

1. **Always run validation before deploying:**

   ```bash
   ruff check . --fix --unsafe-fixes
   ruff format .
   pyright hoyo_buddy/
   ```

2. **Test database migrations in development first:**

   ```bash
   aerich migrate
   aerich upgrade
   ```

3. **Use rolling deployment for production** to minimize resource usage

4. **Monitor health endpoints** to catch issues early

5. **Keep PM2 process list saved:**

   ```bash
   pm2 save
   ```

6. **Set up PM2 startup script** for auto-restart on server reboot:

   ```bash
   pm2 startup
   # Follow the instructions provided
   pm2 save
   ```

## Migration from Dual to Rolling Deployment

To migrate from the dual deployment strategy to rolling deployment:

1. **Stop the sub process:**

   ```bash
   pm2 delete hb-sub
   pm2 save
   ```

2. **Update deployment scripts:**
   Replace calls to `restart.py` with `rolling_restart.py`

3. **Test the rolling deployment:**

   ```bash
   python rolling_restart.py
   ```

4. **Monitor the first few deployments** to ensure stability

5. **Update CI/CD pipelines** if automated deployments are configured

## References

- [PM2 Documentation](https://pm2.keymetrics.io/docs/usage/quick-start/)
- [Discord.py Sharding](https://discordpy.readthedocs.io/en/stable/ext/commands/api.html#sharding)
- [Prometheus Monitoring](https://prometheus.io/docs/introduction/overview/)
