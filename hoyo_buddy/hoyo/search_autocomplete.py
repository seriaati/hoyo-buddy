from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, ClassVar, TypeAlias

from hakushin import Game as HakushinGame

from ..constants import LOCALE_TO_AMBR_LANG, LOCALE_TO_HAKUSHIN_LANG, LOCALE_TO_YATTA_LANG
from ..enums import Game
from .clients import ambr, hakushin, yatta

if TYPE_CHECKING:
    from collections.abc import Mapping

    import aiohttp

    from ..bot.translator import Translator

ItemCategory: TypeAlias = ambr.ItemCategory | yatta.ItemCategory | hakushin.ItemCategory
AutocompleteChoices: TypeAlias = dict[Game, dict[ItemCategory, dict[str, dict[str, str]]]]
Tasks: TypeAlias = dict[Game, dict[ItemCategory, dict[str, asyncio.Task[list[Any]]]]]

HARD_EXCLUDE: set[str] = {"15012", "15004"}

HAKUSHIN_ITEM_CATEGORY_GAME_MAP: Mapping[hakushin.ItemCategory, Game] = {
    hakushin.ItemCategory.GI_CHARACTERS: Game.GENSHIN,
    hakushin.ItemCategory.HSR_CHARACTERS: Game.STARRAIL,
    hakushin.ItemCategory.WEAPONS: Game.GENSHIN,
    hakushin.ItemCategory.LIGHT_CONES: Game.STARRAIL,
    hakushin.ItemCategory.ARTIFACT_SETS: Game.GENSHIN,
    hakushin.ItemCategory.RELICS: Game.STARRAIL,
}
HAKUSHIN_ITEM_CATEGORY_MAP: Mapping[
    tuple[type[ambr.ItemCategory | yatta.ItemCategory], ambr.ItemCategory | yatta.ItemCategory],
    hakushin.ItemCategory,
] = {
    (ambr.ItemCategory, ambr.ItemCategory.CHARACTERS): hakushin.ItemCategory.GI_CHARACTERS,
    (yatta.ItemCategory, yatta.ItemCategory.CHARACTERS): hakushin.ItemCategory.HSR_CHARACTERS,
    (ambr.ItemCategory, ambr.ItemCategory.WEAPONS): hakushin.ItemCategory.WEAPONS,
    (yatta.ItemCategory, yatta.ItemCategory.LIGHT_CONES): hakushin.ItemCategory.LIGHT_CONES,
    (ambr.ItemCategory, ambr.ItemCategory.ARTIFACT_SETS): hakushin.ItemCategory.ARTIFACT_SETS,
    (yatta.ItemCategory, yatta.ItemCategory.RELICS): hakushin.ItemCategory.RELICS,
}


