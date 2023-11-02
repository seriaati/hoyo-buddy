import logging
from pathlib import Path
from typing import List, Optional

import discord
import sentry_sdk
from aiohttp import ClientSession
from discord.ext import commands

from ..db import HoyoAccount
from . import AppCommandTranslator, Translator
from . import locale_str as _T

log = logging.getLogger(__name__)

__all__ = ("HoyoBuddy",)


class HoyoBuddy(commands.AutoShardedBot):
    def __init__(
        self,
        *args,
        session: ClientSession,
        env: str,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.session = session
        self.uptime = discord.utils.utcnow()
        self.translator = Translator(env)
        self.env = env

    async def setup_hook(self):
        await self.translator.load()
        await self.tree.set_translator(AppCommandTranslator(self.translator))

        for filepath in Path("hoyo_buddy/cogs").glob("**/*.py"):
            cog_name = Path(filepath).stem
            try:
                await self.load_extension(f"hoyo_buddy.cogs.{cog_name}")
                log.info("Loaded cog %r", cog_name)
            except Exception:  # skipcq: PYL-W0703
                log.error("Failed to load cog %r", cog_name, exc_info=True)

        await self.load_extension("jishaku")

    def capture_exception(self, e: Exception) -> None:
        if self.env == "prod":
            sentry_sdk.capture_exception(e)
        else:
            log.exception(e)

    async def get_or_fetch_user(self, user_id: int) -> Optional[discord.User]:
        user = self.get_user(user_id)
        if user:
            return user

        try:
            user = await self.fetch_user(user_id)
        except discord.HTTPException:
            return None
        else:
            return user

    @staticmethod
    async def account_autocomplete(
        user_id: int, current: str, locale: discord.Locale, translator: Translator
    ) -> List[discord.app_commands.Choice]:
        accounts = await HoyoAccount.filter(user__id=user_id).all()
        if not accounts:
            return [
                discord.app_commands.Choice(
                    name=discord.app_commands.locale_str(
                        "You don't have any accounts yet. Add one with /accounts",
                        key="no_accounts_autocomplete_choice",
                    ),
                    value="none",
                )
            ]

        return [
            discord.app_commands.Choice(
                name=f"{account} | {translator.translate(_T(account.game, warn_no_key=False), locale)}",
                value=f"{account.uid}_{account.game}",
            )
            for account in accounts
            if current in str(account)
        ]

    async def close(self):
        log.info("Shutting down...")
        await self.translator.unload()
        await super().close()
