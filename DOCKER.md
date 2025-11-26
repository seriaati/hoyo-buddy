# Docker Deployment Guide

This guide covers deploying Hoyo Buddy using Docker and Docker Compose.

## Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose v2.0+
- Git (for cloning the repository with submodules)

### Initial Setup

1. **Clone the repository with submodules:**
   ```bash
   git clone --recurse-submodules https://github.com/seriaati/hoyo-buddy.git
   cd hoyo-buddy
   ```

2. **Create environment file:**
   ```bash
   cp .env.example .env
   ```

3. **Configure environment variables in `.env`:**
   - `DISCORD_TOKEN`: Your Discord bot token
   - `DISCORD_CLIENT_ID`: Your Discord application client ID
   - `DISCORD_CLIENT_SECRET`: Your Discord OAuth2 client secret
   - `POSTGRES_PASSWORD`: Secure password for PostgreSQL
   - `FERNET_KEY`: Generate with:
     ```bash
     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
     ```

4. **Build and start all services:**
   ```bash
   docker compose up -d
   ```

5. **Run database migrations:**
   ```bash
   docker compose exec bot-main aerich upgrade
   ```

## Architecture

The Docker Compose setup includes:

| Service | Purpose | Port | Depends On |
|---------|---------|------|------------|
| `postgres` | PostgreSQL database | 5432 (internal) | - |
| `redis` | Cache (optional) | 6379 (internal) | - |
| `bot-main` | Primary Discord bot instance | - | postgres |
| `bot-sub` | Secondary bot instance (load distribution) | - | postgres, bot-main |
| `web-app` | Flet authentication web app | 5173 | postgres |
| `scheduler` | Automated tasks (check-ins, notifications) | - | postgres |
| `web-server` | Geetest verification server | 8080 | postgres |

### Single Image, Multiple Services

All services use the **same Docker image** but run different entry points:
- **Efficient**: One image build for all services (~500MB-1GB vs 2.5-5GB for separate images)
- **Consistent**: All services use identical code and dependencies
- **Fast deployments**: Pull once, run everywhere

## Service Management

### Start all services:
```bash
docker compose up -d
```

### Start specific services:
```bash
docker compose up -d bot-main scheduler
```

### View logs:
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f bot-main

# Last 100 lines
docker compose logs --tail=100 bot-main
```

### Restart services (zero-downtime):
```bash
# Restart main bot first
docker compose restart bot-main

# Wait for main to be healthy, then restart sub
docker compose restart bot-sub

# Other services can restart independently
docker compose restart web-app scheduler web-server
```

### Stop services:
```bash
docker compose down
```

### Stop and remove volumes (⚠️ deletes data):
```bash
docker compose down -v
```

## Production Deployment

### Building for Production

1. **Build the image:**
   ```bash
   docker compose build
   ```

2. **Tag for registry:**
   ```bash
   docker tag hoyo-buddy:latest your-registry.com/hoyo-buddy:v1.16.13
   docker tag hoyo-buddy:latest your-registry.com/hoyo-buddy:latest
   ```

3. **Push to registry:**
   ```bash
   docker push your-registry.com/hoyo-buddy:v1.16.13
   docker push your-registry.com/hoyo-buddy:latest
   ```

### Dokploy Deployment

For Dokploy, you have two options:

#### Option A: Use Docker Compose (Recommended)
Upload `docker-compose.yml` and `.env` to Dokploy's compose application type.

#### Option B: Separate Services
Create individual services in Dokploy using the same image but different commands:
- `python -OO run.py --sentry --deployment main`
- `python -OO run.py --sentry --deployment sub`
- `python -OO run_web_app.py --sentry`
- `python -OO run_scheduler.py --sentry`
- `python -OO run_web_server.py --sentry`

### Health Checks

Services include health checks for proper orchestration:
- **PostgreSQL**: `pg_isready` check
- **Redis**: `redis-cli ping` check
- **Bot Main**: Process check (ensures bot is running)

Dependent services wait for upstream services to be healthy before starting.

### Zero-Downtime Restarts

The orchestration mimics your `restart.py` logic:
1. Restart `bot-main` first
2. Health check ensures all shards are connected
3. Restart `bot-sub` only after `bot-main` is healthy
4. Other services can restart independently

## Development

### Using Redis (Optional)

Enable Redis for distributed caching:

1. **Start Redis profile:**
   ```bash
   docker compose --profile redis up -d
   ```

2. **Set REDIS_URL in .env:**
   ```env
   REDIS_URL=redis://redis:6379/0
   ```

### Hot Reload with Docker Compose Watch

For active development with auto-reload on file changes:

```bash
docker compose watch
```

This will:
- Sync code changes instantly
- Rebuild on `pyproject.toml` changes
- Preserve `.venv` from the container

### Running Commands in Container

```bash
# Run migrations
docker compose exec bot-main aerich migrate
docker compose exec bot-main aerich upgrade

