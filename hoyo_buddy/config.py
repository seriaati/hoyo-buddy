from __future__ import annotations

from typing import Any, Literal

from dotenv import load_dotenv
from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict

type EnvType = Literal["dev", "test", "prod"]


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

    # Sentry DSNs
    bot_sentry_dsn: str | None = None
    web_server_sentry_dsn: str | None = None
    web_app_sentry_dsn: str | None = None
    scheduler_sentry_dsn: str | None = None

    # Misc
    env: EnvType = "dev"
    db_url: str
    fernet_key: str
    proxy: str | None = None
    redis_url: str | None = None
    user_agent: str | None = "HoyoBuddy/1.0"

    # Heartbeat URLs
    scheduler_heartbeat_url: str | None = None
    heartbeat_url: str | None = None

    # Ports
    web_server_port: int | None = None
    web_app_port: int | None = None
    prometheus_port: int | None = None

    # Command-line arguments
    search: bool = False
    sentry: bool = False
    schedule: bool = False
    prometheus: bool = False
    novelai: bool = False

    # Logging configuration
    log_rotation_size: str = "20 MB"
    log_retention_count: int = 10
    log_compression: str = "gz"
    log_level: str = "DEBUG"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        cli_parse_args=True,
        cli_implicit_flags=True,
        cli_ignore_unknown_args=True,
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
        }


load_dotenv()
CONFIG = Config()  # pyright: ignore[reportCallIssue]
logger.info(f"CLI args: {CONFIG.cli_args}")
