from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, Any, ClassVar, Final

import hakushin
import hakushin.clients
from discord.app_commands import Choice

from hoyo_buddy.constants import LOCALE_TO_AMBR_LANG, LOCALE_TO_HAKUSHIN_LANG, LOCALE_TO_YATTA_LANG
from hoyo_buddy.enums import Game
from hoyo_buddy.utils import sleep

from .clients import ambr, yatta
from .clients.hakushin import ItemCategory as HakushinItemCategory
from .clients.hakushin import ZZZItemCategory

if TYPE_CHECKING:
    from types import CoroutineType

    import aiohttp

    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import AutocompleteChoices, BetaAutocompleteChoices, ItemCategory, Tasks

TO_HAKUSHIN_ITEM_CATEGORY: Final[
    dict[ambr.ItemCategory | yatta.ItemCategory, HakushinItemCategory]
] = {
    ambr.ItemCategory.CHARACTERS: HakushinItemCategory.GI_CHARACTERS,
    ambr.ItemCategory.WEAPONS: HakushinItemCategory.WEAPONS,
    ambr.ItemCategory.ARTIFACT_SETS: HakushinItemCategory.ARTIFACT_SETS,
    yatta.ItemCategory.CHARACTERS: HakushinItemCategory.HSR_CHARACTERS,
    yatta.ItemCategory.LIGHT_CONES: HakushinItemCategory.LIGHT_CONES,
    yatta.ItemCategory.RELICS: HakushinItemCategory.RELICS,
}
HAKUSHIN_ITEM_CATEGORY_GAME_MAP: Final[dict[HakushinItemCategory, Game]] = {
    HakushinItemCategory.GI_CHARACTERS: Game.GENSHIN,
    HakushinItemCategory.HSR_CHARACTERS: Game.STARRAIL,
    HakushinItemCategory.WEAPONS: Game.GENSHIN,
    HakushinItemCategory.LIGHT_CONES: Game.STARRAIL,
    HakushinItemCategory.ARTIFACT_SETS: Game.GENSHIN,
    HakushinItemCategory.RELICS: Game.STARRAIL,
}


