from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "connections": {"default": os.environ["DB_URL"]},
    "apps": {
        "models": {
            "models": ["hoyo_buddy.db.models", "aerich.models"],
            "default_connection": "default",
        }
    },
    "use_tz": True,
    "minsize": 1,
    "maxsize": 20,
}
