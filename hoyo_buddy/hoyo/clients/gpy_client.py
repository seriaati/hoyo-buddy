from typing import TYPE_CHECKING

import genshin
from seria.utils import read_json, write_json

from ...bot.translator import LocaleStr, Translator
from ...constants import (
    AMBR_TRAVELER_ID_TO_ENKA_TRAVELER_ID,
    LOCALE_TO_GPY_LANG,
    TRAVELER_IDS,
    contains_traveler_id,
)
from ...embeds import DefaultEmbed
from ...enums import GAME_CONVERTER, TalentBoost
from ...icons import get_game_icon
from ...utils import get_now
from .ambr_client import AmbrAPIClient
from .enka_client import EnkaAPI

if TYPE_CHECKING:
    from discord import Locale

TALENT_BOOST_DATA_PATH = "./.static/talent_boost.json"
PC_ICON_DATA_PATH = "./.static/pc_icons.json"
GI_TALENT_LEVEL_DATA_PATH = "./.static/talent_levels/gi_{uid}.json"


class GenshinClient(genshin.Client):
    def __init__(
        self,
        cookies: str,
        *,
        uid: int | None = None,
        game: genshin.Game = genshin.Game.GENSHIN,
    ) -> None:
        super().__init__(cookies, game=game, uid=uid)

    def set_lang(self, locale: "Locale") -> None:
        self.lang = LOCALE_TO_GPY_LANG[locale]

    @staticmethod
    def get_daily_reward_embed(
        daily_reward: genshin.models.DailyReward,
        game: genshin.Game,
        locale: "Locale",
        translator: Translator,
    ) -> DefaultEmbed:
        embed = DefaultEmbed(
            locale,
            translator,
            title=LocaleStr("Daily check-in reward claimed", key="reward_claimed_title"),
            description=f"{daily_reward.name} x{daily_reward.amount}",
        )
        embed.set_thumbnail(url=daily_reward.icon)
        converted_game = GAME_CONVERTER[game]
        embed.set_author(
            name=LocaleStr(converted_game.value, warn_no_key=False),
            icon_url=get_game_icon(converted_game),
        )
        return embed

    @staticmethod
    def convert_character_id_to_ambr_format(character: genshin.models.Character) -> str:
        """Convert character ID to the format used by AmbrAPI (traveler ID contains element)."""
        return (
            f"{character.id}-{character.element.lower()}"
            if character.id in TRAVELER_IDS
            else str(character.id)
        )

    @staticmethod
    def _convert_character_id_to_enka_format(character_id: str) -> str:
        """Convert character ID to the format used by EnkaAPI."""
        return (
            AMBR_TRAVELER_ID_TO_ENKA_TRAVELER_ID[character_id]
            if contains_traveler_id(character_id)
            else character_id
        )

    async def update_pc_icons(self) -> None:
        fields = await self.get_lineup_fields()
        pc_icons = {str(character.id): character.pc_icon for character in fields.characters}
        await write_json(PC_ICON_DATA_PATH, pc_icons)

    async def update_gi_chara_talent_lvl_data(self, character: genshin.models.Character) -> None:
        talent_level_data: dict[str, str] = await read_json(
            GI_TALENT_LEVEL_DATA_PATH.format(uid=self.uid)
        )
        talent_boost_data: dict[str, int] = await read_json(TALENT_BOOST_DATA_PATH)

        details = await self.get_character_details(character.id)
        character_id = self.convert_character_id_to_ambr_format(character)

        # Get talent boost type
        if character_id not in talent_boost_data:
            async with AmbrAPIClient() as client:
                talent_boost = await client.fetch_talent_boost(character_id)
            talent_boost_data[character_id] = talent_boost.value
            await write_json(TALENT_BOOST_DATA_PATH, talent_boost_data)
        else:
            talent_boost = TalentBoost(talent_boost_data[character_id])

        # Get talent order
        async with EnkaAPI() as client:
            talent_order = client.get_character_talent_order(
                self._convert_character_id_to_enka_format(character_id)
            )

        # Get talent levels
        talent_levels: list[int] = []
        for i, talent_id in enumerate(talent_order):
            talent = next(talent for talent in details.talents if talent.id == talent_id)

            c3 = character.constellations[2]

            if (  # noqa: PLR0916
                i == 1 and talent_boost is TalentBoost.BOOST_E and c3.activated
            ) or (i == 2 and talent_boost is TalentBoost.BOOST_Q and c3.activated):
                talent_levels.append(talent.level + 3)
            else:
                talent_levels.append(talent.level)

        talent_str = "/".join(str(level) for level in talent_levels)
        talent_level_data[character_id] = talent_str

        talent_level_data["updated_at"] = get_now().isoformat()

        filename = GI_TALENT_LEVEL_DATA_PATH.format(uid=self.uid)
        await write_json(filename, talent_level_data)
