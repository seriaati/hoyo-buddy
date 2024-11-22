from __future__ import annotations

from typing import TYPE_CHECKING

import akasha
from discord import Locale, app_commands
from discord.ext import commands
from enka.errors import WrongUIDFormatError

from hoyo_buddy.commands.leaderboard import LeaderboardCommand
from hoyo_buddy.constants import locale_to_akasha_lang
from hoyo_buddy.db.models import HoyoAccount, get_locale
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Game, LeaderboardType
from hoyo_buddy.exceptions import AccountNotFoundError, LeaderboardNotFoundError
from hoyo_buddy.hoyo.clients.ambr import ItemCategory
from hoyo_buddy.hoyo.transformers import HoyoAccountTransformer  # noqa: TCH001
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.types import User  # noqa: TCH001
from hoyo_buddy.ui.hoyo.leaderboard.akasha import AkashaLbPaginator
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import HoyoBuddy
    from hoyo_buddy.types import Interaction


class LeaderboardCog(commands.GroupCog, name=app_commands.locale_str("lb")):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    @app_commands.command(
        name=app_commands.locale_str("akasha"),
        description=app_commands.locale_str(
            "View Genshin Impact character damage leaderboard (powered by Akasha System)",
            key="leaderboard_akasha_command_description",
        ),
    )
    @app_commands.rename(
        character_id=app_commands.locale_str("character", key="akasha_character_param"),
        calculation_id=app_commands.locale_str("leaderboard", key="akasha_calculation_param"),
        user=app_commands.locale_str("user", key="user_autocomplete_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        character_id=app_commands.locale_str(
            "Character to view the leaderboard for", key="akasha_character_param_desc"
        ),
        calculation_id=app_commands.locale_str(
            "Leaderboard to view", key="akasha_calculation_param_desc"
        ),
        user=app_commands.locale_str(
            "User to search the accounts with, defaults to you",
            key="user_autocomplete_param_description",
        ),
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
        ),
        uid=app_commands.locale_str(
            "UID of the player, this overrides the account parameter if provided",
            key="profile_command_uid_param_description",
        ),
    )
    async def akasha_command(
        self,
        i: Interaction,
        character_id: str,
        calculation_id: str,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
        uid: app_commands.Range[str, 9, 10] | None = None,
    ) -> None:
        if character_id == "none" or calculation_id == "none" or not calculation_id.isdigit():
            raise LeaderboardNotFoundError

        if uid is not None and not uid.isdigit():
            raise WrongUIDFormatError

        if uid is None:
            user = user or i.user
            try:
                account = account or await self.bot.get_account(user.id, (Game.GENSHIN,))
            except AccountNotFoundError:
                uid = None
            else:
                uid = str(account.uid)

        await i.response.defer(ephemeral=ephemeral(i))
        locale = await get_locale(i)

        async with akasha.AkashaAPI(locale_to_akasha_lang(locale)) as api:
            categories = await api.get_categories(character_id)

            if uid is not None:
                you = await api.get_leaderboard_for_uid(int(calculation_id), uid=int(uid))
            else:
                you = None

        category = None
        weapon = None

        for category in categories:
            weapon = next(
                (weapon for weapon in category.weapons if weapon.calculation_id == calculation_id),
                None,
            )
            if weapon is not None:
                break

        if category is None or weapon is None:
            raise LeaderboardNotFoundError

        lb_embed = (
            DefaultEmbed(locale, title=category.name)
            .set_author(
                name=f"{category.character_name} | {weapon.name} R{weapon.refinement}",
                icon_url=weapon.icon,
            )
            .set_thumbnail(url=category.character_icon)
            .set_footer(text=LocaleStr(key="akasha_total_entries", total=category.count))
        )
        view = AkashaLbPaginator(
            calculation_id,
            lb_embed,
            you,
            category.count,
            category.details,
            author=i.user,
            locale=locale,
        )
        await view.start(i)

    @akasha_command.autocomplete("character_id")
    async def character_id_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)
        characters = self.bot.autocomplete_choices[Game.GENSHIN][ItemCategory.CHARACTERS]

        if not characters:
            return self.bot.get_error_choice(LocaleStr(key="search_autocomplete_not_setup"), locale)

        choices = characters.get(locale, characters[Locale.american_english])
        return [choice for choice in choices if current.lower() in choice.name.lower()][:25]

    @akasha_command.autocomplete("calculation_id")
    async def calculation_id_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)

        if not (character_id := i.namespace.character) or character_id == "none":
            return self.bot.get_error_choice(LocaleStr(key="no_leaderboard_found"), locale)

        async with akasha.AkashaAPI(locale_to_akasha_lang(locale)) as api:
            categories = await api.get_categories(character_id)

        if not categories:
            return self.bot.get_error_choice(LocaleStr(key="no_leaderboard_found"), locale)

        choices: list[app_commands.Choice[str]] = [
            app_commands.Choice(
                name=f"{category.name} - {weapon.name}", value=weapon.calculation_id
            )
            for category in categories
            for weapon in category.weapons
        ]
        return [choice for choice in choices if current.lower() in choice.name.lower()][:25]

    @akasha_command.autocomplete("account")
    async def gi_acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current, (Game.GENSHIN,))

    @app_commands.command(
        name=app_commands.locale_str("view"),
        description=app_commands.locale_str("View leaderboards", key="lb_view_command_description"),
    )
    @app_commands.rename(
        lb=app_commands.locale_str("leaderboard", key="akasha_calculation_param"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        lb=app_commands.locale_str("Leaderboard to view", key="akasha_calculation_param_desc"),
        account=app_commands.locale_str(
            "Account to run this command with", key="acc_no_default_param_desc"
        ),
    )
    async def lb_view_command(
        self,
        i: Interaction,
        lb: str,
        account: app_commands.Transform[HoyoAccount, HoyoAccountTransformer],
    ) -> None:
        try:
            lb_type = LeaderboardType(lb)
        except ValueError as e:
            raise LeaderboardNotFoundError from e

        command = LeaderboardCommand()
        await command.run(i, lb_type=lb_type, account=account)

    @lb_view_command.autocomplete("lb")
    async def lb_autocomplete(self, i: Interaction, current: str) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)
        return self.bot.get_enum_choices(list(LeaderboardType), locale, current)

    @lb_view_command.autocomplete("account")
    async def gi_hsr_zzz_honkai_acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)

        try:
            lb = LeaderboardType(i.namespace.leaderboard)
        except ValueError:
            return self.bot.get_error_choice(LocaleStr(key="invalid_lb_selected_error_msg"), locale)

        games = LeaderboardCommand.get_games_by_lb_type(lb)
        if not games:
            return self.bot.get_error_choice(LocaleStr(key="no_game_found"), locale)

        return await self.bot.get_game_account_choices(i, current, games)


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(LeaderboardCog(bot))
