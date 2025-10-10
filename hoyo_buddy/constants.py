from __future__ import annotations

import datetime
import os
import pathlib
from typing import TYPE_CHECKING, Final, Literal

import akasha
import ambr
import enka
import genshin
import hakushin
import yatta
from discord import app_commands
from loguru import logger
from yarl import URL

from hoyo_buddy.config import CONFIG

from .enums import (
    ChallengeType,
    Game,
    GenshinCity,
    GenshinElement,
    HSRElement,
    HSRPath,
    Locale,
    OpenGameLabel,
    Platform,
)

if TYPE_CHECKING:
    from hoyo_buddy.models import ZZZStat
    from hoyo_buddy.types import AutoTaskType, OpenGameGame, OpenGameRegion, SleepTime


STATIC_FOLDER = pathlib.Path("./.static")

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
DB_SMALLINT_MAX = 32767

TRAVELER_IDS = {10000005, 10000007}
AMBR_TRAVELER_ID_TO_ENKA_TRAVELER_ID = {
    "10000005-anemo": "10000005-504",
    "10000005-geo": "10000005-506",
    "10000005-electro": "10000005-507",
    "10000005-dendro": "10000005-508",
    "10000005-hydro": "10000005-503",
    "10000007-anemo": "10000007-704",
    "10000007-geo": "10000007-706",
    "10000007-electro": "10000007-707",
    "10000007-dendro": "10000007-708",
    "10000007-hydro": "10000007-703",
}

TRAILBLAZER_IDS = {
    8001,  # Physics male
    8002,  # Physics female
    8003,  # Fire male
    8004,  # Fire female
    8005,  # Imaginary male
    8006,  # Imaginary female
    8007,  # Ice male
    8008,  # Ice female
    1001,  # March 7th ice
    1224,  # March 7th imaginary
}


def contains_traveler_id(character_id: str) -> bool:
    return any(str(traveler_id) in character_id for traveler_id in TRAVELER_IDS)


SERVER_RESET_HOURS: dict[str, int] = {
    "os_usa": 17,
    "os_euro": 11,
    "prod_official_usa": 17,
    "prod_official_eur": 11,
    "prod_gf_us": 17,
    "prod_gf_eu": 11,
    # Every other server is 4
}
UID_TZ_OFFSET: dict[str, int] = {
    "6": -13,  # America, UTC-5
    "7": -7,  # Europe, UTC+1
    # Every other server is UTC+8
}
GI_UID_PREFIXES: tuple[str, ...] = (
    "1",  # Celestia
    "2",  # Celestia
    "3",  # Celestia
    "5",  # Irminsul
    "6",  # America
    "7",  # Europe
    "8",  # Asia
    "18",  # Asia
    "9",  # TW, HK, MO
)

WEEKDAYS: dict[int, str] = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}

EQUIP_ID_TO_ARTIFACT_POS: dict[str, str] = {
    "EQUIP_BRACER": "flower",
    "EQUIP_NECKLACE": "plume",
    "EQUIP_SHOES": "sands",
    "EQUIP_RING": "goblet",
    "EQUIP_DRESS": "circlet",
}

LOCALE_TO_AKASHA_LANG = {
    Locale.american_english: akasha.Language.ENGLISH,
    Locale.taiwan_chinese: akasha.Language.CHINESE_TRADITIONAL,
    Locale.chinese: akasha.Language.CHINESE_SIMPLIFIED,
    Locale.german: akasha.Language.GERMAN,
    Locale.spain_spanish: akasha.Language.SPANISH,
    Locale.french: akasha.Language.FRENCH,
    Locale.italian: akasha.Language.ITALIAN,
    Locale.japanese: akasha.Language.JAPANESE,
    Locale.korean: akasha.Language.KOREAN,
    Locale.brazil_portuguese: akasha.Language.PORTUGUESE,
    Locale.russian: akasha.Language.RUSSIAN,
    Locale.thai: akasha.Language.THAI,
    Locale.vietnamese: akasha.Language.VIETNAMESE,
    Locale.turkish: akasha.Language.TURKISH,
    Locale.ukrainian: akasha.Language.RUSSIAN,
}
AKASHA_LANG_TO_LOCALE = {v: k for k, v in LOCALE_TO_AKASHA_LANG.items()}


def locale_to_akasha_lang(locale: Locale) -> akasha.Language:
    return LOCALE_TO_AKASHA_LANG.get(locale, akasha.Language.ENGLISH)


LOCALE_TO_HSR_ENKA_LANG: dict[Locale, enka.hsr.Language] = {
    Locale.taiwan_chinese: enka.hsr.Language.TRADITIONAL_CHINESE,
    Locale.chinese: enka.hsr.Language.SIMPLIFIED_CHINESE,
    Locale.german: enka.hsr.Language.GERMAN,
    Locale.american_english: enka.hsr.Language.ENGLISH,
    Locale.spain_spanish: enka.hsr.Language.ESPANOL,
    Locale.french: enka.hsr.Language.FRENCH,
    Locale.indonesian: enka.hsr.Language.INDOENSIAN,
    Locale.japanese: enka.hsr.Language.JAPANESE,
    Locale.korean: enka.hsr.Language.KOREAN,
    Locale.brazil_portuguese: enka.hsr.Language.PORTUGUESE,
    Locale.russian: enka.hsr.Language.RUSSIAN,
    Locale.thai: enka.hsr.Language.THAI,
    Locale.vietnamese: enka.hsr.Language.VIETNAMESE,
}

LOCALE_TO_HSR_CARD_API_LANG: dict[Locale, str] = {
    Locale.taiwan_chinese: "cht",
    Locale.chinese: "cn",
    Locale.german: "de",
    Locale.spain_spanish: "es",
    Locale.french: "fr",
    Locale.indonesian: "id",
    Locale.japanese: "jp",
    Locale.korean: "kr",
    Locale.brazil_portuguese: "pt",
    Locale.russian: "ru",
    Locale.thai: "th",
    Locale.vietnamese: "vi",
    Locale.ukrainian: "ru",
}

LOCALE_TO_GPY_LANG = {
    Locale.american_english: "en-us",
    Locale.taiwan_chinese: "zh-tw",
    Locale.chinese: "zh-cn",
    Locale.german: "de-de",
    Locale.spain_spanish: "es-es",
    Locale.french: "fr-fr",
    Locale.indonesian: "id-id",
    Locale.italian: "it-it",
    Locale.japanese: "ja-jp",
    Locale.korean: "ko-kr",
    Locale.brazil_portuguese: "pt-pt",
    Locale.thai: "th-th",
    Locale.vietnamese: "vi-vn",
    Locale.turkish: "tr-tr",
    Locale.russian: "ru-ru",
    Locale.ukrainian: "ru-ru",
}
GPY_LANG_TO_LOCALE = {v: k for k, v in LOCALE_TO_GPY_LANG.items()}


def locale_to_gpy_lang(locale: Locale) -> str:
    return LOCALE_TO_GPY_LANG.get(locale, "en-us")


HOYO_BUDDY_LOCALES: dict[Locale, dict[str, str]] = {
    Locale.american_english: {"name": "English", "emoji": "🇺🇸"},
    Locale.chinese: {"name": "简体中文", "emoji": "🇨🇳"},
    Locale.taiwan_chinese: {"name": "繁體中文", "emoji": "🇹🇼"},
    Locale.french: {"name": "Français", "emoji": "🇫🇷"},
    Locale.japanese: {"name": "日本語", "emoji": "🇯🇵"},
    Locale.brazil_portuguese: {"name": "Português", "emoji": "🇧🇷"},
    Locale.indonesian: {"name": "Bahasa Indonesia", "emoji": "🇮🇩"},
    Locale.dutch: {"name": "Nederlands", "emoji": "🇳🇱"},
    Locale.vietnamese: {"name": "Tiếng Việt", "emoji": "🇻🇳"},
    Locale.thai: {"name": "ภาษาไทย", "emoji": "🇹🇭"},
    Locale.spain_spanish: {"name": "Español", "emoji": "🇪🇸"},
    Locale.korean: {"name": "한국어", "emoji": "🇰🇷"},
    Locale.turkish: {"name": "Türkçe", "emoji": "🇹🇷"},
    Locale.italian: {"name": "Italiano", "emoji": "🇮🇹"},
    Locale.russian: {"name": "Русский", "emoji": "🇷🇺"},
    Locale.arabic: {"name": "العربية", "emoji": "🇸🇦"},
}

