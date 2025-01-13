# Determine button states based on template and game.
# Templates aren't based on enums, games are.
from __future__ import annotations

from hoyo_buddy.enums import Game

TEMPLATES = {
    Game.GENSHIN: ("hb1", "hb2", "hattvr1", "encard1", "enkacard1", "enkacard2"),
    Game.STARRAIL: ("hb1", "hb2", "src1", "src2", "src3"),
    Game.ZZZ: ("hb1", "hb2", "hb3", "hb4"),
}
TEMPLATE_AUTHORS = {
    "hb": ("@ayasaku_", "@seriaati"),
    "src": ("@korzzex", "@korzzex"),
    "hattvr": ("@algoinde", "@hattvr"),
    "encard": ("@korzzex", "@korzzex"),
    "enkacard": ("@korzzex", "@korzzex"),
}
TEMPLATE_NAMES = {
    "hb": "profile.card_template_select.hb.label",
    "src": "profile.card_template_select.src.label",
    "hattvr": "profile.card_template_select.enka_classic.label",
    "encard": "profile.card_template_select.encard.label",
    "enkacard": "profile.card_template_select.enkacard.label",
}

DISABLE_COLOR = {
    (Game.GENSHIN, "hb1"): True,
    (Game.GENSHIN, "hb2"): True,
    (Game.GENSHIN, "hattvr1"): True,
    (Game.GENSHIN, "encard1"): True,
    (Game.GENSHIN, "enkacard1"): True,
    (Game.GENSHIN, "enkacard2"): True,
    (Game.STARRAIL, "hb1"): False,
    (Game.STARRAIL, "hb2"): True,
    (Game.STARRAIL, "src1"): False,
    (Game.STARRAIL, "src2"): False,
    (Game.STARRAIL, "src3"): False,
    (Game.ZZZ, "hb1"): False,
    (Game.ZZZ, "hb2"): False,
    (Game.ZZZ, "hb3"): False,
    (Game.ZZZ, "hb4"): False,
}
DISABLE_DARK_MODE = {
    (Game.GENSHIN, "hb1"): False,
    (Game.GENSHIN, "hb2"): False,
    (Game.GENSHIN, "hattvr1"): True,
    (Game.GENSHIN, "encard1"): True,
    (Game.GENSHIN, "enkacard1"): True,
    (Game.GENSHIN, "enkacard2"): True,
    (Game.STARRAIL, "hb1"): False,
    (Game.STARRAIL, "hb2"): False,
    (Game.STARRAIL, "src1"): True,
    (Game.STARRAIL, "src2"): True,
    (Game.STARRAIL, "src3"): True,
    (Game.ZZZ, "hb1"): True,
    (Game.ZZZ, "hb2"): True,
    (Game.ZZZ, "hb3"): True,
    (Game.ZZZ, "hb4"): True,
}
DISABLE_IMAGE = {
    (Game.GENSHIN, "hb1"): False,
    (Game.GENSHIN, "hb2"): False,
    (Game.GENSHIN, "hattvr1"): True,
    (Game.GENSHIN, "encard1"): False,
    (Game.GENSHIN, "enkacard1"): False,
    (Game.GENSHIN, "enkacard2"): False,
    (Game.STARRAIL, "hb1"): False,
    (Game.STARRAIL, "hb2"): False,
    (Game.STARRAIL, "src1"): False,
    (Game.STARRAIL, "src2"): False,
    (Game.STARRAIL, "src3"): False,
    (Game.ZZZ, "hb1"): True,
    (Game.ZZZ, "hb2"): True,
    (Game.ZZZ, "hb3"): False,
    (Game.ZZZ, "hb4"): False,
}
