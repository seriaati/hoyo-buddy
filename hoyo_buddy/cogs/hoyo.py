from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from discord import app_commands
from discord.ext import commands

from hoyo_buddy.commands.events import EventsCommand
from hoyo_buddy.utils import ephemeral

from ..commands.challenge import ChallengeCommand
from ..commands.geetest import GeetestCommand
from ..commands.stats import StatsCommand
from ..constants import HB_GAME_TO_GPY_GAME, ZZZ_AGENT_DATA_URL
from ..db.models import HoyoAccount, JSONFile, Settings, draw_locale, get_dyk, get_locale
from ..draw.main_funcs import draw_exploration_card
from ..embeds import DefaultEmbed
from ..enums import Game, GeetestType, Platform
from ..exceptions import FeatureNotImplementedError, InvalidQueryError
from ..hoyo.clients.ambr import AmbrAPIClient
from ..hoyo.clients.yatta import YattaAPIClient
from ..hoyo.transformers import HoyoAccountTransformer  # noqa: TCH001
from ..models import DrawInput
from ..types import User  # noqa: TCH001
from ..ui.hoyo.characters import CharactersView
from ..ui.hoyo.checkin import CheckInUI
from ..ui.hoyo.notes.view import NotesView
from ..ui.hoyo.redeem import RedeemUI

if TYPE_CHECKING:
    from ..bot import HoyoBuddy
    from ..types import Interaction