LOCALE_TO_AMBR_LANG: dict[Locale, ambr.Language] = {
    Locale.taiwan_chinese: ambr.Language.CHT,
    Locale.chinese: ambr.Language.CHS,
    Locale.german: ambr.Language.DE,
    Locale.american_english: ambr.Language.EN,
    Locale.spain_spanish: ambr.Language.ES,
    Locale.french: ambr.Language.FR,
    Locale.indonesian: ambr.Language.ID,
    Locale.japanese: ambr.Language.JP,
    Locale.korean: ambr.Language.KR,
    Locale.brazil_portuguese: ambr.Language.PT,
    Locale.russian: ambr.Language.RU,
    Locale.ukrainian: ambr.Language.RU,
    Locale.thai: ambr.Language.TH,
    Locale.vietnamese: ambr.Language.VI,
    Locale.italian: ambr.Language.IT,
    Locale.turkish: ambr.Language.TR,
}


def locale_to_ambr_lang(locale: Locale) -> ambr.Language:
    return LOCALE_TO_AMBR_LANG.get(locale, ambr.Language.EN)


LOCALE_TO_YATTA_LANG: dict[Locale, yatta.Language] = {
    Locale.taiwan_chinese: yatta.Language.CHT,
    Locale.chinese: yatta.Language.CN,
    Locale.german: yatta.Language.DE,
    Locale.american_english: yatta.Language.EN,
    Locale.spain_spanish: yatta.Language.ES,
    Locale.french: yatta.Language.FR,
    Locale.indonesian: yatta.Language.ID,
    Locale.japanese: yatta.Language.JP,
    Locale.korean: yatta.Language.KR,
    Locale.brazil_portuguese: yatta.Language.PT,
    Locale.russian: yatta.Language.RU,
    Locale.ukrainian: yatta.Language.RU,
    Locale.thai: yatta.Language.TH,
    Locale.vietnamese: yatta.Language.VI,
}

LOCALE_TO_HAKUSHIN_LANG: dict[Locale, hakushin.Language] = {
    Locale.chinese: hakushin.Language.ZH,
    Locale.taiwan_chinese: hakushin.Language.ZH,
    Locale.japanese: hakushin.Language.JA,
    Locale.korean: hakushin.Language.KO,
    Locale.american_english: hakushin.Language.EN,
}


LOCALE_TO_GI_ENKA_LANG: dict[Locale, enka.gi.Language] = {
    Locale.taiwan_chinese: enka.gi.Language.TRADITIONAL_CHINESE,
    Locale.chinese: enka.gi.Language.SIMPLIFIED_CHINESE,
    Locale.german: enka.gi.Language.GERMAN,
    Locale.american_english: enka.gi.Language.ENGLISH,
    Locale.spain_spanish: enka.gi.Language.SPANISH,
    Locale.french: enka.gi.Language.FRENCH,
    Locale.indonesian: enka.gi.Language.INDONESIAN,
    Locale.japanese: enka.gi.Language.JAPANESE,
    Locale.korean: enka.gi.Language.KOREAN,
    Locale.brazil_portuguese: enka.gi.Language.PORTUGUESE,
    Locale.russian: enka.gi.Language.RUSSIAN,
    Locale.ukrainian: enka.gi.Language.RUSSIAN,
    Locale.thai: enka.gi.Language.THAI,
    Locale.vietnamese: enka.gi.Language.VIETNAMESE,
    Locale.italian: enka.gi.Language.ITALIAN,
    Locale.turkish: enka.gi.Language.TURKISH,
}

LOCALE_TO_GI_CARD_API_LANG: dict[Locale, str] = {
    Locale.taiwan_chinese: "cht",
    Locale.chinese: "chs",
    Locale.german: "de",
    Locale.american_english: "en",
    Locale.spain_spanish: "es",
    Locale.french: "fr",
    Locale.indonesian: "id",
    Locale.japanese: "jp",
    Locale.korean: "kr",
    Locale.brazil_portuguese: "pt",
    Locale.russian: "ru",
    Locale.thai: "th",
    Locale.vietnamese: "vi",
    Locale.italian: "it",
    Locale.turkish: "tr",
}

HSR_ELEMENT_DMG_PROPS = {
    12,  # Physical
    22,  # Quantum
    16,  # Ice
    18,  # Electro
    20,  # Wind
    24,  # Imaginary
    14,  # Fire
}

YATTA_PATH_TO_HSR_PATH = {
    yatta.PathType.KNIGHT: HSRPath.PRESERVATION,
    yatta.PathType.MAGE: HSRPath.ERUDITION,
    yatta.PathType.PRIEST: HSRPath.ABUNDANCE,
    yatta.PathType.ROGUE: HSRPath.THE_HUNT,
    yatta.PathType.SHAMAN: HSRPath.HARMONY,
    yatta.PathType.WARLOCK: HSRPath.NIHILITY,
    yatta.PathType.WARRIOR: HSRPath.DESTRUCTION,
    yatta.PathType.MEMORY: HSRPath.REMEMBRANCE,
}

YATTA_PATH_TO_GPY_PATH = {
    yatta.PathType.KNIGHT: genshin.models.StarRailPath.PRESERVATION,
    yatta.PathType.MAGE: genshin.models.StarRailPath.ERUDITION,
    yatta.PathType.PRIEST: genshin.models.StarRailPath.ABUNDANCE,
    yatta.PathType.ROGUE: genshin.models.StarRailPath.THE_HUNT,
    yatta.PathType.SHAMAN: genshin.models.StarRailPath.HARMONY,
    yatta.PathType.WARLOCK: genshin.models.StarRailPath.NIHILITY,
    yatta.PathType.WARRIOR: genshin.models.StarRailPath.DESTRUCTION,
    yatta.PathType.MEMORY: genshin.models.StarRailPath.REMEMBRANCE,
}

GPY_PATH_TO_EKNA_PATH = {
    genshin.models.StarRailPath.PRESERVATION: enka.hsr.Path.PRESERVATION,
    genshin.models.StarRailPath.ERUDITION: enka.hsr.Path.ERUDITION,
    genshin.models.StarRailPath.ABUNDANCE: enka.hsr.Path.ABUNDANCE,
    genshin.models.StarRailPath.THE_HUNT: enka.hsr.Path.THE_HUNT,
    genshin.models.StarRailPath.HARMONY: enka.hsr.Path.HARMONY,
    genshin.models.StarRailPath.NIHILITY: enka.hsr.Path.NIHILITY,
    genshin.models.StarRailPath.DESTRUCTION: enka.hsr.Path.DESTRUCTION,
    genshin.models.StarRailPath.REMEMBRANCE: enka.hsr.Path.REMEMBRANCE,
}

YATTA_COMBAT_TYPE_TO_ELEMENT = {
    yatta.CombatType.ICE: HSRElement.ICE,
    yatta.CombatType.FIRE: HSRElement.FIRE,
    yatta.CombatType.IMAGINARY: HSRElement.IMAGINARY,
    yatta.CombatType.PHYSICAL: HSRElement.PHYSICAL,
    yatta.CombatType.QUANTUM: HSRElement.QUANTUM,
    yatta.CombatType.WIND: HSRElement.WIND,
    yatta.CombatType.THUNDER: HSRElement.THUNDER,
}

HAKUSHIN_GI_ELEMENT_TO_ELEMENT = {
    hakushin.enums.GIElement.ANEMO: GenshinElement.ANEMO,
    hakushin.enums.GIElement.GEO: GenshinElement.GEO,
    hakushin.enums.GIElement.ELECTRO: GenshinElement.ELECTRO,
    hakushin.enums.GIElement.DENDRO: GenshinElement.DENDRO,
    hakushin.enums.GIElement.PYRO: GenshinElement.PYRO,
    hakushin.enums.GIElement.CRYO: GenshinElement.CRYO,
    hakushin.enums.GIElement.HYDRO: GenshinElement.HYDRO,
}

HAKUSHIN_HSR_ELEMENT_TO_ELEMENT = {
    hakushin.enums.HSRElement.WIND: HSRElement.WIND,
    hakushin.enums.HSRElement.FIRE: HSRElement.FIRE,
    hakushin.enums.HSRElement.ICE: HSRElement.ICE,
    hakushin.enums.HSRElement.THUNDER: HSRElement.THUNDER,
    hakushin.enums.HSRElement.PHYSICAL: HSRElement.PHYSICAL,
    hakushin.enums.HSRElement.QUANTUM: HSRElement.QUANTUM,
    hakushin.enums.HSRElement.IMAGINARY: HSRElement.IMAGINARY,
}

