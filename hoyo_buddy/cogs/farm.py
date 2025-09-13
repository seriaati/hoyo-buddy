from __future__ import annotations

import random
from typing import TYPE_CHECKING

from discord import app_commands
from discord.ext import commands

from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.constants import get_describe_kwargs, get_rename_kwargs
from hoyo_buddy.db import FarmNotify, HoyoAccount, Settings, get_locale
from hoyo_buddy.utils.misc import handle_autocomplete_errors

from ..commands.farm import Action, FarmCommand
from ..enums import Game, Locale
from ..hoyo.clients.ambr import ItemCategory
from ..hoyo.transformers import HoyoAccountTransformer
from ..l10n import LocaleStr
from ..types import Interaction
from ..ui.hoyo.genshin.farm import FarmView

if TYPE_CHECKING:
    from ..bot import HoyoBuddy


class Farm(
    commands.GroupCog,
    name=app_commands.locale_str("farm"),  # pyright: ignore[reportArgumentType]
    description=app_commands.locale_str("Farm commands"),  # pyright: ignore[reportArgumentType]
):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    def _get_choices(self, locale: Locale) -> list[app_commands.Choice[str]]:
        """Get characters and weapons autocomplete choices."""
        characters = self.bot.search_autofill[Game.GENSHIN][ItemCategory.CHARACTERS]
        weapons = self.bot.search_autofill[Game.GENSHIN][ItemCategory.WEAPONS]

        if not characters or not weapons:
            return self.bot.get_error_choice(LocaleStr(key="search_autocomplete_not_setup"), locale)

        return characters.get(locale, characters[Locale.american_english]) + weapons.get(
            locale, weapons[Locale.american_english]
        )

    @app_commands.command(
        name=app_commands.locale_str("view"), description=COMMANDS["farm view"].description
    )
    @app_commands.rename(**get_rename_kwargs(account=True))
    @app_commands.describe(**get_describe_kwargs(account=True))
    async def farm_view_command(
        self,
        i: Interaction,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["farm view"].games)
        ] = None,
    ) -> None:
        settings = await Settings.get(user_id=i.user.id)
        account = (
            account
            or await HoyoAccount.filter(user_id=i.user.id, current=True, game=Game.GENSHIN).first()
            or await HoyoAccount.filter(user_id=i.user.id, game=Game.GENSHIN).first()
        )
        uid = None if account is None else account.uid

        view = FarmView(
            uid, dark_mode=settings.dark_mode, author=i.user, locale=await get_locale(i)
        )
        await view.start(i)

    @app_commands.command(
        name=app_commands.locale_str("add"), description=COMMANDS["farm add"].description
    )
    @app_commands.rename(
        query=app_commands.locale_str("query", key="search_command_query_param_name"),
        **get_rename_kwargs(account=True),
    )
    @app_commands.describe(
        query=app_commands.locale_str(
            "Query to search for", key="search_command_query_param_description"
        ),
        **get_describe_kwargs(account_no_default=True),
    )
    async def farm_add_command(
        self,
        i: Interaction,
        account: app_commands.Transform[
            HoyoAccount, HoyoAccountTransformer(COMMANDS["farm add"].games)
        ],
        query: str,
    ) -> None:
        account_ = account or await self.bot.get_account(i.user.id, (Game.GENSHIN,))
        settings = await Settings.get(user_id=i.user.id)
        locale = await get_locale(i)
        command = FarmCommand(i, account_, settings, locale, query, Action.ADD)
        await command.run()

    @app_commands.command(
        name=app_commands.locale_str("remove"), description=COMMANDS["farm remove"].description
    )
    @app_commands.rename(
        query=app_commands.locale_str("query", key="search_command_query_param_name"),
        **get_rename_kwargs(account=True),
    )
    @app_commands.describe(
        query=app_commands.locale_str(
            "Query to search for", key="search_command_query_param_description"
        ),
        **get_describe_kwargs(account_no_default=True),
    )
    async def farm_remove_command(
        self,
        i: Interaction,
        account: app_commands.Transform[
            HoyoAccount, HoyoAccountTransformer(COMMANDS["farm remove"].games)
        ],
        query: str,
    ) -> None:
        account_ = account or await self.bot.get_account(i.user.id, (Game.GENSHIN,))
        settings = await Settings.get(user_id=i.user.id)
        locale = await get_locale(i)
        command = FarmCommand(i, account_, settings, locale, query, Action.REMOVE)
        await command.run()

    @app_commands.command(
        name=app_commands.locale_str("reminder"), description=COMMANDS["farm reminder"].description
    )
    @app_commands.rename(**get_rename_kwargs(account=True))
    @app_commands.describe(**get_describe_kwargs(account=True))
    async def farm_reminder_command(
        self,
        i: Interaction,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["farm reminder"].games)
        ] = None,
    ) -> None:
        account_ = account or await self.bot.get_account(i.user.id, (Game.GENSHIN,))
        settings = await Settings.get(user_id=i.user.id)
        locale = await get_locale(i)
        command = FarmCommand(i, account_, settings, locale)
        await command.run()

    @farm_view_command.autocomplete("account")
    @farm_add_command.autocomplete("account")
    @farm_reminder_command.autocomplete("account")
    @handle_autocomplete_errors
    async def account_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current)

    @farm_remove_command.autocomplete("account")
    @handle_autocomplete_errors
    async def account_with_id_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current, show_id=True)

    @farm_add_command.autocomplete("query")
    @handle_autocomplete_errors
    async def query_autocomplete(self, i: Interaction, current: str) -> list[app_commands.Choice]:
        locale = await get_locale(i)
        choices = [c for c in self._get_choices(locale) if current.lower() in c.name.lower()]
        random.shuffle(choices)
        return choices[:25]

    @farm_remove_command.autocomplete("query")
    @handle_autocomplete_errors
    async def user_query_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice]:
        account_namespace: str | None = i.namespace.account

        if account_namespace is None or account_namespace == "none":
            return self.bot.get_error_choice(
                LocaleStr(key="search_autocomplete_no_results"), await get_locale(i)
            )
        # Find [account_id] from account_namespace
        try:
            account_id = int(account_namespace.split("]")[0].strip("["))
        except ValueError:
            return self.bot.get_error_choice(
                LocaleStr(key="search_autocomplete_no_results"), await get_locale(i)
            )
        locale = await get_locale(i)

        farm_notify = await FarmNotify.get_or_none(account_id=account_id)
        if farm_notify is None:
            return self.bot.get_error_choice(
                LocaleStr(key="search_autocomplete_no_results"), locale
            )

        choices = self._get_choices(locale)
        choices = [
            c
            for c in choices
            if current.lower() in c.name.lower() and c.value in farm_notify.item_ids
        ]

        if not choices:
            return self.bot.get_error_choice(
                LocaleStr(key="search_autocomplete_no_results"), locale
            )

        return choices[:25]


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Farm(bot))
