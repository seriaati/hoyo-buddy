from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from hoyo_buddy.commands.gacha import GachaCommand
from hoyo_buddy.db import HoyoAccount, get_locale

from ..enums import GachaImportSource, Game
from ..hoyo.transformers import HoyoAccountTransformer  # noqa: TC001

if TYPE_CHECKING:
    from ..bot import HoyoBuddy
    from ..types import Interaction, User


class Gacha(
    commands.GroupCog,
    name=app_commands.locale_str("gacha-log"),
    description=app_commands.locale_str("Gacha log commands"),
):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    @app_commands.command(
        name=app_commands.locale_str("import"),
        description=app_commands.locale_str(
            "Import gacha history from the game", key="gacha_import_command_description"
        ),
    )
    @app_commands.rename(
        account=app_commands.locale_str("account", key="account_autocomplete_param_name")
    )
    @app_commands.describe(
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
        )
    )
    async def import_(
        self,
        i: Interaction,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> Any:
        account_ = account or await self.bot.get_account(
            i.user.id, (Game.GENSHIN, Game.ZZZ, Game.STARRAIL)
        )
        await GachaCommand().run_import(i, account_)

    @app_commands.command(
        name=app_commands.locale_str("view"),
        description=app_commands.locale_str(
            "View imported gacha logs", key="gacha_view_command_description"
        ),
    )
    @app_commands.rename(
        account=app_commands.locale_str("account", key="account_autocomplete_param_name")
    )
    @app_commands.describe(
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
        )
    )
    async def view_logs(
        self,
        i: Interaction,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> Any:
        account_ = account or await self.bot.get_account(
            i.user.id, (Game.GENSHIN, Game.ZZZ, Game.STARRAIL)
        )
        await GachaCommand().run_view(i, account_)

    @app_commands.command(
        name=app_commands.locale_str("manage"),
        description=app_commands.locale_str(
            "Manage imported gacha logs", key="gacha_manage_command_description"
        ),
    )
    @app_commands.rename(
        account=app_commands.locale_str("account", key="account_autocomplete_param_name")
    )
    @app_commands.describe(
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
        )
    )
    async def manage_logs(
        self,
        i: Interaction,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> Any:
        account_ = account or await self.bot.get_account(
            i.user.id, (Game.GENSHIN, Game.ZZZ, Game.STARRAIL)
        )
        await GachaCommand().run_manage(i, account_)

    @app_commands.command(
        name=app_commands.locale_str("upload"),
        description=app_commands.locale_str(
            "Upload gacha history file from other sources to import to Hoyo Buddy",
            key="gacha_upload_command_description",
        ),
    )
    @app_commands.rename(
        source=app_commands.locale_str("source", key="source_param_name"),
        file=app_commands.locale_str("file", key="file_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        source=app_commands.locale_str(
            "Source of the gacha history", key="source_param_description"
        ),
        file=app_commands.locale_str("Gacha history file to upload", key="file_param_description"),
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
        ),
    )
    @app_commands.choices(
        source=[
            app_commands.Choice(name=source.value, value=source.value)
            for source in GachaImportSource
        ]
    )
    async def upload(
        self,
        i: Interaction,
        source: str,
        account: app_commands.Transform[HoyoAccount, HoyoAccountTransformer],
        file: discord.Attachment,
    ) -> Any:
        await GachaCommand().run_upload(i, account, GachaImportSource(source), file)

    @import_.autocomplete("account")
    @upload.autocomplete("account")
    @view_logs.autocomplete("account")
    @manage_logs.autocomplete("account")
    async def account_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)
        user: User = i.namespace.user
        return await self.bot.get_account_choices(
            user, i.user.id, current, locale, games=(Game.GENSHIN, Game.ZZZ, Game.STARRAIL)
        )


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Gacha(bot))
