from __future__ import annotations

from typing import TypeAlias

from hoyo_buddy.enums import Locale
from hoyo_buddy.types import FontStyle

NUNITO_LIGHT = "hoyo-buddy-assets/fonts/Nunito/Nunito-Light.ttf"
NUNITO_REGULAR = "hoyo-buddy-assets/fonts/Nunito/Nunito-Regular.ttf"
NUNITO_MEDIUM = "hoyo-buddy-assets/fonts/Nunito/Nunito-Medium.ttf"
NUNITO_BOLD = "hoyo-buddy-assets/fonts/Nunito/Nunito-Bold.ttf"
NUNITO_BLACK = "hoyo-buddy-assets/fonts/Nunito/Nunito-Black.ttf"

NUNITO_LIGHT_ITALIC = "hoyo-buddy-assets/fonts/Nunito/Nunito-LightItalic.ttf"
NUNITO_REGULAR_ITALIC = "hoyo-buddy-assets/fonts/Nunito/Nunito-Italic.ttf"
NUNITO_MEDIUM_ITALIC = "hoyo-buddy-assets/fonts/Nunito/Nunito-MediumItalic.ttf"
NUNITO_BOLD_ITALIC = "hoyo-buddy-assets/fonts/Nunito/Nunito-BoldItalic.ttf"
NUNITO_BLACK_ITALIC = "hoyo-buddy-assets/fonts/Nunito/Nunito-BlackItalic.ttf"

NUNITO_SANS_LIGHT = "hoyo-buddy-assets/fonts/NunitoSans/NunitoSans_10pt-Light.ttf"
NUNITO_SANS_REGULAR = "hoyo-buddy-assets/fonts/NunitoSans/NunitoSans_10pt-Regular.ttf"
NUNITO_SANS_MEDIUM = "hoyo-buddy-assets/fonts/NunitoSans/NunitoSans_10pt-Medium.ttf"
NUNITO_SANS_BOLD = "hoyo-buddy-assets/fonts/NunitoSans/NunitoSans_10pt-Bold.ttf"
NUNITO_SANS_BLACK = "hoyo-buddy-assets/fonts/NunitoSans/NunitoSans_10pt-Black.ttf"

NUNITO_SANS_LIGHT_ITALIC = "hoyo-buddy-assets/fonts/NunitoSans/NunitoSans_10pt-LightItalic.ttf"
NUNITO_SANS_REGULAR_ITALIC = "hoyo-buddy-assets/fonts/NunitoSans/NunitoSans_10pt-Italic.ttf"
NUNITO_SANS_MEDIUM_ITALIC = "hoyo-buddy-assets/fonts/NunitoSans/NunitoSans_10pt-MediumItalic.ttf"
NUNITO_SANS_BOLD_ITALIC = "hoyo-buddy-assets/fonts/NunitoSans/NunitoSans_10pt-BoldItalic.ttf"
NUNITO_SANS_BLACK_ITALIC = "hoyo-buddy-assets/fonts/NunitoSans/NunitoSans_10pt-BlackItalic.ttf"

MPLUSROUNDED1C_LIGHT = "hoyo-buddy-assets/fonts/MPLUSRounded1c/MPLUSRounded1c-Light.ttf"
MPLUSROUNDED1C_REGULAR = "hoyo-buddy-assets/fonts/MPLUSRounded1c/MPLUSRounded1c-Regular.ttf"
MPLUSROUNDED1C_MEDIUM = "hoyo-buddy-assets/fonts/MPLUSRounded1c/MPLUSRounded1c-Medium.ttf"
MPLUSROUNDED1C_BOLD = "hoyo-buddy-assets/fonts/MPLUSRounded1c/MPLUSRounded1c-Bold.ttf"
MPLUSROUNDED1C_BLACK = "hoyo-buddy-assets/fonts/MPLUSRounded1c/MPLUSRounded1c-Black.ttf"

GENSENROUNDEDTW_LIGHT = "hoyo-buddy-assets/fonts/GenSenRounded/GenSenRoundedTW-L-01.ttf"
GENSENROUNDEDTW_REGULAR = "hoyo-buddy-assets/fonts/GenSenRounded/GenSenRoundedTW-R-01.ttf"
GENSENROUNDEDTW_MEDIUM = "hoyo-buddy-assets/fonts/GenSenRounded/GenSenRoundedTW-M-01.ttf"
GENSENROUNDEDTW_BOLD = "hoyo-buddy-assets/fonts/GenSenRounded/GenSenRoundedTW-B-01.ttf"

