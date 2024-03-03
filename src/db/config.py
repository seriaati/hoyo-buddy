import os

from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "connections": {
        "default": os.environ["DB_URL"],
    },
    "apps": {
        "models": {
            "models": ["src.db.models", "aerich.models"],
            "default_connection": "default",
        }
    },
    "use_tz": False,
    "minsize": 1,
    "maxsize": 20,
}
