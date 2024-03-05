import asyncio
import logging
import random
from typing import TYPE_CHECKING, Any

import discord
from discord import app_commands
from discord.ext import commands, tasks
from seria.utils import read_yaml

from ..bot.translator import LocaleStr, Translator
from ..db.models import EnkaCache, HoyoAccount, Settings
from ..draw.hoyo.genshin.notes import draw_genshin_notes_card
from ..draw.hoyo.hsr.notes import draw_hsr_notes_card
from ..draw.static import download_and_save_static_images
from ..emojis import PROJECT_AMBER
from ..enums import Game
from ..exceptions import IncompleteParamError, InvalidQueryError, NoAccountFoundError
from ..hoyo.enka_client import EnkaAPI
from ..hoyo.genshin import ambr
from ..hoyo.hsr import yatta
from ..hoyo.mihomo_client import MihomoAPI
from ..hoyo.transformers import HoyoAccountTransformer  # noqa: TCH001
from ..ui import URLButtonView
from ..ui.hoyo.checkin import CheckInUI
from ..ui.hoyo.genshin.abyss import AbyssView
from ..ui.hoyo.genshin.search import ArtifactSetUI, BookVolumeUI, CharacterUI, TCGCardUI, WeaponUI
from ..ui.hoyo.hsr.search import BookUI, RelicSetUI
from ..ui.hoyo.hsr.search import CharacterUI as HSRCharacterUI
from ..ui.hoyo.profile.view import ProfileView

if TYPE_CHECKING:
    from ..bot.bot import INTERACTION, HoyoBuddy

LOGGER_ = logging.getLogger(__name__)