# Run linting/formatting
docker compose exec bot-main ruff format
docker compose exec bot-main ruff check --fix

# Type checking
docker compose exec bot-main pyright hoyo_buddy/

# Python shell
docker compose exec bot-main python

# Bash shell
docker compose exec bot-main bash
```

### Accessing Logs

Logs are persisted to `./logs/` on the host:
- `logs/hoyo_buddy.log` - Main bot logs
- `logs/web_app.log` - Web app logs
- `logs/scheduler.log` - Scheduler logs
- `logs/web_server.log` - Web server logs

## Optimizations

The Dockerfile includes several optimizations:

### Build Optimizations
- **Multi-stage build**: Separate builder and runtime stages
- **Bytecode compilation**: `UV_COMPILE_BYTECODE=1` for faster startup
- **Layer caching**: Dependencies cached separately from code
- **Copy mode**: `UV_LINK_MODE=copy` for cache mount compatibility

### Runtime Optimizations
- **Minimal base**: Uses Python 3.12 slim image (~50MB base)
- **Non-root user**: Runs as `hoyobuddy` user (UID 999)
- **Bytecode pre-compilation**: Improves cold start by ~30%
- **No uv in final image**: Runtime image doesn't include uv (~10MB saved)

### Security
- Non-root user execution
- Minimal runtime dependencies
- Separate build and runtime stages
- `.dockerignore` prevents sensitive files from being copied

## Troubleshooting

### Container won't start
```bash
# Check logs
docker compose logs bot-main

# Check if database is ready
docker compose exec postgres pg_isready
```

### Database connection issues
```bash
# Verify DB_URL format
postgresql://user:password@postgres:5432/database

# Test connection from container
docker compose exec bot-main python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('$DB_URL'))"
```

### Image build fails
```bash
# Clean build without cache
docker compose build --no-cache

# Verify submodules are initialized
git submodule update --init --recursive
```

### Out of disk space
```bash
# Clean up unused images/containers
docker system prune -a

# Clean up build cache
docker builder prune
```

## Environment Variables Reference

See `.env.example` for all available environment variables and their descriptions.

### Required Variables
- `DISCORD_TOKEN`
- `DISCORD_CLIENT_ID`
- `DISCORD_CLIENT_SECRET`
- `POSTGRES_PASSWORD`
- `FERNET_KEY`

### Optional Variables
- `REDIS_URL` - Enable Redis caching
- `*_SENTRY_DSN` - Enable Sentry error tracking
- `IS_DEV` - Development mode flag

## Migration from PM2

### What's Different

| PM2 | Docker Compose |
|-----|----------------|
| `pm2 start pm2.json` | `docker compose up -d` |
| `pm2 restart hb-main` | `docker compose restart bot-main` |
| `pm2 logs hb-main` | `docker compose logs -f bot-main` |
| `pm2 stop all` | `docker compose down` |
| `.venv/bin/python` | Container handles Python path |

### Zero-Downtime Restarts

Your `restart.py` script logic is now handled by:
1. Docker health checks
2. Service dependencies (`depends_on` with `condition: service_healthy`)
3. Restart policies

### Database Migrations

Run migrations the same way, but through `docker compose exec`:
```bash
docker compose exec bot-main aerich migrate
docker compose exec bot-main aerich upgrade
```

## Additional Resources

- [uv Docker Guide](https://docs.astral.sh/uv/guides/integration/docker/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Dokploy Documentation](https://dokploy.com/docs)
