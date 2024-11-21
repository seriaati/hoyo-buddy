from __future__ import annotations

import datetime
import pathlib
from typing import TYPE_CHECKING, Final, Literal

import akasha
import ambr
import discord
import enka
import genshin
import hakushin
import yatta

from .enums import ChallengeType, Game, GenshinCity, GenshinElement, HSRElement, HSRPath

if TYPE_CHECKING:
    from .types import OffloadAPI

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

TRAILBLAZER_IDS = {8001, 8002, 8003, 8004, 8005, 8006, 1001, 1224}


def contains_traveler_id(character_id: str) -> bool:
    return any(str(traveler_id) in character_id for traveler_id in TRAVELER_IDS)


GI_SERVER_RESET_HOURS: dict[str, int] = {
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
    discord.Locale.american_english: akasha.Language.ENGLISH,
    discord.Locale.taiwan_chinese: akasha.Language.CHINESE_TRADITIONAL,
    discord.Locale.chinese: akasha.Language.CHINESE_SIMPLIFIED,
    discord.Locale.german: akasha.Language.GERMAN,
    discord.Locale.spain_spanish: akasha.Language.SPANISH,
    discord.Locale.french: akasha.Language.FRENCH,
    discord.Locale.italian: akasha.Language.ITALIAN,
    discord.Locale.japanese: akasha.Language.JAPANESE,
    discord.Locale.korean: akasha.Language.KOREAN,
    discord.Locale.brazil_portuguese: akasha.Language.PORTUGUESE,
    discord.Locale.russian: akasha.Language.RUSSIAN,
    discord.Locale.thai: akasha.Language.THAI,
    discord.Locale.vietnamese: akasha.Language.VIETNAMESE,
    discord.Locale.turkish: akasha.Language.TURKISH,
    discord.Locale.ukrainian: akasha.Language.RUSSIAN,
}
AKASHA_LANG_TO_LOCALE = {v: k for k, v in LOCALE_TO_AKASHA_LANG.items()}


def locale_to_akasha_lang(locale: discord.Locale) -> akasha.Language:
    return LOCALE_TO_AKASHA_LANG.get(locale, akasha.Language.ENGLISH)


LOCALE_TO_HSR_ENKA_LANG: dict[discord.Locale, enka.hsr.Language] = {
    discord.Locale.taiwan_chinese: enka.hsr.Language.TRADITIONAL_CHINESE,
    discord.Locale.chinese: enka.hsr.Language.SIMPLIFIED_CHINESE,
    discord.Locale.german: enka.hsr.Language.GERMAN,
    discord.Locale.american_english: enka.hsr.Language.ENGLISH,
    discord.Locale.spain_spanish: enka.hsr.Language.ESPANOL,
    discord.Locale.french: enka.hsr.Language.FRECH,
    discord.Locale.indonesian: enka.hsr.Language.INDOENSIAN,
    discord.Locale.japanese: enka.hsr.Language.JAPANESE,
    discord.Locale.korean: enka.hsr.Language.KOREAN,
    discord.Locale.brazil_portuguese: enka.hsr.Language.PORTUGUESE,
    discord.Locale.russian: enka.hsr.Language.RUSSIAN,
    discord.Locale.thai: enka.hsr.Language.THAI,
    discord.Locale.vietnamese: enka.hsr.Language.VIETNAMESE,
}

LOCALE_TO_HSR_CARD_API_LANG: dict[discord.Locale, str] = {
    discord.Locale.taiwan_chinese: "cht",
    discord.Locale.chinese: "cn",
    discord.Locale.german: "de",
    discord.Locale.spain_spanish: "es",
    discord.Locale.french: "fr",
    discord.Locale.indonesian: "id",
    discord.Locale.japanese: "jp",
    discord.Locale.korean: "kr",
    discord.Locale.brazil_portuguese: "pt",
    discord.Locale.russian: "ru",
    discord.Locale.thai: "th",
    discord.Locale.vietnamese: "vi",
    discord.Locale.ukrainian: "ru",
}