class Hoyo(commands.Cog):
    def __init__(self, bot: "HoyoBuddy") -> None:
        self.bot = bot

        self._search_categories: dict[Game, list[str]] = {
            Game.GENSHIN: [c.value for c in ambr.ItemCategory],
            Game.STARRAIL: [c.value for c in yatta.ItemCategory],
        }

        # [game][category][locale][item_name] -> item_id
        self._search_autocomplete_choices: dict[
            Game,
            dict[
                ambr.ItemCategory | yatta.ItemCategory,
                dict[str, dict[str, str]],
            ],
        ] = {}

    async def cog_load(self) -> None:
        self._update_search_autocomplete_choices.start()

    async def cog_unload(self) -> None:
        self._update_search_autocomplete_choices.cancel()

    async def _fetch_item_task(
        self,
        api: ambr.AmbrAPIClient | yatta.YattaAPIClient,
        item_category: ambr.ItemCategory | yatta.ItemCategory,
        locale: discord.Locale,
    ) -> None:
        if isinstance(api, ambr.AmbrAPIClient) and isinstance(item_category, ambr.ItemCategory):
            game = Game.GENSHIN
            items = await api.fetch_items(item_category)
        elif isinstance(api, yatta.YattaAPIClient) and isinstance(
            item_category, yatta.ItemCategory
        ):
            game = Game.STARRAIL
            items = await api.fetch_items_(item_category)
        else:
            msg = f"Invalid item category: {item_category!r}"
            raise TypeError(msg)

        category_locale_choices = (
            self._search_autocomplete_choices.setdefault(game, {})
            .setdefault(item_category, {})
            .setdefault(locale.value, {})
        )
        for item in items:
            category_locale_choices[item.name] = str(item.id)

    async def _setup_search_autocomplete_choices(self) -> None:
        LOGGER_.info("Setting up search autocomplete choices")
        start = self.bot.loop.time()

        for locale in ambr.LOCALE_TO_AMBR_LANG:
            async with ambr.AmbrAPIClient(locale, self.bot.translator) as api:
                for item_category in ambr.ItemCategory:
                    await self._fetch_item_task(api, item_category, locale)

        for locale in yatta.LOCALE_TO_YATTA_LANG:
            async with yatta.YattaAPIClient(locale, self.bot.translator) as api:
                for item_category in yatta.ItemCategory:
                    await self._fetch_item_task(api, item_category, locale)

        LOGGER_.info(
            "Finished setting up search autocomplete choices, took %.2f seconds",
            self.bot.loop.time() - start,
        )

    @tasks.loop(hours=24)
    async def _update_search_autocomplete_choices(self) -> None:
        if self.bot.env == "dev":
            return
        await self._setup_search_autocomplete_choices()

    @_update_search_autocomplete_choices.before_loop
    async def _before_update_search_autocomplete_choices(self) -> None:
        await self.bot.wait_until_ready()

    @staticmethod
    async def _account_autocomplete(
        user_id: int,
        current: str,
        locale: discord.Locale,
        translator: Translator,
    ) -> list[discord.app_commands.Choice]:
        accounts = await HoyoAccount.filter(user_id=user_id).all()
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
                name=f"{account} | {translator.translate(LocaleStr(account.game, warn_no_key=False), locale)}",
                value=f"{account.uid}_{account.game}",
            )
            for account in accounts
            if current.lower() in str(account).lower()
        ]

    @staticmethod
    def _get_error_app_command_choice(error_message: str) -> app_commands.Choice[str]:
        return app_commands.Choice(
            name=app_commands.locale_str(error_message, warn_no_key=False),
            value="none",
        )

    @app_commands.command(
        name=app_commands.locale_str("check-in", translate=False),
        description=app_commands.locale_str(
            "Game daily check-in", key="checkin_command_description"
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
    async def checkin_command(
        self,
        i: "INTERACTION",
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> Any:
        settings = await Settings.get(user_id=i.user.id)
        account = (
            account
            or await HoyoAccount.filter(user_id=i.user.id, current=True).first()
            or await HoyoAccount.filter(user_id=i.user.id).first()
        )
        if account is None:
            raise NoAccountFoundError

        view = CheckInUI(
            account,
            dark_mode=settings.dark_mode,
            author=i.user,
            locale=settings.locale or i.locale,
            translator=self.bot.translator,
        )
        await view.start(i)

    @checkin_command.autocomplete("account")
    async def checkin_command_autocomplete(
        self, i: "INTERACTION", current: str
    ) -> list[app_commands.Choice]:
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
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
    async def search_command(  # noqa: C901, PLR0911, PLR0912, PLR0914, PLR0915
        self,
        i: "INTERACTION",
        game_value: str,
        category_value: str,
        query: str,
    ) -> Any:
        if category_value == "none" or query == "none":
            raise InvalidQueryError
        try:
            game = Game(game_value)
        except ValueError as e:
            raise InvalidQueryError from e

        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale

        if game is Game.GENSHIN:
            try:
                category = ambr.ItemCategory(category_value)
            except ValueError as e:
                raise InvalidQueryError from e

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
                return await weapon_ui.start(i)

            if category is ambr.ItemCategory.NAMECARDS:
                async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    namecard_detail = await api.fetch_namecard_detail(int(query))
                    embed = api.get_namecard_embed(namecard_detail)
                    return await i.followup.send(embed=embed)

            if category is ambr.ItemCategory.ARTIFACT_SETS:
                artifact_set_ui = ArtifactSetUI(
                    query,
                    author=i.user,
                    locale=locale,
                    translator=i.client.translator,
                )
                return await artifact_set_ui.start(i)

            if category is ambr.ItemCategory.FOOD:
                async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    food_detail = await api.fetch_food_detail(int(query))
                    embed = api.get_food_embed(food_detail)
                    return await i.followup.send(embed=embed)

            if category is ambr.ItemCategory.MATERIALS:
                async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    material_detail = await api.fetch_material_detail(int(query))
                    embed = api.get_material_embed(material_detail)
                    return await i.followup.send(embed=embed)

            if category is ambr.ItemCategory.FURNISHINGS:
                async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    furniture_detail = await api.fetch_furniture_detail(int(query))
                    embed = api.get_furniture_embed(furniture_detail)
                    return await i.followup.send(
                        embed=embed,
                        view=URLButtonView(
                            i.client.translator,
                            locale,
                            url=f"https://ambr.top/{api.lang.value}/archive/furniture/{query}/",
                            label="ambr.top",
                            emoji=PROJECT_AMBER,
                        ),
                    )

            if category is ambr.ItemCategory.FURNISHING_SETS:
                async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    furniture_set_detail = await api.fetch_furniture_set_detail(int(query))
                    embed = api.get_furniture_set_embed(furniture_set_detail)
                    return await i.followup.send(
                        embed=embed,
                        view=URLButtonView(
                            i.client.translator,
                            locale,
                            url=f"https://ambr.top/{api.lang.value}/archive/furnitureSuite/{query}/",
                            label="ambr.top",
                            emoji=PROJECT_AMBER,
                        ),
                    )

            if category is ambr.ItemCategory.LIVING_BEINGS:
                async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    monster_detail = await api.fetch_monster_detail(int(query))
                    embed = api.get_monster_embed(monster_detail)
                    return await i.followup.send(
                        embed=embed,
                        view=URLButtonView(
                            i.client.translator,
                            locale,
                            url=f"https://ambr.top/{api.lang.value}/archive/monster/{query}/",
                            label="ambr.top",
                            emoji=PROJECT_AMBER,
                        ),
                    )

            if category is ambr.ItemCategory.BOOKS:
                async with ambr.AmbrAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    book = await api.fetch_book_detail(int(query))
                    book_volume_ui = BookVolumeUI(
                        book,
                        api.lang.value,
                        author=i.user,
                        locale=locale,
                        translator=i.client.translator,
                    )
                    return await book_volume_ui.start(i)

            if category is ambr.ItemCategory.TCG:
                tcg_card_ui = TCGCardUI(
                    int(query), author=i.user, locale=locale, translator=i.client.translator
                )
                return await tcg_card_ui.start(i)
        elif game is Game.STARRAIL:
            try:
                category = yatta.ItemCategory(category_value)
            except ValueError as e:
                raise InvalidQueryError from e

            if category is yatta.ItemCategory.ITEMS:
                async with yatta.YattaAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    item = await api.fetch_item_detail(int(query))
                    embed = api.get_item_embed(item)
                    return await i.followup.send(embed=embed)

            if category is yatta.ItemCategory.LIGHT_CONES:
                async with yatta.YattaAPIClient(locale, i.client.translator) as api:
                    await i.response.defer()
                    light_cone = await api.fetch_light_cone_detail(int(query))
                    embed = api.get_light_cone_embed(light_cone)
                    return await i.followup.send(embed=embed)

            if category is yatta.ItemCategory.BOOKS:
                book_ui = BookUI(
                    query, author=i.user, locale=locale, translator=i.client.translator
                )
                return await book_ui.start(i)

            if category is yatta.ItemCategory.RELICS:
                relic_set_ui = RelicSetUI(
                    query, author=i.user, locale=locale, translator=i.client.translator
                )
                return await relic_set_ui.start(i)

            if category is yatta.ItemCategory.CHARACTERS:
                try:
                    character_id = int(query)
                except ValueError as e:
                    raise InvalidQueryError from e

                character_ui = HSRCharacterUI(
                    character_id,
                    author=i.user,
                    locale=locale,
                    translator=i.client.translator,
                )
                return await character_ui.start(i)

    @search_command.autocomplete("category_value")
    async def search_command_category_autocomplete(
        self, i: "INTERACTION", current: str
    ) -> list[app_commands.Choice]:
        try:
            game = Game(i.namespace.game)
        except ValueError:
            return [self._get_error_app_command_choice("Invalid game selected")]

        return [
            app_commands.Choice(
                name=app_commands.locale_str(c, warn_no_key=False),
                value=c,
            )
            for c in self._search_categories[game]
            if current.lower() in c.lower()
        ]

    @search_command.autocomplete("query")
    async def search_command_query_autocomplete(
        self, i: "INTERACTION", current: str
    ) -> list[app_commands.Choice]:
        try:
            game = Game(i.namespace.game)
        except ValueError:
            return [self._get_error_app_command_choice("Invalid game selected")]

        try:
            if game is Game.GENSHIN:
                category = ambr.ItemCategory(i.namespace.category)
            elif game is Game.STARRAIL:
                category = yatta.ItemCategory(i.namespace.category)
            else:
                return [self._get_error_app_command_choice("Invalid game selected")]
        except ValueError:
            return [self._get_error_app_command_choice("Invalid category selected")]

        if not current:
            locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
            autocomplete_choices = self._search_autocomplete_choices[game][category][locale.value]
        else:
            autocomplete_choices = {
                k: v
                for c in self._search_autocomplete_choices[game][category].values()
                for k, v in c.items()
            }

        choices = [
            app_commands.Choice(name=choice, value=item_id)
            for choice, item_id in autocomplete_choices.items()
            if current.lower() in choice.lower()
        ]

        random.shuffle(choices)
        return choices[:25]

    @app_commands.command(
        name=app_commands.locale_str("profile", translate=False),
        description=app_commands.locale_str(
            "View your in-game profile and generate character build cards",
            key="profile_command_description",
        ),
    )
    @app_commands.rename(
        account=app_commands.locale_str("account", key="account_autocomplete_param_name"),
        uid=app_commands.locale_str("uid", translate=False),
        game_value=app_commands.locale_str("game", key="search_command_game_param_name"),
    )
    @app_commands.describe(
        account=app_commands.locale_str(
            "Account to run this command with, defaults to the selected one in /accounts",
            key="account_autocomplete_param_description",
            replace_command_mentions=False,
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
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
        uid: app_commands.Range[str, 9, 10] | None = None,
        game_value: str | None = None,
    ) -> None:
        await i.response.defer()

        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        uid_, game = await self._get_uid_and_game(i.user.id, account, uid, game_value)

        if game is Game.GENSHIN:
            async with EnkaAPI(locale) as client:
                data = await client.fetch_showcase(uid_)

            cache = await EnkaCache.get(uid=uid_)
            view = ProfileView(
                uid_,
                game,
                cache.extras,
                await read_yaml("hoyo-buddy-assets/assets/gi-build-card/data.yaml"),
                genshin_data=data,
                author=i.user,
                locale=locale,
                translator=self.bot.translator,
            )
        elif game is Game.STARRAIL:
            client = MihomoAPI(locale)
            data = await client.fetch_user(uid_)

            cache = await EnkaCache.get(uid=uid_)
            view = ProfileView(
                uid_,
                game,
                cache.extras,
                await read_yaml("hoyo-buddy-assets/assets/hsr-build-card/data.yaml"),
                star_rail_data=data,
                author=i.user,
                locale=locale,
                translator=self.bot.translator,
            )
        else:
            raise NotImplementedError

        await view.start(i)

    async def _get_uid_and_game(
        self, user_id: int, account: HoyoAccount | None, uid: str | None, game_value: str | None
    ) -> tuple[int, Game]:
        if uid is not None:
            uid_ = int(uid)
            if game_value is None:
                raise IncompleteParamError(
                    LocaleStr(
                        "You must specify the game of the UID",
                        key="game_value_incomplete_param_error_message",
                    )
                )
            game = Game(game_value)
        elif account is None:
            account_ = (
                await HoyoAccount.filter(user_id=user_id, current=True).first()
                or await HoyoAccount.filter(user_id=user_id).first()
            )
            if account_ is None:
                raise NoAccountFoundError
            uid_ = account_.uid
            game = account_.game
        else:
            uid_ = account.uid
            game = account.game

        return uid_, game

    @profile_command.autocomplete("account")
    async def profile_command_autocomplete(
        self, i: "INTERACTION", current: str
    ) -> list[app_commands.Choice]:
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        return await self._account_autocomplete(i.user.id, current, locale, self.bot.translator)

    @app_commands.command(
        name=app_commands.locale_str("abyss-enemies", translate=False),
        description=app_commands.locale_str(
            "View the current abyss enemies", key="abyss_command_description"
        ),
    )
    async def abyss_enemies_command(self, i: "INTERACTION") -> None:
        settings = await Settings.get(user_id=i.user.id)

        view = AbyssView(
            dark_mode=settings.dark_mode,
            author=i.user,
            locale=settings.locale or i.locale,
            translator=self.bot.translator,
        )
        view.add_items()
        await view.update(i)

    @app_commands.command(
        name=app_commands.locale_str("notes", translate=False),
        description=app_commands.locale_str(
            "View real-time notes", key="notes_command_description"
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
    async def notes_command(
        self,
        i: "INTERACTION",
        account: app_commands.Transform[HoyoAccount | None, HoyoAccountTransformer] = None,
    ) -> None:
        settings = await Settings.get(user_id=i.user.id)
        account = (
            account
            or await HoyoAccount.filter(user_id=i.user.id, current=True).first()
            or await HoyoAccount.filter(user_id=i.user.id).first()
        )
        if account is None:
            raise NoAccountFoundError

        await i.response.defer()

        locale = settings.locale or i.locale
        client = account.client
        client.set_lang(locale)

        if account.game is Game.GENSHIN:
            notes = await client.get_genshin_notes()
            await download_and_save_static_images(
                [exped.character_icon for exped in notes.expeditions], "gi-notes", self.bot.session
            )
            buffer = await asyncio.to_thread(
                draw_genshin_notes_card,
                notes,
                locale,
                self.bot.translator,
                settings.dark_mode,
            )
        elif account.game is Game.STARRAIL:
            notes = await client.get_starrail_notes()
            await download_and_save_static_images(
                [exped.item_url for exped in notes.expeditions], "hsr-notes", self.bot.session
            )
            buffer = await asyncio.to_thread(
                draw_hsr_notes_card,
                notes,
                locale,
                self.bot.translator,
                settings.dark_mode,
            )
        else:
            raise NotImplementedError

        buffer.seek(0)
        file_ = discord.File(buffer, filename="notes.webp")
        await i.followup.send(file=file_)

    @notes_command.autocomplete("account")
    async def notes_command_autocomplete(
        self, i: "INTERACTION", current: str
    ) -> list[app_commands.Choice]:
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        return await self._account_autocomplete(i.user.id, current, locale, self.bot.translator)


async def setup(bot: "HoyoBuddy") -> None:
    await bot.add_cog(Hoyo(bot))
