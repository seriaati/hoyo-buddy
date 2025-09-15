from __future__ import annotations

from typing import TYPE_CHECKING, cast

from discord import app_commands
from discord.ext import commands

from hoyo_buddy.commands.characters import CharactersCommand
from hoyo_buddy.commands.configs import COMMANDS, CommandName
from hoyo_buddy.constants import get_describe_kwargs, get_rename_kwargs
from hoyo_buddy.db import HoyoAccount, Settings
from hoyo_buddy.db.utils import show_anniversary_dismissible
from hoyo_buddy.hoyo.transformers import HoyoAccountTransformer
from hoyo_buddy.types import Interaction, User
from hoyo_buddy.utils import ephemeral
from hoyo_buddy.utils.misc import handle_autocomplete_errors

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy


class Characters(
    commands.GroupCog,
    name=app_commands.locale_str("characters"),  # pyright: ignore[reportArgumentType]
    description=app_commands.locale_str("Characters commands"),  # pyright: ignore[reportArgumentType]
):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    async def characters_command(
        self, i: Interaction, user: User, account: HoyoAccount | None
    ) -> None:
        user = user or i.user
        await i.response.defer(ephemeral=ephemeral(i))

        if not isinstance(i.command, app_commands.Command):
            msg = "i.command is not an instance of Command"
            raise TypeError(msg)

        command_key = cast("CommandName", i.client.get_command_name(i.command))
        account = account or await self.bot.get_account(
            user.id, COMMANDS[command_key].games, COMMANDS[command_key].platform
        )
        settings = await Settings.get(user_id=i.user.id)

        command = CharactersCommand(account, settings)
        await command.run(i)

        await show_anniversary_dismissible(i)

    @app_commands.command(name="genshin", description=COMMANDS["characters genshin"].description)
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def genshin_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["characters genshin"].games)
        ] = None,
    ) -> None:
        await self.characters_command(i, user, account)

    @app_commands.command(name="hsr", description=COMMANDS["characters hsr"].description)
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def hsr_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["characters hsr"].games)
        ] = None,
    ) -> None:
        await self.characters_command(i, user, account)

    @app_commands.command(name="zzz", description=COMMANDS["characters zzz"].description)
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def zzz_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["characters zzz"].games)
        ] = None,
    ) -> None:
        await self.characters_command(i, user, account)

    @app_commands.command(name="honkai", description=COMMANDS["characters honkai"].description)
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def honkai_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["characters honkai"].games)
        ] = None,
    ) -> None:
        await self.characters_command(i, user, account)

    @genshin_command.autocomplete("account")
    @hsr_command.autocomplete("account")
    @zzz_command.autocomplete("account")
    @honkai_command.autocomplete("account")
    @handle_autocomplete_errors
    async def genshin_acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current)


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Characters(bot))
