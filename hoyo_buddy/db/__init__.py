import logging
from types import TracebackType
from typing import Optional, Type

from tortoise import Tortoise

log = logging.getLogger(__name__)


class Database:
    def __init__(self, db_url: Optional[str]):
        self.db_url = db_url or "sqlite://db.sqlite3"

    async def __aenter__(self):
        DB_CONFIG = {
            "connections": {
                "default": self.db_url,
            },
            "apps": {
                "models": {
                    "models": ["hoyo_buddy.db.models"],
                    "default_connection": "default",
                }
            },
            "use_tz": False,
            "minsize": 1,
            "maxsize": 20,
        }

        await Tortoise.init(config=DB_CONFIG)
        log.info("Connected to database")
        await Tortoise.generate_schemas()

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ):
        await Tortoise.close_connections()
