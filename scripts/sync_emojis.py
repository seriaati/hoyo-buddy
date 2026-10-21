"""Sync the emojis in hoyo-buddy-assets/assets/emojis to the bot's application emojis.

Uploads images whose name (file stem) isn't an application emoji of the bot yet, then writes the
emoji markdowns to hoyo_buddy/emoji_ids.json under the current env (CONFIG.env), which
hoyo_buddy/emojis.py reads. Run it with the dev and prod bot's .env after adding an emoji:
    uv run scripts/sync_emojis.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import discord
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from hoyo_buddy.config import CONFIG

EMOJI_DIR = Path("hoyo-buddy-assets/assets/emojis")
EMOJI_IDS_PATH = Path("hoyo_buddy/emoji_ids.json")


async def main() -> None:
    files = sorted(f for f in EMOJI_DIR.iterdir() if f.suffix in {".png", ".gif"})

    async with discord.Client(intents=discord.Intents.none()) as client:
        await client.login(CONFIG.discord_token)
        app_emojis = {emoji.name: emoji for emoji in await client.fetch_application_emojis()}

        for file in files:
            name = file.stem
            if name in app_emojis:
                continue

            app_emojis[name] = await client.create_application_emoji(
                name=name, image=file.read_bytes()
            )
            logger.info(f"Created emoji {name!r}")

    emoji_ids = json.loads(EMOJI_IDS_PATH.read_text(encoding="utf-8"))
    emoji_ids[CONFIG.env] = {file.stem: str(app_emojis[file.stem]) for file in files}
    EMOJI_IDS_PATH.write_text(json.dumps(emoji_ids, indent=2) + "\n", encoding="utf-8")
    logger.info(f"Wrote {len(files)} emojis for env {CONFIG.env!r} to {EMOJI_IDS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
