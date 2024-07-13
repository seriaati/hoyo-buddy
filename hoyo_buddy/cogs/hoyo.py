from __future__ import annotations

from typing import TYPE_CHECKING

import enka
from discord import app_commands
from discord.ext import commands

from ..bot.translator import LocaleStr
from ..commands.challenge import ChallengeCommand
from ..commands.geetest import GeetestCommand
from ..commands.profile import ProfileCommand
from ..db.models import HoyoAccount, Settings, get_locale
from ..draw.main_funcs import draw_exploration_card
from ..embeds import DefaultEmbed
from ..enums import Game, GeetestType, Platform
from ..exceptions import FeatureNotImplementedError, IncompleteParamError, InvalidQueryError
from ..hoyo.clients.ambr import AmbrAPIClient
from ..hoyo.clients.yatta import YattaAPIClient
from ..hoyo.transformers import HoyoAccountTransformer  # noqa: TCH001
from ..models import DrawInput
from ..types import User  # noqa: TCH001
from ..ui.hoyo.characters import CharactersView
from ..ui.hoyo.checkin import CheckInUI
from ..ui.hoyo.notes.view import NotesView
from ..ui.hoyo.redeem import RedeemUI
from ..utils import ephemeral

if TYPE_CHECKING:
    from ..bot import HoyoBuddy
    from ..types import Interaction


