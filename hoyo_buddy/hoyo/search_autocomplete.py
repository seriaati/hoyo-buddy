from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, Any, ClassVar, Final

import hakushin
import hakushin.clients
from discord.app_commands import Choice

from ..constants import LOCALE_TO_AMBR_LANG, LOCALE_TO_HAKUSHIN_LANG, LOCALE_TO_YATTA_LANG
from ..enums import Game
from .clients import ambr, yatta
from .clients.hakushin import ItemCategory as HakushinItemCategory
from .clients.hakushin import ZZZItemCategory

if TYPE_CHECKING:
    import aiohttp
    from discord import Locale

    from ..l10n import Translator
    from ..types import AutocompleteChoices, BetaAutocompleteChoices, ItemCategory, Tasks


HARD_EXCLUDE: Final[set[str]] = {"15012", "15004"}

HAKUSHIN_ITEM_CATEGORY_GAME_MAP: Final[dict[HakushinItemCategory, Game]] = {
    HakushinItemCategory.GI_CHARACTERS: Game.GENSHIN,
    HakushinItemCategory.HSR_CHARACTERS: Game.STARRAIL,
    HakushinItemCategory.WEAPONS: Game.GENSHIN,
    HakushinItemCategory.LIGHT_CONES: Game.STARRAIL,
    HakushinItemCategory.ARTIFACT_SETS: Game.GENSHIN,
    HakushinItemCategory.RELICS: Game.STARRAIL,
}
HAKUSHIN_GI_ITEM_CATEGORY_MAP: Final[dict[ambr.ItemCategory, HakushinItemCategory]] = {
    ambr.ItemCategory.CHARACTERS: HakushinItemCategory.GI_CHARACTERS,
    ambr.ItemCategory.WEAPONS: HakushinItemCategory.WEAPONS,
    ambr.ItemCategory.ARTIFACT_SETS: HakushinItemCategory.ARTIFACT_SETS,
}
HAKUSHIN_HSR_ITEM_CATEGORY_MAP: Final[dict[yatta.ItemCategory, HakushinItemCategory]] = {
    yatta.ItemCategory.CHARACTERS: HakushinItemCategory.HSR_CHARACTERS,
    yatta.ItemCategory.LIGHT_CONES: HakushinItemCategory.LIGHT_CONES,
    yatta.ItemCategory.RELICS: HakushinItemCategory.RELICS,
}


