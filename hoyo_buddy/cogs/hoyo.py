from typing import Any, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..bot import HoyoBuddy, Translator
from ..bot import locale_str as _T
from ..bot.bot import INTERACTION
from ..db import Game, HoyoAccount, Settings, User
from ..exceptions import InvalidQuery
from ..hoyo.genshin import ambr
from ..ui.hoyo.checkin import CheckInUI
from ..ui.hoyo.search.character import CharacterUI
from ..ui.hoyo.search.weapon import WeaponUI


class Hoyo(commands.Cog):
    def __init__(self, bot: HoyoBuddy):
        self.bot = bot

    @staticmethod
    async def _account_autocomplete(
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

    @staticmethod
    async def _no_account_response(i, locale):
        return await i.response.send_message(
            i.client.translator.translate(
                _T(
                    "You don't have any accounts yet. Add one with </accounts>",
                    key="no_accounts_autocomplete_selected",
                ),
                locale,
            ),
            ephemeral=True,
        )

    @staticmethod
    async def _get_user(user_id: int) -> User:
        return await User.get(id=user_id).prefetch_related("settings")

    @staticmethod
    def _get_locale(user: User, interaction_locale: discord.Locale) -> discord.Locale:
        return user.settings.locale or interaction_locale

    @staticmethod
    async def _get_specific_account(account_value: str, user: User) -> HoyoAccount:
        uid, game = account_value.split("_")
        account = await user.accounts.filter(uid=uid, game=game).first()
        if account is None:
            raise AssertionError("Account not found")
        return account

    @staticmethod
    def _get_game_choices() -> List[app_commands.Choice[str]]:
        return [
            app_commands.Choice(
                name=app_commands.locale_str(game.value, warn_no_key=False),
                value=game.value,
            )
            for game in Game
        ]

    @staticmethod
    def _get_error_app_command_choice(error_message: str) -> app_commands.Choice[str]:
        return app_commands.Choice(
            name=app_commands.locale_str(error_message, warn_no_key=False),
            value="none",
        )

    async def _get_first_account(
        self, user: User, i: discord.Interaction, locale: discord.Locale
    ) -> Optional[HoyoAccount]:
        accounts = await user.accounts.all()
        if not accounts:
            await self._no_account_response(i, locale)
        else:
            return accounts[0]

    async def _get_account(
        self,
        user: User,
        account_value: Optional[str],
        i: discord.Interaction,
        locale: discord.Locale,
    ) -> Optional[HoyoAccount]:
        if account_value is None:
            return await self._get_first_account(user, i, locale)
        if account_value == "none":
            await self._no_account_response(i, locale)
        else:
            return await self._get_specific_account(account_value, user)

    @app_commands.command(
        name=app_commands.locale_str("check-in", translate=False),
        description=app_commands.locale_str(
            "Game daily check-in", key="checkin_command_description"
        ),
    )
    @app_commands.rename(
        acc_value=app_commands.locale_str("account", key="account_autocomplete_param_name")
    )
    @app_commands.describe(
        acc_value=app_commands.locale_str(
            "Account to run this command with, defaults to the first one",
            key="account_autocomplete_param_description",
        )
    )
    async def checkin_command(
        self, i: discord.Interaction[HoyoBuddy], acc_value: Optional[str] = None
    ) -> Any:
        user = await self._get_user(i.user.id)
        locale = self._get_locale(user, i.locale)
        account = await self._get_account(user, acc_value, i, locale)
        if account is None:
            return

        dark_mode = user.settings.dark_mode
        view = CheckInUI(
            account,
            dark_mode=dark_mode,
            author=i.user,
            locale=locale,
            translator=self.bot.translator,
        )
        await view.start(i)

    @checkin_command.autocomplete("acc_value")
    async def check_in_command_autocomplete(
        self, i: INTERACTION, current: str
    ) -> List[app_commands.Choice]:
        locale = await Settings.get_locale(i.user.id, i.client.redis_pool) or i.locale
        return await self._account_autocomplete(i.user.id, current, locale, self.bot.translator)

    @app_commands.command(
        name=app_commands.locale_str("search", translate=False),
        description=app_commands.locale_str(
            "Search anything game related", key="search_command_description"
        ),
    )
    @app_commands.rename(
        game_value=app_commands.locale_str("game", key="search_command_game_param_name"),
        category_value=app_commands.locale_str(
            "category", key="search_command_category_param_name"
        ),
        query=app_commands.locale_str("query", key="search_command_query_param_name"),
    )
    @app_commands.describe(
        game_value=app_commands.locale_str(
            "Game to search in", key="search_command_game_param_description"
        ),
        category_value=app_commands.locale_str(
            "Category to search in", key="search_command_category_param_description"
        ),
        query=app_commands.locale_str(
            "Query to search for", key="search_command_query_param_description"
        ),
    )
    @app_commands.choices(
        game_value=[
            app_commands.Choice(
                name=app_commands.locale_str(Game.GENSHIN.value, warn_no_key=False),
                value=Game.GENSHIN.value,
            ),
            app_commands.Choice(
                name=app_commands.locale_str(Game.STARRAIL.value, warn_no_key=False),
                value=Game.STARRAIL.value,
            ),
        ]
    )
    async def search_command(
        self,
        i: discord.Interaction[HoyoBuddy],
        game_value: str,
        category_value: str,
        query: str,
    ) -> Any:
        if category_value == "none" or query == "none":
            raise InvalidQuery

        locale = await Settings.get_locale(i.user.id, i.client.redis_pool) or i.locale
        game = Game(game_value)

        if game is Game.GENSHIN:
            category = ambr.ItemCategory(category_value)
            async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                if category is ambr.ItemCategory.CHARACTERS:
                    character_ui = CharacterUI(
                        query,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                    )
                    return await character_ui.update(i)
                if category is ambr.ItemCategory.WEAPONS:
                    weapon_ui = WeaponUI(
                        query,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                    )
                    return await weapon_ui.update(i)
                if category is ambr.ItemCategory.NAMECARDS:
                    namecard_detail = await api.fetch_namecard_detail(int(query))
                    embed = api.get_namecard_embed(namecard_detail)
                elif category is ambr.ItemCategory.ARTIFACT_SETS:
                    artifact_set_detail = await api.fetch_artifact_set_detail(int(query))
                    embed = api.get_artifact_set_embed(artifact_set_detail)
                else:
                    raise NotImplementedError
                await i.response.send_message(embed=embed)

    @search_command.autocomplete("category_value")
    async def search_command_category_autocomplete(
        self, i: discord.Interaction, current: str
    ) -> List[app_commands.Choice]:
        try:
            game = Game(i.namespace.game)
        except ValueError:
            return [self._get_error_app_command_choice("Invalid game selected")]

        if game is Game.GENSHIN:
            return [
                app_commands.Choice(
                    name=app_commands.locale_str(c.value, warn_no_key=False),
                    value=c.value,
                )
                for c in ambr.ItemCategory
                if current in c.value
            ]

        return [self._get_error_app_command_choice("Invalid game selected")]

    @search_command.autocomplete("query")
    async def search_command_query_autocomplete(
        self, i: discord.Interaction[HoyoBuddy], current: str
    ) -> List[app_commands.Choice]:
        try:
            game = Game(i.namespace.game)
        except ValueError:
            return [self._get_error_app_command_choice("Invalid game selected")]
        if game is Game.GENSHIN:
            try:
                category = ambr.ItemCategory(i.namespace.category)
            except ValueError:
                return [self._get_error_app_command_choice("Invalid category selected")]
        else:
            return [self._get_error_app_command_choice("Invalid game selected")]

        locale = await Settings.get_locale(i.user.id, i.client.redis_pool) or i.locale
        async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
            if category is ambr.ItemCategory.CHARACTERS:
                items = await api.fetch_characters()
            elif category is ambr.ItemCategory.WEAPONS:
                items = await api.fetch_weapons()
            elif category is ambr.ItemCategory.NAMECARDS:
                items = await api.fetch_namecards()
            elif category is ambr.ItemCategory.ARTIFACT_SETS:
                items = await api.fetch_artifact_sets()
            else:
                return [self._get_error_app_command_choice("Invalid category selected")]
            return [
                app_commands.Choice(name=item.name, value=str(item.id))
                for item in items
                if current in item.name
            ][:25]


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Hoyo(bot))
