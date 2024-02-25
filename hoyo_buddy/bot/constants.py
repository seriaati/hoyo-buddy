import discord
import mihomo

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

LOCALE_TO_MIHOMO_LANG: dict[discord.Locale, mihomo.Language] = {
    discord.Locale.taiwan_chinese: mihomo.Language.CHT,
    discord.Locale.chinese: mihomo.Language.CHS,
    discord.Locale.german: mihomo.Language.DE,
    discord.Locale.american_english: mihomo.Language.EN,
    discord.Locale.spain_spanish: mihomo.Language.ES,
    discord.Locale.french: mihomo.Language.FR,
    discord.Locale.indonesian: mihomo.Language.ID,
    discord.Locale.japanese: mihomo.Language.JP,
    discord.Locale.korean: mihomo.Language.KR,
    discord.Locale.brazil_portuguese: mihomo.Language.PT,
    discord.Locale.russian: mihomo.Language.RU,
    discord.Locale.thai: mihomo.Language.TH,
    discord.Locale.vietnamese: mihomo.Language.VI,
}