ENKA_GI_ELEMENT_TO_ELEMENT = {
    enka.gi.Element.ANEMO: GenshinElement.ANEMO,
    enka.gi.Element.GEO: GenshinElement.GEO,
    enka.gi.Element.ELECTRO: GenshinElement.ELECTRO,
    enka.gi.Element.DENDRO: GenshinElement.DENDRO,
    enka.gi.Element.PYRO: GenshinElement.PYRO,
    enka.gi.Element.CRYO: GenshinElement.CRYO,
    enka.gi.Element.HYDRO: GenshinElement.HYDRO,
    enka.gi.Element.NONE: GenshinElement.NONE,
}
ELEMENT_TO_ENKA_GI_ELEMENT = {v: k for k, v in ENKA_GI_ELEMENT_TO_ELEMENT.items()}


def convert_gi_element_to_enka(element: GenshinElement) -> enka.gi.Element:
    return ELEMENT_TO_ENKA_GI_ELEMENT[element]


AMBR_ELEMENT_TO_ELEMENT = {
    ambr.Element.ANEMO: GenshinElement.ANEMO,
    ambr.Element.GEO: GenshinElement.GEO,
    ambr.Element.ELECTRO: GenshinElement.ELECTRO,
    ambr.Element.DENDRO: GenshinElement.DENDRO,
    ambr.Element.PYRO: GenshinElement.PYRO,
    ambr.Element.CRYO: GenshinElement.CRYO,
    ambr.Element.HYDRO: GenshinElement.HYDRO,
}
AMBR_CITY_TO_CITY = {
    ambr.City.MONDSTADT: GenshinCity.MONDSTADT,
    ambr.City.LIYUE: GenshinCity.LIYUE,
    ambr.City.INAZUMA: GenshinCity.INAZUMA,
    ambr.City.SUMERU: GenshinCity.SUMERU,
    ambr.City.FONTAINE: GenshinCity.FONTAINE,
    ambr.City.NATLAN: GenshinCity.NATLAN,
    ambr.City.NOD_KRAI: GenshinCity.NOD_KRAI,
}
AMBR_WEAPON_TYPES = {
    "WEAPON_SWORD_ONE_HAND": 1,
    "WEAPON_CATALYST": 10,
    "WEAPON_CLAYMORE": 11,
    "WEAPON_BOW": 12,
    "WEAPON_POLE": 13,
}

FIGHT_PROP_CONVERTER: Final[dict[int, enka.gi.FightPropType]] = {
    # Base properties
    2000: enka.gi.FightPropType.FIGHT_PROP_MAX_HP,
    2001: enka.gi.FightPropType.FIGHT_PROP_CUR_ATTACK,
    2002: enka.gi.FightPropType.FIGHT_PROP_CUR_DEFENSE,
    28: enka.gi.FightPropType.FIGHT_PROP_ELEMENT_MASTERY,
    # Extra properties
    20: enka.gi.FightPropType.FIGHT_PROP_CRITICAL,
    22: enka.gi.FightPropType.FIGHT_PROP_CRITICAL_HURT,
    26: enka.gi.FightPropType.FIGHT_PROP_HEAL_ADD,
    27: enka.gi.FightPropType.FIGHT_PROP_HEALED_ADD,
    23: enka.gi.FightPropType.FIGHT_PROP_CHARGE_EFFICIENCY,
    # Element properties
    40: enka.gi.FightPropType.FIGHT_PROP_FIRE_ADD_HURT,
    42: enka.gi.FightPropType.FIGHT_PROP_WATER_ADD_HURT,
    43: enka.gi.FightPropType.FIGHT_PROP_GRASS_ADD_HURT,
    41: enka.gi.FightPropType.FIGHT_PROP_ELEC_ADD_HURT,
    44: enka.gi.FightPropType.FIGHT_PROP_WIND_ADD_HURT,
    46: enka.gi.FightPropType.FIGHT_PROP_ICE_ADD_HURT,
    45: enka.gi.FightPropType.FIGHT_PROP_ROCK_ADD_HURT,
    30: enka.gi.FightPropType.FIGHT_PROP_PHYSICAL_ADD_HURT,
    # Artifact properties
    2: enka.gi.FightPropType.FIGHT_PROP_HP,
    3: enka.gi.FightPropType.FIGHT_PROP_HP_PERCENT,
    4: enka.gi.FightPropType.FIGHT_PROP_BASE_ATTACK,
    5: enka.gi.FightPropType.FIGHT_PROP_ATTACK,
    6: enka.gi.FightPropType.FIGHT_PROP_ATTACK_PERCENT,
    8: enka.gi.FightPropType.FIGHT_PROP_DEFENSE,
    9: enka.gi.FightPropType.FIGHT_PROP_DEFENSE_PERCENT,
}
"""Mapping of hoyolab API property types to enka property types."""


def convert_fight_prop(prop_id: int) -> enka.gi.FightPropType:
    """Convert a hoyolab API property type to an enka property type.

    This function may return the input if the property type is not recognized, but we dont type hint it to do so.
    This is to prevent crashes in case of an unknown property type.
    """
    return FIGHT_PROP_CONVERTER.get(prop_id, prop_id)  # pyright: ignore[reportReturnType]


DMG_BONUS_IDS: Final[set[int]] = {40, 42, 43, 41, 44, 46, 45, 30}
"""IDs of damage bonus properties."""

ELEMENT_TO_BONUS_PROP_ID: Final[dict[GenshinElement, int]] = {
    GenshinElement.PYRO: 40,
    GenshinElement.HYDRO: 42,
    GenshinElement.DENDRO: 43,
    GenshinElement.ELECTRO: 41,
    GenshinElement.ANEMO: 44,
    GenshinElement.CRYO: 46,
    GenshinElement.GEO: 45,
}

HB_GAME_TO_GPY_GAME: dict[Game, genshin.Game] = {
    Game.GENSHIN: genshin.Game.GENSHIN,
    Game.STARRAIL: genshin.Game.STARRAIL,
    Game.HONKAI: genshin.Game.HONKAI,
    Game.ZZZ: genshin.Game.ZZZ,
    Game.TOT: genshin.Game.TOT,
}
"""Hoyo Buddy game enum to genshin.py game enum."""

GPY_GAME_TO_HB_GAME = {v: k for k, v in HB_GAME_TO_GPY_GAME.items()}
"""Genshin.py game enum to Hoyo Buddy game enum."""

GEETEST_SERVERS = {
    "prod": "http://geetest-server-test.seria.moe",
    "test": "http://geetest-server-test.seria.moe",
    "dev": "http://localhost:5000",
}

WEB_APP_URLS = {
    "prod": "https://hb-app.seria.moe",
    "test": "https://hb-app.seria.moe",
    "dev": "http://localhost:8645",
}

UTC_8 = datetime.timezone(datetime.timedelta(hours=8))

HAKUSHIN_HSR_SKILL_TYPE_NAMES = {
    "Normal": "hsr.normal_attack",
    "BPSkill": "hsr.skill",
    "Ultra": "hsr.ultimate",
    "Maze": "hsr.technique",
    "MazeNormal": "hsr.technique",
    "Talent": "hsr.talent",
}
GI_SKILL_TYPE_KEYS = {
    1: "gi.skill",
    2: "gi.burst",
    3: "gi.passive",
    4: "gi.passive",
    5: "gi.passive",
}

GAME_CHALLENGE_TYPES: Final[dict[Game, tuple[ChallengeType, ...]]] = {
    Game.GENSHIN: (
        ChallengeType.SPIRAL_ABYSS,
        ChallengeType.IMG_THEATER,
        ChallengeType.HARD_CHALLENGE,
    ),
    Game.STARRAIL: (
        ChallengeType.MOC,
        ChallengeType.PURE_FICTION,
        ChallengeType.APC_SHADOW,
        ChallengeType.ANOMALY,
    ),
    Game.ZZZ: (ChallengeType.SHIYU_DEFENSE, ChallengeType.ASSAULT),
}
CHALLENGE_TYPE_GAMES = {
    type_: game for game, types in GAME_CHALLENGE_TYPES.items() for type_ in types
}

