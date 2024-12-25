from __future__ import annotations

from typing import TYPE_CHECKING

from discord import app_commands
from discord.ext.commands import GroupCog

from hoyo_buddy.commands.challenge import ChallengeCommand
from hoyo_buddy.constants import USER_ACCOUNT_DESCRIBE_KWARGS, USER_ACCOUNT_RENAME_KWARGS
from hoyo_buddy.db import HoyoAccount  # noqa: TC001
from hoyo_buddy.enums import ChallengeType, Game
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
        description=app_commands.locale_str("Zombiegal challenges"),
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
        description=app_commands.locale_str(
            "Generate Spiral Abyss card", key="challenge_command_abyss_desc"
        ),
    )
    @app_commands.rename(**USER_ACCOUNT_RENAME_KWARGS)
    @app_commands.describe(**USER_ACCOUNT_DESCRIBE_KWARGS)
    async def abyss_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await self.challenge_command(i, ChallengeType.SPIRAL_ABYSS, user, account)

    @genshin.command(
        name=app_commands.locale_str("theater"),
        description=app_commands.locale_str(
            "Generate Imaginarium Theater card", key="challenge_command_theater_desc"
        ),
    )
    @app_commands.rename(**USER_ACCOUNT_RENAME_KWARGS)
    @app_commands.describe(**USER_ACCOUNT_DESCRIBE_KWARGS)
    async def img_theater_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await self.challenge_command(i, ChallengeType.IMG_THEATER, user, account)

    @hsr.command(
        name=app_commands.locale_str("moc"),
        description=app_commands.locale_str(
            "Generate Memory of Chaos card", key="challenge_command_moc_desc"
        ),
    )
    @app_commands.rename(**USER_ACCOUNT_RENAME_KWARGS)
    @app_commands.describe(**USER_ACCOUNT_DESCRIBE_KWARGS)
    async def moc_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await self.challenge_command(i, ChallengeType.MOC, user, account)

    @hsr.command(
        name=app_commands.locale_str("pure-fiction"),
        description=app_commands.locale_str(
            "Generate Pure Fiction card", key="challenge_command_pf_desc"
        ),
    )
    @app_commands.rename(**USER_ACCOUNT_RENAME_KWARGS)
    @app_commands.describe(**USER_ACCOUNT_DESCRIBE_KWARGS)
    async def pf_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await self.challenge_command(i, ChallengeType.PURE_FICTION, user, account)

    @hsr.command(
        name=app_commands.locale_str("apc-shadow"),
        description=app_commands.locale_str(
            "Generate Apocalyptic Shadow card", key="challenge_command_apc_shadow_desc"
        ),
    )
    @app_commands.rename(**USER_ACCOUNT_RENAME_KWARGS)
    @app_commands.describe(**USER_ACCOUNT_DESCRIBE_KWARGS)
    async def apc_shadow_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await self.challenge_command(i, ChallengeType.APC_SHADOW, user, account)

    @zzz.command(
        name=app_commands.locale_str("shiyu"),
        description=app_commands.locale_str(
            "Generate Shiyu Defense card", key="challenge_command_shiyu_desc"
        ),
    )
    @app_commands.rename(**USER_ACCOUNT_RENAME_KWARGS)
    @app_commands.describe(**USER_ACCOUNT_DESCRIBE_KWARGS)
    async def shiyu_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await self.challenge_command(i, ChallengeType.SHIYU_DEFENSE, user, account)

    @abyss_command.autocomplete("account")
    @img_theater_command.autocomplete("account")
    async def gi_autocomplete(self, i: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current, (Game.GENSHIN,))

    @moc_command.autocomplete("account")
    @pf_command.autocomplete("account")
    @apc_shadow_command.autocomplete("account")
    async def hsr_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current, (Game.STARRAIL,))

    @shiyu_command.autocomplete("account")
    async def zzz_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current, (Game.ZZZ,))


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Challenge(bot))
