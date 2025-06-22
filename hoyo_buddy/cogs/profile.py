from __future__ import annotations

from typing import TYPE_CHECKING

import enka
from discord import app_commands
from discord.ext.commands import GroupCog

from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.commands.profile import ProfileCommand
from hoyo_buddy.constants import get_describe_kwargs, get_rename_kwargs
from hoyo_buddy.db import HoyoAccount, get_locale
from hoyo_buddy.db.utils import show_anniversary_dismissible, show_dismissible
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.exceptions import FeatureNotImplementedError
from hoyo_buddy.hoyo.clients import ambr, hakushin, yatta
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.models import Dismissible
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.hoyo.transformers import HoyoAccountTransformer
    from hoyo_buddy.types import Interaction, User


def gen_character_id_rename(max_: int) -> dict[str, app_commands.locale_str]:
    return {
        f"character_id{num}": app_commands.locale_str(
            f"character-{num}", key="profile_character_param_name", num=num
        )
        for num in range(1, max_ + 1)
    }


def gen_character_id_describe(max_: int) -> dict[str, app_commands.locale_str]:
    return {
        f"character_id{num}": app_commands.locale_str(
            "Character to generate the card for", key="profile_command_character_param_desc"
        )
        for num in range(1, max_ + 1)
    }


class Profile(
    GroupCog,
    name=app_commands.locale_str("profile"),
    description=app_commands.locale_str("Profile commands"),
):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    async def _parse_params(
        self, user_id: int, account: HoyoAccount | None, uid: str | None, game: Game
    ) -> tuple[int, HoyoAccount | None]:
        """Get the UID and game from the account or the provided UID and game value."""
        account_ = None
        if uid is not None:
            try:
                uid_ = int(uid)
            except ValueError as e:
                raise enka.errors.WrongUIDFormatError from e
        else:
            account_ = account or await self.bot.get_account(user_id, (game,))
            uid_ = account_.uid

        return uid_, account_

    async def profile_command(
        self,
        i: Interaction,
        game: Game,
        *,
        user: User = None,
        account: HoyoAccount | None = None,
        uid: app_commands.Range[str, 9, 10] | None = None,
        character_id1: str | None = None,
        character_id2: str | None = None,
        character_id3: str | None = None,
        character_id4: str | None = None,
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        locale = await get_locale(i)
        user = user or i.user

        uid_, account_ = await self._parse_params(user.id, account, uid, game)
        command = ProfileCommand(
            uid=uid_,
            game=game,
            account=account_,
            character_ids=[character_id1, character_id2, character_id3, character_id4],
            locale=locale,
            user=i.user,
        )
        if game is Game.GENSHIN:
            view = await command.run_genshin()
        elif game is Game.STARRAIL:
            view = await command.run_hsr()
        elif game is Game.ZZZ:
            view = await command.run_zzz()
        else:
            raise FeatureNotImplementedError(game=game)

        await view.start(i)

        shown = await show_anniversary_dismissible(i)
        if shown:
            return

        if game is Game.ZZZ:
            await show_dismissible(
                i,
                Dismissible(
                    id="m3_art",
                    description=LocaleStr(key="dismissible_m3_art_desc"),
                    image="https://img.seria.moe/kVbCOBrqEMHlQsVd.png",
                ),
            )

        if game is Game.STARRAIL:
            await show_dismissible(
                i,
                Dismissible(
                    id="hsr_temp2",
                    description=LocaleStr(key="dismissible_hsr_temp2_desc"),
                    image="https://img.seria.moe/HLHoTSwcXvAPHzJB.png",
                ),
            )

    @app_commands.command(
        name=app_commands.locale_str("genshin"), description=COMMANDS["profile genshin"].description
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True), **gen_character_id_rename(4))
    @app_commands.describe(
        **get_describe_kwargs(user=True, account=True, uid=True), **gen_character_id_describe(4)
    )
    async def profile_gi_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["profile genshin"].games)
        ] = None,
        uid: app_commands.Range[str, 9, 10] | None = None,
        character_id1: str | None = None,
        character_id2: str | None = None,
        character_id3: str | None = None,
        character_id4: str | None = None,
    ) -> None:
        await self.profile_command(
            i,
            Game.GENSHIN,
            user=user,
            account=account,
            uid=uid,
            character_id1=character_id1,
            character_id2=character_id2,
            character_id3=character_id3,
            character_id4=character_id4,
        )

    @app_commands.command(
        name=app_commands.locale_str("hsr"), description=COMMANDS["profile hsr"].description
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True), **gen_character_id_rename(4))
    @app_commands.describe(
        **get_describe_kwargs(user=True, account=True, uid=True), **gen_character_id_describe(4)
    )
    async def profile_hsr_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["profile hsr"].games)
        ] = None,
        uid: app_commands.Range[str, 9, 10] | None = None,
        character_id1: str | None = None,
        character_id2: str | None = None,
        character_id3: str | None = None,
        character_id4: str | None = None,
    ) -> None:
        await self.profile_command(
            i,
            Game.STARRAIL,
            user=user,
            account=account,
            uid=uid,
            character_id1=character_id1,
            character_id2=character_id2,
            character_id3=character_id3,
            character_id4=character_id4,
        )

    @app_commands.command(
        name=app_commands.locale_str("zzz"), description=COMMANDS["profile zzz"].description
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True), **gen_character_id_rename(3))
    @app_commands.describe(
        **get_describe_kwargs(user=True, account=True), **gen_character_id_describe(3)
    )
    async def profile_zzz_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["profile zzz"].games)
        ] = None,
        character_id1: str | None = None,
        character_id2: str | None = None,
        character_id3: str | None = None,
    ) -> None:
        await self.profile_command(
            i,
            Game.ZZZ,
            user=user,
            account=account,
            character_id1=character_id1,
            character_id2=character_id2,
            character_id3=character_id3,
        )

    @profile_gi_command.autocomplete("account")
    @profile_hsr_command.autocomplete("account")
    @profile_zzz_command.autocomplete("account")
    async def acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current)

    async def profile_character_autocomplete(
        self, i: Interaction, current: str, *, game: Game
    ) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)

        if game is Game.GENSHIN:
            category = ambr.ItemCategory.CHARACTERS
        elif game is Game.STARRAIL:
            category = yatta.ItemCategory.CHARACTERS
        elif game is Game.ZZZ:
            category = hakushin.ZZZItemCategory.AGENTS
        else:
            return self.bot.get_error_choice(
                LocaleStr(key="search_autocomplete_no_results"), locale
            )

        choices = self.bot.autocomplete_choices[game][category].get(
            locale, self.bot.autocomplete_choices[game][category][Locale.american_english]
        )
        if not choices:
            return self.bot.get_error_choice(
                LocaleStr(key="search_autocomplete_no_results"), locale
            )

        return [choice for choice in choices if current.lower() in choice.name.lower()][:25]

    @profile_gi_command.autocomplete("character_id1")
    @profile_gi_command.autocomplete("character_id2")
    @profile_gi_command.autocomplete("character_id3")
    @profile_gi_command.autocomplete("character_id4")
    async def profile_character1_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.profile_character_autocomplete(i, current, game=Game.GENSHIN)

    @profile_hsr_command.autocomplete("character_id1")
    @profile_hsr_command.autocomplete("character_id2")
    @profile_hsr_command.autocomplete("character_id3")
    @profile_hsr_command.autocomplete("character_id4")
    async def profile_character2_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.profile_character_autocomplete(i, current, game=Game.STARRAIL)

    @profile_zzz_command.autocomplete("character_id1")
    @profile_zzz_command.autocomplete("character_id2")
    @profile_zzz_command.autocomplete("character_id3")
    async def profile_character3_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.profile_character_autocomplete(i, current, game=Game.ZZZ)


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Profile(bot))
