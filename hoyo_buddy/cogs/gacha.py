from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands

from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.commands.gacha import GachaCommand
from hoyo_buddy.constants import get_describe_kwargs, get_rename_kwargs
from hoyo_buddy.db import HoyoAccount, show_anniversary_dismissible
from hoyo_buddy.utils.misc import handle_autocomplete_errors

from ..enums import GachaImportSource, Game
from ..hoyo.transformers import HoyoAccountTransformer
from ..types import Interaction

if TYPE_CHECKING:
    from ..bot import HoyoBuddy


class Gacha(
    commands.GroupCog,
    name=app_commands.locale_str("gacha-log"),  # pyright: ignore[reportArgumentType]
    description=app_commands.locale_str("Gacha log commands"),  # pyright: ignore[reportArgumentType]
):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    @app_commands.command(
        name=app_commands.locale_str("import"), description=COMMANDS["gacha-log import"].description
    )
    @app_commands.rename(**get_rename_kwargs(account=True))
    @app_commands.describe(**get_describe_kwargs(account_no_default=True))
    async def import_(
        self,
        i: Interaction,
        account: app_commands.Transform[
            HoyoAccount, HoyoAccountTransformer(COMMANDS["gacha-log import"].games)
        ],
    ) -> Any:
        account_ = account or await self.bot.get_account(
            i.user.id, (Game.GENSHIN, Game.ZZZ, Game.STARRAIL)
        )
        await GachaCommand.run_import(i, account_)
        await show_anniversary_dismissible(i)

    @app_commands.command(
        name=app_commands.locale_str("view"), description=COMMANDS["gacha-log view"].description
    )
    @app_commands.rename(**get_rename_kwargs(account=True))
    @app_commands.describe(**get_describe_kwargs(account_no_default=True))
    async def view_logs(
        self,
        i: Interaction,
        account: app_commands.Transform[
            HoyoAccount, HoyoAccountTransformer(COMMANDS["gacha-log view"].games)
        ],
    ) -> Any:
        account_ = account or await self.bot.get_account(
            i.user.id, (Game.GENSHIN, Game.ZZZ, Game.STARRAIL)
        )
        await GachaCommand.run_view(i, account_)
        await show_anniversary_dismissible(i)

    @app_commands.command(
        name=app_commands.locale_str("manage"), description=COMMANDS["gacha-log manage"].description
    )
    @app_commands.rename(**get_rename_kwargs(account=True))
    @app_commands.describe(**get_describe_kwargs(account_no_default=True))
    async def manage_logs(
        self,
        i: Interaction,
        account: app_commands.Transform[
            HoyoAccount, HoyoAccountTransformer(COMMANDS["gacha-log manage"].games)
        ],
    ) -> Any:
        account_ = account or await self.bot.get_account(
            i.user.id, (Game.GENSHIN, Game.ZZZ, Game.STARRAIL)
        )
        await GachaCommand.run_manage(i, account_)
        await show_anniversary_dismissible(i)

    @app_commands.command(
        name=app_commands.locale_str("upload"), description=COMMANDS["gacha-log upload"].description
    )
    @app_commands.rename(
        source=app_commands.locale_str("source", key="source_param_name"),
        file=app_commands.locale_str("file", key="file_param_name"),
        **get_rename_kwargs(account=True),
    )
    @app_commands.describe(
        source=app_commands.locale_str(
            "Source of the gacha history", key="source_param_description"
        ),
        file=app_commands.locale_str("Gacha history file to upload", key="file_param_description"),
        **get_describe_kwargs(account_no_default=True),
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
        account: app_commands.Transform[
            HoyoAccount, HoyoAccountTransformer(COMMANDS["gacha-log upload"].games)
        ],
        file: discord.Attachment,
    ) -> Any:
        await GachaCommand.run_upload(i, account, GachaImportSource(source), file)
        await show_anniversary_dismissible(i)

    @import_.autocomplete("account")
    @upload.autocomplete("account")
    @view_logs.autocomplete("account")
    @manage_logs.autocomplete("account")
    @handle_autocomplete_errors
    async def account_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current)


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Gacha(bot))
