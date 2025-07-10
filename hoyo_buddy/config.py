from __future__ import annotations

from typing import Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

from hoyo_buddy.types import Deployment

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
    deployment: Deployment = "main"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", cli_parse_args=True, cli_implicit_flags=True
    )

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    @property
    def cli_args(self) -> dict[str, bool]:
        return {
            "search": self.search,
            "sentry": self.sentry,
            "schedule": self.schedule,
            "prometheus": self.prometheus,
            "novelai": self.novelai,
            "web_server": self.web_server,
        }


load_dotenv()
CONFIG = Config()  # pyright: ignore[reportCallIssue]