class Hoyo(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    async def _get_uid_and_game(
        self, user_id: int, account: HoyoAccount | None, uid: str | None, game_value: str | None
    ) -> tuple[int, Game, HoyoAccount | None]:
        """Get the UID and game from the account or the provided UID and game value."""
        account_ = None
        if uid is not None:
            if game_value is None:
                raise IncompleteParamError(
                    LocaleStr(key="game_value_incomplete_param_error_message")
                )
            try:
                uid_ = int(uid)
            except ValueError as e:
                raise enka.errors.WrongUIDFormatError from e

            try:
                game = Game(game_value)
            except ValueError as e:
                raise InvalidQueryError from e
        else:
            try:
                games = (
                    (Game(game_value),) if game_value is not None else (Game.GENSHIN, Game.STARRAIL, Game.ZZZ)
                )
            except ValueError as e:
                raise InvalidQueryError from e

            account_ = account or await self.bot.get_account(user_id, games)
            uid_ = account_.uid
            game = account_.game

        return uid_, game, account_

    @app_commands.command(
        name=app_commands.locale_str("check-in"),
        description=app_commands.locale_str(
            "Game daily check-in", key="checkin_command_description"
        ),
    )
    @app_commands.rename(
        user=app_commands.locale_str("user", key="user_autocomplete_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        user=app_commands.locale_str(
            "User to search the accounts with, defaults to you",
            key="user_autocomplete_param_description",
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
            user.id, (Game.GENSHIN, Game.STARRAIL, Game.HONKAI, Game.ZZZ)
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
        name=app_commands.locale_str("profile"),
        description=app_commands.locale_str(
            "View your in-game profile and generate character build cards",
            key="profile_command_description",
        ),
    )
    @app_commands.rename(
        user=app_commands.locale_str("user", key="user_autocomplete_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
        uid=app_commands.locale_str("uid"),
        game_value=app_commands.locale_str("game", key="search_command_game_param_name"),
    )
    @app_commands.describe(
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
        game_value=app_commands.locale_str(
            "Game of the UID", key="profile_command_game_value_description"
        ),
    )
    async def profile_command(
        self,
        i: Interaction,
        user: User = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
        uid: app_commands.Range[str, 9, 10] | None = None,
        game_value: str | None = None,
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        locale = await get_locale(i)
        user = user or i.user
        uid_, game, account_ = await self._get_uid_and_game(user.id, account, uid, game_value)

        handler = ProfileCommand(
            uid=uid_,
            game=game,
            account=account_,
            locale=locale,
            user=i.user,
            translator=self.bot.translator,
        )

        if game is Game.GENSHIN:
            view = await handler.run_genshin()
        elif game is Game.STARRAIL:
            view = await handler.run_hsr()
        elif game is Game.ZZZ:
            view = await handler.run_zzz()
        else:
            raise FeatureNotImplementedError(platform=Platform.HOYOLAB, game=game)

        await view.start(i)

    @app_commands.command(
        name=app_commands.locale_str("notes"),
        description=app_commands.locale_str(
            "View real-time notes", key="notes_command_description"
        ),
    )
    @app_commands.rename(
        user=app_commands.locale_str("user", key="user_autocomplete_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        user=app_commands.locale_str(
            "User to search the accounts with, defaults to you",
            key="user_autocomplete_param_description",
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
        account_ = account or await self.bot.get_account(
            user.id, (Game.GENSHIN, Game.STARRAIL, Game.ZZZ)
        )
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
        description=app_commands.locale_str(
            "View all of your characters", key="characters_command_description"
        ),
    )
    @app_commands.rename(
        user=app_commands.locale_str("user", key="user_autocomplete_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        user=app_commands.locale_str(
            "User to search the accounts with, defaults to you",
            key="user_autocomplete_param_description",
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
        account_ = account or await self.bot.get_account(user.id, [Game.GENSHIN, Game.STARRAIL])
        settings = await Settings.get(user_id=i.user.id)

        if account_.game is Game.GENSHIN:
            async with AmbrAPIClient(translator=self.bot.translator) as client:
                element_char_counts = await client.fetch_element_char_counts()
                path_char_counts = {}
        elif account_.game is Game.STARRAIL:
            async with YattaAPIClient(translator=self.bot.translator) as client:
                element_char_counts = await client.fetch_element_char_counts()
                path_char_counts = await client.fetch_path_char_counts()
        else:
            raise FeatureNotImplementedError(platform=account_.platform, game=account_.game)

        view = CharactersView(
            account_,
            settings.dark_mode,
            element_char_counts,
            path_char_counts,
            author=i.user,
            locale=settings.locale or i.locale,
            translator=self.bot.translator,
        )
        await view.start(i, show_first_time_msg=account_.game is Game.GENSHIN)

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
            "User to search the accounts with, defaults to you",
            key="user_autocomplete_param_description",
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
            "View your exploration statistics in Genshin Impact",
            key="exploration_command_description",
        ),
    )
    @app_commands.rename(
        user=app_commands.locale_str("user", key="user_autocomplete_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        user=app_commands.locale_str(
            "User to search the accounts with, defaults to you",
            key="user_autocomplete_param_description",
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
                locale=locale,
                session=self.bot.session,
                filename="exploration.webp",
                executor=i.client.executor,
                loop=i.client.loop,
            ),
            genshin_user,
            self.bot.translator,
        )
        embed = DefaultEmbed(locale, self.bot.translator).add_acc_info(account_)
        embed.set_image(url="attachment://exploration.webp")
        await i.followup.send(embed=embed, files=[file_])

    @app_commands.command(
        name=app_commands.locale_str("redeem"),
        description=app_commands.locale_str(
            "Redeem codes for in-game rewards", key="redeem_command_description"
        ),
    )
    @app_commands.rename(
        user=app_commands.locale_str("user", key="user_autocomplete_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
    )
    @app_commands.describe(
        user=app_commands.locale_str(
            "User to search the accounts with, defaults to you",
            key="user_autocomplete_param_description",
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
            user.id, (Game.GENSHIN, Game.STARRAIL, Game.ZZZ), (Platform.HOYOLAB,)
        )
        locale = await get_locale(i)

        view = RedeemUI(account_, author=i.user, locale=locale, translator=self.bot.translator)
        await i.followup.send(embed=view.start_embed, view=view)
        view.message = await i.original_response()

    @app_commands.command(
        name=app_commands.locale_str("geetest"),
        description=app_commands.locale_str(
            "Complete geetest verification", key="geetest_command_description"
        ),
    )
    @app_commands.rename(
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
        type_=app_commands.locale_str("type", key="geetest_command_type_param_name"),
    )
    @app_commands.describe(
        account=app_commands.locale_str(
            "Account to run this command with", key="acc_no_default_param_desc"
        ),
        type_=app_commands.locale_str(
            "Type of geetest verification", key="geetest_cmd_type_param_desc"
        ),
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
        command = GeetestCommand(self.bot, i, account, type_)
        await command.run()
        command.start_listener()

    @geetest_command.autocomplete("type_")
    async def geetest_type_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)
        return self.bot.get_enum_autocomplete(
            [GeetestType.DAILY_CHECKIN, GeetestType.REALTIME_NOTES], locale, current
        )

    @profile_command.autocomplete("game_value")
    async def profile_game_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        locale = await get_locale(i)
        return self.bot.get_enum_autocomplete([Game.GENSHIN, Game.STARRAIL], locale, current)

    @exploration_command.autocomplete("account")
    async def exploration_command_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice]:
        locale = await get_locale(i)
        user: User = i.namespace.user
        return await self.bot.get_account_autocomplete(
            user, i.user.id, current, locale, self.bot.translator, (Game.GENSHIN,)
        )

    @challenge_command.autocomplete("account")
    @characters_command.autocomplete("account")
    async def gi_hsr_acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice]:
        locale = await get_locale(i)
        user: User = i.namespace.user
        return await self.bot.get_account_autocomplete(
            user, i.user.id, current, locale, self.bot.translator, (Game.GENSHIN, Game.STARRAIL)
        )

    @redeem_command.autocomplete("account")
    @notes_command.autocomplete("account")
    @profile_command.autocomplete("account")
    async def gi_hsr_zzz_acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice]:
        locale = await get_locale(i)
        user: User = i.namespace.user
        return await self.bot.get_account_autocomplete(
            user,
            i.user.id,
            current,
            locale,
            self.bot.translator,
            (Game.GENSHIN, Game.STARRAIL, Game.ZZZ),
        )

    @checkin_command.autocomplete("account")
    @geetest_command.autocomplete("account")
    async def all_game_acc_autocomplete(
        self, i: Interaction, current: str
    ) -> list[app_commands.Choice]:
        locale = await get_locale(i)
        user: User = i.namespace.user
        return await self.bot.get_account_autocomplete(
            user,
            i.user.id,
            current,
            locale,
            self.bot.translator,
            (Game.GENSHIN, Game.STARRAIL, Game.HONKAI, Game.ZZZ),
        )


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Hoyo(bot))
