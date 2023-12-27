import os

from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "connections": {
        "default": os.getenv("DB_URL") or "sqlite://db.sqlite3",
    },
    "apps": {
        "models": {
            "models": ["hoyo_buddy.db.models", "aerich.models"],
            "default_connection": "default",
        }
    },
    "use_tz": False,
    "minsize": 1,
    "maxsize": 20,
}
