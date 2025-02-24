from __future__ import annotations

from typing import TYPE_CHECKING

from discord import app_commands
from discord.ext import commands

from hoyo_buddy.commands.events import EventsCommand
from hoyo_buddy.db import HoyoAccount, Settings, get_dyk, get_locale
from hoyo_buddy.ui.hoyo.genshin.exploration import ExplorationView
from hoyo_buddy.ui.hoyo.mimo import MimoView
from hoyo_buddy.ui.hoyo.web_events import WebEventsView
from hoyo_buddy.utils import ephemeral

from ..commands.geetest import GeetestCommand
from ..commands.stats import StatsCommand
from ..constants import HB_GAME_TO_GPY_GAME, get_describe_kwargs, get_rename_kwargs
from ..enums import Game, GeetestType, Platform
from ..exceptions import CantRedeemCodeError, InvalidQueryError
from ..hoyo.transformers import HoyoAccountTransformer  # noqa: TC001
from ..types import User  # noqa: TC001
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
        description=app_commands.locale_str(
            "Game daily check-in", key="checkin_command_description"
        ),
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
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
        )
        await view.start(i)

    @app_commands.command(
        name=app_commands.locale_str("notes"),
        description=app_commands.locale_str(
            "View real-time notes", key="notes_command_description"
        ),
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def notes_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        user = user or i.user
        account_ = account or await self.bot.get_account(
            user.id, (Game.GENSHIN, Game.STARRAIL, Game.ZZZ, Game.HONKAI)
        )
        accounts = await self.bot.get_accounts(
            user.id, (Game.GENSHIN, Game.STARRAIL, Game.ZZZ, Game.HONKAI)
        )
        settings = await Settings.get(user_id=i.user.id)

        view = NotesView(
            account_,
            accounts,
            dark_mode=settings.dark_mode,
            author=i.user,
            locale=settings.locale or i.locale,
        )
        await view.start(i)

    @app_commands.command(
        name=app_commands.locale_str("exploration"),
        description=app_commands.locale_str(
            "View your exploration statistics in Genshin Impact",
            key="exploration_command_description",
        ),
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
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

        view = ExplorationView(account_, dark_mode=settings.dark_mode, author=i.user, locale=locale)
        await view.start(i)

    @app_commands.command(
        name=app_commands.locale_str("redeem"),
        description=app_commands.locale_str(
            "Redeem codes for in-game rewards", key="redeem_command_description"
        ),
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
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
        if not account_.can_redeem_code:
            raise CantRedeemCodeError

        locale = await get_locale(i)
        available_codes = await RedeemUI.fetch_available_codes(
            i.client.session, game=HB_GAME_TO_GPY_GAME[account_.game]
        )
        view = RedeemUI(account_, available_codes, author=i.user, locale=locale)
        await i.followup.send(embed=view.start_embed, view=view, content=await get_dyk(i))
        view.message = await i.original_response()

    @app_commands.command(
        name=app_commands.locale_str("geetest"),
        description=app_commands.locale_str(
            "Complete geetest verification", key="geetest_command_description"
        ),
    )
    @app_commands.rename(
        type_=app_commands.locale_str("type", key="geetest_command_type_param_name"),
        **get_rename_kwargs(account=True),
    )
    @app_commands.describe(
        type_=app_commands.locale_str(
            "Type of geetest verification", key="geetest_cmd_type_param_desc"
        ),
        **get_describe_kwargs(account_no_default=True),
    )
    async def geetest_command(
        self,
        i: Interaction,
        account: app_commands.Transform[HoyoAccount, HoyoAccountTransformer],
        type_: str,
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
        description=app_commands.locale_str(
            "View game account statistics", key="stats_command_description"
        ),
    )
    @app_commands.rename(**get_rename_kwargs(user=True))
    @app_commands.describe(**get_describe_kwargs(user=True))
    async def stats_command(self, i: Interaction, user: User = None) -> None:
        command = StatsCommand(user)
        await command.run(i)

    @app_commands.command(
        name=app_commands.locale_str("events"),
        description=app_commands.locale_str(
            "View ongoing game events", key="events_command_description"
        ),
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def events_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await EventsCommand.run(i, user=user, account=account)

    @app_commands.command(
        name=app_commands.locale_str("mimo"),
        description=app_commands.locale_str("Traveling Mimo event management", key="mimo_cmd_desc"),
    )
    @app_commands.rename(**get_rename_kwargs(account=True))
    @app_commands.describe(**get_describe_kwargs(account=True))
    async def mimo_command(
        self,
        i: Interaction,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        account = account or await self.bot.get_account(
            i.user.id, (Game.ZZZ, Game.STARRAIL, Game.GENSHIN), Platform.HOYOLAB
        )
        settings = await Settings.get(user_id=i.user.id)
        view = MimoView(
            account, dark_mode=settings.dark_mode, author=i.user, locale=settings.locale or i.locale
        )
        await view.start(i)

    @app_commands.command(
        name=app_commands.locale_str("web-events"),
        description=app_commands.locale_str(
            "View ongoing web events and set notifier", key="web_events_cmd_desc"
        ),
    )
    @app_commands.rename(**get_rename_kwargs(account=True))
    @app_commands.describe(**get_describe_kwargs(account=True))
    async def web_events_command(
        self,
        i: Interaction,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        account = account or await self.bot.get_account(
            i.user.id,
            (Game.GENSHIN, Game.STARRAIL, Game.ZZZ, Game.HONKAI, Game.TOT),
            platform=Platform.HOYOLAB,
        )
        view = WebEventsView(account, author=i.user, locale=i.locale)
        await view.start(i)

    @geetest_command.autocomplete("type_")
    async def geetest_type_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)
        return self.bot.get_enum_choices(
            (GeetestType.DAILY_CHECKIN, GeetestType.REALTIME_NOTES), locale, current
        )

    @exploration_command.autocomplete("account")
    async def gi_acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current, (Game.GENSHIN,))

    @events_command.autocomplete("account")
    async def gi_hsr_zzz_acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(
            i, current, (Game.GENSHIN, Game.STARRAIL, Game.ZZZ)
        )

    @notes_command.autocomplete("account")
    async def gi_hsr_zzz_honkai_acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(
            i, current, (Game.GENSHIN, Game.STARRAIL, Game.ZZZ, Game.HONKAI)
        )

    @redeem_command.autocomplete("account")
    async def gi_hsr_zzz_tot_acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(
            i, current, (Game.GENSHIN, Game.STARRAIL, Game.ZZZ, Game.TOT), Platform.HOYOLAB
        )

    @mimo_command.autocomplete("account")
    async def mimo_acc_autofill(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(
            i, current, (Game.STARRAIL, Game.ZZZ, Game.GENSHIN), Platform.HOYOLAB
        )

    @checkin_command.autocomplete("account")
    @geetest_command.autocomplete("account")
    async def all_game_acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(
            i, current, (Game.GENSHIN, Game.STARRAIL, Game.ZZZ, Game.HONKAI, Game.TOT)
        )

    @web_events_command.autocomplete("account")
    async def hoyolab_all_game_acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(
            i,
            current,
            (Game.GENSHIN, Game.STARRAIL, Game.ZZZ, Game.HONKAI, Game.TOT),
            platform=Platform.HOYOLAB,
        )


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Hoyo(bot))