class AutocompleteSetup:
    _result: ClassVar[AutocompleteChoices]
    _beta_result: ClassVar[BetaAutocompleteChoices]
    _beta_id_to_category: ClassVar[dict[str, str]]
    """Item ID to ItemCategory.value."""
    _category_beta_ids: ClassVar[dict[tuple[Game, ItemCategory], list[str | int] | list[int]]]
    _tasks: ClassVar[Tasks]

    @classmethod
    def _get_ambr_task(
        cls, api: ambr.AmbrAPIClient, category: ambr.ItemCategory
    ) -> CoroutineType[Any, Any, list[Any]] | None:
        match category:
            case ambr.ItemCategory.CHARACTERS:
                return api.fetch_characters(traveler_gender_symbol=True)
            case ambr.ItemCategory.WEAPONS:
                return api.fetch_weapons()
            case ambr.ItemCategory.ARTIFACT_SETS:
                return api.fetch_artifact_sets()
            case ambr.ItemCategory.FOOD:
                return api.fetch_foods()
            case ambr.ItemCategory.MATERIALS:
                return api.fetch_materials()
            case ambr.ItemCategory.FURNISHINGS:
                return api.fetch_furnitures()
            case ambr.ItemCategory.FURNISHING_SETS:
                return api.fetch_furniture_sets()
            case ambr.ItemCategory.NAMECARDS:
                return api.fetch_namecards()
            case ambr.ItemCategory.LIVING_BEINGS:
                return api.fetch_monsters()
            case ambr.ItemCategory.BOOKS:
                return api.fetch_books()
            case ambr.ItemCategory.TCG:
                return api.fetch_tcg_cards()
            case _:
                return None

    @classmethod
    def _get_yatta_task(
        cls, api: yatta.YattaAPIClient, category: yatta.ItemCategory
    ) -> CoroutineType[Any, Any, list[Any]]:
        match category:
            case yatta.ItemCategory.CHARACTERS:
                return api.fetch_characters(trailblazer_gender_symbol=True)
            case yatta.ItemCategory.LIGHT_CONES:
                return api.fetch_light_cones()
            case yatta.ItemCategory.ITEMS:
                return api.fetch_items()
            case yatta.ItemCategory.RELICS:
                return api.fetch_relic_sets()
            case yatta.ItemCategory.BOOKS:
                return api.fetch_books()

    @classmethod
    def _get_hakushin_gi_task(
        cls, api: hakushin.clients.GIClient, category: HakushinItemCategory
    ) -> CoroutineType[Any, Any, list[Any]] | None:
        match category:
            case HakushinItemCategory.GI_CHARACTERS:
                return api.fetch_characters()
            case HakushinItemCategory.WEAPONS:
                return api.fetch_weapons()
            case HakushinItemCategory.ARTIFACT_SETS:
                return api.fetch_artifact_sets()
            case _:
                return None

    @classmethod
    def _get_hakushin_hsr_task(
        cls, api: hakushin.clients.HSRClient, category: HakushinItemCategory
    ) -> CoroutineType[Any, Any, list[Any]] | None:
        match category:
            case HakushinItemCategory.HSR_CHARACTERS:
                return api.fetch_characters()
            case HakushinItemCategory.LIGHT_CONES:
                return api.fetch_light_cones()
            case HakushinItemCategory.RELICS:
                return api.fetch_relic_sets()
            case _:
                return None

    @classmethod
    def _get_hakushin_zzz_task(
        cls, api: hakushin.clients.ZZZClient, category: ZZZItemCategory
    ) -> CoroutineType[Any, Any, list[Any]] | None:
        match category:
            case ZZZItemCategory.AGENTS:
                return api.fetch_characters()
            case ZZZItemCategory.W_ENGINES:
                return api.fetch_weapons()
            case ZZZItemCategory.DRIVE_DISCS:
                return api.fetch_drive_discs()
            case ZZZItemCategory.BANGBOOS:
                return api.fetch_bangboos()

    @classmethod
    async def _setup_ambr(cls, session: aiohttp.ClientSession) -> None:
        game = Game.GENSHIN

        for locale in LOCALE_TO_AMBR_LANG:
            api = ambr.AmbrAPIClient(locale, session=session)
            for category in ambr.ItemCategory:
                coro = cls._get_ambr_task(api, category)
                if coro is not None:
                    task = asyncio.create_task(coro)
                    cls._tasks[game][category][locale] = task
                    await sleep("search_autofill")

    @classmethod
    async def _setup_yatta(cls, session: aiohttp.ClientSession) -> None:
        game = Game.STARRAIL

        for locale in LOCALE_TO_YATTA_LANG:
            api = yatta.YattaAPIClient(locale, session=session)
            for category in yatta.ItemCategory:
                coro = cls._get_yatta_task(api, category)
                task = asyncio.create_task(coro)
                cls._tasks[game][category][locale] = task
                await sleep("search_autofill")

    @classmethod
    async def _setup_hakushin(cls, session: aiohttp.ClientSession) -> None:
        for locale, lang in LOCALE_TO_HAKUSHIN_LANG.items():
            gi_api = hakushin.HakushinAPI(hakushin.Game.GI, lang, session=session)
            hsr_api = hakushin.HakushinAPI(hakushin.Game.HSR, lang, session=session)
            zzz_api = hakushin.HakushinAPI(hakushin.Game.ZZZ, lang, session=session)

            for category in HakushinItemCategory:
                game = HAKUSHIN_ITEM_CATEGORY_GAME_MAP[category]
                if game is Game.GENSHIN:
                    coro = cls._get_hakushin_gi_task(gi_api, category)
                else:
                    coro = cls._get_hakushin_hsr_task(hsr_api, category)

                if coro is not None:
                    task = asyncio.create_task(coro)
                    cls._tasks[game][category][locale] = task
                    await sleep("search_autofill")

            for category in ZZZItemCategory:
                game = Game.ZZZ
                coro = cls._get_hakushin_zzz_task(zzz_api, category)
                if coro is not None:
                    task = asyncio.create_task(coro)
                    cls._tasks[game][category][locale] = task
                    await sleep("search_autofill")

    @classmethod
    def _add_to_beta_results(
        cls,
        game: Game,
        category: ambr.ItemCategory | yatta.ItemCategory | ZZZItemCategory,
        locale: Locale,
    ) -> None:
        if isinstance(category, ambr.ItemCategory | yatta.ItemCategory):
            hakushin_category = TO_HAKUSHIN_ITEM_CATEGORY.get(category)
            if hakushin_category is None:
                return
            task = cls._tasks[game][hakushin_category].get(locale)
        else:
            task = cls._tasks[game][category].get(locale)

        if task is None:
            return
        items = task.result()
        beta_ids = cls._category_beta_ids.get((game, category), [])

        for beta_id in beta_ids:
            item = next((i for i in items if str(i.id) == str(beta_id)), None)
            if item is None:
                continue

            cls._beta_result[game][locale].append(Choice(name=item.name, value=str(item.id)))
            cls._beta_id_to_category[str(item.id)] = category.value

    @classmethod
    async def start(
        cls, session: aiohttp.ClientSession
    ) -> tuple[AutocompleteChoices, dict[str, str], BetaAutocompleteChoices]:
        # Initialize variables
        cls._result = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        cls._beta_result = defaultdict(lambda: defaultdict(list))
        cls._beta_id_to_category = {}
        cls._category_beta_ids = {}
        cls._tasks = defaultdict(lambda: defaultdict(dict))

        creat_task_tasks = [
            asyncio.create_task(cls._setup_ambr(session)),
            asyncio.create_task(cls._setup_yatta(session)),
            asyncio.create_task(cls._setup_hakushin(session)),
        ]
        await asyncio.gather(*creat_task_tasks, return_exceptions=True)

        tasks = [
            task
            for categories in cls._tasks.values()
            for locales in categories.values()
            for task in locales.values()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        async with hakushin.HakushinAPI(hakushin.Game.GI) as api:
            gi_new = await api.fetch_new()
        async with hakushin.HakushinAPI(hakushin.Game.HSR) as api:
            hsr_new = await api.fetch_new()
        async with hakushin.HakushinAPI(hakushin.Game.ZZZ) as api:
            zzz_new = await api.fetch_new()

        cls._category_beta_ids = {
            (Game.GENSHIN, ambr.ItemCategory.CHARACTERS): gi_new.character_ids,
            (Game.STARRAIL, yatta.ItemCategory.CHARACTERS): hsr_new.character_ids,
            (Game.GENSHIN, ambr.ItemCategory.WEAPONS): gi_new.weapon_ids,
            (Game.STARRAIL, yatta.ItemCategory.LIGHT_CONES): hsr_new.light_cone_ids,
            (Game.GENSHIN, ambr.ItemCategory.ARTIFACT_SETS): gi_new.artifact_set_ids,
            (Game.STARRAIL, yatta.ItemCategory.RELICS): hsr_new.relic_set_ids,
            (Game.ZZZ, ZZZItemCategory.AGENTS): zzz_new.character_ids,
            (Game.ZZZ, ZZZItemCategory.W_ENGINES): zzz_new.weapon_ids,
            (Game.ZZZ, ZZZItemCategory.DRIVE_DISCS): zzz_new.equipment_ids,
            (Game.ZZZ, ZZZItemCategory.BANGBOOS): zzz_new.bangboo_ids,
        }

        for game, categories in cls._tasks.items():
            for category, locales in categories.items():
                if isinstance(category, HakushinItemCategory):
                    continue

                beta_ids = cls._category_beta_ids.get((game, category), [])
                beta_ids = [str(i) for i in beta_ids]

                for locale, task in locales.items():
                    items = task.result()
                    for item in items:
                        if not hasattr(item, "id") or not hasattr(item, "name"):
                            continue

                        # rarity is None means it's a beta item
                        if hasattr(item, "rarity") and item.rarity is None:
                            continue

                        # only hakushin has beta items
                        if (
                            isinstance(category, ZZZItemCategory)
                            and str(item.id) in beta_ids
                            # NOTE: This is a special exception for SAnby, since she is reworked in
                            # the new version, she is placed in the new items, therefore considered
                            # as a beta item, but she is already released in the official version.
                            and str(item.id) != "1381"
                        ):
                            continue

                        cls._result[game][category][locale].append(
                            Choice(name=item.name, value=str(item.id))
                        )

        for game in (Game.GENSHIN, Game.STARRAIL, Game.ZZZ):
            for category in list(TO_HAKUSHIN_ITEM_CATEGORY.keys()) + list(ZZZItemCategory):
                for locale in LOCALE_TO_HAKUSHIN_LANG:
                    cls._add_to_beta_results(game, category, locale)

        return cls._result, cls._beta_id_to_category, cls._beta_result
