from __future__ import annotations

import argparse
from typing import Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

type EnvType = Literal["dev", "test", "prod"]


class Config(BaseSettings):
    # Discord
    discord_token: str
    discord_client_id: int
    discord_client_secret: str

    # AI image generation
    nai_token: str
    nai_host_url: str

    # Proxy API URLs
    render_url: str
    render2_url: str
    render3_url: str
    render4_url: str
    fly_url: str
    fly2_url: str
    railway_url: str
    vercel_url: str
    leapcell_url: str

    # API keys
    daily_checkin_api_token: str
    hoyo_codes_api_key: str
    img_upload_api_key: str

    # Misc
    env: EnvType = "dev"
    sentry_dsn: str
    db_url: str
    fernet_key: str

    # Command-line arguments
    search: bool
    sentry: bool
    schedule: bool
    prometheus: bool
    novelai: bool

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--search", action="store_true", help="Enable search")
    parser.add_argument("--sentry", action="store_true", help="Enable sentry")
    parser.add_argument("--schedule", action="store_true", help="Enable schedule")
    parser.add_argument("--prometheus", action="store_true", help="Enable Prometheus")
    parser.add_argument("--novelai", action="store_true", help="Enable NovelAI")
    return parser.parse_args()


if __name__ == "__main__":
    load_dotenv()
    args = parse_args()
else:
    args = argparse.Namespace(search=False, sentry=False, schedule=False)

CONFIG = Config(
    search=args.search,
    sentry=args.sentry,
    schedule=args.schedule,
    prometheus=args.prometheus,
    novelai=args.novelai,
)  # pyright: ignore[reportCallIssue]
