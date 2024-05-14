import logging
import pickle
from typing import TYPE_CHECKING, Any, TypeAlias

if TYPE_CHECKING:
    from discord import Locale
    from enka import gi, hsr

    from hoyo_buddy.models import HoyolabHSRCharacter


LOGGER_ = logging.getLogger(__name__)

Data: TypeAlias = "gi.ShowcaseResponse | hsr.ShowcaseResponse | list[HoyolabHSRCharacter]"
Character: TypeAlias = "gi.Character | hsr.Character | HoyolabHSRCharacter"
CacheExtras: TypeAlias = dict[str, dict[str, Any]]


class BaseClient:
    def _update_cache_with_live_data(
        self,
        cache: bytes | None,
        extras: CacheExtras,
        live_data: Data,
        locale: "Locale",
    ) -> tuple[bytes, CacheExtras]:
        live_chara_data: dict[str, Any] = {"live": True, "locale": locale.value}
        characters = live_data if isinstance(live_data, list) else live_data.characters

        if cache is None:
            cache = pickle.dumps(live_data)
            extras.update({str(char.id): live_chara_data for char in characters})
            return cache, extras

        cache_data: Data = pickle.loads(cache)

        live_character_ids: list[str] = []
        for character in characters:
            live_character_ids.append(str(character.id))
            if str(character.id) not in extras:
                extras[str(character.id)] = live_chara_data
            else:
                extras[str(character.id)].update(live_chara_data)

        not_live_cache_charas: list["Character"] = []

        for character in characters:
            if str(character.id) not in live_character_ids:
                not_live_cache_charas.append(character)
                extras[str(character.id)].update({"live": False})

        if isinstance(cache_data, list):
            # not_live_cache_charas: list[HoyolabHSRCharacter]
            # live_data: list[HoyolabHSRCharacter]
            cache_data = not_live_cache_charas + live_data  # pyright: ignore [reportOperatorIssue]
        else:
            # not_live_cache_charas: list[GICharacter | HSRCharacter]
            # live_data: ShowcaseResponse | StarrailInfoParsed
            cache_data.characters = not_live_cache_charas + live_data.characters  # pyright: ignore [reportOperatorIssue, reportAttributeAccessIssue]
            cache_data.player = live_data.player  # pyright: ignore [reportAttributeAccessIssue]

        cache = pickle.dumps(cache_data)

        return cache, extras

    def _set_all_live_to_false(self, cache: bytes | None, extras: CacheExtras) -> CacheExtras:
        if cache is None:
            return extras

        cache_data: Data = pickle.loads(cache)
        characters = cache_data if isinstance(cache_data, list) else cache_data.characters
        for character in characters:
            extras[str(character.id)].update({"live": False})

        return extras
