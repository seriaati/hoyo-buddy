from __future__ import annotations

import datetime
from typing import Final

import ambr
import discord
import enka
import genshin
import hakushin
import yatta

from .enums import ChallengeType, Game, GenshinCity, GenshinElement, HSRElement, HSRPath

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


UID_SERVER_RESET_HOURS: dict[str, int] = {
    "6": 17,  # America, 5 PM
    "7": 11,  # Europe, 11 AM
    # Every other server resets at 4 AM
}
UID_TZ_OFFSET: dict[str, int] = {
    "6": -13,  # America, UTC-5
    "7": -7,  # Europe, UTC+1
    # Every other server is UTC+8
}
UID_STARTS: tuple[str, ...] = (
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
}

STARRAIL_RES = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master"

HB_GAME_TO_GPY_GAME: dict[Game, genshin.Game] = {
    Game.GENSHIN: genshin.Game.GENSHIN,
    Game.STARRAIL: genshin.Game.STARRAIL,
    Game.HONKAI: genshin.Game.HONKAI,
}
"""Hoyo Buddy game enum to genshin.py game enum."""

GPY_GAME_TO_HB_GAME = {v: k for k, v in HB_GAME_TO_GPY_GAME.items()}
"""Genshin.py game enum to Hoyo Buddy game enum."""

GEETEST_SERVERS = {
    "prod": "http://geetest-server-test.seriaati.xyz",
    "test": "http://geetest-server-test.seriaati.xyz",
    "dev": "http://localhost:5000",
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
    Game.GENSHIN: (ChallengeType.SPIRAL_ABYSS,),
    Game.STARRAIL: (ChallengeType.MOC, ChallengeType.PURE_FICTION, ChallengeType.APC_SHADOW),
}
