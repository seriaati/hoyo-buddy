# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hoyo Buddy is a feature-rich Discord bot for Hoyoverse gamers that supports multiple games (Genshin Impact, Honkai: Star Rail, Honkai Impact 3rd, Zenless Zone Zero, Tears of Themis). It operates as a Discord user app with multi-game, multi-account, and multi-language support.

## Development Commands

### Package Management
```bash
uv sync                    # Install dependencies
uv sync --frozen --no-dev  # Install production dependencies only
```

### Code Quality
```bash
ruff check                 # Lint code
ruff format               # Format code  
pyright hoyo_buddy/       # Type checking
```

### Database Operations
```bash
aerich migrate            # Create migrations
aerich upgrade            # Apply migrations
```

### Running Applications
```bash
python run.py             # Main Discord bot
python run_web_app.py     # Web authentication app
pm2 start pm2.json        # Production deployment (both apps)
```

## Architecture Overview

### Core Structure
- **hoyo_buddy/bot/** - Discord bot core (bot.py, command_tree.py, error_handler.py)
- **hoyo_buddy/cogs/** - Discord.py cogs for command organization
- **hoyo_buddy/commands/** - Command implementations
- **hoyo_buddy/db/** - Database layer with Tortoise ORM models
- **hoyo_buddy/hoyo/** - Game-specific logic and API clients
- **hoyo_buddy/ui/** - Discord UI components (views, modals, buttons)
- **hoyo_buddy/draw/** - Image generation system using Pillow
- **hoyo_buddy/web_app/** - Flet-based web application for authentication
- **l10n/** - Internationalization files (YAML format, 13+ languages)

### Key Design Patterns

**Multi-Game Architecture**: Game-specific logic separated by enum (`Game.GENSHIN`, `Game.STARRAIL`, etc.) with unified interfaces and game-specific implementations.

**Database Design**: PostgreSQL with Tortoise ORM for async operations. Models include User, HoyoAccount, Settings, NotifSettings supporting multiple accounts per user per game.

**Internationalization**: YAML-based translation system with locale-aware formatting managed via Transifex platform.

**Image Generation**: Asset-based card generation system with game-specific templates, font management for multi-language support, and performance optimization.

**Authentication Flow**: Web-based authentication using Flet framework supporting multiple login methods (QR code, email/password, mobile) with HoYoLAB and Miyoushe integration.

## Code Standards

### Python Requirements
- Python 3.11+ with `from __future__ import annotations`
- Async/await patterns throughout
- Type hints required (pyright standard mode)
- Google-style docstrings
- Pydantic for data validation

### Ruff Configuration
- Line length: 100 characters
- Comprehensive linting with project-specific ignores
- Required imports: `from __future__ import annotations`
- Quote annotations enabled for type checking

### Database Operations
- Tortoise ORM with PostgreSQL
- Migration-based schema changes with aerich
- Async operations only

## Key Dependencies

### Core Framework
- `discord.py[speed]>=2.5.0` - Discord API wrapper
- `tortoise-orm>=0.21.7` - Async ORM
- `asyncpg>=0.29.0` - PostgreSQL driver

### Game APIs
- `genshin[auth,sqlite,socks-proxy]` - HoYoLAB API wrapper
- `enka>=2.4.3` - Player showcase data
- `hakushin-py>=0.4.4` - Game data API
- `yatta-py>=1.3.11` - Star Rail data
- `ambr-py` - Genshin Impact data
- `akasha-py>=0.2.9` - Character leaderboards

### Utilities
- `loguru>=0.7.2` - Logging
- `pydantic>=2.8.2` - Data validation
- `pillow>=10.4.0` - Image processing
- `flet[web]>=0.26.0` - Web app framework

## Development Notes

### Asset Management
- `hoyo-buddy-assets/` contains images and fonts for card generation
- Assets organized by game and feature type
- Font files support multi-language rendering

### Error Handling
- Centralized error handling with Sentry integration
- User-friendly error messages with localization
- Comprehensive logging with structured output

### Testing
- Limited test coverage focusing on critical components
- Quality gates enforced via GitHub Actions
- Ruff and pyright checks required for CI

### Production Deployment
- PM2 configuration for process management
- Separate processes for bot and web authentication app
- Monitoring and logging integration