class AutocompleteSetup:
    _result: ClassVar[AutocompleteChoices] = {}
    _beta_id_to_category: ClassVar[dict[str, str]] = {}
    """Item ID to ItemCategory.value."""
    _category_beta_ids: ClassVar[dict[tuple[Game, ItemCategory], list[int]]] = {}
    _translator: ClassVar[Translator]
    _tasks: ClassVar[Tasks] = {}

    @classmethod
    def _get_ambr_task(  # noqa: PLR0911
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
    ) -> asyncio.Task[list[Any]] | None:
        match category:
            case yatta.ItemCategory.CHARACTERS:
                return tg.create_task(api.fetch_characters())
            case yatta.ItemCategory.LIGHT_CONES:
                return tg.create_task(api.fetch_light_cones())
            case yatta.ItemCategory.ITEMS:
                return tg.create_task(api.fetch_items())
            case yatta.ItemCategory.RELICS:
                return tg.create_task(api.fetch_relic_sets())
            case yatta.ItemCategory.BOOKS:
                return tg.create_task(api.fetch_books())
            case _:
                return None

    @classmethod
    def _get_hakushin_task(  # noqa: PLR0911
        cls, api: hakushin.HakushinAPI, category: ItemCategory, tg: asyncio.TaskGroup
    ) -> asyncio.Task[list[Any]] | None:
        match category:
            case hakushin.ItemCategory.GI_CHARACTERS:
                return tg.create_task(
                    api.fetch_characters(HakushinGame.GI, traveler_gender_symbol=True)
                )
            case hakushin.ItemCategory.HSR_CHARACTERS:
                return tg.create_task(api.fetch_characters(HakushinGame.HSR))
            case hakushin.ItemCategory.WEAPONS:
                return tg.create_task(api.fetch_weapons())
            case hakushin.ItemCategory.LIGHT_CONES:
                return tg.create_task(api.fetch_light_cones())
            case hakushin.ItemCategory.ARTIFACT_SETS:
                return tg.create_task(api.fetch_artifact_sets())
            case hakushin.ItemCategory.RELICS:
                return tg.create_task(api.fetch_relic_sets())
            case _:
                return None

    @classmethod
    async def _setup_ambr(cls, tg: asyncio.TaskGroup, session: aiohttp.ClientSession) -> None:
        game = Game.GENSHIN
        if game not in cls._tasks:
            cls._tasks[game] = {}

        for locale in LOCALE_TO_AMBR_LANG:
            api = ambr.AmbrAPIClient(locale, cls._translator, session=session)
            for category in ambr.ItemCategory:
                if category not in cls._tasks[game]:
                    cls._tasks[game][category] = {}

                task = cls._get_ambr_task(api, category, tg)
                if task is not None:
                    cls._tasks[game][category][locale.value] = task
                    await asyncio.sleep(0.1)

    @classmethod
    async def _set_yatta(cls, tg: asyncio.TaskGroup, session: aiohttp.ClientSession) -> None:
        game = Game.STARRAIL
        if game not in cls._tasks:
            cls._tasks[game] = {}

        for locale in LOCALE_TO_YATTA_LANG:
            api = yatta.YattaAPIClient(locale, cls._translator, session=session)
            for category in yatta.ItemCategory:
                if category not in cls._tasks[game]:
                    cls._tasks[game][category] = {}

                task = cls._get_yatta_task(api, category, tg)
                if task is not None:
                    cls._tasks[game][category][locale.value] = task
                    await asyncio.sleep(0.1)

    @classmethod
    async def _set_hakushin(cls, tg: asyncio.TaskGroup, session: aiohttp.ClientSession) -> None:
        for locale in LOCALE_TO_HAKUSHIN_LANG:
            api = hakushin.HakushinAPI(locale, cls._translator, session=session)
            for category in hakushin.ItemCategory:
                game = HAKUSHIN_ITEM_CATEGORY_GAME_MAP[category]

                if game not in cls._tasks:
                    cls._tasks[game] = {}
                if category not in cls._tasks[game]:
                    cls._tasks[game][category] = {}

                task = cls._get_hakushin_task(api, category, tg)
                if task is not None:
                    cls._tasks[game][category][locale.value] = task
                    await asyncio.sleep(0.1)

    @classmethod
    def _inject_hakushin_items(
        cls,
        game: Game,
        category: ambr.ItemCategory | yatta.ItemCategory,
        locale: str,
        items: list[Any],
    ) -> None:
        try:
            hakushin_task = cls._tasks[game][
                HAKUSHIN_ITEM_CATEGORY_MAP[(type(category), category)]
            ][locale]
        except KeyError:
            return

        hakushin_items = hakushin_task.result()
        current_item_names: set[str] = {item.name for item in items}
        current_item_ids: set[str] = {str(item.id) for item in items}
        injected: list[Any] = []

        for hakushin_item in hakushin_items:
            if (
                hakushin_item.name in current_item_names
                or hakushin_item.id in current_item_ids
                or str(hakushin_item.id) in HARD_EXCLUDE
            ):
                continue
            items.append(hakushin_item)
            injected.append(hakushin_item)

    @classmethod
    def _get_unreleased_content_item_category(cls, game: Game) -> ItemCategory:
        return (
            ambr.ItemCategory.UNRELEASED_CONTENT
            if game is Game.GENSHIN
            else yatta.ItemCategory.UNRELEASED_CONTENT
        )

    @classmethod
    def _inject_to_unreleased_content(
        cls, game: Game, category: ItemCategory, locale: str, items: list[Any]
    ) -> None:
        beta_category = cls._get_unreleased_content_item_category(game)
        if beta_category not in cls._result[game]:
            cls._result[game][beta_category] = {}
        if locale not in cls._result[game][beta_category]:
            cls._result[game][beta_category][locale] = {}

        for item in items:
            for beta_id in cls._category_beta_ids.get((game, category), []):
                if str(item.id) == str(beta_id):
                    cls._result[game][beta_category][locale].update({item.name: str(item.id)})
                    cls._beta_id_to_category[str(item.id)] = category.value

    @classmethod
    async def start(
        cls, translator: Translator, session: aiohttp.ClientSession
    ) -> tuple[AutocompleteChoices, dict[str, str]]:
        cls._translator = translator

        async with asyncio.TaskGroup() as tg:
            tg.create_task(cls._setup_ambr(tg, session))
            tg.create_task(cls._set_yatta(tg, session))
            tg.create_task(cls._set_hakushin(tg, session))

        async with hakushin.HakushinAPI() as api:
            gi_new = await api.fetch_new(HakushinGame.GI)
            hsr_new = await api.fetch_new(HakushinGame.HSR)

        cls._category_beta_ids = {
            (Game.GENSHIN, ambr.ItemCategory.CHARACTERS): gi_new.character_ids,
            (Game.STARRAIL, yatta.ItemCategory.CHARACTERS): hsr_new.character_ids,
            (Game.GENSHIN, ambr.ItemCategory.WEAPONS): gi_new.weapon_ids,
            (Game.STARRAIL, yatta.ItemCategory.LIGHT_CONES): hsr_new.light_cone_ids,
            (Game.GENSHIN, ambr.ItemCategory.ARTIFACT_SETS): gi_new.artifact_set_ids,
            (Game.STARRAIL, yatta.ItemCategory.RELICS): hsr_new.relic_set_ids,
        }

        for game, game_items in cls._tasks.items():
            cls._result[game] = {}
            for category, category_items in game_items.items():
                if isinstance(category, hakushin.ItemCategory):
                    continue

                cls._result[game][category] = {}
                for locale, task in category_items.items():
                    items = task.result()
                    cls._inject_hakushin_items(game, category, locale, items)
                    cls._inject_to_unreleased_content(game, category, locale, items)
                    cls._result[game][category][locale] = {
                        item.name: str(item.id) for item in items if item.name
                    }

        return cls._result, cls._beta_id_to_category