ZENLESS_DATA_URL = "https://git.mero.moe/dimbreath/ZenlessData/raw/branch/master"
ZENLESS_DATA_LANGS = ("CHT", "DE", "EN", "ES", "FR", "ID", "JA", "KO", "PT", "RU", "TH", "VI")
ZZZ_ITEM_TEMPLATE_URL = f"{ZENLESS_DATA_URL}//FileCfg/ItemTemplateTb.json"
ZZZ_AVATAR_TEMPLATE_URL = f"{ZENLESS_DATA_URL}/FileCfg/AvatarBaseTemplateTb.json"
ZZZ_TEXT_MAP_URL = f"{ZENLESS_DATA_URL}/TextMap/TextMap_{{lang}}TemplateTb.json"
ZZZ_AVATAR_BATTLE_TEMP_URL = f"{ZENLESS_DATA_URL}/FileCfg/AvatarBattleTemplateTb.json"
ZZZ_AVATAR_BATTLE_TEMP_JSON = "zzz_avatar_battle_temp.json"

ZZZ_AGENT_CORE_LEVEL_MAP = {1: "0", 2: "A", 3: "B", 4: "C", 5: "D", 6: "E", 7: "F"}

ZZZ_RARITY_NUM_TO_RARITY: dict[int, Literal["B", "A", "S"]] = {4: "S", 3: "A", 2: "B"}

LOCALE_TO_ZENLESS_DATA_LANG: dict[Locale, str] = {
    Locale.taiwan_chinese: "CHT",
    Locale.german: "DE",
    Locale.american_english: "EN",
    Locale.spain_spanish: "ES",
    Locale.french: "FR",
    Locale.indonesian: "ID",
    Locale.japanese: "JA",
    Locale.korean: "KO",
    Locale.brazil_portuguese: "PT",
    Locale.russian: "RU",
    Locale.thai: "TH",
    Locale.vietnamese: "VI",
}
ZENLESS_DATA_LANG_TO_LOCALE = {v: k for k, v in LOCALE_TO_ZENLESS_DATA_LANG.items()}


def locale_to_zenless_data_lang(locale: Locale) -> str:
    return LOCALE_TO_ZENLESS_DATA_LANG.get(locale, "EN")


STARRAIL_DATA_URL = "https://gitlab.com/Dimbreath/turnbasedgamedata/-/raw/main"
HSR_AVATAR_CONFIG_URL = f"{STARRAIL_DATA_URL}/ExcelOutput/AvatarConfig.json"
HSR_AVATAR_CONFIG_LD_URL = f"{STARRAIL_DATA_URL}/ExcelOutput/AvatarConfigLD.json"
HSR_EQUIPMENT_CONFIG_URL = f"{STARRAIL_DATA_URL}/ExcelOutput/EquipmentConfig.json"
HSR_TEXT_MAP_URL = f"{STARRAIL_DATA_URL}/TextMap/TextMap{{lang}}.json"

STARRAIL_DATA_LANGS = (
    "CHS",
    "CHT",
    "DE",
    "EN",
    "ES",
    "FR",
    "ID",
    "JP",
    "KR",
    "PT",
    "RU",
    "TH",
    "VI",
)

LOCALE_TO_STARRAIL_DATA_LANG: dict[Locale, str] = {
    Locale.chinese: "CHS",
    Locale.taiwan_chinese: "CHT",
    Locale.german: "DE",
    Locale.american_english: "EN",
    Locale.spain_spanish: "ES",
    Locale.french: "FR",
    Locale.indonesian: "ID",
    Locale.japanese: "JP",
    Locale.korean: "KR",
    Locale.brazil_portuguese: "PT",
    Locale.russian: "RU",
    Locale.thai: "TH",
    Locale.vietnamese: "VI",
}

ZZZ_ENKA_STAT_TO_GPY_ZZZ_PROPERTY = {
    enka.zzz.StatType.CRIT_RATE_FLAT: genshin.models.ZZZPropertyType.CRIT_RATE,
    enka.zzz.StatType.CRIT_DMG_FLAT: genshin.models.ZZZPropertyType.CRIT_DMG,
    enka.zzz.StatType.ANOMALY_PRO_FLAT: genshin.models.ZZZPropertyType.ANOMALY_PROFICIENCY,
    enka.zzz.StatType.ANOMALY_MASTERY_PERCENT: genshin.models.ZZZPropertyType.ANOMALY_MASTERY,
    enka.zzz.StatType.ENERGY_REGEN_PERCENT: genshin.models.ZZZPropertyType.ENERGY_REGEN,
    enka.zzz.StatType.IMPACT_PERCENT: genshin.models.ZZZPropertyType.IMPACT,
    enka.zzz.StatType.ATK_BASE: genshin.models.ZZZPropertyType.BASE_ATK,
    enka.zzz.StatType.HP_FLAT: genshin.models.ZZZPropertyType.FLAT_HP,
    enka.zzz.StatType.ATK_FLAT: genshin.models.ZZZPropertyType.FLAT_ATK,
    enka.zzz.StatType.DEF_FLAT: genshin.models.ZZZPropertyType.FLAT_DEF,
    enka.zzz.StatType.PEN_FLAT: genshin.models.ZZZPropertyType.FLAT_PEN,
    enka.zzz.StatType.HP_PERCENT: genshin.models.ZZZPropertyType.HP_PERCENT,
    enka.zzz.StatType.ATK_PERCENT: genshin.models.ZZZPropertyType.ATK_PERCENT,
    enka.zzz.StatType.DEF_PERCENT: genshin.models.ZZZPropertyType.DEF_PERCENT,
    enka.zzz.StatType.PEN_RATIO_FLAT: genshin.models.ZZZPropertyType.PEN_PERCENT,
    enka.zzz.StatType.PHYSICAL_DMG_BONUS_FLAT: genshin.models.ZZZPropertyType.DISC_PHYSICAL_DMG_BONUS,
    enka.zzz.StatType.FIRE_DMG_BONUS_FLAT: genshin.models.ZZZPropertyType.DISC_FIRE_DMG_BONUS,
    enka.zzz.StatType.ICE_DMG_BONUS_FLAT: genshin.models.ZZZPropertyType.DISC_ICE_DMG_BONUS,
    enka.zzz.StatType.ELECTRIC_DMG_BONUS_FLAT: genshin.models.ZZZPropertyType.DISC_ELECTRIC_DMG_BONUS,
    enka.zzz.StatType.ETHER_DMG_BONUS_FLAT: genshin.models.ZZZPropertyType.DISC_ETHER_DMG_BONUS,
}

ZZZ_ENKA_SKILLTYPE_TO_GPY_SKILLTYPE = {
    enka.zzz.SkillType.BASIC_ATK: genshin.models.ZZZSkillType.BASIC_ATTACK,
    enka.zzz.SkillType.DASH: genshin.models.ZZZSkillType.DODGE,
    enka.zzz.SkillType.ASSIST: genshin.models.ZZZSkillType.ASSIST,
    enka.zzz.SkillType.SPECIAL_ATK: genshin.models.ZZZSkillType.SPECIAL_ATTACK,
    enka.zzz.SkillType.ULTIMATE: genshin.models.ZZZSkillType.CHAIN_ATTACK,
    enka.zzz.SkillType.CORE_SKILL: genshin.models.ZZZSkillType.CORE_SKILL,
}

ZZZ_ENKA_ELEMENT_TO_ZZZELEMENTTYPE = {
    enka.zzz.Element.PHYSICAL: genshin.models.ZZZElementType.PHYSICAL,
    enka.zzz.Element.FIRE: genshin.models.ZZZElementType.FIRE,
    enka.zzz.Element.ICE: genshin.models.ZZZElementType.ICE,
    enka.zzz.Element.ELECTRIC: genshin.models.ZZZElementType.ELECTRIC,
    enka.zzz.Element.ETHER: genshin.models.ZZZElementType.ETHER,
    enka.zzz.Element.FIRE_FROST: genshin.models.ZZZElementType.ICE,  # Miyabi element
    enka.zzz.Element.AURIC_ETHER: genshin.models.ZZZElementType.ETHER,  # Yi Xuan element
}

