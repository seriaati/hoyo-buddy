# Copilot Instructions for Hoyo Buddy

## Overview

Discord bot (user app) for Hoyoverse games with multi-game/account/language support. Python 3.12+, discord.py, PostgreSQL/Tortoise ORM, Pillow image generation, Flet web auth, uv package manager.

## Development Workflow (ALWAYS THIS ORDER)

**1. Install dependencies** (required first, ~30-60s):
```bash
uv sync --frozen
```

**2. Make changes**, then validate:
```bash
ruff format                         # Format code (100 char lines)
ruff check --fix --unsafe-fixes     # Auto-fix linting
pyright hoyo_buddy/                 # Type check (~30-60s, ignore missing import errors)
```

**3. Database changes** (if models modified):
```bash
aerich migrate      # Generate migration
aerich upgrade      # Apply migration
```

**4. Run locally**:
```bash
python run.py              # Bot (needs .env: discord_token, discord_client_id, discord_client_secret, db_url, fernet_key)
python run_web_app.py      # Auth web app
pm2 start pm2.json         # Production (5 processes)
```

## Code Standards

- **First import ALWAYS**: `from __future__ import annotations`
- **Type hints**: Required on all functions (pyright standard mode)
- **Docstrings**: Google-style for public APIs
- **Async**: Use async/await throughout, no blocking I/O
- **No unnecessary comments**: Code should be self-documenting
- **Line length**: 100 characters max
- **Dependencies**: Add to `pyproject.toml`, run `uv sync`, use `[tool.uv.sources]` for git dependencies

## Architecture Patterns

**Multi-Game Design**: Game enum (`Game.GENSHIN`, `Game.STARRAIL`, `Game.ZZZ`, `Game.HONKAI`, `Game.TOT`) drives polymorphic behavior. See `hoyo_buddy/enums.py` for full list and `hoyo_buddy/draw/funcs/` for game-specific implementations.

**Discord Bot Structure**:
- `hoyo_buddy/cogs/` - Discord.py cogs group commands (e.g., `build.py`, `profile.py`)
- `hoyo_buddy/commands/` - Command logic implementations
- `hoyo_buddy/ui/discord/` - Custom UI wrappers (`View`, `Modal`, `Button`, `Select`) with localization
- `hoyo_buddy/ui/hoyo/` - Game-specific UI components

**Database Layer** (Tortoise ORM):
- Models: `User`, `HoyoAccount` (multi-account per user per game), `Settings`, `NotesNotify`, `CardSettings`
- Async only, PostgreSQL backend
- Migrations: `aerich migrate` after model changes, files in `migrations/models/`

**Internationalization** (`l10n/`):
- YAML files per locale (13+ languages), managed via Transifex
- `LocaleStr` class with `.translate()` method
- `Translator` singleton with game-specific mi18n data
- Discord locale enum: `Locale.american_english`, `Locale.japanese`, etc.

**Image Generation** (`hoyo_buddy/draw/`):
- `Drawer` class: Pillow-based, locale-aware font rendering
- Assets in `hoyo-buddy-assets/` submodule (images, fonts)
- Game-specific card templates in `draw/funcs/genshin.py`, `draw/funcs/hsr.py`, etc.

**API Clients** (`hoyo_buddy/hoyo/clients/`):
- `gpy.py`: HoYoLAB/Miyoushe (via genshin.py)
- `ambr.py`, `yatta.py`, `hakushin.py`: Game data
- `enka/`: Player showcase data
- All async with error handling

**Auto Tasks** (`hoyo_buddy/hoyo/auto_tasks/`):
- `daily_checkin.py`: Auto check-in
- `auto_redeem.py`: Gift code redemption
- `notes_check.py`: Resin/stamina notifications
- APScheduler-based, triggered by `run_scheduler.py`

## Critical Gotchas

1. **CI workaround**: GitHub Actions requires `uv pip uninstall uvloop` after `uv sync` (see `.github/workflows/pyright.yml`)
2. **Pyright import errors**: Expect missing import errors for some dependencies - ignore them per CLAUDE.md
3. **Git submodule**: `hoyo-buddy-assets/` may need `git submodule update --init` after clone
4. **Test files excluded**: `test*.py` ignored by git and linting (see `.gitignore`, `ruff.toml`)
5. **Bot data**: `hoyo_buddy/bot/data/*.json` excluded except `nsfw_tags.json`, `grafana_dashboard.json`

## File Locations Reference

| Feature | Location | Notes |
|---------|----------|-------|
| Discord commands | `hoyo_buddy/cogs/*.py` | Cogs inherit from `commands.Cog` or `commands.GroupCog` |
| Command logic | `hoyo_buddy/commands/*.py` | Business logic separated from Discord interface |
| DB models | `hoyo_buddy/db/models/*.py` | Tortoise ORM, async only |
| Error handling | `hoyo_buddy/bot/error_handler.py` | Centralized error → embed conversion |
| Game enums | `hoyo_buddy/enums.py` | `Game`, `Platform`, `ChallengeType`, `Locale`, etc. |
| Translations | `l10n/*.yaml` | Transifex-managed, DO NOT edit directly |
| Entry points | `run*.py` | Bot, web app, scheduler, web server |
| Config | `pyproject.toml`, `ruff.toml`, `pm2.json` | Dependencies, linting, production deployment |

## Adding New Features

**New command**: Add cog in `hoyo_buddy/cogs/`, logic in `hoyo_buddy/commands/`, translations in `l10n/en_US.yaml`
**New game support**: Add enum to `Game`, create `draw/funcs/<game>.py`, update UI components
**New DB model**: Add to `hoyo_buddy/db/models/`, run `aerich migrate`, update `__init__.py`
**New API client**: Add to `hoyo_buddy/hoyo/clients/`, follow async pattern with error handling

See CLAUDE.md, GEMINI.md for extended AI guidance. See CONTRIBUTING.md for prerequisites.