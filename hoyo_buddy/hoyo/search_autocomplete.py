from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, ClassVar, TypeAlias

from ..constants import LOCALE_TO_AMBR_LANG, LOCALE_TO_YATTA_LANG
from ..enums import Game
from .clients import ambr_client as ambr
from .clients import yatta_client as yatta

if TYPE_CHECKING:
    import aiohttp

    from ..bot.translator import Translator

ITEM_CATEGORY: TypeAlias = ambr.ItemCategory | yatta.ItemCategory
AUTOCOMPLETE_CHOICES: TypeAlias = dict[Game, dict[ITEM_CATEGORY, dict[str, dict[str, str]]]]
"""[game][category][locale.value][item_name] = item_id"""
TASKS: TypeAlias = dict[Game, dict[ITEM_CATEGORY, dict[str, asyncio.Task[list[Any]]]]]

LOGGER_ = logging.getLogger(__name__)


class AutocompleteSetup:
    _result: ClassVar[AUTOCOMPLETE_CHOICES] = {}
    _translator: ClassVar[Translator]
    _tasks: ClassVar[TASKS] = {}

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
    async def _setup_ambr(cls, tg: asyncio.TaskGroup, session: aiohttp.ClientSession) -> None:
        game = Game.GENSHIN
        cls._tasks[game] = {}

        for locale in LOCALE_TO_AMBR_LANG:
            api = ambr.AmbrAPIClient(locale, cls._translator, session=session)
            for category in ambr.ItemCategory:
                cls._tasks[game][category] = {}
                task = cls._get_ambr_task(api, category, tg)
                if task is not None:
                    cls._tasks[game][category][locale.value] = task
                    await asyncio.sleep(0.1)

    @classmethod
    async def _set_yatta(cls, tg: asyncio.TaskGroup, session: aiohttp.ClientSession) -> None:
        game = Game.STARRAIL
        cls._tasks[game] = {}

        for locale in LOCALE_TO_YATTA_LANG:
            api = yatta.YattaAPIClient(locale, cls._translator, session=session)
            for category in yatta.ItemCategory:
                cls._tasks[game][category] = {}
                task = cls._get_yatta_task(api, category, tg)
                if task is not None:
                    cls._tasks[game][category][locale.value] = task
                    await asyncio.sleep(0.1)

    @classmethod
    async def start(
        cls, translator: Translator, session: aiohttp.ClientSession
    ) -> AUTOCOMPLETE_CHOICES:
        cls._translator = translator

        async with asyncio.TaskGroup() as tg:
            tg.create_task(cls._setup_ambr(tg, session))
            tg.create_task(cls._set_yatta(tg, session))

        for game, game_items in cls._tasks.items():
            cls._result[game] = {}
            for category, category_items in game_items.items():
                cls._result[game][category] = {}
                for locale, task in category_items.items():
                    items = task.result()
                    cls._result[game][category][locale] = {
                        item.name: item.id for item in items if item.name
                    }

        return cls._result