ZZZ_ENKA_AGENT_STAT_TYPE_TO_ZZZ_AGENT_PROPERTY = {
    enka.zzz.AgentStatType.MAX_HP: genshin.models.ZZZPropertyType.AGENT_HP,
    enka.zzz.AgentStatType.ATK: genshin.models.ZZZPropertyType.AGENT_ATK,
    enka.zzz.AgentStatType.DEF: genshin.models.ZZZPropertyType.AGENT_DEF,
    enka.zzz.AgentStatType.IMPACT: genshin.models.ZZZPropertyType.AGENT_IMPACT,
    enka.zzz.AgentStatType.CRIT_RATE: genshin.models.ZZZPropertyType.AGENT_CRIT_RATE,
    enka.zzz.AgentStatType.CRIT_DMG: genshin.models.ZZZPropertyType.AGENT_CRIT_DMG,
    enka.zzz.AgentStatType.ANOMALY_PROFICIENCY: genshin.models.ZZZPropertyType.AGENT_ANOMALY_PROFICIENCY,
    enka.zzz.AgentStatType.ANOMALY_MASTERY: genshin.models.ZZZPropertyType.AGENT_ANOMALY_MASTERY,
    enka.zzz.AgentStatType.PEN_RATIO: genshin.models.ZZZPropertyType.AGENT_PEN_RATIO,
    enka.zzz.AgentStatType.PEN: genshin.models.ZZZPropertyType.AGENT_PEN,
    enka.zzz.AgentStatType.ENERGY_REGEN: genshin.models.ZZZPropertyType.AGENT_ENERGY_GEN,
    enka.zzz.AgentStatType.SHEER_FORCE: genshin.models.ZZZPropertyType.AGENT_SHEER_FORCE,
    enka.zzz.AgentStatType.AAA: genshin.models.ZZZPropertyType.AGENT_ADRENALINE,
    enka.zzz.AgentStatType.PHYSICAL_DMG_BONUS: genshin.models.ZZZPropertyType.PHYSICAL_DMG_BONUS,
    enka.zzz.AgentStatType.FIRE_DMG_BONUS: genshin.models.ZZZPropertyType.FIRE_DMG_BONUS,
    enka.zzz.AgentStatType.ICE_DMG_BONUS: genshin.models.ZZZPropertyType.ICE_DMG_BONUS,
    enka.zzz.AgentStatType.ELECTRIC_DMG_BONUS: genshin.models.ZZZPropertyType.ELECTRIC_DMG_BONUS,
    enka.zzz.AgentStatType.ETHER_DMG_BONUS: genshin.models.ZZZPropertyType.ETHER_DMG_BONUS,
    enka.zzz.AgentStatType.SHEER_DMG_BONUS: genshin.models.ZZZPropertyType.ETHER_DMG_BONUS,  # for yi xuan?
}

ZZZ_ENKA_SPECIALTY_TO_GPY_SPECIALTY: Final[
    dict[enka.zzz.ProfessionType, genshin.models.ZZZSpecialty | None]
] = {
    enka.zzz.ProfessionType.ANOMALY: genshin.models.ZZZSpecialty.ANOMALY,
    enka.zzz.ProfessionType.ATTACK: genshin.models.ZZZSpecialty.ATTACK,
    enka.zzz.ProfessionType.DEFENSE: genshin.models.ZZZSpecialty.DEFENSE,
    enka.zzz.ProfessionType.SUPPORT: genshin.models.ZZZSpecialty.SUPPORT,
    enka.zzz.ProfessionType.STUN: genshin.models.ZZZSpecialty.STUN,
    enka.zzz.ProfessionType.RUPTURE: genshin.models.ZZZSpecialty.RUPTURE,
    enka.zzz.ProfessionType.UNKNOWN: None,
}

LOCALE_TO_ZZZ_ENKA_LANG: Final[dict[Locale, enka.zzz.Language]] = {
    Locale.american_english: enka.zzz.Language.ENGLISH,
    Locale.japanese: enka.zzz.Language.JAPANESE,
    Locale.korean: enka.zzz.Language.KOREAN,
    Locale.chinese: enka.zzz.Language.SIMPLIFIED_CHINESE,
    Locale.taiwan_chinese: enka.zzz.Language.TRADITIONAL_CHINESE,
    Locale.russian: enka.zzz.Language.RUSSIAN,
    Locale.vietnamese: enka.zzz.Language.VIETNAMESE,
    Locale.thai: enka.zzz.Language.THAI,
    Locale.brazil_portuguese: enka.zzz.Language.PORTUGUESE,
    Locale.indonesian: enka.zzz.Language.INDONESIAN,
    Locale.french: enka.zzz.Language.FRENCH,
    Locale.spain_spanish: enka.zzz.Language.ESPANOL,
    Locale.german: enka.zzz.Language.GERMAN,
}


def locale_to_starrail_data_lang(locale: Locale) -> str:
    return LOCALE_TO_STARRAIL_DATA_LANG.get(locale, "EN")


HSR_ASSETS_URL = "https://raw.githubusercontent.com/seriaati/HSRAssets/refs/heads/main"
HSR_DEFAULT_ART_URL = f"{HSR_ASSETS_URL}/avatardrawcardresult/Texture2D/{{char_id}}.png"
HSR_TEAM_ICON_URL = f"{HSR_ASSETS_URL}/avatariconteam/Texture2D/{{char_id}}.png"
ZZZ_M3_ART_URL = "https://api.hakush.in/zzz/UI/Mindscape_{char_id}_2.webp"
ZZZ_M6_ART_URL = "https://api.hakush.in/zzz/UI/Mindscape_{char_id}_3.webp"

UIGF_GAME_KEYS: Final[dict[Game, str]] = {
    Game.GENSHIN: "hk4e",
    Game.STARRAIL: "hkrpg",
    Game.ZZZ: "nap",
}

BANNER_TYPE_NAMES: Final[dict[Game, dict[int, str]]] = {
    Game.GENSHIN: {
        301: "banner_type_character_event",
        302: "banner_type_weapon_event",
        200: "banner_type_standard_banner",
        500: "banner_type_chronicled_wish",
        100: "banner_type_beginners_wish",
    },
    Game.STARRAIL: {
        11: "banner_type_character_warp",
        12: "banner_type_light_cone_warp",
        1: "banner_type_stellar_warp",
        2: "banner_type_departure_warp",
        21: "banner_type_fgo_character",
        22: "banner_type_fgo_light_cone",
    },
    Game.ZZZ: {
        2: "banner_type_exclusive_channel",
        3: "banner_type_w_engine_channel",
        1: "banner_type_standard_channel",
        5: "banner_type_bangboo_channel",
    },
}

BANNER_WIN_RATE_TITLES: Final[dict[Game, dict[int, str]]] = {
    Game.GENSHIN: {301: "50/50", 302: "50/50", 500: "50/50"},
    Game.STARRAIL: {11: "50/50", 12: "75/25", 21: "50/50", 22: "75/25"},
    Game.ZZZ: {2: "50/50", 3: "75/25"},
}

BANNER_GUARANTEE_NUMS: Final[dict[Game, dict[int, int]]] = {
    Game.GENSHIN: {301: 90, 302: 80, 200: 90, 500: 90, 100: 20},
    Game.STARRAIL: {11: 90, 12: 80, 1: 90, 2: 50, 21: 90, 22: 80},
    Game.ZZZ: {2: 90, 3: 80, 1: 90, 5: 80},
}

STANDARD_ITEMS: Final[dict[Game, set[int]]] = {
    Game.GENSHIN: {
        # Characters
        10000079,  # Dehya
        10000016,  # Diluc
        10000003,  # Jean
        10000042,  # Keqing
        10000041,  # Mona
        10000035,  # Qiqi
        10000069,  # Tighnari
        # Weapons
        15502,  # Amo's Bow
        11501,  # Aquila Favonia
        14502,  # Lost Prayer to the Sacred Winds
        13505,  # Primordial Jade Winged-Spear
        14501,  # Skyward Atlas
        11502,  # Skyward Blade
        15501,  # Skyward Harp
        12501,  # Skyward Pride
        13502,  # Skyward Spine
        12502,  # Wolf's Gravestone
    },
    Game.STARRAIL: {
        # Characters
        1211,  # Bailu
        1101,  # Bronya
        1107,  # Clara
        1104,  # Gepard
        1003,  # Himeko
        1004,  # Welt
        1209,  # Yanqing
        1205,  # Blade
        1102,  # Seele
        # Light Cones
        23003,  # But the Battle Isn't Over
        23004,  # In the Name of the World
        23005,  # Moment of Victory
        23000,  # Night on the Milky Way
        23012,  # Sleep Like the Dead
        23002,  # Something Irreplaceable
        23013,  # Time Waits for No One
    },
    Game.ZZZ: {
        # Agents
        1181,  # Grace
        1101,  # Koleda
        1141,  # Lycaon
        1021,  # Nekomata
        1211,  # Rina
        1041,  # Soldier 11
        # W-Engines
        14102,  # Steel Cushion
        14110,  # Hellfire Gears
        14114,  # The Restrained
        14104,  # The Brimstone
        14118,  # Fusion Compiler
        14121,  # Weeping Cradle
    },
}

CHARACTER_MAX_LEVEL: Final[dict[Game, int]] = {
    Game.GENSHIN: 90,
    Game.STARRAIL: 80,
    Game.ZZZ: 60,
    Game.HONKAI: 80,
}