LOCALE_TO_GPY_LANG = {
    discord.Locale.american_english: "en-us",
    discord.Locale.taiwan_chinese: "zh-tw",
    discord.Locale.chinese: "zh-cn",
    discord.Locale.german: "de-de",
    discord.Locale.spain_spanish: "es-es",
    discord.Locale.french: "fr-fr",
    discord.Locale.indonesian: "id-id",
    discord.Locale.italian: "it-it",
    discord.Locale.japanese: "ja-jp",
    discord.Locale.korean: "ko-kr",
    discord.Locale.brazil_portuguese: "pt-pt",
    discord.Locale.thai: "th-th",
    discord.Locale.vietnamese: "vi-vn",
    discord.Locale.turkish: "tr-tr",
    discord.Locale.russian: "ru-ru",
    discord.Locale.ukrainian: "ru-ru",
}
GPY_LANG_TO_LOCALE = {v: k for k, v in LOCALE_TO_GPY_LANG.items()}


def locale_to_gpy_lang(locale: discord.Locale) -> str:
    return LOCALE_TO_GPY_LANG.get(locale, "en-us")


HOYO_BUDDY_LOCALES: dict[discord.Locale, dict[str, str]] = {
    discord.Locale.american_english: {"name": "English", "emoji": "🇺🇸"},
    discord.Locale.chinese: {"name": "简体中文", "emoji": "🇨🇳"},
    discord.Locale.taiwan_chinese: {"name": "繁體中文", "emoji": "🇹🇼"},
    discord.Locale.french: {"name": "Français", "emoji": "🇫🇷"},
    discord.Locale.japanese: {"name": "日本語", "emoji": "🇯🇵"},
    discord.Locale.brazil_portuguese: {"name": "Português", "emoji": "🇧🇷"},
    discord.Locale.indonesian: {"name": "Bahasa Indonesia", "emoji": "🇮🇩"},
    discord.Locale.dutch: {"name": "Nederlands", "emoji": "🇳🇱"},
    discord.Locale.vietnamese: {"name": "Tiếng Việt", "emoji": "🇻🇳"},
    discord.Locale.thai: {"name": "ภาษาไทย", "emoji": "🇹🇭"},
    discord.Locale.spain_spanish: {"name": "Español", "emoji": "🇪🇸"},
    discord.Locale.korean: {"name": "한국어", "emoji": "🇰🇷"},
    discord.Locale.turkish: {"name": "Türkçe", "emoji": "🇹🇷"},
    discord.Locale.italian: {"name": "Italiano", "emoji": "🇮🇹"},
    discord.Locale.russian: {"name": "Русский", "emoji": "🇷🇺"},
}

LOCALE_TO_AMBR_LANG: dict[discord.Locale, ambr.Language] = {
    discord.Locale.taiwan_chinese: ambr.Language.CHT,
    discord.Locale.chinese: ambr.Language.CHS,
    discord.Locale.german: ambr.Language.DE,
    discord.Locale.american_english: ambr.Language.EN,
    discord.Locale.spain_spanish: ambr.Language.ES,
    discord.Locale.french: ambr.Language.FR,
    discord.Locale.indonesian: ambr.Language.ID,
    discord.Locale.japanese: ambr.Language.JP,
    discord.Locale.korean: ambr.Language.KR,
    discord.Locale.brazil_portuguese: ambr.Language.PT,
    discord.Locale.russian: ambr.Language.RU,
    discord.Locale.ukrainian: ambr.Language.RU,
    discord.Locale.thai: ambr.Language.TH,
    discord.Locale.vietnamese: ambr.Language.VI,
    discord.Locale.italian: ambr.Language.IT,
    discord.Locale.turkish: ambr.Language.TR,
}

