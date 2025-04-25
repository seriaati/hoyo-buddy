from __future__ import annotations

from typing import TYPE_CHECKING

from discord import app_commands
from discord.ext.commands import GroupCog

from hoyo_buddy.commands.challenge import ChallengeCommand
from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.constants import get_describe_kwargs, get_rename_kwargs
from hoyo_buddy.db import HoyoAccount  # noqa: TC001
from hoyo_buddy.enums import ChallengeType
from hoyo_buddy.hoyo.transformers import HoyoAccountTransformer  # noqa: TC001
from hoyo_buddy.types import User  # noqa: TC001
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.types import Interaction


class Challenge(
    GroupCog,
    name=app_commands.locale_str("challenge"),
    description=app_commands.locale_str("Challenge commands"),
):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    genshin = app_commands.Group(
        name=app_commands.locale_str("genshin"),
        description=app_commands.locale_str("Genshin Impact challenges"),
    )
    hsr = app_commands.Group(
        name=app_commands.locale_str("hsr"),
        description=app_commands.locale_str("Honkai Star Rail challenges"),
    )
    zzz = app_commands.Group(
        name=app_commands.locale_str("zzz"),
        description=app_commands.locale_str("Zenless Zone Zero challenges"),
    )

    async def challenge_command(
        self, i: Interaction, challenge_type: ChallengeType, user: User, account: HoyoAccount | None
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))
        user = user or i.user
        command = ChallengeCommand(i, user, account)
        await command.run(challenge_type)

    @genshin.command(
        name=app_commands.locale_str("abyss"),
        description=COMMANDS["challenge genshin abyss"].description,
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def abyss_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["challenge genshin abyss"].games)
        ] = None,
    ) -> None:
        await self.challenge_command(i, ChallengeType.SPIRAL_ABYSS, user, account)

    @genshin.command(
        name=app_commands.locale_str("theater"),
        description=COMMANDS["challenge genshin theater"].description,
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def img_theater_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["challenge genshin theater"].games)
        ] = None,
    ) -> None:
        await self.challenge_command(i, ChallengeType.IMG_THEATER, user, account)

    @hsr.command(
        name=app_commands.locale_str("moc"), description=COMMANDS["challenge hsr moc"].description
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def moc_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["challenge hsr moc"].games)
        ] = None,
    ) -> None:
        await self.challenge_command(i, ChallengeType.MOC, user, account)

    @hsr.command(
        name=app_commands.locale_str("pure-fiction"),
        description=COMMANDS["challenge hsr pure-fiction"].description,
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def pf_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["challenge hsr pure-fiction"].games)
        ] = None,
    ) -> None:
        await self.challenge_command(i, ChallengeType.PURE_FICTION, user, account)

    @hsr.command(
        name=app_commands.locale_str("apc-shadow"),
        description=COMMANDS["challenge hsr apc-shadow"].description,
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def apc_shadow_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["challenge hsr apc-shadow"].games)
        ] = None,
    ) -> None:
        await self.challenge_command(i, ChallengeType.APC_SHADOW, user, account)

    @zzz.command(
        name=app_commands.locale_str("shiyu"),
        description=COMMANDS["challenge zzz shiyu"].description,
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def shiyu_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["challenge zzz shiyu"].games)
        ] = None,
    ) -> None:
        await self.challenge_command(i, ChallengeType.SHIYU_DEFENSE, user, account)

    @zzz.command(
        name=app_commands.locale_str("assault"),
        description=COMMANDS["challenge zzz assault"].description,
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def assault_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["challenge zzz assault"].games)
        ] = None,
    ) -> None:
        await self.challenge_command(i, ChallengeType.ASSAULT, user, account)

    @abyss_command.autocomplete("account")
    @img_theater_command.autocomplete("account")
    @moc_command.autocomplete("account")
    @pf_command.autocomplete("account")
    @apc_shadow_command.autocomplete("account")
    @shiyu_command.autocomplete("account")
    @assault_command.autocomplete("account")
    async def acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current)


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Challenge(bot))