def is_standard_item(game: Game, item_id: int) -> bool:
    if game not in STANDARD_ITEMS:
        msg = f"Game {game} is missing from the standard items list."
        raise ValueError(msg)
    return item_id in STANDARD_ITEMS[game]


def locale_to_hakushin_lang(locale: Locale) -> hakushin.Language:
    return LOCALE_TO_HAKUSHIN_LANG.get(locale, hakushin.Language.EN)


# From https://www.prydwen.gg/zenless/guides/disk-drives-stats/
DISC_SUBSTAT_VALUES: dict[Literal["B", "A", "S"], dict[genshin.models.ZZZPropertyType, float]] = {
    "B": {
        genshin.models.ZZZPropertyType.FLAT_ATK: 7,
        genshin.models.ZZZPropertyType.ATK_PERCENT: 1,
        genshin.models.ZZZPropertyType.FLAT_HP: 39,
        genshin.models.ZZZPropertyType.HP_PERCENT: 1,
        genshin.models.ZZZPropertyType.FLAT_DEF: 5,
        genshin.models.ZZZPropertyType.DEF_PERCENT: 1.6,
        genshin.models.ZZZPropertyType.CRIT_RATE: 0.8,
        genshin.models.ZZZPropertyType.CRIT_DMG: 1.6,
        genshin.models.ZZZPropertyType.FLAT_PEN: 3,
        genshin.models.ZZZPropertyType.ANOMALY_PROFICIENCY: 3,
    },
    "A": {
        genshin.models.ZZZPropertyType.FLAT_ATK: 15,
        genshin.models.ZZZPropertyType.ATK_PERCENT: 2,
        genshin.models.ZZZPropertyType.FLAT_HP: 79,
        genshin.models.ZZZPropertyType.HP_PERCENT: 2,
        genshin.models.ZZZPropertyType.FLAT_DEF: 10,
        genshin.models.ZZZPropertyType.DEF_PERCENT: 3.2,
        genshin.models.ZZZPropertyType.CRIT_RATE: 1.6,
        genshin.models.ZZZPropertyType.CRIT_DMG: 3.2,
        genshin.models.ZZZPropertyType.FLAT_PEN: 6,
        genshin.models.ZZZPropertyType.ANOMALY_PROFICIENCY: 6,
    },
    "S": {
        genshin.models.ZZZPropertyType.FLAT_ATK: 19,
        genshin.models.ZZZPropertyType.ATK_PERCENT: 3,
        genshin.models.ZZZPropertyType.FLAT_HP: 112,
        genshin.models.ZZZPropertyType.HP_PERCENT: 3,
        genshin.models.ZZZPropertyType.FLAT_DEF: 15,
        genshin.models.ZZZPropertyType.DEF_PERCENT: 4.8,
        genshin.models.ZZZPropertyType.CRIT_RATE: 2.4,
        genshin.models.ZZZPropertyType.CRIT_DMG: 4.8,
        genshin.models.ZZZPropertyType.FLAT_PEN: 9,
        genshin.models.ZZZPropertyType.ANOMALY_PROFICIENCY: 9,
    },
}


def get_disc_substat_roll_num(
    disc_rarity: Literal["B", "A", "S"], prop: genshin.models.ZZZProperty | ZZZStat
) -> int:
    if not isinstance(prop.type, genshin.models.ZZZPropertyType):
        return 0

    value = DISC_SUBSTAT_VALUES[disc_rarity][prop.type]
    prop_value = float(prop.value.replace("%", ""))
    return round(prop_value / value)


CODE_CHANNEL_IDS = {
    Game.GENSHIN: 1310017049896026135,
    Game.STARRAIL: 1310017113695457300,
    Game.ZZZ: 1310017277202006067,
}

USER_RENAME = {"user": app_commands.locale_str("user", key="user_autocomplete_param_name")}
USER_DESCRIBE = {
    "user": app_commands.locale_str(
        "User to run this command with, defaults to you", key="user_autocomplete_param_description"
    )
}
ACCOUNT_RENAME = {
    "account": app_commands.locale_str("account", key="account_autocomplete_param_name")
}
ACCOUNT_DESCRIBE = {
    "account": app_commands.locale_str(
        "Account to run this command with, defaults to the selected one in /accounts",
        key="account_autocomplete_param_description",
    )
}
ACCOUNT_NO_DEFAULT_DESCRIBE = {
    "account": app_commands.locale_str(
        "Account to run this command with", key="acc_no_default_param_desc"
    )
}
UID_DESCRIBE = {
    "uid": app_commands.locale_str(
        "UID of the player, this overrides the account parameter if provided",
        key="profile_command_uid_param_description",
    )
}


def get_rename_kwargs(
    *, user: bool = False, account: bool = False
) -> dict[str, app_commands.locale_str]:
    result: dict[str, app_commands.locale_str] = {}
    if user:
        result.update(USER_RENAME)
    if account:
        result.update(ACCOUNT_RENAME)
    return result


def get_describe_kwargs(
    *,
    user: bool = False,
    account: bool = False,
    account_no_default: bool = False,
    uid: bool = False,
) -> dict[str, app_commands.locale_str]:
    if account and account_no_default:
        msg = "account and account_no_default cannot be True at the same time."
        raise ValueError(msg)

    result: dict[str, app_commands.locale_str] = {}
    if user:
        result.update(USER_DESCRIBE)
    if account:
        result.update(ACCOUNT_DESCRIBE)
    if account_no_default:
        result.update(ACCOUNT_NO_DEFAULT_DESCRIBE)
    if uid:
        result.update(UID_DESCRIBE)
    return result


ZZZ_DISC_SUBSTATS = (
    ("Crit", 20103, ""),
    ("CritDmg", 21103, ""),
    ("ElementMystery", 31203, ""),
    ("PenDelta", 23203, ""),
    ("HpMax", 11103, ""),
    ("HpMax", 11102, "%"),
    ("Atk", 12103, ""),
    ("Atk", 12102, "%"),
    ("Def", 13103, ""),
    ("Def", 13102, "%"),
)
# LocaleStr key, substat id, LocaleStr append

ZZZ_AGENT_STAT_TO_DISC_SUBSTAT = {
    1: 11102,  # HP
    2: 12102,  # ATK
    3: 13102,  # DEF
    5: 20103,  # CRIT RATE
    6: 21103,  # CRIT DMG
    8: 31203,  # AP
    9: 23203,  # PEN
}

BLOCK_COLORS: dict[bool, dict[int, str]] = {
    True: {5: "#9E6D35", 4: "#544A81", 3: "#4F6C92", 2: "#4E7669", 1: "#787881"},
    False: {5: "#CC8E4A", 4: "#837BCE", 3: "#6C93B9", 2: "#6DA795", 1: "#9B9B9B"},
}

POST_REPLIES = (
    "very useful!",
    "wow-",
    "cool :D",
    "nice!",
    "nice post!",
    "great post :o",
    "awesome :D",
    "interesting :o",
    "pretty informative!",
)

NO_BETA_CONTENT_GUILDS = {916725085019181056, 888984573403340860, 1084856284198752388}
"""Discord servers that don't allow unreleased game content."""


DOCS_URL = "https://hb-docs.seria.moe{lang}/docs/{page}"
LOCALE_TO_DOCS_LANG = {
    Locale.taiwan_chinese: "/zh-Hant",
    Locale.chinese: "/zh-Hans",
    Locale.vietnamese: "/vi",
    Locale.spain_spanish: "/es",
}
HEADINGS = {
    "how-does-the-email-and-password-login-method-work": {
        Locale.taiwan_chinese: "電子郵件和密碼登錄方式如何運作",
        Locale.chinese: "電子郵件和密碼登錄方式如何運作",
        Locale.vietnamese: "phương-pháp-đăng-nhập-bằng-email-và-mật-khẩu-hoạt-động-như-thế-nào",
    },
    "i-am-a-console-player": {
        Locale.taiwan_chinese: "我是主機玩家",
        Locale.chinese: "我是主機玩家",
        Locale.vietnamese: "tôi-chới-trên-máy-chơi-game-playstation-và-xbox",
    },
    "which-login-method-should-i-use": {
        Locale.taiwan_chinese: "我應該選擇哪種登入方式",
        Locale.chinese: "我應該選擇哪種登入方式",
        Locale.vietnamese: "tôi-nên-sử-dụng-phương-thức-đăng-nhập-nào",
    },
    "too-many-requests-error-when-trying-to-add-accounts-using-email--password-method": {
        Locale.taiwan_chinese: "嘗試使用電子郵件和密碼方法新增帳戶時出現請求過多錯誤",
        Locale.chinese: "嘗試使用電子郵件和密碼方法新增帳戶時出現請求過多錯誤",
        Locale.vietnamese: "lỗi-quá-nhiều-yêu-cầu-khi-cố-gắng-thêm-tài-khoản-bằng-phương-pháp-email-và-mật-khẩu",
    },
}


