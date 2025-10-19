# Copilot Instructions for Hoyo Buddy

## Project Overview

**Hoyo Buddy** is a Discord bot for Hoyoverse games (Genshin, Star Rail, HI3, ZZZ, ToT) with multi-game, multi-account, multi-language support. Python 3.12+, 288 files, ~9.3MB. Uses discord.py, PostgreSQL/Tortoise ORM, Pillow, Flet, and uv package manager.

## Build & Validation Commands (ALWAYS IN THIS ORDER)

### 1. Install Dependencies (REQUIRED FIRST)
```bash
uv sync --frozen  # ~30-60s, MUST run before any other command
```

### 2. Lint & Format
```bash
ruff check --fix --unsafe-fixes  # Auto-fix lint issues
ruff format                       # Format code
```
- Line length: 100 chars, requires `from __future__ import annotations` as first import

### 3. Type Check
```bash
pyright hoyo_buddy/  # ~30-60s, missing import errors can be ignored
```

### 4. Database Migrations (if models changed)
```bash
aerich migrate    # Create migrations
aerich upgrade    # Apply migrations
```

### 5. Run Applications
```bash
python run.py              # Main bot (requires .env file)
python run_web_app.py      # Web auth app
pm2 start pm2.json         # Production: all services
```

## CI/CD - Primary Validation Gate

**pyright.yml** (runs on push/PR):
1. Install uv: `astral-sh/setup-uv@v7`
2. `uv sync --frozen`
3. `uv pip uninstall uvloop` (workaround for CI)
4. `jakebailey/pyright-action@v2` on `hoyo_buddy/` with `--outputjson`

**Pre-commit:** ruff + ruff-format (auto-runs on commit)

## Project Structure

**Key Directories:**
- `hoyo_buddy/bot/` - Discord bot core (bot.py, command_tree.py, error_handler.py)
- `hoyo_buddy/cogs/` - Discord.py cogs
- `hoyo_buddy/commands/` - Command implementations
- `hoyo_buddy/db/models/` - Tortoise ORM models (User, HoyoAccount, Settings, NotifSettings)
- `hoyo_buddy/draw/funcs/` - Image generation by game (Pillow-based)
- `hoyo_buddy/hoyo/clients/` - API clients (ambr, yatta, hakushin, enka, akasha)
- `hoyo_buddy/hoyo/auto_tasks/` - Automated tasks (check-in, redemption)
- `hoyo_buddy/ui/hoyo/` - Game-specific UI (views, modals, buttons)
- `hoyo_buddy/web_app/` - Flet-based web authentication
- `l10n/` - i18n YAML files (13+ languages, Transifex-managed)
- `migrations/models/` - Aerich database migrations
- `hoyo-buddy-assets/` - Images/fonts (git submodule)

**Config Files:** pyproject.toml (deps, pyright, aerich), ruff.toml (linting), pm2.json (5 processes)

**Entry Points:** run.py (bot), run_web_app.py (auth), run_scheduler.py, run_web_server.py

## Code Standards

**Python:** 3.12+, `from __future__ import annotations` required, type hints on all functions, Google-style docstrings, async/await throughout, no unnecessary comments

**Ruff:** 100 char lines, quote annotations enabled, special ignores for migrations/tests/draw

**Database:** Tortoise ORM with PostgreSQL, async only, migrations required after model changes

## Architecture Patterns

**Multi-Game:** Game enum (`Game.GENSHIN`, `Game.STARRAIL`, `Game.ZZZ`) with unified interfaces
**Database:** Multi-account per user per game support
**i18n:** YAML translations with locale-aware formatting
**Images:** Asset-based card generation with game-specific templates
**Auth:** Flet web app with QR/email/mobile login for HoYoLAB/Miyoushe

## Critical Workarounds

1. **uvloop in CI:** Run `uv pip uninstall uvloop` after `uv sync` (causes issues in GitHub Actions)
2. **Pyright import errors:** Missing import errors can be ignored (expected behavior per CLAUDE.md)
3. **Environment:** Requires `.env` with `discord_token`, `discord_client_id`, `discord_client_secret`, `db_url`, `fernet_key`
4. **Assets:** `hoyo-buddy-assets/` is git submodule, may need `git submodule update --init`
5. **Tests:** Limited test coverage - focus on critical components only

## Common Workflows

**Code Change:** `uv sync --frozen` → make changes → `ruff format` → `ruff check --fix --unsafe-fixes` → `pyright hoyo_buddy/` → if DB changed: `aerich migrate`

**Add Dependency:** Edit `pyproject.toml` → `uv sync` (updates uv.lock) → git sources in `[tool.uv.sources]`

**Excluded from Git:** .venv/, .env, *.log, test*.py, .cache/, hoyo_buddy/bot/data/*.json (except whitelist)

## Reference Documentation

See CLAUDE.md and GEMINI.md for AI-specific guidance. See CONTRIBUTING.md for contribution process. Trust these instructions - they were validated against actual repo structure and CI. Only search if info is incomplete or errors occur.