LOCALE_TO_YATTA_LANG: dict[discord.Locale, yatta.Language] = {
    discord.Locale.taiwan_chinese: yatta.Language.CHT,
    discord.Locale.chinese: yatta.Language.CN,
    discord.Locale.german: yatta.Language.DE,
    discord.Locale.american_english: yatta.Language.EN,
    discord.Locale.spain_spanish: yatta.Language.ES,
    discord.Locale.french: yatta.Language.FR,
    discord.Locale.indonesian: yatta.Language.ID,
    discord.Locale.japanese: yatta.Language.JP,
    discord.Locale.korean: yatta.Language.KR,
    discord.Locale.brazil_portuguese: yatta.Language.PT,
    discord.Locale.russian: yatta.Language.RU,
    discord.Locale.ukrainian: yatta.Language.RU,
    discord.Locale.thai: yatta.Language.TH,
    discord.Locale.vietnamese: yatta.Language.VI,
}

LOCALE_TO_HAKUSHIN_LANG: dict[discord.Locale, hakushin.Language] = {
    discord.Locale.chinese: hakushin.Language.ZH,
    discord.Locale.taiwan_chinese: hakushin.Language.ZH,
    discord.Locale.japanese: hakushin.Language.JA,
    discord.Locale.korean: hakushin.Language.KO,
    discord.Locale.american_english: hakushin.Language.EN,
}


LOCALE_TO_GI_ENKA_LANG: dict[discord.Locale, enka.gi.Language] = {
    discord.Locale.taiwan_chinese: enka.gi.Language.TRADITIONAL_CHINESE,
    discord.Locale.chinese: enka.gi.Language.SIMPLIFIED_CHINESE,
    discord.Locale.german: enka.gi.Language.GERMAN,
    discord.Locale.american_english: enka.gi.Language.ENGLISH,
    discord.Locale.spain_spanish: enka.gi.Language.SPANISH,
    discord.Locale.french: enka.gi.Language.FRENCH,
    discord.Locale.indonesian: enka.gi.Language.INDONESIAN,
    discord.Locale.japanese: enka.gi.Language.JAPANESE,
    discord.Locale.korean: enka.gi.Language.KOREAN,
    discord.Locale.brazil_portuguese: enka.gi.Language.PORTUGUESE,
    discord.Locale.russian: enka.gi.Language.RUSSIAN,
    discord.Locale.ukrainian: enka.gi.Language.RUSSIAN,
    discord.Locale.thai: enka.gi.Language.THAI,
    discord.Locale.vietnamese: enka.gi.Language.VIETNAMESE,
    discord.Locale.italian: enka.gi.Language.ITALIAN,
    discord.Locale.turkish: enka.gi.Language.TURKISH,
}

LOCALE_TO_GI_CARD_API_LANG: dict[discord.Locale, str] = {
    discord.Locale.taiwan_chinese: "cht",
    discord.Locale.chinese: "chs",
    discord.Locale.german: "de",
    discord.Locale.american_english: "en",
    discord.Locale.spain_spanish: "es",
    discord.Locale.french: "fr",
    discord.Locale.indonesian: "id",
    discord.Locale.japanese: "jp",
    discord.Locale.korean: "kr",
    discord.Locale.brazil_portuguese: "pt",
    discord.Locale.russian: "ru",
    discord.Locale.thai: "th",
    discord.Locale.vietnamese: "vi",
    discord.Locale.italian: "it",
    discord.Locale.turkish: "tr",
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
}