def get_docs_url(page: str, *, locale: Locale) -> str:
    heading = page.split("#", 1)[1] if "#" in page else ""
    if heading in HEADINGS:
        page = page.replace(heading, HEADINGS[heading].get(locale, heading))
    return DOCS_URL.format(lang=LOCALE_TO_DOCS_LANG.get(locale, ""), page=page)


AMBR_UI_URL = "https://gi.yatta.moe/assets/UI/{filename}.png"
PLAYER_GIRL_GACHA_ART = "https://img.seria.moe/EiTcXToCGWUYtfDe.png"
PLAYER_BOY_GACHA_ART = "https://img.seria.moe/BPFICCXWkbOJrsqe.png"

RELIC_PROP_ID_TO_ENKA_TYPE: dict[int, enka.hsr.StatType] = {
    27: enka.hsr.StatType.HP_DELTA,
    29: enka.hsr.StatType.ATK_DELTA,
    31: enka.hsr.StatType.DEF_DELTA,
    32: enka.hsr.StatType.HP_BOOST,
    33: enka.hsr.StatType.ATK_BOOST,
    34: enka.hsr.StatType.DEF_BOOST,
    51: enka.hsr.StatType.SPEED_DELTA,
    52: enka.hsr.StatType.CRIT_RATE,
    53: enka.hsr.StatType.CRIT_DMG,
    56: enka.hsr.StatType.EFFECT_HIT_RATE,
    57: enka.hsr.StatType.EFFECT_RES,
    59: enka.hsr.StatType.BREAK_EFFECT,
}


def relic_prop_id_to_enka_type(prop_id: int) -> enka.hsr.StatType | None:
    """Connvert relic property id in genshin.py to enka substat type enum."""
    enum = RELIC_PROP_ID_TO_ENKA_TYPE.get(prop_id)
    if enum is None:
        logger.error(f"Cannot convert this prop ID to enka.hsr.StatType: {prop_id!r}")
    return enum


# From https://honkai-star-rail.fandom.com/wiki/Relic/Stats
RELIC_SUBSTAT_VALUES = {
    enka.hsr.StatType.SPEED_DELTA: {
        5: {"high": 2.6, "mid": 2.3, "low": 2.0},
        4: {"high": 2.0, "mid": 1.8, "low": 1.6},
        3: {"high": 1.4, "mid": 1.3, "low": 1.2},
        2: {"high": 1.2, "mid": 1.1, "low": 1.0},
    },
    enka.hsr.StatType.HP_DELTA: {
        5: {"high": 42.33751, "mid": 38.103755, "low": 33.87},
        4: {"high": 33.87, "mid": 30.483, "low": 27.096},
        3: {"high": 25.402506, "mid": 22.862253, "low": 20.322},
        2: {"high": 16.935, "mid": 15.2415, "low": 13.548},
    },
    enka.hsr.StatType.ATK_DELTA: {
        5: {"high": 21.168754, "mid": 19.051877, "low": 16.935},
        4: {"high": 16.935, "mid": 15.2415, "low": 13.548},
        3: {"high": 10.161, "mid": 11.431126, "low": 12.701252},
        2: {"high": 8.4675, "mid": 7.62075, "low": 6.774},
    },
    enka.hsr.StatType.DEF_DELTA: {
        5: {"high": 21.168754, "mid": 19.051877, "low": 16.935},
        4: {"high": 16.935, "mid": 15.2415, "low": 13.548},
        3: {"high": 10.161, "mid": 11.431126, "low": 12.701252},
        2: {"high": 8.4675, "mid": 7.62075, "low": 6.774},
    },
    enka.hsr.StatType.HP_BOOST: {
        5: {"high": 4.32, "mid": 3.888, "low": 3.456},
        4: {"high": 3.456, "mid": 3.1104, "low": 2.7648},
        3: {"high": 2.592, "mid": 2.3328, "low": 2.0736},
        2: {"high": 1.728, "mid": 1.5552, "low": 1.3824},
    },
    enka.hsr.StatType.ATK_BOOST: {
        5: {"high": 4.32, "mid": 3.888, "low": 3.456},
        4: {"high": 3.456, "mid": 3.1104, "low": 2.7648},
        3: {"high": 2.592, "mid": 2.3328, "low": 2.0736},
        2: {"high": 1.728, "mid": 1.5552, "low": 1.3824},
    },
    enka.hsr.StatType.DEF_BOOST: {
        5: {"high": 5.4, "mid": 4.86, "low": 4.32},
        4: {"high": 4.32, "mid": 3.888, "low": 3.456},
        3: {"high": 2.592, "mid": 2.916, "low": 3.24},
        2: {"high": 2.16, "mid": 1.944, "low": 1.728},
    },
    enka.hsr.StatType.BREAK_EFFECT: {
        5: {"high": 6.48, "mid": 5.832, "low": 5.184},
        4: {"high": 5.184, "mid": 4.6656, "low": 4.1472},
        3: {"high": 3.888, "mid": 3.4992, "low": 3.1104},
        2: {"high": 2.592, "mid": 2.3328, "low": 2.0736},
    },
    enka.hsr.StatType.EFFECT_HIT_RATE: {
        5: {"high": 4.32, "mid": 3.888, "low": 3.456},
        4: {"high": 3.456, "mid": 3.1104, "low": 2.7648},
        3: {"high": 2.592, "mid": 2.3328, "low": 2.0736},
        2: {"high": 1.728, "mid": 1.5552, "low": 1.3824},
    },
    enka.hsr.StatType.EFFECT_RES: {
        5: {"high": 4.32, "mid": 3.888, "low": 3.456},
        4: {"high": 3.456, "mid": 3.1104, "low": 2.7648},
        3: {"high": 2.592, "mid": 2.3328, "low": 2.0736},
        2: {"high": 1.728, "mid": 1.5552, "low": 1.3824},
    },
    enka.hsr.StatType.CRIT_RATE: {
        5: {"high": 3.24, "mid": 2.916, "low": 2.592},
        4: {"high": 2.592, "mid": 2.3328, "low": 2.0736},
        3: {"high": 1.5552, "mid": 1.7496, "low": 1.944},
        2: {"high": 1.296, "mid": 1.1664, "low": 1.0368},
    },
    enka.hsr.StatType.CRIT_DMG: {
        5: {"high": 6.48, "mid": 5.832, "low": 5.184},
        4: {"high": 5.184, "mid": 4.6656, "low": 4.1472},
        3: {"high": 3.888, "mid": 3.4992, "low": 3.1104},
        2: {"high": 2.592, "mid": 2.3328, "low": 2.0736},
    },
}


def get_relic_substat_roll_num(
    *, stat_type: int | enka.hsr.StatType, stat_value: float, rarity: int
) -> int:
    if isinstance(stat_type, int):
        stat_type_ = relic_prop_id_to_enka_type(stat_type)
        if stat_type_ is None:
            return 1
        stat_type = stat_type_

    increment_options = RELIC_SUBSTAT_VALUES[stat_type][rarity]
    closest_sum = float("inf")
    closest_counts: dict[str, int] = {}

    # Recursive search function
    def search(sum_: float, counts: dict[str, int], index: int) -> None:
        nonlocal closest_sum, closest_counts

        # If we've iterated through all options
        if index == len(increment_options):
            if abs(sum_ - stat_value) < abs(closest_sum - stat_value):
                closest_sum = sum_
                closest_counts = counts.copy()
            return

        # Get the current increment key
        increment_keys = list(increment_options.keys())
        increment = increment_keys[index]

        # Try all possible counts for the current increment
        i = 0
        while sum_ + i * increment_options[increment] <= stat_value + 0.01:
            counts[increment] = i
            search(sum_ + i * increment_options[increment], counts, index + 1)
            i += 1

    # Initialize search
    search(0, dict.fromkeys(increment_options, 0), 0)

    return max(sum(closest_counts.values()), 1)


DC_MAX_FILESIZE = 10 * 1024 * 1024  # 10 MB

NO_MASKED_LINK_GUILDS = {998109815521947678}
"""Discord servers that have masked links AutoMod rules."""