class AutocompleteSetup:
    _result: ClassVar[AutocompleteChoices] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    _beta_result: ClassVar[BetaAutocompleteChoices] = defaultdict(lambda: defaultdict(list))
    _beta_id_to_category: ClassVar[dict[str, str]] = {}
    """Item ID to ItemCategory.value."""
    _category_beta_ids: ClassVar[dict[tuple[Game, ItemCategory], list[int]]] = {}
    _translator: ClassVar[Translator]
    _tasks: ClassVar[Tasks] = defaultdict(lambda: defaultdict(dict))

    @classmethod
    def _get_ambr_task(
        cls, api: ambr.AmbrAPIClient, category: ambr.ItemCategory, tg: asyncio.TaskGroup
    ) -> asyncio.Task[list[Any]] | None:
        match category:
            case ambr.ItemCategory.CHARACTERS:
                return tg.create_task(api.fetch_characters(traveler_gender_symbol=True))
            case ambr.ItemCategory.WEAPONS:
                return tg.create_task(api.fetch_weapons())
            case ambr.ItemCategory.ARTIFACT_SETS:
                return tg.create_task(api.fetch_artifact_sets())
            case ambr.ItemCategory.FOOD:
                return tg.create_task(api.fetch_foods())
            case ambr.ItemCategory.MATERIALS:
                return tg.create_task(api.fetch_materials())
            case ambr.ItemCategory.FURNISHINGS:
                return tg.create_task(api.fetch_furnitures())
            case ambr.ItemCategory.FURNISHING_SETS:
                return tg.create_task(api.fetch_furniture_sets())
            case ambr.ItemCategory.NAMECARDS:
                return tg.create_task(api.fetch_namecards())
            case ambr.ItemCategory.LIVING_BEINGS:
                return tg.create_task(api.fetch_monsters())
            case ambr.ItemCategory.BOOKS:
                return tg.create_task(api.fetch_books())
            case ambr.ItemCategory.TCG:
                return tg.create_task(api.fetch_tcg_cards())
            case _:
                return None

    @classmethod
    def _get_yatta_task(
        cls, api: yatta.YattaAPIClient, category: yatta.ItemCategory, tg: asyncio.TaskGroup
    ) -> asyncio.Task[list[Any]]:
        match category:
            case yatta.ItemCategory.CHARACTERS:
                return tg.create_task(api.fetch_characters(trailblazer_gender_symbol=True))
            case yatta.ItemCategory.LIGHT_CONES:
                return tg.create_task(api.fetch_light_cones())
            case yatta.ItemCategory.ITEMS:
                return tg.create_task(api.fetch_items())
            case yatta.ItemCategory.RELICS:
                return tg.create_task(api.fetch_relic_sets())
            case yatta.ItemCategory.BOOKS:
                return tg.create_task(api.fetch_books())

    @classmethod
    def _get_hakushin_gi_task(
        cls, api: hakushin.clients.GIClient, category: HakushinItemCategory, tg: asyncio.TaskGroup
    ) -> asyncio.Task[list[Any]] | None:
        match category:
            case HakushinItemCategory.GI_CHARACTERS:
                return tg.create_task(api.fetch_characters())
            case HakushinItemCategory.WEAPONS:
                return tg.create_task(api.fetch_weapons())
            case HakushinItemCategory.ARTIFACT_SETS:
                return tg.create_task(api.fetch_artifact_sets())
            case _:
                return None

    @classmethod
    def _get_hakushin_hsr_task(
        cls, api: hakushin.clients.HSRClient, category: HakushinItemCategory, tg: asyncio.TaskGroup
    ) -> asyncio.Task[list[Any]] | None:
        match category:
            case HakushinItemCategory.HSR_CHARACTERS:
                return tg.create_task(api.fetch_characters())
            case HakushinItemCategory.LIGHT_CONES:
                return tg.create_task(api.fetch_light_cones())
            case HakushinItemCategory.RELICS:
                return tg.create_task(api.fetch_relic_sets())
            case _:
                return None

    @classmethod
    def _get_hakushin_zzz_task(
        cls, api: hakushin.clients.ZZZClient, category: ZZZItemCategory, tg: asyncio.TaskGroup
    ) -> asyncio.Task[list[Any]]:
        match category:
            case ZZZItemCategory.AGENTS:
                return tg.create_task(api.fetch_characters())
            case ZZZItemCategory.W_ENGINES:
                return tg.create_task(api.fetch_weapons())
            case ZZZItemCategory.DRIVE_DISCS:
                return tg.create_task(api.fetch_drive_discs())
            case ZZZItemCategory.BANGBOOS:
                return tg.create_task(api.fetch_bangboos())

    @classmethod
    async def _setup_ambr(cls, tg: asyncio.TaskGroup, session: aiohttp.ClientSession) -> None:
        game = Game.GENSHIN

        for locale in LOCALE_TO_AMBR_LANG:
            api = ambr.AmbrAPIClient(locale, cls._translator, session=session)
            for category in ambr.ItemCategory:
                task = cls._get_ambr_task(api, category, tg)
                if task is not None:
                    cls._tasks[game][category][locale] = task
                    await asyncio.sleep(0.1)

    @classmethod
    async def _setup_yatta(cls, tg: asyncio.TaskGroup, session: aiohttp.ClientSession) -> None:
        game = Game.STARRAIL

        for locale in LOCALE_TO_YATTA_LANG:
            api = yatta.YattaAPIClient(locale, cls._translator, session=session)
            for category in yatta.ItemCategory:
                task = cls._get_yatta_task(api, category, tg)
                cls._tasks[game][category][locale] = task
                await asyncio.sleep(0.1)

    @classmethod
    async def _setup_hakushin(cls, tg: asyncio.TaskGroup, session: aiohttp.ClientSession) -> None:
        for locale, lang in LOCALE_TO_HAKUSHIN_LANG.items():
            gi_api = hakushin.HakushinAPI(hakushin.Game.GI, lang, session=session)
            hsr_api = hakushin.HakushinAPI(hakushin.Game.HSR, lang, session=session)
            zzz_api = hakushin.HakushinAPI(hakushin.Game.ZZZ, lang, session=session)

            for category in HakushinItemCategory:
                game = HAKUSHIN_ITEM_CATEGORY_GAME_MAP[category]
                if game is Game.GENSHIN:
                    task = cls._get_hakushin_gi_task(gi_api, category, tg)
                else:
                    task = cls._get_hakushin_hsr_task(hsr_api, category, tg)
                if task is not None:
                    cls._tasks[game][category][locale] = task
                    await asyncio.sleep(0.1)

            for category in ZZZItemCategory:
                game = Game.ZZZ
                task = cls._get_hakushin_zzz_task(zzz_api, category, tg)
                cls._tasks[game][category][locale] = task
                await asyncio.sleep(0.1)

    @classmethod
    def _inject_hakushin_items(
        cls, game: Game, category: ambr.ItemCategory | yatta.ItemCategory, locale: Locale, items: list[Any]
    ) -> None:
        hakushin_category = (
            HAKUSHIN_GI_ITEM_CATEGORY_MAP.get(category)
            if isinstance(category, ambr.ItemCategory)
            else HAKUSHIN_HSR_ITEM_CATEGORY_MAP.get(category)
        )
        if hakushin_category is None:
            return

        try:
            hakushin_task = cls._tasks[game][hakushin_category][locale]
        except KeyError:
            return

        hakushin_items = hakushin_task.result()
        current_item_names: set[str] = {item.name for item in items}
        current_item_ids: set[str] = {str(item.id) for item in items}

        for hakushin_item in hakushin_items:
            if (
                hakushin_item.name in current_item_names
                or hakushin_item.id in current_item_ids
                or str(hakushin_item.id) in HARD_EXCLUDE
            ):
                continue
            items.append(hakushin_item)

    @classmethod
    def _add_to_beta_results(cls, game: Game, category: ItemCategory, locale: Locale, items: list[Any]) -> None:
        beta_ids = cls._category_beta_ids.get((game, category), [])

        for beta_id in beta_ids:
            item = next((i for i in items if str(i.id) == str(beta_id)), None)
            if item is None:
                continue

            cls._beta_result[game][locale].append(Choice(name=item.name, value=str(item.id)))
            cls._beta_id_to_category[str(item.id)] = category.value

    @classmethod
    async def start(
        cls, translator: Translator, session: aiohttp.ClientSession
    ) -> tuple[AutocompleteChoices, dict[str, str], BetaAutocompleteChoices]:
        cls._translator = translator

        async with asyncio.TaskGroup() as tg:
            tg.create_task(cls._setup_ambr(tg, session))
            tg.create_task(cls._setup_yatta(tg, session))
            tg.create_task(cls._setup_hakushin(tg, session))

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

        for game, game_items in cls._tasks.items():
            for category, category_items in game_items.items():
                if isinstance(category, HakushinItemCategory):
                    continue

                for locale, task in category_items.items():
                    items = task.result()
                    if isinstance(category, ambr.ItemCategory | yatta.ItemCategory):
                        cls._inject_hakushin_items(game, category, locale, items)

                    cls._add_to_beta_results(game, category, locale, items)
                    cls._result[game][category][locale] = [Choice(name=item.name, value=str(item.id)) for item in items]

        return cls._result, cls._beta_id_to_category, cls._beta_result
