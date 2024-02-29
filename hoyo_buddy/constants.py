import discord
from ambr import Language as AmbrLanguage
from mihomo import Language as MihomoLanguage
from yatta import Language as YattaLanguage

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

MIHOMO_LANG_TO_LOCALE: dict[MihomoLanguage, discord.Locale] = {
    MihomoLanguage.CHT: discord.Locale.taiwan_chinese,
    MihomoLanguage.CHS: discord.Locale.chinese,
    MihomoLanguage.DE: discord.Locale.german,
    MihomoLanguage.EN: discord.Locale.american_english,
    MihomoLanguage.ES: discord.Locale.spain_spanish,
    MihomoLanguage.FR: discord.Locale.french,
    MihomoLanguage.ID: discord.Locale.indonesian,
    MihomoLanguage.JP: discord.Locale.japanese,
    MihomoLanguage.KR: discord.Locale.korean,
    MihomoLanguage.PT: discord.Locale.brazil_portuguese,
    MihomoLanguage.RU: discord.Locale.russian,
    MihomoLanguage.TH: discord.Locale.thai,
    MihomoLanguage.VI: discord.Locale.vietnamese,
}

LOCALE_TO_MIHOMO_LANG: dict[discord.Locale, MihomoLanguage] = {
    discord.Locale.taiwan_chinese: MihomoLanguage.CHT,
    discord.Locale.chinese: MihomoLanguage.CHS,
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
