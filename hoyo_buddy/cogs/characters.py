from __future__ import annotations

from typing import TYPE_CHECKING

from discord import app_commands
from discord.ext import commands

from hoyo_buddy.commands.characters import CharactersCommand
from hoyo_buddy.constants import get_describe_kwargs, get_rename_kwargs
from hoyo_buddy.db import HoyoAccount, Settings
from hoyo_buddy.enums import Game
from hoyo_buddy.hoyo.transformers import HoyoAccountTransformer  # noqa: TC001
from hoyo_buddy.types import User  # noqa: TC001
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.types import Interaction


class Characters(
    commands.GroupCog,
    name=app_commands.locale_str("characters"),
    description=app_commands.locale_str("Characters commands"),
):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    async def characters_command(
        self, i: Interaction, user: User, account: HoyoAccount | None, game: Game
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        user = user or i.user
        account_ = account or await self.bot.get_account(user.id, (game,))
        settings = await Settings.get(user_id=i.user.id)

        command = CharactersCommand(account_, settings)
        await command.run(i)

    @app_commands.command(
        name="genshin",
        description=app_commands.locale_str(
            "View and filter your Genshin Impact characters", key="characters_cmd_genshin_desc"
        ),
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def genshin_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await self.characters_command(i, user, account, Game.GENSHIN)

    @app_commands.command(
        name="hsr",
        description=app_commands.locale_str(
            "View and filter your Honkai Star Rail characters", key="characters_cmd_hsr_desc"
        ),
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def hsr_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await self.characters_command(i, user, account, Game.STARRAIL)

    @app_commands.command(
        name="zzz",
        description=app_commands.locale_str(
            "View and filter your Zenless Zone Zero agents", key="characters_cmd_zzz_desc"
        ),
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def zzz_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await self.characters_command(i, user, account, Game.ZZZ)

    @app_commands.command(
        name="honkai",
        description=app_commands.locale_str(
            "View and filter your Honkai Impact 3rd characters", key="characters_cmd_honkai_desc"
        ),
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def honkai_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await self.characters_command(i, user, account, Game.HONKAI)

    @genshin_command.autocomplete("account")
    async def genshin_acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current, (Game.GENSHIN,))

    @hsr_command.autocomplete("account")
    async def hsr_acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current, (Game.STARRAIL,))

    @zzz_command.autocomplete("account")
    async def zzz_acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current, (Game.ZZZ,))

    @honkai_command.autocomplete("account")
    async def honkai_acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current, (Game.HONKAI,))


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Characters(bot))
