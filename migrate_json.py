from __future__ import annotations

import asyncio
import logging
import os

from seria import utils

from hoyo_buddy.db.models import JSONFile
from hoyo_buddy.db.pgsql import Database

LOGGER_ = logging.getLogger("migrate_json")


async def main() -> None:
    async with Database():
        # Migrate talent level data
        folder = "./.static/talent_levels"
        for filename in os.listdir(folder):
            if not filename.endswith(".json"):
                continue

            data = await utils.read_json(f"{folder}/{filename}")

            await JSONFile.write(f"talent_levels/{filename}", data)

        # Migrate PC icon data
        folder = "./.static/pc_icons.json"
        data = await utils.read_json(folder)
        await JSONFile.write("pc_icons.json", data)

        # Migrate talent boost data
        folder = "./.static/talent_boost.json"
        data = await utils.read_json(folder)
        await JSONFile.write("talent_boost.json", data)


if __name__ == "__main__":
    LOGGER_.info("Migrating JSON data...")
    asyncio.run(main())
    LOGGER_.info("Migration complete.")
