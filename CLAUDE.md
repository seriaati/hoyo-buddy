# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hoyo Buddy is a feature-rich Discord bot for Hoyoverse gamers supporting multiple games (Genshin Impact, Honkai: Star Rail, Honkai Impact 3rd, Zenless Zone Zero, Tears of Themis). It runs as a Discord **user app** (no server invite required) with multi-game, multi-account, and multi-language support.

## Development Commands

All commands run under `uv`. Prefix scripts with `uv run` (e.g. `uv run run.py`).

### Package Management

```bash
uv sync                    # Install dependencies (incl. dev)
uv sync --frozen --no-dev  # Production dependencies only
```

Several core deps (`genshin`, `enka`, `ambr-py`, `yatta-py`, `akasha-py`, `hakushin`, `szgf`, `hb-data`, `novelai`) are installed from git forks under the maintainer's GitHub — see `[tool.uv.sources]` in `pyproject.toml`. Bumping them requires `uv lock`.

### Code Quality

```bash
uv run ruff check . --fix --unsafe-fixes && uv run ruff format .   # Lint + auto-fix + format (the canonical pre-PR command)
uv run pyright                                                     # Type checking (pinned to 1.1.408; missing-import errors can be ignored)
```

CI (GitHub Actions) enforces both ruff and pyright on PRs. `ruff` rules include limits on function length, argument count, and complexity — add a targeted `# noqa` with justification only when a longer function is genuinely warranted.

### Database Operations

```bash
uv run aerich migrate     # Create a migration after changing db models
uv run aerich upgrade     # Apply migrations (also used for first-time DB init)
```

Migrations live in `migrations/`. Aerich config points at `hoyo_buddy.db.config.DB_CONFIG` (see `[tool.aerich]` in `pyproject.toml`).

### Running Applications (three separate processes)

```bash
uv run run.py             # Discord bot
uv run run_api.py         # FastAPI server (login + gacha-log viewing)
uv run run_scheduler.py   # Background task scheduler (auto check-in, auto mimo, etc.)
pm2 start pm2.json        # Production: runs api + scheduler (bot is managed separately, see rolling_restart.py)
```

### Bot CLI Arguments (`run.py`)

- `--sentry` — enable Sentry SDK
- `--search` — run the search autocomplete setup task
- `--schedule` — load the `schedule` cog
- `--prometheus` — load the `prometheus` cog (starts the metrics server)
- `--novelai` — enable NovelAI integration features

### Required Environment Variables (`.env`)

`DISCORD_TOKEN`, `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DATABASE_URL` (e.g. `postgres://postgres:postgres@localhost:5432/hoyobuddy`), `FERNET_KEY` (any value in dev). Config is loaded via `pydantic-settings` in `hoyo_buddy/config.py` (`CONFIG`).

## Architecture Overview

The system is **three cooperating processes** sharing one PostgreSQL database and Redis cache:

1. **Bot** (`run.py` → `hoyo_buddy/bot/`) — the Discord client and command surface.
2. **API** (`run_api.py` → `hoyo_buddy/api/`) — FastAPI app for the web login flow and gacha-log import/viewing. The user-facing web frontend is a separate repo (`hb-app`).
3. **Scheduler** (`run_scheduler.py` → `hoyo_buddy/scheduler/`) — APScheduler-driven background jobs (auto check-in, code redemption, mimo, notifications) defined under `hoyo_buddy/hoyo/auto_tasks/`.

### Core Structure