OPEN_GAME_BASE_URL = URL("https://st-direct.pages.dev/event")
OPEN_GAME_URLS: dict[OpenGameRegion, dict[OpenGameGame, URL]] = {
    "global": {
        "gi": OPEN_GAME_BASE_URL / "genshin",
        "gi_cloud": OPEN_GAME_BASE_URL / "genshin_cloud",
        "hsr": OPEN_GAME_BASE_URL / "hsr",
        "zzz": OPEN_GAME_BASE_URL / "zzz",
    },
    "cn": {
        "gi": OPEN_GAME_BASE_URL / "yuanshen",
        "gi_cloud": OPEN_GAME_BASE_URL / "ys_cg",
        "hsr": OPEN_GAME_BASE_URL / "sr",
        "hsr_cloud": OPEN_GAME_BASE_URL / "sr_cg",
        "zzz": OPEN_GAME_BASE_URL / "nap",
        "zzz_cloud": OPEN_GAME_BASE_URL / "nap_cg",
    },
    "vietnam": {
        "gi": OPEN_GAME_BASE_URL / "ysvn",
        "hsr": OPEN_GAME_BASE_URL / "hsrvn",
        "zzz": OPEN_GAME_BASE_URL / "zzzvn",
    },
}

AVAILABLE_OPEN_GAMES: dict[
    Platform, dict[Game, tuple[tuple[OpenGameLabel, OpenGameRegion, OpenGameGame], ...]]
] = {
    Platform.HOYOLAB: {
        Game.GENSHIN: (
            (OpenGameLabel.DEFAULT, "global", "gi"),
            (OpenGameLabel.CLOUD, "global", "gi_cloud"),
            (OpenGameLabel.VIETNAM, "vietnam", "gi"),
        ),
        Game.STARRAIL: (
            (OpenGameLabel.DEFAULT, "global", "hsr"),
            (OpenGameLabel.VIETNAM, "vietnam", "hsr"),
        ),
        Game.ZZZ: (
            (OpenGameLabel.DEFAULT, "global", "zzz"),
            (OpenGameLabel.VIETNAM, "vietnam", "zzz"),
        ),
    },
    Platform.MIYOUSHE: {
        Game.GENSHIN: (
            (OpenGameLabel.DEFAULT, "cn", "gi"),
            (OpenGameLabel.CLOUD, "cn", "gi_cloud"),
        ),
        Game.STARRAIL: (
            (OpenGameLabel.DEFAULT, "cn", "hsr"),
            (OpenGameLabel.CLOUD, "cn", "hsr_cloud"),
        ),
        Game.ZZZ: ((OpenGameLabel.DEFAULT, "cn", "zzz"), (OpenGameLabel.CLOUD, "cn", "zzz_cloud")),
    },
}


def get_open_game_url(*, region: OpenGameRegion, game: OpenGameGame) -> URL:
    region_urls = OPEN_GAME_URLS.get(region)
    if region_urls is None:
        msg = f"Invalid region: {region!r}"
        raise ValueError(msg)

    url = region_urls.get(game)
    if url is None:
        msg = f"Invalid game {game!r} for region {region!r}"
        raise ValueError(msg)

    return url


AUTO_TASK_INTERVALS: dict[AutoTaskType, int] = {
    "redeem": 3600 * 2,  # 2 hours
    "mimo_task": 3600 * 4,  # 4 hours
    "mimo_buy": 3600 * 5,  # 5 hours
    "mimo_draw": 3600 * 10,  # 10 hours
}
AUTO_TASK_LAST_TIME_FIELDS: dict[AutoTaskType, str] = {
    "redeem": "last_redeem_time",
    "mimo_task": "last_mimo_task_time",
    "mimo_buy": "last_mimo_buy_time",
    "mimo_draw": "last_mimo_draw_time",
    "checkin": "last_checkin_time",
}
AUTO_TASK_TOGGLE_FIELDS: dict[AutoTaskType, str] = {
    "redeem": "auto_redeem",
    "mimo_task": "mimo_auto_task",
    "mimo_buy": "mimo_auto_buy",
    "mimo_draw": "mimo_auto_draw",
    "checkin": "daily_checkin",
}
NOTIF_SETTING_FIELDS: dict[AutoTaskType, tuple[str, str]] = {
    "checkin": ("notify_on_checkin_success", "notify_on_checkin_failure"),
    "mimo_task": ("mimo_task_success", "mimo_task_failure"),
    "mimo_buy": ("mimo_buy_success", "mimo_buy_failure"),
    "mimo_draw": ("mimo_draw_success", "mimo_draw_failure"),
    "redeem": ("redeem_success", "redeem_failure"),
}

PLATFORM_TO_REGION: dict[Platform, genshin.Region] = {
    Platform.HOYOLAB: genshin.Region.OVERSEAS,
    Platform.MIYOUSHE: genshin.Region.CHINESE,
}
REGION_TO_PLATFORM = {v: k for k, v in PLATFORM_TO_REGION.items()}

SLEEP_TIMES: dict[SleepTime, float] = {
    "redeem": 6.0,
    "mimo_task": 5.0,
    "mimo_shop": 0.5,
    "mimo_comment": 2.0,
    "mimo_lottery": 0.5,
    "search_autofill": 0.1,
    "checkin": 2.5,
    "notes_check": 1.2,
    "dm": 0.1,
}

CONCURRENT_TASK_NUM = 250
MAX_PROXY_ERROR_NUM = 8

AUTO_TASK_FEATURE_KEYS: dict[AutoTaskType, str] = {
    "redeem": "auto_redeem_toggle.label",
    "mimo_task": "mimo_auto_finish_and_claim_button_label",
    "mimo_buy": "mimo_auto_buy_button_label",
    "mimo_draw": "mimo_auto_draw_button_label",
    "checkin": "auto_checkin_button_label",
}
AUTO_TASK_COMMANDS: dict[AutoTaskType, str] = {
    "redeem": "</redeem>",
    "mimo_task": "</mimo>",
    "mimo_buy": "</mimo>",
    "mimo_draw": "</mimo>",
    "checkin": "</check-in>",
}

GUILD_ID = 1131592943791263745 if CONFIG.is_dev else 1000727526194298910
SUPPORTER_ROLE_ID = 1376358430947676184 if CONFIG.is_dev else 1117992633827082251

HB_BIRTHDAY = datetime.date(2024, 6, 7)

POOL_MAX_WORKERS = 1 if CONFIG.is_dev else min(32, (os.cpu_count() or 1))

INSTALL_URL = "https://one.hb.seria.moe/install"

YATTA_PROP_TYPE_TO_GPY_TYPE: dict[str, int] = {
    "maxHP": 1,
    "attack": 2,
    "defence": 3,
    "speed": 4,
    "criticalChance": 52,
    "criticalDamage": 53,
    "criticalChanceBase": 5,
    "criticalDamageBase": 6,
    "healRatioBase": 7,
    "sPRatioBase": 9,
    "statusProbabilityBase": 10,
    "statusResistanceBase": 11,
    "breakDamageAddedRatio": 59,
    "breakDamageAddedRatioBase": 58,
    "healRatio": 55,
    "maxSP": 60,
    "sPRatio": 54,
    "statusProbability": 56,
    "statusResistance": 57,
    "physicalAddedRatio": 12,
    "physicalResistance": 13,
    "fireAddedRatio": 14,
    "fireResistance": 15,
    "iceAddedRatio": 16,
    "iceResistance": 17,
    "thunderAddedRatio": 18,
    "thunderResistance": 19,
    "windAddedRatio": 20,
    "windResistance": 21,
    "quantumAddedRatio": 22,
    "quantumResistance": 23,
    "imaginaryAddedRatio": 24,
    "imaginaryResistance": 25,
    "baseHP": 26,
    "hPDelta": 27,
    "hPAddedRatio": 32,
    "baseAttack": 28,
    "attackDelta": 29,
    "attackAddedRatio": 33,
    "baseDefence": 30,
    "defenceDelta": 31,
    "defenceAddedRatio": 34,
    "baseSpeed": 35,
    "physicalResistanceDelta": 37,
    "fireResistanceDelta": 38,
    "iceResistanceDelta": 39,
    "thunderResistanceDelta": 40,
    "windResistanceDelta": 41,
    "quantumResistanceDelta": 42,
    "imaginaryResistanceDelta": 43,
    "speedDelta": 51,
}
GPY_TYPE_TO_YATTA_PROP_TYPE = {v: k for k, v in YATTA_PROP_TYPE_TO_GPY_TYPE.items()}
