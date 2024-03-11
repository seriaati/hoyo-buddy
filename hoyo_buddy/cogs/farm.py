import logging
import random
from typing import TYPE_CHECKING

from discord import app_commands
from discord.ext import commands

from ..bot.translator import LocaleStr
from ..db.models import FarmNotify, HoyoAccount, Settings
from ..embeds import DefaultEmbed
from ..enums import Game
from ..exceptions import InvalidQueryError, NoAccountFoundError
from ..hoyo.clients.ambr_client import ItemCategory
from ..hoyo.transformers import HoyoAccountTransformer  # noqa: TCH001
from ..ui.hoyo.farm import FarmView
from ..ui.hoyo.farm_notify import FarmNotifyView

if TYPE_CHECKING:
    from ..bot.bot import INTERACTION, HoyoBuddy

LOGGER_ = logging.getLogger(__name__)


class Farm(commands.GroupCog, name="farm"):
    def __init__(self, bot: "HoyoBuddy") -> None:
        self.bot = bot

    @app_commands.command(
        name=app_commands.locale_str("view", translate=False),
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
            replace_command_mentions=False,
        )
    )
    async def farm_view_command(
        self,
        i: "INTERACTION",
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
        name=app_commands.locale_str("add", translate=False),
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
            replace_command_mentions=False,
        ),
    )
    async def farm_add_command(
        self,
        i: "INTERACTION",
        query: str,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        account = (
            account
            or await HoyoAccount.filter(user_id=i.user.id, current=True, game=Game.GENSHIN).first()
            or await HoyoAccount.filter(user_id=i.user.id, game=Game.GENSHIN).first()
        )
        if account is None:
            raise NoAccountFoundError([Game.GENSHIN])

        characters = self.bot.search_autocomplete_choices[Game.GENSHIN][ItemCategory.CHARACTERS]
        weapons = self.bot.search_autocomplete_choices[Game.GENSHIN][ItemCategory.WEAPONS]
        valid_item_ids = {id_ for c in characters.values() for id_ in c.values()} | {
            id_ for w in weapons.values() for id_ in w.values()
        }

        if query not in valid_item_ids:
            raise InvalidQueryError

        settings = await Settings.get(user_id=i.user.id)
        farm_notify, _ = await FarmNotify.get_or_create(account=account)
        if query in farm_notify.item_ids:
            embed = DefaultEmbed(
                settings.locale or i.locale,
                self.bot.translator,
                title=LocaleStr(
                    "Item already in list", key="farm_add_command.item_already_in_list"
                ),
                description=LocaleStr(
                    "This item is already in your farm reminder list.",
                    key="farm_add_command.item_already_in_list_description",
                ),
            )
            return await i.response.send_message(embed=embed)

        farm_notify.item_ids.append(query)
        # NOTE: This is a workaround for a bug in tortoise-orm
        await FarmNotify.filter(account=account).update(item_ids=farm_notify.item_ids)

        view = FarmNotifyView(
            farm_notify,
            settings.dark_mode,
            self.bot.session,
            author=i.user,
            locale=settings.locale or i.locale,
            translator=self.bot.translator,
        )
        await view.start(i)

    @app_commands.command(
        name=app_commands.locale_str("remove", translate=False),
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
            replace_command_mentions=False,
        ),
    )
    async def farm_remove_command(
        self,
        i: "INTERACTION",
        query: str,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        account = (
            account
            or await HoyoAccount.filter(user_id=i.user.id, current=True, game=Game.GENSHIN).first()
            or await HoyoAccount.filter(user_id=i.user.id, game=Game.GENSHIN).first()
        )
        if account is None:
            raise NoAccountFoundError([Game.GENSHIN])

        settings = await Settings.get(user_id=i.user.id)
        farm_notify, _ = await FarmNotify.get_or_create(account=account)
        if query not in farm_notify.item_ids:
            embed = DefaultEmbed(
                settings.locale or i.locale,
                self.bot.translator,
                title=LocaleStr("Item not found", key="farm_remove_command.item_not_found"),
                description=LocaleStr(
                    "This item is not in your farm reminder list.",
                    key="farm_remove_command.item_not_found_description",
                ),
            )
            return await i.response.send_message(embed=embed)

        farm_notify.item_ids.remove(query)
        # NOTE: This is a workaround for a bug in tortoise-orm
        await FarmNotify.filter(account=account).update(item_ids=farm_notify.item_ids)

        view = FarmNotifyView(
            farm_notify,
            settings.dark_mode,
            self.bot.session,
            author=i.user,
            locale=settings.locale or i.locale,
            translator=self.bot.translator,
        )
        await view.start(i)

    @app_commands.command(
        name=app_commands.locale_str("notify", translate=False),
        description=app_commands.locale_str(
            "Notify you when materials of characters/weapons are farmable",
            key="farm_notify_command_description",
        ),
    )
    @app_commands.rename(
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
            replace_command_mentions=False,
        ),
    )
    async def farm_notify_command(
        self,
        i: "INTERACTION",
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        account = (
            account
            or await HoyoAccount.filter(user_id=i.user.id, current=True, game=Game.GENSHIN).first()
            or await HoyoAccount.filter(user_id=i.user.id, game=Game.GENSHIN).first()
        )
        if account is None:
            raise NoAccountFoundError([Game.GENSHIN])

        settings = await Settings.get(user_id=i.user.id)
        farm_notify, _ = await FarmNotify.get_or_create(account=account)

        view = FarmNotifyView(
            farm_notify,
            settings.dark_mode,
            self.bot.session,
            author=i.user,
            locale=settings.locale or i.locale,
            translator=self.bot.translator,
        )
        await view.start(i)

    @farm_view_command.autocomplete("account")
    @farm_add_command.autocomplete("account")
    @farm_remove_command.autocomplete("account")
    @farm_notify_command.autocomplete("account")
    async def account_autocomplete(
        self, i: "INTERACTION", current: str
    ) -> list[app_commands.Choice[str]]:
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        return await self.bot._get_account_autocomplete(
            i.user.id, current, locale, self.bot.translator, {Game.GENSHIN}
        )

    @farm_add_command.autocomplete("query")
    async def query_autocomplete(self, i: "INTERACTION", current: str) -> list[app_commands.Choice]:
        characters = self.bot.search_autocomplete_choices[Game.GENSHIN][ItemCategory.CHARACTERS]
        weapons = self.bot.search_autocomplete_choices[Game.GENSHIN][ItemCategory.WEAPONS]

        if not current:
            locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
            choice_dict = dict(characters[locale.value].items())
        else:
            choice_dict = {k: v for c in characters.values() for k, v in c.items()} | {
                k: v for w in weapons.values() for k, v in w.items()
            }

        choices = [
            app_commands.Choice(name=name, value=value)
            for name, value in choice_dict.items()
            if current.lower() in name.lower()
        ]

        random.shuffle(choices)
        return choices[:25]

    @farm_remove_command.autocomplete("query")
    async def user_query_autocomplete(
        self, i: "INTERACTION", current: str
    ) -> list[app_commands.Choice]:
        farm_notify = await FarmNotify.get_or_none(account__user_id=i.user.id)
        if farm_notify is None:
            return []

        characters = self.bot.search_autocomplete_choices[Game.GENSHIN][ItemCategory.CHARACTERS]
        weapons = self.bot.search_autocomplete_choices[Game.GENSHIN][ItemCategory.WEAPONS]

        if not current:
            locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
            choice_dict = dict(characters[locale.value].items()) | dict(
                weapons[locale.value].items()
            )
        else:
            choice_dict = {k: v for c in characters.values() for k, v in c.items()} | {
                k: v for w in weapons.values() for k, v in w.items()
            }

        choices = [
            app_commands.Choice(name=name, value=value)
            for name, value in choice_dict.items()
            if current.lower() in name.lower() and value in farm_notify.item_ids
        ]

        random.shuffle(choices)
        return choices[:25]


async def setup(bot: "HoyoBuddy") -> None:
    await bot.add_cog(Farm(bot))