YATTA_PATH_TO_GPY_PATH = {
    yatta.PathType.KNIGHT: genshin.models.StarRailPath.PRESERVATION,
    yatta.PathType.MAGE: genshin.models.StarRailPath.ERUDITION,
    yatta.PathType.PRIEST: genshin.models.StarRailPath.ABUNDANCE,
    yatta.PathType.ROGUE: genshin.models.StarRailPath.THE_HUNT,
    yatta.PathType.SHAMAN: genshin.models.StarRailPath.HARMONY,
    yatta.PathType.WARLOCK: genshin.models.StarRailPath.NIHILITY,
    yatta.PathType.WARRIOR: genshin.models.StarRailPath.DESTRUCTION,
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

STARRAIL_RES = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master"

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

WEB_APP_URLS = {"prod": "https://hb-app.seria.moe", "test": "https://hb-app.seria.moe", "dev": "http://localhost:8645"}

UTC_8 = datetime.timezone(datetime.timedelta(hours=8))

HAKUSHIN_HSR_SKILL_TYPE_NAMES = {
    "Normal": "hsr.normal_attack",
    "BPSkill": "hsr.skill",
    "Ultra": "hsr.ultimate",
    "Maze": "hsr.technique",
    "MazeNormal": "hsr.technique",
    "Talent": "hsr.talent",
}
GI_SKILL_TYPE_KEYS = {1: "gi.skill", 2: "gi.burst", 3: "gi.passive", 4: "gi.passive", 5: "gi.passive"}

GAME_CHALLENGE_TYPES: Final[dict[Game, tuple[ChallengeType, ...]]] = {
    Game.GENSHIN: (ChallengeType.SPIRAL_ABYSS, ChallengeType.IMG_THEATER),
    Game.STARRAIL: (ChallengeType.MOC, ChallengeType.PURE_FICTION, ChallengeType.APC_SHADOW),
    Game.ZZZ: (ChallengeType.SHIYU_DEFENSE,),
}

ZENLESS_ASSET_SCRAPE_URL = "https://raw.githubusercontent.com/seriaati/ZenlessAssetScrape/main/data/lite"
ZZZ_AGENT_DATA_URL = f"{ZENLESS_ASSET_SCRAPE_URL}/agent_data.json"

ZENLESS_DATA_URL = "https://git.mero.moe/dimbreath/ZenlessData/raw/branch/master"
ZENLESS_DATA_LANGS = ("CHT", "DE", "EN", "ES", "FR", "ID", "JA", "KO", "PT", "RU", "TH", "VI")
ZZZ_ITEM_TEMPLATE_URL = f"{ZENLESS_DATA_URL}//FileCfg/ItemTemplateTb.json"
ZZZ_AVATAR_TEMPLATE_URL = f"{ZENLESS_DATA_URL}/FileCfg/AvatarBaseTemplateTb.json"
ZZZ_TEXT_MAP_URL = f"{ZENLESS_DATA_URL}/TextMap/TextMap_{{lang}}TemplateTb.json"

LOCALE_TO_ZENLESS_DATA_LANG: dict[discord.Locale, str] = {
    discord.Locale.taiwan_chinese: "CHT",
    discord.Locale.german: "DE",
    discord.Locale.american_english: "EN",
    discord.Locale.spain_spanish: "ES",
    discord.Locale.french: "FR",
    discord.Locale.indonesian: "ID",
    discord.Locale.japanese: "JA",
    discord.Locale.korean: "KO",
    discord.Locale.brazil_portuguese: "PT",
    discord.Locale.russian: "RU",
    discord.Locale.thai: "TH",
    discord.Locale.vietnamese: "VI",
}


def locale_to_zenless_data_lang(locale: discord.Locale) -> str:
    return LOCALE_TO_ZENLESS_DATA_LANG.get(locale, "EN")


STARRAIL_DATA_URL = "https://gitlab.com/Dimbreath/turnbasedgamedata/-/raw/main"
HSR_AVATAR_CONFIG_URL = f"{STARRAIL_DATA_URL}/ExcelOutput/AvatarConfig.json"
HSR_EQUIPMENT_CONFIG_URL = f"{STARRAIL_DATA_URL}/ExcelOutput/EquipmentConfig.json"
HSR_TEXT_MAP_URL = f"{STARRAIL_DATA_URL}/TextMap/TextMap{{lang}}.json"

STARRAIL_DATA_LANGS = ("CHS", "CHT", "DE", "EN", "ES", "FR", "ID", "JP", "KR", "PT", "RU", "TH", "VI")

LOCALE_TO_STARRAIL_DATA_LANG: dict[discord.Locale, str] = {
    discord.Locale.chinese: "CHS",
    discord.Locale.taiwan_chinese: "CHT",
    discord.Locale.german: "DE",
    discord.Locale.american_english: "EN",
    discord.Locale.spain_spanish: "ES",
    discord.Locale.french: "FR",
    discord.Locale.indonesian: "ID",
    discord.Locale.japanese: "JP",
    discord.Locale.korean: "KR",
    discord.Locale.brazil_portuguese: "PT",
    discord.Locale.russian: "RU",
    discord.Locale.thai: "TH",
    discord.Locale.vietnamese: "VI",
}


def locale_to_starrail_data_lang(locale: discord.Locale) -> str:
    return LOCALE_TO_STARRAIL_DATA_LANG.get(locale, "EN")


FORT_OF_FANS_URL = "https://raw.githubusercontent.com/FortOfFans/HSR/main"
HSR_DEFAULT_ART_URL = f"{FORT_OF_FANS_URL}/spriteoutput/avatardrawcardresult/{{char_id}}.png"
HSR_TEAM_ICON_URL = f"{FORT_OF_FANS_URL}/spriteoutput/avatariconteam/{{char_id}}.png"
ZZZ_DEFAULT_ART_URL = "https://api.hakush.in/zzz/UI/Mindscape_{char_id}_3.webp"

UIGF_GAME_KEYS: Final[dict[Game, str]] = {Game.GENSHIN: "hk4e", Game.STARRAIL: "hkrpg", Game.ZZZ: "nap"}

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
    Game.STARRAIL: {11: "50/50", 12: "75/25"},
    Game.ZZZ: {2: "50/50", 3: "75/25"},
}

