from __future__ import annotations

import discord
import enka
import hakushin
from ambr import Language as AmbrLanguage
from genshin import Game as GPYGame
from yatta import Language as YattaLanguage
from yatta import PathType

from .enums import Game, HSRPath

DB_INTEGER_MAX = 2147483647
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

TRAILBLAZER_IDS = {8001, 8002, 8003, 8004}


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
ENKA_HSR_LANG_TO_LOCALE = {v: k for k, v in LOCALE_TO_HSR_ENKA_LANG.items()}

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
    discord.Locale.british_english: "en-us",
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
}
GPY_LANG_TO_LOCALE = {v: k for k, v in LOCALE_TO_GPY_LANG.items()}


HOYO_BUDDY_LOCALES: dict[discord.Locale, dict[str, str]] = {
    discord.Locale.american_english: {"name": "English (US)", "emoji": "🇺🇸"},
    discord.Locale.chinese: {"name": "简体中文", "emoji": "🇨🇳"},
    discord.Locale.taiwan_chinese: {"name": "繁體中文", "emoji": "🇹🇼"},
    discord.Locale.french: {"name": "Français", "emoji": "🇫🇷"},
    discord.Locale.japanese: {"name": "日本語", "emoji": "🇯🇵"},
    discord.Locale.brazil_portuguese: {"name": "Português (BR)", "emoji": "🇧🇷"},
    discord.Locale.indonesian: {"name": "Bahasa Indonesia", "emoji": "🇮🇩"},
    discord.Locale.dutch: {"name": "Nederlands", "emoji": "🇳🇱"},
}

LOCALE_TO_AMBR_LANG: dict[discord.Locale, AmbrLanguage] = {
    discord.Locale.taiwan_chinese: AmbrLanguage.CHT,
    discord.Locale.chinese: AmbrLanguage.CHS,
    discord.Locale.german: AmbrLanguage.DE,
    discord.Locale.american_english: AmbrLanguage.EN,
    discord.Locale.spain_spanish: AmbrLanguage.ES,
    discord.Locale.french: AmbrLanguage.FR,
    discord.Locale.indonesian: AmbrLanguage.ID,
    discord.Locale.japanese: AmbrLanguage.JP,
    discord.Locale.korean: AmbrLanguage.KR,
    discord.Locale.brazil_portuguese: AmbrLanguage.PT,
    discord.Locale.russian: AmbrLanguage.RU,
    discord.Locale.thai: AmbrLanguage.TH,
    discord.Locale.vietnamese: AmbrLanguage.VI,
    discord.Locale.italian: AmbrLanguage.IT,
    discord.Locale.turkish: AmbrLanguage.TR,
}

LOCALE_TO_YATTA_LANG: dict[discord.Locale, YattaLanguage] = {
    discord.Locale.taiwan_chinese: YattaLanguage.CHT,
    discord.Locale.chinese: YattaLanguage.CN,
    discord.Locale.german: YattaLanguage.DE,
    discord.Locale.american_english: YattaLanguage.EN,
    discord.Locale.spain_spanish: YattaLanguage.ES,
    discord.Locale.french: YattaLanguage.FR,
    discord.Locale.indonesian: YattaLanguage.ID,
    discord.Locale.japanese: YattaLanguage.JP,
    discord.Locale.korean: YattaLanguage.KR,
    discord.Locale.brazil_portuguese: YattaLanguage.PT,
    discord.Locale.russian: YattaLanguage.RU,
    discord.Locale.thai: YattaLanguage.TH,
    discord.Locale.vietnamese: YattaLanguage.VI,
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
    PathType.KNIGHT: HSRPath.PRESERVATION,
    PathType.MAGE: HSRPath.ERUDITION,
    PathType.PRIEST: HSRPath.ABUNDANCE,
    PathType.ROGUE: HSRPath.THE_HUNT,
    PathType.SHAMAN: HSRPath.HARMONY,
    PathType.WARLOCK: HSRPath.NIHILITY,
    PathType.WARRIOR: HSRPath.DESTRUCTION,
}

STARRAIL_RES = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master"

HB_GAME_TO_GPY_GAME: dict[Game, GPYGame] = {
    Game.GENSHIN: GPYGame.GENSHIN,
    Game.STARRAIL: GPYGame.STARRAIL,
    Game.HONKAI: GPYGame.HONKAI,
}
"""Hoyo Buddy game enum to genshin.py game enum."""

GPY_GAME_TO_HB_GAME = {v: k for k, v in HB_GAME_TO_GPY_GAME.items()}
"""Genshin.py game enum to Hoyo Buddy game enum."""

GEETEST_SERVERS = {
    "prod": "https://geetest-server.seriaati.xyz",
    "test": "http://geetest-server-test.seriaati.xyz",
    "dev": "http://localhost:5000",
}