NOTOSANSKR_LIGHT = "hoyo-buddy-assets/fonts/NotoSansKR/NotoSansKR-Light.ttf"
NOTOSANSKR_REGULAR = "hoyo-buddy-assets/fonts/NotoSansKR/NotoSansKR-Regular.ttf"
NOTOSANSKR_MEDIUM = "hoyo-buddy-assets/fonts/NotoSansKR/NotoSansKR-Medium.ttf"
NOTOSANSKR_BOLD = "hoyo-buddy-assets/fonts/NotoSansKR/NotoSansKR-Bold.ttf"
NOTOSANSKR_BLACK = "hoyo-buddy-assets/fonts/NotoSansKR/NotoSansKR-Black.ttf"

ZENMARUGOTHIC_LIGHT = "hoyo-buddy-assets/fonts/ZenMaruGothic/ZenMaruGothic-Light.ttf"
ZENMARUGOTHIC_REGULAR = "hoyo-buddy-assets/fonts/ZenMaruGothic/ZenMaruGothic-Regular.ttf"
ZENMARUGOTHIC_MEDIUM = "hoyo-buddy-assets/fonts/ZenMaruGothic/ZenMaruGothic-Medium.ttf"
ZENMARUGOTHIC_BOLD = "hoyo-buddy-assets/fonts/ZenMaruGothic/ZenMaruGothic-Bold.ttf"
ZENMARUGOTHIC_BLACK = "hoyo-buddy-assets/fonts/ZenMaruGothic/ZenMaruGothic-Black.ttf"

NOTOSANSTC_LIGHT = "hoyo-buddy-assets/fonts/NotoSansTC/NotoSansTC-Light.ttf"
NOTOSANSTC_REGULAR = "hoyo-buddy-assets/fonts/NotoSansTC/NotoSansTC-Regular.ttf"
NOTOSANSTC_MEDIUM = "hoyo-buddy-assets/fonts/NotoSansTC/NotoSansTC-Medium.ttf"
NOTOSANSTC_BOLD = "hoyo-buddy-assets/fonts/NotoSansTC/NotoSansTC-Bold.ttf"
NOTOSANSTC_BLACK = "hoyo-buddy-assets/fonts/NotoSansTC/NotoSansTC-Black.ttf"

NOTOSANSSC_LIGHT = "hoyo-buddy-assets/fonts/NotoSansSC/NotoSansSC-Light.ttf"
NOTOSANSSC_REGULAR = "hoyo-buddy-assets/fonts/NotoSansSC/NotoSansSC-Regular.ttf"
NOTOSANSSC_MEDIUM = "hoyo-buddy-assets/fonts/NotoSansSC/NotoSansSC-Medium.ttf"
NOTOSANSSC_BOLD = "hoyo-buddy-assets/fonts/NotoSansSC/NotoSansSC-Bold.ttf"
NOTOSANSSC_BLACK = "hoyo-buddy-assets/fonts/NotoSansSC/NotoSansSC-Black.ttf"

NOTOSANSJP_LIGHT = "hoyo-buddy-assets/fonts/NotoSansJP/NotoSansJP-Light.ttf"
NOTOSANSJP_REGULAR = "hoyo-buddy-assets/fonts/NotoSansJP/NotoSansJP-Regular.ttf"
NOTOSANSJP_MEDIUM = "hoyo-buddy-assets/fonts/NotoSansJP/NotoSansJP-Medium.ttf"
NOTOSANSJP_BOLD = "hoyo-buddy-assets/fonts/NotoSansJP/NotoSansJP-Bold.ttf"
NOTOSANSJP_BLACK = "hoyo-buddy-assets/fonts/NotoSansJP/NotoSansJP-Black.ttf"

NOTOSANSTHAI_LIGHT = "hoyo-buddy-assets/fonts/NotoSansThai/NotoSansThai-Light.ttf"
NOTOSANSTHAI_REGULAR = "hoyo-buddy-assets/fonts/NotoSansThai/NotoSansThai-Regular.ttf"
NOTOSANSTHAI_MEDIUM = "hoyo-buddy-assets/fonts/NotoSansThai/NotoSansThai-Medium.ttf"
NOTOSANSTHAI_BOLD = "hoyo-buddy-assets/fonts/NotoSansThai/NotoSansThai-Bold.ttf"
NOTOSANSTHAI_BLACK = "hoyo-buddy-assets/fonts/NotoSansThai/NotoSansThai-Black.ttf"