- **hoyo_buddy/bot/** — Discord bot core: `bot.py`, `command_tree.py`, `error_handler.py`, `cache.py`
- **hoyo_buddy/cogs/** — discord.py cogs grouping commands (admin, build, challenge, characters, farm, gacha, hoyo, leaderboard, login, profile, search, settings, etc.)
- **hoyo_buddy/commands/** — command implementations invoked by cogs
- **hoyo_buddy/db/** — Tortoise ORM layer; models in `hoyo_buddy/db/models/` (`User`, `HoyoAccount`, `Settings`, `NotifSettings`, `GachaHistory`, `CardSettings`, `Leaderboard`, …)
- **hoyo_buddy/hoyo/** — game-specific logic: API `clients/`, `auto_tasks/`, `farm_data.py`, `transformers.py`, `search_autocomplete.py`
- **hoyo_buddy/ui/** — Discord UI components (views, modals, buttons)
- **hoyo_buddy/draw/** — Pillow-based image/card generation (`drawer.py`, `fonts.py`, `funcs/`, `main_funcs.py`)
- **hoyo_buddy/api/** — FastAPI app (`app.py`, `routers/`, `deps.py`, `session.py`)
- **hoyo_buddy/scheduler/** — scheduler entrypoint (`main.py`)
- **l10n/** — YAML translation files (13+ languages), synced via Transifex

### Key Design Patterns

**Multi-Game Architecture**: Game-specific behavior is keyed by the `Game` enum (`Game.GENSHIN`, `Game.STARRAIL`, `Game.ZZZ`, …) in `hoyo_buddy/enums.py`, with unified interfaces and per-game implementations.

**Database**: PostgreSQL via Tortoise ORM, async-only. Supports multiple accounts per user per game. Schema changes are migration-based with aerich.

**Internationalization**: YAML-based locale system (`hoyo_buddy/l10n.py`, `translator`), locale-aware formatting, managed on Transifex. See "Localization (l10n)" below for usage.

**Image Generation**: Asset-driven card rendering with per-game templates and multi-language font management. CPU-bound draw work runs in a `ProcessPoolExecutor` (prod) / `ThreadPoolExecutor` (dev), set up in `run.py`.

**Authentication Flow**: Web-based login handled by the FastAPI API (QR code, email/password, mobile) integrating HoYoLAB and Miyoushe, backed by `genshin.py`. Credentials are encrypted with `FERNET_KEY`.

**Caching**: `aiohttp-client-cache` over Redis (prod, via `REDIS_URL`) or SQLite (dev fallback), 12-hour expiry.

## Code Standards

Don't add unnecessary comments.

### Python Requirements

- **Python 3.12+** with `from __future__ import annotations` required in every module
- Async/await throughout; no blocking I/O in coroutines
- Type hints required (pyright standard mode). Annotate empty collections (`x: list[int] = []`). Avoid `Unknown`; use `typing.Any` for genuinely dynamic external data
- Do **not** use `assert` for type narrowing — use `typing.cast`
- Google-style docstrings; Pydantic for data validation
- Keep functions small (lint-enforced complexity/length limits)

### Ruff Configuration (`ruff.toml`)

- Line length: 100
- `from __future__ import annotations` is a required import
- Quoted annotations enabled

### File Placement Conventions

- Cogs → `hoyo_buddy/cogs/`
- Utility functions → `hoyo_buddy/utils/`
- Pydantic/data models → `hoyo_buddy/models/`
- Shared types → `hoyo_buddy/types.py`
- Constants → `hoyo_buddy/constants.py`

## Development Notes

### Assets

`hoyo-buddy-assets/` (private submodule) holds images and fonts for card generation, organized by game and feature. Font files back multi-language rendering.

### Localization (l10n)

All user-facing strings go through `LocaleStr` (defined in `hoyo_buddy/l10n.py`), never raw `str`. The global `translator` resolves a `LocaleStr` to a given `Locale` at render time.

**Adding a new string** — when a feature needs a new string, unless explicitly told otherwise:

1. Use `LocaleStr(key="my_new_key")` in code (UI labels, embed text, command descriptions, etc.).
2. Add **only** the corresponding key to `l10n/en_US.yaml`. This is the source language file (`SOURCE_LANG = "en_US"`) — do **not** edit the other `l10n/*.yaml` files; translators handle every other language via Transifex. Adding to `en_US.yaml` alone is sufficient (untranslated locales fall back to the en_US source string).

```python
from hoyo_buddy.l10n import LocaleStr

# en_US.yaml:  account_deleted_description: "{account} has been deleted."
label = LocaleStr(key="account_deleted_description", account=str(account))
text = label.translate(locale)          # or translator.translate(label, locale)
```

Key points:
- Keys are flat, dotted strings (e.g. `notif_modal.notify_interval.label`). Keyword args passed to `LocaleStr` fill `{placeholder}` slots in the YAML value via `str.format`.
- Never call `str()` on a `LocaleStr` — it logs an error. Always go through `.translate(locale)` / `translator.translate(...)`.
- Use `custom_str=...` for dynamic, non-translatable text; `default=...` for a fallback. Helper subclasses exist for common cases (`EnumStr`, `LevelStr`, `RarityStr`, `WeekdayStr`, `TimeRemainingStr`).
- Strings sourced from Hoyoverse's own data use `mi18n_game=` / `data_game=` instead of an `en_US.yaml` key — these are fetched, not authored.
- A missing source key logs `"String ... is missing in source lang file"` at runtime, so verify the key exists in `en_US.yaml`.

### Error Handling

Centralized in `hoyo_buddy/bot/error_handler.py` with Sentry integration and localized, user-friendly messages.

### Testing

There is currently **no automated test suite**. Quality gates are ruff + pyright via GitHub Actions; validate changes by running the relevant process and exercising the affected command/flow.

### Production Deployment

PM2 (`pm2.json`) runs the API and scheduler with `-OO`. The bot is deployed with a custom rolling-restart routine (`rolling_restart.py`) to avoid downtime.
