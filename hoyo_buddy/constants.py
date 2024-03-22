import discord
from ambr import Language as AmbrLanguage
from enka import Language as EnkaLanguage
from mihomo import Language as MihomoLanguage
from yatta import Language as YattaLanguage
from yatta import PathType

from .enums import HSRPath

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

LOCALE_TO_MIHOMO_LANG: dict[discord.Locale, MihomoLanguage] = {
    discord.Locale.taiwan_chinese: MihomoLanguage.CHT,
    discord.Locale.chinese: MihomoLanguage.CHS,  # .CN
    discord.Locale.german: MihomoLanguage.DE,
    discord.Locale.american_english: MihomoLanguage.EN,
    discord.Locale.spain_spanish: MihomoLanguage.ES,
    discord.Locale.french: MihomoLanguage.FR,
    discord.Locale.indonesian: MihomoLanguage.ID,
    discord.Locale.japanese: MihomoLanguage.JP,
    discord.Locale.korean: MihomoLanguage.KR,
    discord.Locale.brazil_portuguese: MihomoLanguage.PT,
    discord.Locale.russian: MihomoLanguage.RU,
    discord.Locale.thai: MihomoLanguage.TH,
    discord.Locale.vietnamese: MihomoLanguage.VI,
}
MIHOMO_LANG_TO_LOCALE = {v: k for k, v in LOCALE_TO_MIHOMO_LANG.items()}

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

LOCALE_TO_ENKA_LANG: dict[discord.Locale, EnkaLanguage] = {
    discord.Locale.taiwan_chinese: EnkaLanguage.TRADITIONAL_CHINESE,
    discord.Locale.chinese: EnkaLanguage.SIMPLIFIED_CHINESE,
    discord.Locale.german: EnkaLanguage.GERMAN,
    discord.Locale.american_english: EnkaLanguage.ENGLISH,
    discord.Locale.spain_spanish: EnkaLanguage.SPANISH,
    discord.Locale.french: EnkaLanguage.FRENCH,
    discord.Locale.indonesian: EnkaLanguage.INDONESIAN,
    discord.Locale.japanese: EnkaLanguage.JAPANESE,
    discord.Locale.korean: EnkaLanguage.KOREAN,
    discord.Locale.brazil_portuguese: EnkaLanguage.PORTUGUESE,
    discord.Locale.russian: EnkaLanguage.RUSSIAN,
    discord.Locale.thai: EnkaLanguage.THAI,
    discord.Locale.vietnamese: EnkaLanguage.VIETNAMESE,
    discord.Locale.italian: EnkaLanguage.ITALIAN,
    discord.Locale.turkish: EnkaLanguage.TURKISH,
}
ENKA_LANG_TO_LOCALE = {v: k for k, v in LOCALE_TO_ENKA_LANG.items()}

LOCALE_TO_CARD_API_LANG: dict[discord.Locale, str] = {
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

# NSFW tags for AI art generation feature
NSFW_TAGS: set[str] = {
    "nsfw",
    "pussy",
    "vaginal",
    "futanari",
    "nipple pull",
    "cowgirl position",
    "cum on breast",
    "happy sex",
    "bound arms",
    "cock in thighhigh",
    "deepthroat",
    "fruit insertion",
    "transformation",
    "mound of venus",
    "footjob",
    "wakamezake",
    "leg lock",
    "upright straddle",
    "penis",
    "thigh sex",
    "stomach bulge",
    "testicles",
    "female ejaculation",
    "breast grab",
    "spanked",
    "mind control",
    "cum on food",
    "nyotaimori",
    "breast feeding",
    "double penetration",
    "double vaginal",
    "tally",
    "femdom",
    "cum",
    "grinding",
    "ring gag",
    "groping",
    "enema",
    "tribadism",
    "navel piercing",
    "buttjob",
    "vibrator",
    "vibrator in thighhighs",
    "masturbation",
    "pubic hair",
    "cunnilingus",
    "clitoris",
    "body writing",
    "clothed masturbation",
    "frogtie",
    "facial",
    "cameltoe",
    "x-ray",
    "cross-section",
    "internal cumshot",
    "exhibitionism",
    "bra lift",
    "caught",
    "blood",
    "tapegag",
    "tamakeri",
    "nipple torture",
    "walk-in",
    "gangbang",
    "anal insertion",
    "anus",
    "anilingus",
    "anal beads",
    "voyeurism",
    "crotch rope",
    "crotch rub",
    "rope",
    "humiliation",
    "group sex",
    "orgy",
    "teamwork",
    "spread ass",
    "no pussy",
    "underwater sex",
    "insertion",
    "nipple tweak",
    "rape",
    "penetration",
    "cum on hair",
    "bound wrists",
    "ejaculation",
    "reverse cowgirl",
    "lactation",
    "breast sucking",
    "nipple suck",
    "girl on top",
    "wide hips",
    "large insertion",
    "anal fingering",
    "bondage",
    "bitgag",
    "handjob",
    "cleave gag",
    "bdsm",
    "pillory",
    "stocks",
    "shibari",
    "fingering",
    "cock ring",
    "huge ass",
    "censored",
    "gokkun",
    "vore",
    "puffy nipples",
    "leash",
    "gag",
    "ass",
    "amputee",
    "hitachi magic wand",
    "uncensored",
    "panty gag",
    "fat mons",
    "ballgag",
    "clothed sex",
    "piercing",
    "anal",
    "pussy juice",
    "doggystyle",
    "ganguro",
    "hogtie",
    "wooden horse",
    "breast smother",
    "fisting",
    "suspension",
    "anal fisting",
    "have to pee",
    "peeing",
    "small nipples",
    "cervix",
    "multiple paizuri",
    "oral",
    "fellatio",
    "hairjob",
    "virgin",
    "facesitting",
    "double anal",
    "pegging",
    "slave",
    "about to be raped",
    "sex",
    "molestation",
}
