from __future__ import annotations

from typing import Any, Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

type EnvType = Literal["dev", "test", "prod"]
type Deployment = Literal["main", "sub"]


class Config(BaseSettings):
    # Discord
    discord_token: str
    discord_client_id: int
    discord_client_secret: str

    # AI image generation
    nai_token: str | None = None
    nai_host_url: str | None = None

    # API keys
    hoyo_codes_api_key: str | None = None
    img_upload_api_key: str | None = None

    # Misc
    env: EnvType = "dev"
    sentry_dsn: str | None = None
    db_url: str
    fernet_key: str
    proxy: str
    redis_url: str | None = None

    # Command-line arguments
    search: bool = False
    sentry: bool = False
    schedule: bool = False
    prometheus: bool = False
    novelai: bool = False
    deployment: Deployment = "main"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", cli_parse_args=True, cli_implicit_flags=True
    )

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    @property
    def cli_args(self) -> dict[str, Any]:
        return {
            "search": self.search,
            "sentry": self.sentry,
            "schedule": self.schedule,
            "prometheus": self.prometheus,
            "novelai": self.novelai,
            "deployment": self.deployment,
        }


load_dotenv()
CONFIG = Config()  # pyright: ignore[reportCallIssue]