BANNER_GUARANTEE_NUMS: Final[dict[Game, dict[int, int]]] = {
    Game.GENSHIN: {301: 90, 302: 80, 200: 90, 500: 90, 100: 20},
    Game.STARRAIL: {11: 90, 12: 80, 1: 90, 2: 50},
    Game.ZZZ: {2: 90, 3: 80, 1: 90, 5: 80},
}

STANDARD_END_DATES: Final[dict[Game, dict[int, datetime.date]]] = {
    Game.GENSHIN: {
        10000079: datetime.date(2023, 3, 21),  # Dehya
        10000042: datetime.date(2021, 3, 2),  # Keqing
        10000069: datetime.date(2022, 9, 9),  # Tighnari
    }
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

CHARACTER_MAX_LEVEL: Final[dict[Game, int]] = {Game.GENSHIN: 90, Game.STARRAIL: 80, Game.ZZZ: 60, Game.HONKAI: 80}


def is_standard_item(game: Game, item_id: int) -> bool:
    if game not in STANDARD_ITEMS:
        msg = f"Game {game} is missing from the standard items list."
        raise ValueError(msg)
    return item_id in STANDARD_ITEMS[game]


def locale_to_hakushin_lang(locale: discord.Locale) -> hakushin.Language:
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


def get_disc_substat_roll_num(disc_rarity: Literal["B", "A", "S"], prop: genshin.models.ZZZProperty) -> int:
    if not isinstance(prop.type, genshin.models.ZZZPropertyType):
        return 0

    value = DISC_SUBSTAT_VALUES[disc_rarity][prop.type]
    prop_value = float(prop.value.replace("%", ""))
    return round(prop_value / value)


OFFLOAD_APIS: dict[OffloadAPI, str] = {
    "VERCEL": "https://daily-checkin-api.vercel.app",
    "RENDER": "https://daily-checkin-api.onrender.com",
    "FLY": "https://daily-checkin-api.fly.dev",
    "B4A": "https://dailycheckinapi-z7nqjbte.b4a.run",
    "RAILWAY": "https://dailycheckinapi-production.up.railway.app"
}