NOTOSANS_LIGHT = "hoyo-buddy-assets/fonts/NotoSans/NotoSans-Light.ttf"
NOTOSANS_REGULAR = "hoyo-buddy-assets/fonts/NotoSans/NotoSans-Regular.ttf"
NOTOSANS_MEDIUM = "hoyo-buddy-assets/fonts/NotoSans/NotoSans-Medium.ttf"
NOTOSANS_BOLD = "hoyo-buddy-assets/fonts/NotoSans/NotoSans-Bold.ttf"
NOTOSANS_BLACK = "hoyo-buddy-assets/fonts/NotoSans/NotoSans-Black.ttf"

NOTOSANSARABIC_LIGHT = "hoyo-buddy-assets/fonts/NotoSansArabic/NotoSansArabic-Light.ttf"
NOTOSANSARABIC_REGULAR = "hoyo-buddy-assets/fonts/NotoSansArabic/NotoSansArabic-Regular.ttf"
NOTOSANSARABIC_MEDIUM = "hoyo-buddy-assets/fonts/NotoSansArabic/NotoSansArabic-Medium.ttf"
NOTOSANSARABIC_BOLD = "hoyo-buddy-assets/fonts/NotoSansArabic/NotoSansArabic-Bold.ttf"
NOTOSANSARABIC_BLACK = "hoyo-buddy-assets/fonts/NotoSansArabic/NotoSansArabic-Black.ttf"

TAJAWAL_LIGHT = "hoyo-buddy-assets/fonts/Tajawal/Tajawal-Light.ttf"
TAJAWAL_REGULAR = "hoyo-buddy-assets/fonts/Tajawal/Tajawal-Regular.ttf"
TAJAWAL_MEDIUM = "hoyo-buddy-assets/fonts/Tajawal/Tajawal-Medium.ttf"
TAJAWAL_BOLD = "hoyo-buddy-assets/fonts/Tajawal/Tajawal-Bold.ttf"
TAJAWAL_BLACK = "hoyo-buddy-assets/fonts/Tajawal/Tajawal-Black.ttf"

SUPPORTED_BY_NUNITO: tuple[Locale, ...] = (
    Locale.american_english,
    Locale.british_english,
    Locale.bulgarian,
    Locale.croatian,
    Locale.czech,
    Locale.indonesian,
    Locale.danish,
    Locale.dutch,
    Locale.finnish,
    Locale.french,
    Locale.german,
    Locale.hungarian,
    Locale.italian,
    Locale.latin_american_spanish,
    Locale.lithuanian,
    Locale.norwegian,
    Locale.polish,
    Locale.brazil_portuguese,
    Locale.romanian,
    Locale.russian,
    Locale.spain_spanish,
    Locale.swedish,
    Locale.turkish,
    Locale.ukrainian,
    Locale.vietnamese,
)
SUPPORTED_BY_GOTHIC: tuple[Locale, ...] = (
    Locale.american_english,
    Locale.british_english,
    Locale.bulgarian,
    Locale.indonesian,
    Locale.danish,
    Locale.dutch,
    Locale.finnish,
    Locale.french,
    Locale.german,
    Locale.italian,
    Locale.latin_american_spanish,
    Locale.norwegian,
    Locale.brazil_portuguese,
    Locale.russian,
    Locale.spain_spanish,
    Locale.swedish,
)

FontMapping: TypeAlias = dict[tuple[Locale, ...] | Locale, dict[FontStyle, str]]