class Hoyo(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    @app_commands.command(
        name=app_commands.locale_str("check-in"),
        description=app_commands.locale_str("Game daily check-in", key="checkin_command_description"),
    )
    @app_commands.rename(
        user=app_commands.locale_str("user", key="user_autocomplete_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        user=app_commands.locale_str(
            "User to search the accounts with, defaults to you", key="user_autocomplete_param_description"
        ),
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
        ),
    )
    async def checkin_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        user = user or i.user
        account_ = account or await self.bot.get_account(
            user.id, (Game.GENSHIN, Game.STARRAIL, Game.HONKAI, Game.ZZZ, Game.TOT)
        )
        settings = await Settings.get(user_id=i.user.id)
        view = CheckInUI(
            account_,
            dark_mode=settings.dark_mode,
            author=i.user,
            locale=settings.locale or i.locale,
            translator=self.bot.translator,
        )
        await view.start(i)

    @app_commands.command(
        name=app_commands.locale_str("notes"),
        description=app_commands.locale_str("View real-time notes", key="notes_command_description"),
    )
    @app_commands.rename(
        user=app_commands.locale_str("user", key="user_autocomplete_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        user=app_commands.locale_str(
            "User to search the accounts with, defaults to you", key="user_autocomplete_param_description"
        ),
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
        ),
    )
    async def notes_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        user = user or i.user
        account_ = account or await self.bot.get_account(user.id, (Game.GENSHIN, Game.STARRAIL, Game.ZZZ, Game.HONKAI))
        settings = await Settings.get(user_id=i.user.id)

        view = NotesView(
            account_,
            settings.dark_mode,
            author=i.user,
            locale=settings.locale or i.locale,
            translator=self.bot.translator,
        )
        await view.start(i)

    @app_commands.command(
        name=app_commands.locale_str("characters"),
        description=app_commands.locale_str("View all of your characters", key="characters_command_description"),
    )
    @app_commands.rename(
        user=app_commands.locale_str("user", key="user_autocomplete_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        user=app_commands.locale_str(
            "User to search the accounts with, defaults to you", key="user_autocomplete_param_description"
        ),
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
        ),
    )
    async def characters_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        user = user or i.user
        account_ = account or await self.bot.get_account(user.id, (Game.GENSHIN, Game.STARRAIL, Game.ZZZ, Game.HONKAI))
        settings = await Settings.get(user_id=i.user.id)

        if account_.game is Game.GENSHIN:
            async with AmbrAPIClient(translator=self.bot.translator) as client:
                element_char_counts = await client.fetch_element_char_counts()
                path_char_counts = {}
                faction_char_counts = {}
        elif account_.game is Game.STARRAIL:
            async with YattaAPIClient(translator=self.bot.translator) as client:
                element_char_counts = await client.fetch_element_char_counts()
                path_char_counts = await client.fetch_path_char_counts()
                faction_char_counts = {}
        elif account_.game is Game.ZZZ:
            agent_data: dict[str, Any] = await JSONFile.fetch_and_cache(
                i.client.session, url=ZZZ_AGENT_DATA_URL, filename="zzz_agent_data.json"
            )

            element_char_counts: dict[str, int] = defaultdict(int)
            path_char_counts = {}
            faction_char_counts: dict[str, int] = defaultdict(int)

            for agent in agent_data.values():
                if agent["beta"]:
                    continue
                element_char_counts[agent["element"].lower()] += 1
                faction_char_counts[agent["faction"].lower()] += 1
        elif account_.game is Game.HONKAI:
            element_char_counts = {}
            path_char_counts = {}
            faction_char_counts = {}
        else:
            raise FeatureNotImplementedError(platform=account_.platform, game=account_.game)

        view = CharactersView(
            account_,
            settings.dark_mode,
            element_char_counts,
            path_char_counts,
            faction_char_counts,
            author=i.user,
            locale=settings.locale or i.locale,
            translator=self.bot.translator,
        )
        await view.start(i)

    @app_commands.command(
        name=app_commands.locale_str("challenge"),
        description=app_commands.locale_str(
            "View game end-game content statistics, like spiral abyss, memory of chaos, etc.",
            key="challenge_command_description",
        ),
    )
    @app_commands.rename(
        user=app_commands.locale_str("user", key="user_autocomplete_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        user=app_commands.locale_str(
            "User to search the accounts with, defaults to you", key="user_autocomplete_param_description"
        ),
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
        ),
    )
    async def challenge_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))
        command = ChallengeCommand(i, user, account)
        await command.run()

    @app_commands.command(
        name=app_commands.locale_str("exploration"),
        description=app_commands.locale_str(
            "View your exploration statistics in Genshin Impact", key="exploration_command_description"
        ),
    )
    @app_commands.rename(
        user=app_commands.locale_str("user", key="user_autocomplete_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        user=app_commands.locale_str(
            "User to search the accounts with, defaults to you", key="user_autocomplete_param_description"
        ),
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
        ),
    )
    async def exploration_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        user = user or i.user
        account_ = account or await self.bot.get_account(user.id, (Game.GENSHIN,))

        settings = await Settings.get(user_id=i.user.id)
        locale = settings.locale or i.locale
        account_.client.set_lang(locale)
        genshin_user = await account_.client.get_partial_genshin_user(account_.uid)

        file_ = await draw_exploration_card(
            DrawInput(
                dark_mode=settings.dark_mode,
                locale=draw_locale(locale, account_),
                session=self.bot.session,
                filename="exploration.png",
                executor=i.client.executor,
                loop=i.client.loop,
            ),
            genshin_user,
            self.bot.translator,
        )
        embed = DefaultEmbed(locale, self.bot.translator).add_acc_info(account_)
        embed.set_image(url="attachment://exploration.png")
        await i.followup.send(embed=embed, files=[file_], content=await get_dyk(i))

    @app_commands.command(
        name=app_commands.locale_str("redeem"),
        description=app_commands.locale_str("Redeem codes for in-game rewards", key="redeem_command_description"),
    )
    @app_commands.rename(
        user=app_commands.locale_str("user", key="user_autocomplete_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        user=app_commands.locale_str(
            "User to search the accounts with, defaults to you", key="user_autocomplete_param_description"
        ),
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
        ),
    )
    async def redeem_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        user = user or i.user
        account_ = account or await self.bot.get_account(
            user.id, (Game.GENSHIN, Game.STARRAIL, Game.ZZZ, Game.TOT), Platform.HOYOLAB
        )
        locale = await get_locale(i)

        available_codes = await RedeemUI.fetch_available_codes(
            i.client.session, game=HB_GAME_TO_GPY_GAME[account_.game]
        )
        view = RedeemUI(account_, available_codes, author=i.user, locale=locale, translator=self.bot.translator)
        await i.followup.send(embed=view.start_embed, view=view, content=await get_dyk(i))
        view.message = await i.original_response()

    @app_commands.command(
        name=app_commands.locale_str("geetest"),
        description=app_commands.locale_str("Complete geetest verification", key="geetest_command_description"),
    )
    @app_commands.rename(
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
        type_=app_commands.locale_str("type", key="geetest_command_type_param_name"),
    )
    @app_commands.describe(
        account=app_commands.locale_str("Account to run this command with", key="acc_no_default_param_desc"),
        type_=app_commands.locale_str("Type of geetest verification", key="geetest_cmd_type_param_desc"),
    )
    async def geetest_command(
        self, i: Interaction, account: app_commands.Transform[HoyoAccount, HoyoAccountTransformer], type_: str
    ) -> None:
        try:
            type_ = GeetestType(type_)
        except ValueError as e:
            raise InvalidQueryError from e

        await i.response.defer(ephemeral=ephemeral(i))
        command = GeetestCommand(self.bot, account, type_)
        await command.run(i)

    @app_commands.command(
        name=app_commands.locale_str("stats"),
        description=app_commands.locale_str("View game account statistics", key="stats_command_description"),
    )
    @app_commands.rename(user=app_commands.locale_str("user", key="user_autocomplete_param_name"))
    @app_commands.describe(
        user=app_commands.locale_str(
            "User to search the accounts with, defaults to you", key="user_autocomplete_param_description"
        )
    )
    async def stats_command(self, i: Interaction, user: User = None) -> None:
        command = StatsCommand(user)
        await command.run(i)

    @app_commands.command(
        name=app_commands.locale_str("events"),
        description=app_commands.locale_str("View ongoing game events", key="events_command_description"),
    )
    @app_commands.rename(account=app_commands.locale_str("account", key="account_autocomplete_param_name"))
    @app_commands.describe(
        account=app_commands.locale_str("Account to run this command with", key="acc_no_default_param_desc")
    )
    async def events_command(
        self, i: Interaction, account: app_commands.Transform[HoyoAccount, HoyoAccountTransformer]
    ) -> None:
        await EventsCommand.run(i, account=account)

    @geetest_command.autocomplete("type_")
    async def geetest_type_autocomplete(self, i: Interaction, current: str) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)
        return self.bot.get_enum_choices((GeetestType.DAILY_CHECKIN, GeetestType.REALTIME_NOTES), locale, current)

    @exploration_command.autocomplete("account")
    async def gi_acc_autocomplete(self, i: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current, (Game.GENSHIN,))

    @challenge_command.autocomplete("account")
    @events_command.autocomplete("account")
    async def gi_hsr_zzz_acc_autocomplete(self, i: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current, (Game.GENSHIN, Game.STARRAIL, Game.ZZZ))

    @notes_command.autocomplete("account")
    @characters_command.autocomplete("account")
    async def gi_hsr_zzz_honkai_acc_autocomplete(self, i: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current, (Game.GENSHIN, Game.STARRAIL, Game.ZZZ, Game.HONKAI))

    @redeem_command.autocomplete("account")
    async def gi_hsr_zzz_tot_acc_autocomplete(self, i: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current, (Game.GENSHIN, Game.STARRAIL, Game.ZZZ, Game.TOT))

    @checkin_command.autocomplete("account")
    @geetest_command.autocomplete("account")
    async def all_game_acc_autocomplete(self, i: Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current)


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Hoyo(bot))
