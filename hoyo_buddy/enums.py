from __future__ import annotations

from enum import IntEnum, StrEnum


class Game(StrEnum):
    GENSHIN = "Genshin Impact"
    STARRAIL = "Honkai: Star Rail"
    HONKAI = "Honkai Impact 3rd"


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


class Weekday(IntEnum):
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7


class TalentBoost(IntEnum):
    BOOST_E = 1
    BOOST_Q = 2


class GenshinElement(StrEnum):
    ANEMO = "anemo"
    GEO = "geo"
    ELECTRO = "electro"
    DENDRO = "dendro"
    PYRO = "pyro"
    CRYO = "cryo"
    HYDRO = "hydro"


class GenshinCity(StrEnum):
    MONDSTADT = "mondstadt"
    LIYUE = "liyue"
    INAZUMA = "inazuma"
    SUMERU = "sumeru"
    FONTAINE = "fontaine"


class HSRElement(StrEnum):
    FIRE = "fire"
    ICE = "ice"
    IMAGINARY = "imaginary"
    PHYSICAL = "physical"
    QUANTUM = "quantum"
    # LIGHTNING = "lightning"
    WIND = "wind"
    THUNDER = "thunder"


class HSRPath(StrEnum):
    DESTRUCTION = "destruction"  # 毀滅
    THE_HUNT = "the_hunt"  # 巡獵
    ERUDITION = "erudition"  # 智識
    HARMONY = "harmony"  # 同諧
    NIHILITY = "nihility"  # 虛無
    PRESERVATION = "preservation"  # 存護
    ABUNDANCE = "abundance"  # 豐饒


class Platform(StrEnum):
    HOYOLAB = "HoYoLAB"
    MIYOUSHE = "Miyoushe"
