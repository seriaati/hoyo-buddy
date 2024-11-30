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
from hoyo_buddy.exceptions import (
    AccountNotFoundError,
    LeaderboardNotFoundError,
    NoAccountFoundError,
)
from hoyo_buddy.hoyo.clients.ambr import ItemCategory
from hoyo_buddy.hoyo.transformers import HoyoAccountTransformer  # noqa: TC001
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.types import User  # noqa: TC001
from hoyo_buddy.ui.hoyo.leaderboard.akasha import AkashaLbPaginator
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.types import Interaction

GUILD_ONLY_MAX_MEMBER_COUNT = 100
GUILD_ONLY_MAX_UID_COUNT = 30


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
        category_=app_commands.locale_str("leaderboard", key="akasha_calculation_param"),
        calculation_id=app_commands.locale_str("weapon", key="akasha_weapon_param"),
        variant=app_commands.locale_str("variant", key="akasha_variant_param"),
        user=app_commands.locale_str("user", key="user_autocomplete_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
        guild_only_=app_commands.locale_str("guild-only", key="guild_only_command_param_name"),
    )
    @app_commands.describe(
        character_id=app_commands.locale_str(
            "Character to view the leaderboard for", key="akasha_character_param_desc"
        ),
        category_=app_commands.locale_str(
            "Leaderboard to view", key="akasha_calculation_param_desc"
        ),
        calculation_id=app_commands.locale_str(
            "Weapon to view the leaderboard for", key="akasha_weapon_param_desc"
        ),
        variant=app_commands.locale_str(
            "Variant of the leaderboard to view, defaults to the main one",
            key="akasha_variant_param_desc",
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
        guild_only_=app_commands.locale_str(
            "Only show guild members' rankings in the leaderboard",
            key="guild_only_command_param_desc",
        ),
    )
    @app_commands.choices(
        guild_only_=[
            app_commands.Choice(name=app_commands.locale_str("Yes", key="yes_choice"), value=1),
            app_commands.Choice(name=app_commands.locale_str("No", key="no_choice"), value=0),
        ]
    )
    async def akasha_command(
        self,
        i: Interaction,
        character_id: str,
        category_: str,
        calculation_id: str,
        variant: str | None = None,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
        uid: app_commands.Range[str, 9, 10] | None = None,
        guild_only_: int = 0,
    ) -> None:
        guild_only = bool(guild_only_)
        if character_id == "none" or not calculation_id.isdigit() or variant == "none":
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

        # Guild leaderboard
        uids: list[int] = []
        if guild_only:
            if i.guild is None:
                raise LeaderboardNotFoundError
            if len([m for m in i.guild.members if not m.bot]) > GUILD_ONLY_MAX_MEMBER_COUNT:
                raise LeaderboardNotFoundError

            if not i.guild.chunked:
                await i.guild.chunk()

            for member in i.guild.members:
                if member.bot:
                    continue

                try:
                    accounts = await self.bot.get_accounts(member.id, (Game.GENSHIN,))
                except NoAccountFoundError:
                    continue
                uids.extend(account.uid for account in accounts)

            uids = list(set(uids))
            if len(uids) > GUILD_ONLY_MAX_UID_COUNT:
                raise LeaderboardNotFoundError

        async with akasha.AkashaAPI(locale_to_akasha_lang(locale)) as api:
            categories = await api.get_categories(character_id)

            you = None
            if uid is not None:
                async for board in api.get_leaderboards(
                    int(calculation_id), max_page=1, uids=(int(uid),)
                ):
                    you = board
                    break

        category = next((category for category in categories if category.id == category_), None)
        if category is None:
            raise LeaderboardNotFoundError

        weapon = next(
            (weapon for weapon in category.weapons if weapon.calculation_id == calculation_id), None
        )
        if weapon is None:
            raise LeaderboardNotFoundError

        filter_name = ""
        if variant is not None:
            filter_ = next((filter_ for filter_ in weapon.filters if filter_.id == variant), None)
            if filter_ is None:
                raise LeaderboardNotFoundError
            filter_name = f" ({filter_.name})"

        lb_embed = (
            DefaultEmbed(locale, title=f"{category.name}{filter_name}")
            .set_author(name=f"{weapon.name} R{weapon.refinement}", icon_url=weapon.icon)
            .set_thumbnail(url=category.character_icon)
            .set_footer(text=LocaleStr(key="akasha_total_entries", total=category.count))
        )
        view = AkashaLbPaginator(
            calculation_id,
            lb_embed,
            you,
            variant=variant,
            uids=uids,
            lb_size=category.count,
            lb_details=category.details,
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

    @akasha_command.autocomplete("category_")
    async def category_autocomplete(
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
            app_commands.Choice(name=category.name, value=category.id) for category in categories
        ]
        return [choice for choice in choices if current.lower() in choice.name.lower()][:25]

    @akasha_command.autocomplete("calculation_id")
    async def calculation_id_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)

        if (
            not (character_id := i.namespace.character)
            or character_id == "none"
            or not (category := i.namespace.leaderboard)
            or category == "none"
        ):
            return self.bot.get_error_choice(LocaleStr(key="no_leaderboard_found"), locale)

        async with akasha.AkashaAPI(locale_to_akasha_lang(locale)) as api:
            categories = await api.get_categories(character_id)

        if not categories:
            return self.bot.get_error_choice(LocaleStr(key="no_leaderboard_found"), locale)

        category_ = next((c for c in categories if c.id == category), None)
        if category_ is None:
            return self.bot.get_error_choice(LocaleStr(key="no_leaderboard_found"), locale)

        choices: list[app_commands.Choice[str]] = [
            app_commands.Choice(
                name=f"{weapon.name} R{weapon.refinement}", value=weapon.calculation_id
            )
            for weapon in category_.weapons
        ]
        return [choice for choice in choices if current.lower() in choice.name.lower()][:25]

    @akasha_command.autocomplete("variant")
    async def variant_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)

        if (
            not (character_id := i.namespace.character)
            or character_id == "none"
            or not (category := i.namespace.leaderboard)
            or category == "none"
            or not (calculation_id := i.namespace.weapon)
            or not calculation_id.isdigit()
        ):
            return self.bot.get_error_choice(LocaleStr(key="no_leaderboard_found"), locale)

        async with akasha.AkashaAPI(locale_to_akasha_lang(locale)) as api:
            categories = await api.get_categories(character_id)

        if not categories:
            return self.bot.get_error_choice(LocaleStr(key="no_leaderboard_found"), locale)

        category_ = next((c for c in categories if c.id == category), None)
        if category_ is None:
            return self.bot.get_error_choice(LocaleStr(key="no_leaderboard_found"), locale)

        weapon = next((w for w in category_.weapons if w.calculation_id == calculation_id), None)
        if weapon is None:
            return self.bot.get_error_choice(LocaleStr(key="no_leaderboard_found"), locale)

        choices: list[app_commands.Choice[str]] = [
            app_commands.Choice(name=filter_.name, value=filter_.id) for filter_ in weapon.filters
        ]
        if not choices:
            return self.bot.get_error_choice(
                LocaleStr(key="search_autocomplete_no_results"), locale
            )
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
