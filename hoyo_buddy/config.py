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

    # API keys
    hoyo_codes_api_key: str
    img_upload_api_key: str

    # Misc
    env: EnvType = "dev"
    sentry_dsn: str
    db_url: str
    fernet_key: str
    proxy: str

    # Command-line arguments
    search: bool = False
    sentry: bool = False
    schedule: bool = False
    prometheus: bool = False
    novelai: bool = False
    web_server: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def update_from_args(self, args: argparse.Namespace) -> None:
        self.search = args.search
        self.sentry = args.sentry
        self.schedule = args.schedule
        self.prometheus = args.prometheus
        self.novelai = args.novelai
        self.web_server = args.web_server

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"


def parse_args(*, default: bool) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--search", action="store_true", help="Enable search", default=default)
    parser.add_argument("--sentry", action="store_true", help="Enable sentry", default=default)
    parser.add_argument("--schedule", action="store_true", help="Enable schedule", default=default)
    parser.add_argument(
        "--prometheus", action="store_true", help="Enable Prometheus", default=default
    )
    parser.add_argument("--novelai", action="store_true", help="Enable NovelAI", default=default)
    parser.add_argument(
        "--web-server", action="store_true", help="Enable web server", default=default
    )
    return parser.parse_args()


load_dotenv()
CONFIG = Config()  # pyright: ignore[reportCallIssue]
