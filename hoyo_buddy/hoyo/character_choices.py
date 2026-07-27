from __future__ import annotations

from typing import TYPE_CHECKING

import hb_data
from discord.app_commands import Choice

from hoyo_buddy.constants import (
    GI_UGC_CHARACTER_IDS,
    TRAILBLAZER_IDS,
    TRAVELER_ELEMENTS,
    TRAVELER_IDS,
    locale_to_genshin_data_lang,
    locale_to_starrail_data_lang,
    locale_to_zenless_data_lang,
)
from hoyo_buddy.enums import HSRPath
from hoyo_buddy.l10n import EnumStr, translator

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale

HB_DATA_PATH_TO_HSR_PATH: dict[hb_data.hsr.Path, HSRPath] = {
    hb_data.hsr.Path.DESTRUCTION: HSRPath.DESTRUCTION,
    hb_data.hsr.Path.THE_HUNT: HSRPath.THE_HUNT,
    hb_data.hsr.Path.ERUDITION: HSRPath.ERUDITION,
    hb_data.hsr.Path.HARMONY: HSRPath.HARMONY,
    hb_data.hsr.Path.NIHILITY: HSRPath.NIHILITY,
    hb_data.hsr.Path.PRESERVATION: HSRPath.PRESERVATION,
    hb_data.hsr.Path.ABUNDANCE: HSRPath.ABUNDANCE,
    hb_data.hsr.Path.REMEMBRANCE: HSRPath.REMEMBRANCE,
    hb_data.hsr.Path.ELATION: HSRPath.ELATION,
}


async def get_gi_character_choices(
    locale: Locale, *, ambr_traveler_ids: bool = False
) -> list[Choice[str]]:
    """Get GI character autocomplete choices from hb-data.

    Args:
        locale: Locale to translate the character names to.
        ambr_traveler_ids: Whether to expand Travelers into one choice per element with
            AmbrAPI-format values (e.g. 10000005-anemo), for commands that pass the
            value to AmbrAPI. Otherwise Travelers use their base IDs (e.g. 10000005).
    """
    async with hb_data.GIClient() as client:
        characters = client.get_characters(
            lang=hb_data.gi.Language(locale_to_genshin_data_lang(locale))
        )

    choices: list[Choice[str]] = []
    for character in characters:
        if character.id in GI_UGC_CHARACTER_IDS:
            continue

        if character.id in TRAVELER_IDS:
            gender = "♂" if character.id == 10000005 else "♀"
            if ambr_traveler_ids:
                for element in TRAVELER_ELEMENTS:
                    element_str = translator.translate(EnumStr(element), locale)
                    choices.append(
                        Choice(
                            name=f"{character.name} ({element_str}) ({gender})",
                            value=f"{character.id}-{element.name.lower()}",
                        )
                    )
                continue
            choices.append(Choice(name=f"{character.name} ({gender})", value=str(character.id)))
        else:
            choices.append(Choice(name=character.name, value=str(character.id)))

    return choices


async def get_hsr_character_choices(locale: Locale) -> list[Choice[str]]:
    """Get HSR character autocomplete choices from hb-data."""
    async with hb_data.HSRClient() as client:
        characters = client.get_characters(
            lang=hb_data.hsr.Language(locale_to_starrail_data_lang(locale))
        )

    choices: list[Choice[str]] = []
    for character in characters:
        name = character.name
        if character.id in TRAILBLAZER_IDS:
            path_str = translator.translate(
                EnumStr(HB_DATA_PATH_TO_HSR_PATH[character.path]), locale
            )
            # TRAILBLAZER_IDS also contains non-trailblazers (like March 7th) that
            # need the path suffix to be distinguishable, but not a gender symbol
            gender = (
                ("♂" if character.id % 2 != 0 else "♀")
                if str(character.id).startswith("80")
                else ""
            )
            name = f"{name} ({path_str}) ({gender})" if gender else f"{name} ({path_str})"
        choices.append(Choice(name=name, value=str(character.id)))

    return choices


async def get_zzz_character_choices(locale: Locale) -> list[Choice[str]]:
    """Get ZZZ character autocomplete choices from hb-data."""
    async with hb_data.ZZZClient() as client:
        characters = client.get_characters(
            lang=hb_data.zzz.Language(locale_to_zenless_data_lang(locale))
        )

    return [Choice(name=character.name, value=str(character.id)) for character in characters]