DEFAULT_FONT_MAPPING: FontMapping = {
    (Locale.chinese, Locale.taiwan_chinese): {
        "light": GENSENROUNDEDTW_LIGHT,
        "regular": GENSENROUNDEDTW_REGULAR,
        "medium": GENSENROUNDEDTW_MEDIUM,
        "bold": GENSENROUNDEDTW_BOLD,
    },
    Locale.japanese: {
        "light": MPLUSROUNDED1C_LIGHT,
        "regular": MPLUSROUNDED1C_REGULAR,
        "medium": MPLUSROUNDED1C_MEDIUM,
        "bold": MPLUSROUNDED1C_BOLD,
        "black": MPLUSROUNDED1C_BLACK,
    },
    Locale.korean: {
        "light": NOTOSANSKR_LIGHT,
        "regular": NOTOSANSKR_REGULAR,
        "medium": NOTOSANSKR_MEDIUM,
        "bold": NOTOSANSKR_BOLD,
        "black": NOTOSANSKR_BLACK,
    },
    Locale.thai: {
        "light": NOTOSANSTHAI_LIGHT,
        "regular": NOTOSANSTHAI_REGULAR,
        "medium": NOTOSANSTHAI_MEDIUM,
        "bold": NOTOSANSTHAI_BOLD,
        "black": NOTOSANSTHAI_BLACK,
    },
    Locale.hindi: {
        "light": NOTOSANS_LIGHT,
        "regular": NOTOSANS_BLACK,
        "medium": NOTOSANS_MEDIUM,
        "bold": NOTOSANS_BOLD,
        "black": NOTOSANS_BLACK,
    },
    Locale.arabic: {
        "light": TAJAWAL_LIGHT,
        "regular": TAJAWAL_REGULAR,
        "medium": TAJAWAL_MEDIUM,
        "bold": TAJAWAL_BOLD,
        "black": TAJAWAL_BLACK,
    },
    SUPPORTED_BY_NUNITO: {
        "light": NUNITO_LIGHT,
        "regular": NUNITO_REGULAR,
        "medium": NUNITO_MEDIUM,
        "bold": NUNITO_BOLD,
        "black": NUNITO_BLACK,
        "light_italic": NUNITO_LIGHT_ITALIC,
        "regular_italic": NUNITO_REGULAR_ITALIC,
        "medium_italic": NUNITO_MEDIUM_ITALIC,
        "bold_italic": NUNITO_BOLD_ITALIC,
        "black_italic": NUNITO_BLACK_ITALIC,
    },
}

SANS_FONT_MAPPING: FontMapping = {
    Locale.chinese: {
        "light": NOTOSANSSC_LIGHT,
        "regular": NOTOSANSSC_REGULAR,
        "medium": NOTOSANSSC_MEDIUM,
        "bold": NOTOSANSSC_BOLD,
        "black": NOTOSANSSC_BLACK,
    },
    Locale.taiwan_chinese: {
        "light": NOTOSANSTC_LIGHT,
        "regular": NOTOSANSTC_REGULAR,
        "medium": NOTOSANSTC_MEDIUM,
        "bold": NOTOSANSTC_BOLD,
        "black": NOTOSANSTC_BLACK,
    },
    Locale.japanese: {
        "light": NOTOSANSJP_LIGHT,
        "regular": NOTOSANSJP_REGULAR,
        "medium": NOTOSANSJP_MEDIUM,
        "bold": NOTOSANSJP_BOLD,
        "black": NOTOSANSJP_BLACK,
    },
    Locale.korean: {
        "light": NOTOSANSKR_LIGHT,
        "regular": NOTOSANSKR_REGULAR,
        "medium": NOTOSANSKR_MEDIUM,
        "bold": NOTOSANSKR_BOLD,
        "black": NOTOSANSKR_BLACK,
    },
    Locale.thai: {
        "light": NOTOSANSTHAI_LIGHT,
        "regular": NOTOSANSTHAI_REGULAR,
        "medium": NOTOSANSTHAI_MEDIUM,
        "bold": NOTOSANSTHAI_BOLD,
        "black": NOTOSANSTHAI_BLACK,
    },
    Locale.arabic: {
        "light": NOTOSANSARABIC_LIGHT,
        "regular": NOTOSANSARABIC_REGULAR,
        "medium": NOTOSANSARABIC_MEDIUM,
        "bold": NOTOSANSARABIC_BOLD,
        "black": NOTOSANSARABIC_BLACK,
    },
    SUPPORTED_BY_NUNITO: {
        "light": NUNITO_SANS_LIGHT,
        "regular": NUNITO_SANS_REGULAR,
        "medium": NUNITO_SANS_MEDIUM,
        "bold": NUNITO_SANS_BOLD,
        "black": NUNITO_SANS_BLACK,
        "light_italic": NUNITO_SANS_LIGHT_ITALIC,
        "regular_italic": NUNITO_SANS_REGULAR_ITALIC,
        "medium_italic": NUNITO_SANS_MEDIUM_ITALIC,
        "bold_italic": NUNITO_SANS_BOLD_ITALIC,
        "black_italic": NUNITO_SANS_BLACK_ITALIC,
    },
}

GOTHIC_FONT_MAPPING: FontMapping = {
    SUPPORTED_BY_GOTHIC: {
        "light": ZENMARUGOTHIC_LIGHT,
        "regular": ZENMARUGOTHIC_REGULAR,
        "medium": ZENMARUGOTHIC_MEDIUM,
        "bold": ZENMARUGOTHIC_BOLD,
        "black": ZENMARUGOTHIC_BLACK,
    }
}
