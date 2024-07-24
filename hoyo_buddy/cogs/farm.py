from __future__ import annotations

import random
from typing import TYPE_CHECKING

from discord import Locale, app_commands
from discord.ext import commands

from ..bot.translator import LocaleStr
from ..commands.farm import Action, FarmCommand
from ..db.models import FarmNotify, HoyoAccount, Settings, get_locale
from ..enums import Game
from ..hoyo.clients.ambr import ItemCategory
from ..hoyo.transformers import HoyoAccountTransformer  # noqa: TCH001
from ..ui.hoyo.farm import FarmView

if TYPE_CHECKING:
    from ..bot import HoyoBuddy
    from ..types import Interaction, User


class Farm(
    commands.GroupCog,
    name=app_commands.locale_str("farm"),
    description=app_commands.locale_str("Farm commands"),
):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    @app_commands.command(
        name=app_commands.locale_str("view"),
        description=app_commands.locale_str(
            "View farmable domains in Genshin Impact", key="farm_view_command_description"
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
    async def farm_view_command(
        self,
        i: Interaction,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        settings = await Settings.get(user_id=i.user.id)
        account = (
            account
            or await HoyoAccount.filter(user_id=i.user.id, current=True, game=Game.GENSHIN).first()
            or await HoyoAccount.filter(user_id=i.user.id, game=Game.GENSHIN).first()
        )
        uid = None if account is None else account.uid

        view = FarmView(
            uid,
            settings.dark_mode,
            author=i.user,
            locale=settings.locale or i.locale,
            translator=self.bot.translator,
        )
        await view.start(i)

    @app_commands.command(
        name=app_commands.locale_str("add"),
        description=app_commands.locale_str(
            "Add character/weapon to be notified when its materials are farmable",
            key="farm_add_command_description",
        ),
    )
    @app_commands.rename(
        query=app_commands.locale_str("query", key="search_command_query_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        query=app_commands.locale_str(
            "Query to search for", key="search_command_query_param_description"
        ),
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
        ),
    )
    async def farm_add_command(
        self,
        i: Interaction,
        account: app_commands.Transform[HoyoAccount, HoyoAccountTransformer],
        query: str,
    ) -> None:
        account_ = account or await self.bot.get_account(i.user.id, (Game.GENSHIN,))
        settings = await Settings.get(user_id=i.user.id)
        command = FarmCommand(i, account_, settings, query, Action.ADD)
        await command.run()

    @app_commands.command(
        name=app_commands.locale_str("remove"),
        description=app_commands.locale_str(
            "Remove character/weapon from farm reminder list", key="farm_remove_command_description"
        ),
    )
    @app_commands.rename(
        query=app_commands.locale_str("query", key="search_command_query_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        query=app_commands.locale_str(
            "Query to search for", key="search_command_query_param_description"
        ),
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
        ),
    )
    async def farm_remove_command(
        self,
        i: Interaction,
        account: app_commands.Transform[HoyoAccount, HoyoAccountTransformer],
        query: str,
    ) -> None:
        account_ = account or await self.bot.get_account(i.user.id, (Game.GENSHIN,))
        settings = await Settings.get(user_id=i.user.id)
        command = FarmCommand(i, account_, settings, query, Action.REMOVE)
        await command.run()

    @app_commands.command(
        name=app_commands.locale_str("reminder"),
        description=app_commands.locale_str(
            "Notify you when materials of characters/weapons are farmable",
            key="farm_reminder_command_description",
        ),
    )
    @app_commands.rename(
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
        ),
    )
    async def farm_reminder_command(
        self,
        i: Interaction,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        account_ = account or await self.bot.get_account(i.user.id, (Game.GENSHIN,))
        settings = await Settings.get(user_id=i.user.id)
        command = FarmCommand(i, account_, settings)
        await command.run()

    @farm_view_command.autocomplete("account")
    @farm_add_command.autocomplete("account")
    @farm_remove_command.autocomplete("account")
    @farm_reminder_command.autocomplete("account")
    async def account_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)
        user: User = i.namespace.user
        return await self.bot.get_account_autocomplete(
            user, i.user.id, current, locale, self.bot.translator, (Game.GENSHIN,)
        )

    @farm_add_command.autocomplete("query")
    async def query_autocomplete(self, i: Interaction, current: str) -> list[app_commands.Choice]:
        locale = await get_locale(i)

        try:
            characters = self.bot.autocomplete_choices[Game.GENSHIN][ItemCategory.CHARACTERS]
            weapons = self.bot.autocomplete_choices[Game.GENSHIN][ItemCategory.WEAPONS]
        except KeyError:
            return self.bot.get_error_autocomplete(
                LocaleStr(key="search_autocomplete_not_setup"), locale
            )

        choice_dict = dict(
            characters.get(locale.value, characters[Locale.american_english.value]).items()
        ) | dict(weapons.get(locale.value, weapons[Locale.american_english.value]).items())

        choices = [
            app_commands.Choice(name=name, value=value)
            for name, value in choice_dict.items()
            if current.lower() in name.lower()
        ]

        random.shuffle(choices)
        return choices[:25]

    @farm_remove_command.autocomplete("query")
    async def user_query_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice]:
        account_namespace: str = i.namespace.account
        account = await HoyoAccountTransformer().transform(i, account_namespace)
        locale = await get_locale(i)

        farm_notify = await FarmNotify.get_or_none(account_id=account.id)
        if farm_notify is None:
            return self.bot.get_error_autocomplete(
                LocaleStr(key="search_autocomplete_no_results"), locale
            )

        try:
            characters = self.bot.autocomplete_choices[Game.GENSHIN][ItemCategory.CHARACTERS]
            weapons = self.bot.autocomplete_choices[Game.GENSHIN][ItemCategory.WEAPONS]
        except KeyError:
            return self.bot.get_error_autocomplete(
                LocaleStr(key="search_autocomplete_not_setup"), locale
            )

        try:
            choice_dict = dict(characters[locale.value].items()) | dict(
                weapons[locale.value].items()
            )
        except KeyError:
            choice_dict = dict(characters[Locale.american_english.value].items()) | dict(
                weapons[Locale.american_english.value].items()
            )

        choices = [
            app_commands.Choice(name=name, value=value)
            for name, value in choice_dict.items()
            if current.lower() in name.lower() and value in farm_notify.item_ids
        ]

        if not choices:
            return self.bot.get_error_autocomplete(
                LocaleStr(key="search_autocomplete_no_results"), locale
            )

        return choices[:25]


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Farm(bot))
