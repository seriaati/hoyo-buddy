import logging
from typing import TYPE_CHECKING

from discord import app_commands
from discord.ext import commands
from genshin.errors import GenshinException
from mihomo.errors import HttpRequestError, UserNotFound
from seria.utils import read_yaml

from ..bot.bot import USER  # noqa: TCH001
from ..bot.translator import LocaleStr
from ..db.models import EnkaCache, HoyoAccount, Settings
from ..draw.main_funcs import draw_exploration_card
from ..enums import Game
from ..exceptions import IncompleteParamError
from ..hoyo.clients.ambr_client import AmbrAPIClient
from ..hoyo.clients.enka_client import EnkaAPI
from ..hoyo.clients.mihomo_client import MihomoAPI
from ..hoyo.clients.yatta_client import YattaAPIClient
from ..hoyo.transformers import HoyoAccountTransformer  # noqa: TCH001
from ..models import DrawInput
from ..ui.hoyo.characters import CharactersView
from ..ui.hoyo.checkin import CheckInUI
from ..ui.hoyo.genshin.abyss import AbyssView
from ..ui.hoyo.notes.view import NotesView
from ..ui.hoyo.profile.view import ProfileView
from ..ui.hoyo.redeem import RedeemUI

if TYPE_CHECKING:
    from mihomo.models import StarrailInfoParsed

    from ..bot.bot import INTERACTION, HoyoBuddy
    from ..models import HoyolabHSRCharacter

LOGGER_ = logging.getLogger(__name__)


