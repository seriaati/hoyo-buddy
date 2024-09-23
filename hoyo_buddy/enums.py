from __future__ import annotations

from enum import IntEnum, StrEnum


class Game(StrEnum):
    GENSHIN = "Genshin Impact"
    STARRAIL = "Honkai: Star Rail"
    HONKAI = "Honkai Impact 3rd"
    ZZZ = "Zenless Zone Zero"
    TOT = "Tears of Themis"


class NotesNotifyType(IntEnum):
    RESIN = 1
    """Genshin Impact Resin"""
    REALM_CURRENCY = 2
    """Genshin Impact Realm Currency (serenitea pot)"""
    TB_POWER = 3
    """Star Rail Trailblaze Power"""
    GI_EXPED = 4
    """Genshin Impact Expedition"""
    HSR_EXPED = 5
    """Star Rail Expedition"""
    PT = 6
    """Genshin Impact Parametric Transformer"""
    GI_DAILY = 7
    """Genshin Impact Daily Commissions"""
    HSR_DAILY = 8
    """Star Rail Daily Training"""
    RESIN_DISCOUNT = 9
    """Genshin Impact Resin Discount"""
    ECHO_OF_WAR = 10
    """Star Rail Echo of War"""
    RESERVED_TB_POWER = 11
    """Star Rail Reserved Trailblaze Power"""
    BATTERY = 12
    """ZZZ Battery Charge"""
    ZZZ_DAILY = 13
    """ZZZ Engagement"""
    SCRATCH_CARD = 14
    """ZZZ Scratch Card Mania"""
    VIDEO_STORE = 15
    """ZZZ Video Store Management"""
    PLANAR_FISSURE = 16
    """Planar Fissur Double Drop Rate"""


class TalentBoost(IntEnum):
    BOOST_E = 1
    BOOST_Q = 2


class GenshinElement(StrEnum):
    ANEMO = "Anemo"
    GEO = "Geo"
    ELECTRO = "Electro"
    DENDRO = "Dendro"
    PYRO = "Pyro"
    CRYO = "Cryo"
    HYDRO = "Hydro"


class GenshinCity(StrEnum):
    MONDSTADT = "Mondstadt"
    LIYUE = "Liyue"
    INAZUMA = "Inazuma"
    SUMERU = "Sumeru"
    FONTAINE = "Fontaine"
    NATLAN = "Natlan"


class HSRElement(StrEnum):
    FIRE = "Fire"
    ICE = "Ice"
    IMAGINARY = "Imaginary"
    PHYSICAL = "Physical"
    QUANTUM = "Quantum"
    # LIGHTNING = "lightning"
    WIND = "Wind"
    THUNDER = "Thunder"


class HSRPath(StrEnum):
    DESTRUCTION = "Destruction"  # 毀滅
    THE_HUNT = "The Hunt"  # 巡獵
    ERUDITION = "Erudition"  # 智識
    HARMONY = "Harmony"  # 同諧
    NIHILITY = "Nihility"  # 虛無
    PRESERVATION = "Preservation"  # 存護
    ABUNDANCE = "Abundance"  # 豐饒


class Platform(StrEnum):
    HOYOLAB = "HoYoLAB"
    MIYOUSHE = "Miyoushe"


class CharacterType(IntEnum):
    """/profile character types."""

    CACHE = 1
    LIVE = 2
    BUILD = 3


class GeetestType(StrEnum):
    """Geetest type."""

    DAILY_CHECKIN = "Daily check-in"
    REALTIME_NOTES = "Real-time notes"


class ChallengeType(StrEnum):
    """Challenge type."""

    SPIRAL_ABYSS = "Spiral abyss"
    MOC = "Memory of chaos"
    PURE_FICTION = "Pure fiction"
    APC_SHADOW = "Apocalyptic shadow"
    IMG_THEATER = "img_theater_large_block_title"
    SHIYU_DEFENSE = "Shiyu defense"


class ZZZElement(StrEnum):
    ETHER = "Ether"
    FIRE = "Fire"
    ICE = "Ice"
    PHYSICAL = "Physical"
    ELECTRIC = "Electric"


class BetaItemCategory(StrEnum):
    UNRELEASED_CONTENT = "Unreleased Content"


class GachaImportSource(StrEnum):
    STAR_RAIL_STATION = "Star Rail Station"
    ZZZ_RNG_MOE = "zzz.rng.moe"
    STAR_DB = "stardb.gg"
    UIGF = "UIGF"
    SRGF = "SRGF"
    GENSHIN_WIZARD = "Genshin Wizard"


class LeaderboardType(StrEnum):
    ACHIEVEMENT = "achievement"
