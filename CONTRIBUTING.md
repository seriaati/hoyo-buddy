# Contribution Guidelines

Hi, thank you for being interested in contributing to Hoyo Buddy, let's get started!  
In case you have any questions, you can [DM me on Discord](https://discord.com/users/410036441129943050) or join the [Discord server](https://dsc.gg/hoyo-buddy) and tag me there.

## Translation Contributions

Translations of Hoyo Buddy are hosted on [Transifex](https://app.transifex.com/seria/hoyo-buddy/dashboard/), to contribute, DM me your e-mail and the language you want to translate so I can add you to the translation team.
For languages available, see [Discord's documentation](https://discord.com/developers/docs/reference#locales).

## Code Contributions

Note: This guide may become outdated as the project evolves, most things should still be relevant over time, but if you find anything wrong or confusing, please open an issue or DM me on Discord (seria_ati).

### Prerequisites

Before contributing, make sure you have basic understandings of the following:  

- Python
- Asyncio
- SQL
- [discord.py](https://github.com/Rapptz/discord.py)
- [Pillow](https://github.com/python-pillow/Pillow) (only if your contribution is about image generation)

### Tools Needed

- Any IDE, ones that support language server protocols are preferred
- Git
- [uv](https://docs.astral.sh/uv/)

### Setting Up

#### Development Environment

1. Fork this repo and clone it to your environment using `git clone`
2. Install the dependencies with `uv sync`
3. Install ruff with `uv tool install ruff`
4. Install the [ruff VSCode extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff).
5. Install the [Pylance VSCode extension](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance).

#### Discord Bot

1. Create a new Discord application and bot on the [Discord Developer Portal](https://discord.com/developers/applications), save the bot token.
2. Invite the bot to your server.
3. Go to OAuth2 and save the client ID and client secret.
4. Put `http://localhost:8645/custom_oauth_callback` as a redirect URL.
5. Put `DISCORD_TOKEN`, `DISCORD_CLIENT_ID`, and `DISCORD_CLIENT_SECRET` in a `.env` file in the root directory.

#### Database

1. Download and install [PostgreSQL](https://www.postgresql.org/download/).
2. Create a new database named `hoyobuddy`.
3. Put `DATABASE_URL` in the `.env` file: `postgres://postgres:postgres@localhost:5432/hoyobuddy`
4. Run initial migrations with `uv run aerich upgrade`.

If you ever make changes to the database models, make sure to create a new migration with `uv run aerich migrate`.

#### CLI Arguments

Some features require additional CLI arguments to be passed when running the bot, here are the available arguments:

- `--sentry`: Enable Sentry SDK.
- `--search`: Run the search autocomplete setup task.
- `--schedule`: Load the [`schedule`](https://github.com/seriaati/hoyo-buddy/blob/main/hoyo_buddy/cogs/schedule.py) cog.
- `--prometheus`: Load the [`prometheus`](https://github.com/seriaati/hoyo-buddy/blob/main/hoyo_buddy/cogs/prometheus.py) cog, which starts the prometheus metrics server.
- `--novelai`: Enable NovelAI integration features.

#### Environment Variables

Only the following environment variables are required to run the bot:

- `DISCORD_TOKEN`
- `DISCORD_CLIENT_ID`
- `DISCORD_CLIENT_SECRET`
- `DATABASE_URL`
- `FERNET_KEY` (can use any value in development)

### Code Style and Quality

To prevent errors in the earliest stage possible, and to ensure consistent code style, this project uses basedpyright for type checking, and ruff for linting and formatting.

There are GitHub Actions set up to check for type and linting errors on pull requests, you will be required to fix any errors before your pull request can be merged.

You **MUST** write your code with proper type hints, and make sure there are no type errors. If you have the Pylance and ruff VSCode extension installed, you should see red (for type errors) and yellow (for linting errors) squiggly lines under problematic code. Make sure there are none before submitting your PR.

#### Commands

To check for type errors, run:

```bash
basedpyright
```

To check for linting errors + formatting + auto-fixes, run:

```bash
ruff check . --fix --unsafe-fixes && ruff format .
```

#### About Type Hints

Besides the basics of typing the function signatures, here are some additional guidelines:

Initialize empty lists or dicts with types:

```py
my_list: list[int] = []
my_dict: dict[str, int] = {}
```

Although this project doesn't enforce it, try to avoid Unknown types, you can use `Any` when necessary. (e.g. when dealing with dynamic data from external sources)

```py
from typing import Any

my_dict: dict[str, Any] = {}
```

Do not use asserts for type narrowing, use `typing.cast` instead:

```py
from typing import cast

value = cast(str, value)
```

#### About Functions

Try to keep your functions small and simple. Basically, follow the basic principles of clean code. This project has lint rules for maximum function length, variable, and complexity to enforce this. However, if you think a function needs to be longer or more complex for a valid reason, feel free to add `# noqa` comments.

#### About File Structure

Try to keep related code together and put stuff in where it makes the most sense.

- Cog: `hoyo_buddy/cogs/`.
- Utility function:  `hoyo_buddy/utils/`.
- Database models: `hoyo_buddy/models/`.
- Types: `hoyo_buddy/types.py`.
- Constants: `hoyo_buddy/constants.py`.

And so on.

### Making a Contribution

1. Create a new branch from `main` for your changes, like `feat/my-new-feature` or `fix/bug-description`.
2. Make your changes.
3. Commit your changes with clear and descriptive commit messages.
4. Push your branch to your forked repository.
5. Open a pull request to the `main` branch of this repository.

### Components

Hoyo Buddy is made up of several components:

- Bot: The Discord bot, run with `uv run run.py`.
- Scheduler: A background task scheduler for tasks like auto check-in and auto mimo, run with `uv run run_scheduler.py`.
- Web app: Web application for login and gacha-log viewing, run with `uv run run_web_app.py`.
- Web server: Web server for displaying Geetests, run with `uv run run_web_server.py`.