class Hoyo(commands.Cog):
    def __init__(self, bot: "HoyoBuddy") -> None:
        self.bot = bot

    async def _get_uid_and_game(
        self, user_id: int, account: HoyoAccount | None, uid: str | None, game_value: str | None
    ) -> tuple[int, Game, HoyoAccount | None]:
        """Get the UID and game from the account or the provided UID and game value."""
        account_ = None
        if uid is not None:
            if game_value is None:
                raise IncompleteParamError(
                    LocaleStr(
                        "You must specify the game of the UID",
                        key="game_value_incomplete_param_error_message",
                    )
                )
            uid_ = int(uid)
            game = Game(game_value)
        else:
            account_ = account or await self.bot.get_account(user_id, [Game.GENSHIN, Game.STARRAIL])
            uid_ = account_.uid
            game = account_.game

        return uid_, game, account_

    @app_commands.command(
        name=app_commands.locale_str("check-in", translate=False),
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
        i: "INTERACTION",
        user: USER = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        user = user or i.user
        account_ = account or await self.bot.get_account(
            user.id, (Game.GENSHIN, Game.STARRAIL, Game.HONKAI)
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
        name=app_commands.locale_str("profile", translate=False),
        description=app_commands.locale_str(
            "View your in-game profile and generate character build cards",
            key="profile_command_description",
        ),
    )
    @app_commands.rename(
        user=app_commands.locale_str("user", key="user_autocomplete_param_name"),
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
        uid=app_commands.locale_str("uid", translate=False),
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
    async def profile_command(
        self,
        i: "INTERACTION",
        user: USER = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
        uid: app_commands.Range[str, 9, 10] | None = None,
        game_value: str | None = None,
    ) -> None:
        await i.response.defer()

        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        user = user or i.user
        uid_, game, account_ = await self._get_uid_and_game(user.id, account, uid, game_value)

        if game is Game.GENSHIN:
            async with EnkaAPI(locale) as client:
                data = await client.fetch_showcase(uid_)

            cache = await EnkaCache.get(uid=uid_)
            view = ProfileView(
                uid_,
                game,
                cache.extras,
                await read_yaml("hoyo-buddy-assets/assets/gi-build-card/data.yaml"),
                hoyolab_characters=[],
                genshin_data=data,
                author=i.user,
                locale=locale,
                translator=self.bot.translator,
            )
        elif game is Game.STARRAIL:
            hoyolab_charas: list[HoyolabHSRCharacter] = []
            starrail_data: StarrailInfoParsed | None = None
            hoyolab_user = None

            try:
                client = MihomoAPI(locale)
                starrail_data = await client.fetch_user(uid_)
            except (HttpRequestError, UserNotFound):
                if account_ is None:
                    # mihomo fails and no hoyolab account provided, raise error
                    raise

            if account_ is not None:
                client = account_.client
                client.set_lang(locale)
                if starrail_data is None:
                    hoyolab_user = await client.get_starrail_user()
                try:
                    hoyolab_charas = await client.get_hoyolab_hsr_characters()
                except GenshinException:
                    if starrail_data is None:
                        # mihomo and hoyolab both failed, raise error
                        raise

            cache = await EnkaCache.get(uid=uid_)
            view = ProfileView(
                uid_,
                game,
                cache.extras,
                await read_yaml("hoyo-buddy-assets/assets/hsr-build-card/data.yaml"),
                hoyolab_characters=hoyolab_charas,
                hoyolab_user=hoyolab_user,
                starrail_data=starrail_data,
                author=i.user,
                locale=locale,
                translator=self.bot.translator,
            )
        else:
            raise NotImplementedError

        await view.start(i)

    @app_commands.command(
        name=app_commands.locale_str("notes", translate=False),
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
        i: "INTERACTION",
        user: USER = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        user = user or i.user
        account_ = account or await self.bot.get_account(user.id, [Game.GENSHIN, Game.STARRAIL])
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale

        view = NotesView(
            account_,
            account_.user.settings,
            author=i.user,
            locale=locale,
            translator=self.bot.translator,
        )
        await view.start(i)

    @app_commands.command(
        name=app_commands.locale_str("characters", translate=False),
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
        i: "INTERACTION",
        user: USER = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await i.response.defer()

        user = user or i.user
        account_ = account or await self.bot.get_account(user.id, [Game.GENSHIN, Game.STARRAIL])
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale

        if account_.game is Game.GENSHIN:
            async with AmbrAPIClient(translator=self.bot.translator) as client:
                element_char_counts = await client.fetch_element_char_counts()
                path_char_counts = {}
        elif account_.game is Game.STARRAIL:
            async with YattaAPIClient(translator=self.bot.translator) as client:
                element_char_counts = await client.fetch_element_char_counts()
                path_char_counts = await client.fetch_path_char_counts()
        else:
            raise NotImplementedError

        view = CharactersView(
            account_,
            account_.user.settings.dark_mode,
            element_char_counts,
            path_char_counts,
            author=i.user,
            locale=locale,
            translator=self.bot.translator,
        )
        await view.start(i, show_first_time_msg=account_.game is Game.GENSHIN)

    @app_commands.command(
        name=app_commands.locale_str("abyss", translate=False),
        description=app_commands.locale_str(
            "View your spiral abyss data", key="abyss__command_description"
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
    async def abyss_command(
        self,
        i: "INTERACTION",
        user: USER = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        user = user or i.user
        account_ = account or await self.bot.get_account(i.user.id, (Game.GENSHIN,))
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale

        view = AbyssView(
            account_,
            account_.user.settings.dark_mode,
            author=i.user,
            locale=locale,
            translator=self.bot.translator,
        )
        await view.start(i)

    @app_commands.command(
        name=app_commands.locale_str("exploration", translate=False),
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
        i: "INTERACTION",
        user: USER = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        await i.response.defer()

        user = user or i.user
        account_ = account or await self.bot.get_account(user.id, (Game.GENSHIN,))

        settings = await Settings.get(user_id=i.user.id)
        account_.client.set_lang(settings.locale or i.locale)
        genshin_user = await account_.client.get_partial_genshin_user(account_.uid)

        file_ = await draw_exploration_card(
            DrawInput(
                dark_mode=settings.dark_mode,
                locale=settings.locale or i.locale,
                session=self.bot.session,
                filename="exploration.webp",
            ),
            genshin_user,
            self.bot.translator,
        )
        await i.followup.send(files=[file_])

    @app_commands.command(
        name=app_commands.locale_str("redeem", translate=False),
        description=app_commands.locale_str(
            "Redeem codes for in-game rewards",
            key="redeem_command_description",
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
        i: "INTERACTION",
        user: USER = None,
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        user = user or i.user
        account_ = account or await self.bot.get_account(user.id, (Game.GENSHIN, Game.STARRAIL))
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale

        view = RedeemUI(account_, author=i.user, locale=locale, translator=self.bot.translator)
        await i.response.send_message(embed=view.start_embed, view=view)
        view.message = await i.original_response()

    @abyss_command.autocomplete("account")
    @exploration_command.autocomplete("account")
    async def characters_command_autocomplete(
        self, i: "INTERACTION", current: str
    ) -> list[app_commands.Choice]:
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        user: USER = i.namespace.user
        return await self.bot.get_account_autocomplete(
            user,
            i.user.id,
            current,
            locale,
            self.bot.translator,
            (Game.GENSHIN,),
        )

    @characters_command.autocomplete("account")
    @profile_command.autocomplete("account")
    @notes_command.autocomplete("account")
    @redeem_command.autocomplete("account")
    async def account_autocomplete(
        self, i: "INTERACTION", current: str
    ) -> list[app_commands.Choice]:
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        user: USER = i.namespace.user
        return await self.bot.get_account_autocomplete(
            user,
            i.user.id,
            current,
            locale,
            self.bot.translator,
            (Game.GENSHIN, Game.STARRAIL),
        )

    @checkin_command.autocomplete("account")
    async def checkin_command_autocomplete(
        self, i: "INTERACTION", current: str
    ) -> list[app_commands.Choice]:
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        user: USER = i.namespace.user
        return await self.bot.get_account_autocomplete(
            user,
            i.user.id,
            current,
            locale,
            self.bot.translator,
            (Game.GENSHIN, Game.STARRAIL, Game.HONKAI),
        )


async def setup(bot: "HoyoBuddy") -> None:
    await bot.add_cog(Hoyo(bot))
