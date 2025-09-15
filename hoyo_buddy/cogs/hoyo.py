from __future__ import annotations

from typing import TYPE_CHECKING

from discord import app_commands
from discord.ext import commands

from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.commands.events import EventsCommand
from hoyo_buddy.db import HoyoAccount, Settings, get_dyk, get_locale
from hoyo_buddy.db.utils import show_anniversary_dismissible
from hoyo_buddy.ui.hoyo.genshin.exploration import ExplorationView
from hoyo_buddy.ui.hoyo.mimo import MimoView
from hoyo_buddy.ui.hoyo.web_events import WebEventsView
from hoyo_buddy.utils import ephemeral
from hoyo_buddy.utils.misc import handle_autocomplete_errors

from ..commands.geetest import GeetestCommand
from ..commands.stats import StatsCommand
from ..constants import HB_GAME_TO_GPY_GAME, get_describe_kwargs, get_rename_kwargs
from ..enums import GeetestType
from ..exceptions import CantRedeemCodeError, InvalidQueryError
from ..hoyo.transformers import HoyoAccountTransformer
from ..types import Interaction, User
from ..ui.hoyo.checkin import CheckInUI
from ..ui.hoyo.notes.view import NotesView
from ..ui.hoyo.redeem import RedeemUI

if TYPE_CHECKING:
    from ..bot import HoyoBuddy


class Hoyo(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    @app_commands.command(
        name=app_commands.locale_str("check-in"), description=COMMANDS["check-in"].description
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def checkin_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["check-in"].games)
        ] = None,
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        user = user or i.user
        account = account or await self.bot.get_account(
            user.id, COMMANDS["check-in"].games, COMMANDS["check-in"].platform
        )
        settings = await Settings.get(user_id=i.user.id)
        view = CheckInUI(
            account, dark_mode=settings.dark_mode, author=i.user, locale=await get_locale(i)
        )
        await view.start(i)

        await show_anniversary_dismissible(i)

    @app_commands.command(
        name=app_commands.locale_str("notes"), description=COMMANDS["notes"].description
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def notes_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["notes"].games)
        ] = None,
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        user = user or i.user
        account = account or await self.bot.get_account(
            user.id, COMMANDS["notes"].games, COMMANDS["notes"].platform
        )
        accounts = await self.bot.get_accounts(user.id, COMMANDS["notes"].games)
        settings = await Settings.get(user_id=i.user.id)

        view = NotesView(
            account,
            accounts,
            dark_mode=settings.dark_mode,
            author=i.user,
            locale=await get_locale(i),
        )
        await view.start(i)

        await show_anniversary_dismissible(i)

    @app_commands.command(
        name=app_commands.locale_str("exploration"), description=COMMANDS["exploration"].description
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def exploration_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["exploration"].games)
        ] = None,
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        user = user or i.user
        account = account or await self.bot.get_account(
            user.id, COMMANDS["exploration"].games, COMMANDS["exploration"].platform
        )
        settings = await Settings.get(user_id=i.user.id)
        locale = await get_locale(i)

        view = ExplorationView(account, dark_mode=settings.dark_mode, author=i.user, locale=locale)
        await view.start(i)

        await show_anniversary_dismissible(i)

    @app_commands.command(
        name=app_commands.locale_str("redeem"), description=COMMANDS["redeem"].description
    )
    @app_commands.rename(**get_rename_kwargs(account=True))
    @app_commands.describe(**get_describe_kwargs(account=True))
    async def redeem_command(
        self,
        i: Interaction,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["redeem"].games)
        ] = None,
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        account = account or await self.bot.get_account(
            i.user.id, COMMANDS["redeem"].games, COMMANDS["redeem"].platform
        )
        if not account.can_redeem_code:
            raise CantRedeemCodeError

        await account.fetch_related("notif_settings")
        locale = await get_locale(i)
        available_codes = await RedeemUI.fetch_available_codes(
            i.client.session, game=HB_GAME_TO_GPY_GAME[account.game]
        )
        view = RedeemUI(account, available_codes, author=i.user, locale=locale)
        await i.followup.send(embed=view.start_embed, view=view, content=await get_dyk(i))
        view.message = await i.original_response()

        await show_anniversary_dismissible(i)

    @app_commands.command(
        name=app_commands.locale_str("geetest"), description=COMMANDS["geetest"].description
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
        account: app_commands.Transform[
            HoyoAccount, HoyoAccountTransformer(COMMANDS["geetest"].games)
        ],
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
        name=app_commands.locale_str("stats"), description=COMMANDS["stats"].description
    )
    @app_commands.rename(**get_rename_kwargs(user=True))
    @app_commands.describe(**get_describe_kwargs(user=True))
    async def stats_command(self, i: Interaction, user: User = None) -> None:
        command = StatsCommand(user)
        await command.run(i)

        await show_anniversary_dismissible(i)

    @app_commands.command(
        name=app_commands.locale_str("events"), description=COMMANDS["events"].description
    )
    @app_commands.rename(**get_rename_kwargs(user=True, account=True))
    @app_commands.describe(**get_describe_kwargs(user=True, account=True))
    async def events_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["events"].games)
        ] = None,
    ) -> None:
        await EventsCommand.run(i, user=user, account=account)

        await show_anniversary_dismissible(i)

    @app_commands.command(
        name=app_commands.locale_str("mimo"), description=COMMANDS["mimo"].description
    )
    @app_commands.rename(**get_rename_kwargs(account=True))
    @app_commands.describe(**get_describe_kwargs(account=True))
    async def mimo_command(
        self,
        i: Interaction,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["mimo"].games)
        ] = None,
    ) -> None:
        account = account or await self.bot.get_account(
            i.user.id, COMMANDS["mimo"].games, COMMANDS["mimo"].platform
        )
        settings = await Settings.get(user_id=i.user.id)
        view = MimoView(
            account, dark_mode=settings.dark_mode, author=i.user, locale=await get_locale(i)
        )
        await view.start(i)

        await show_anniversary_dismissible(i)

    @app_commands.command(
        name=app_commands.locale_str("web-events"), description=COMMANDS["web-events"].description
    )
    @app_commands.rename(**get_rename_kwargs(account=True))
    @app_commands.describe(**get_describe_kwargs(account=True))
    async def web_events_command(
        self,
        i: Interaction,
        account: app_commands.Transform[
            HoyoAccount | None, HoyoAccountTransformer(COMMANDS["web-events"].games)
        ] = None,
    ) -> None:
        account = account or await self.bot.get_account(
            i.user.id, COMMANDS["web-events"].games, platform=COMMANDS["web-events"].platform
        )
        view = WebEventsView(account, author=i.user, locale=await get_locale(i))
        await view.start(i)

        await show_anniversary_dismissible(i)

    @geetest_command.autocomplete("type_")
    @handle_autocomplete_errors
    async def geetest_type_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)
        return self.bot.get_enum_choices(
            (GeetestType.DAILY_CHECKIN, GeetestType.REALTIME_NOTES), locale, current
        )

    @exploration_command.autocomplete("account")
    @events_command.autocomplete("account")
    @notes_command.autocomplete("account")
    @redeem_command.autocomplete("account")
    @mimo_command.autocomplete("account")
    @checkin_command.autocomplete("account")
    @geetest_command.autocomplete("account")
    @web_events_command.autocomplete("account")
    @handle_autocomplete_errors
    async def acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self.bot.get_game_account_choices(i, current)


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Hoyo(bot))
