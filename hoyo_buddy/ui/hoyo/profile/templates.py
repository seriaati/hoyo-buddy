# Determine button states based on template and game.
# Templates aren't based on enums, games are.

from hoyo_buddy.enums import Game

TEMPLATES: dict[Game, tuple[str, ...]] = {
    Game.GENSHIN: ("hb1", "hb2", "encard1", "enkacard1", "enkacard2", "enka1"),
    Game.STARRAIL: ("hb1", "hb2", "src1", "src2", "src3", "enka1"),
    Game.ZZZ: ("hb1", "hb2", "hb3", "hb4", "enka1"),
}
TEMPLATE_AUTHORS: dict[str, tuple[str, str]] = {
    "hb": ("@ayasaku_", "@seriaati"),
    "src": ("@korzzex", "@korzzex"),
    "encard": ("@korzzex", "@korzzex"),
    "enkacard": ("@korzzex", "@korzzex"),
    "enka": ("enka.network", "@LumiFae"),
}
TEMPLATE_NAMES = {
    "hb": "profile.card_template_select.hb.label",
    "src": "profile.card_template_select.src.label",
    "encard": "profile.card_template_select.encard.label",
    "enkacard": "profile.card_template_select.enkacard.label",
    "enka": "profile.card_template_select.enka.label",
}

DISABLE_COLOR = {
    (Game.GENSHIN, "hb1"): True,
    (Game.GENSHIN, "hb2"): True,
    (Game.GENSHIN, "encard1"): True,
    (Game.GENSHIN, "enkacard1"): True,
    (Game.GENSHIN, "enkacard2"): True,
    (Game.GENSHIN, "enka1"): True,
    (Game.STARRAIL, "hb1"): False,
    (Game.STARRAIL, "hb2"): True,
    (Game.STARRAIL, "src1"): False,
    (Game.STARRAIL, "src2"): False,
    (Game.STARRAIL, "src3"): False,
    (Game.STARRAIL, "enka1"): True,
    (Game.ZZZ, "hb1"): False,
    (Game.ZZZ, "hb2"): False,
    (Game.ZZZ, "hb3"): False,
    (Game.ZZZ, "hb4"): False,
    (Game.ZZZ, "enka1"): True,
}
DISABLE_DARK_MODE = {
    (Game.GENSHIN, "hb1"): False,
    (Game.GENSHIN, "hb2"): False,
    (Game.GENSHIN, "encard1"): True,
    (Game.GENSHIN, "enkacard1"): True,
    (Game.GENSHIN, "enkacard2"): True,
    (Game.GENSHIN, "enka1"): True,
    (Game.STARRAIL, "hb1"): False,
    (Game.STARRAIL, "hb2"): False,
    (Game.STARRAIL, "src1"): True,
    (Game.STARRAIL, "src2"): True,
    (Game.STARRAIL, "src3"): True,
    (Game.STARRAIL, "enka1"): True,
    (Game.ZZZ, "hb1"): True,
    (Game.ZZZ, "hb2"): True,
    (Game.ZZZ, "hb3"): True,
    (Game.ZZZ, "hb4"): True,
    (Game.ZZZ, "enka1"): True,
}
DISABLE_IMAGE = {
    (Game.GENSHIN, "hb1"): False,
    (Game.GENSHIN, "hb2"): False,
    (Game.GENSHIN, "encard1"): False,
    (Game.GENSHIN, "enkacard1"): False,
    (Game.GENSHIN, "enkacard2"): False,
    (Game.GENSHIN, "enka1"): True,
    (Game.STARRAIL, "hb1"): False,
    (Game.STARRAIL, "hb2"): False,
    (Game.STARRAIL, "src1"): False,
    (Game.STARRAIL, "src2"): False,
    (Game.STARRAIL, "src3"): False,
    (Game.STARRAIL, "enka1"): True,
    (Game.ZZZ, "hb1"): True,
    (Game.ZZZ, "hb2"): True,
    (Game.ZZZ, "hb3"): False,
    (Game.ZZZ, "hb4"): False,
    (Game.ZZZ, "enka1"): True,
}

TEMPLATE_PREVIEWS = {
    (Game.GENSHIN, "hb1"): "https://iili.io/24hQO3G.png",
    (Game.GENSHIN, "hb2"): "https://iili.io/24hQZyQ.png",
    (Game.GENSHIN, "encard1"): "https://iili.io/24hZGcb.png",
    (Game.GENSHIN, "enkacard1"): "https://iili.io/24ht5ga.png",
    (Game.GENSHIN, "enkacard2"): "https://iili.io/24hDSuR.png",
    (Game.GENSHIN, "enka1"): "https://img.seria.moe/ljQyVGVKyxpLCSLG.png",
    (Game.STARRAIL, "hb1"): "https://img.seria.moe/lkOMrQRXnQnZqrvX.png",
    (Game.STARRAIL, "hb2"): "https://img.seria.moe/JyxFhSgpXAdNBMkJ.png",
    (Game.STARRAIL, "src1"): "https://iili.io/24hL2ig.png",
    (Game.STARRAIL, "src2"): "https://iili.io/24hLR0G.png",
    (Game.STARRAIL, "src3"): "https://iili.io/24hLw5Q.png",
    (Game.STARRAIL, "enka1"): "https://img.seria.moe/xrmRTweZsHNYXIIR.png",
    (Game.ZZZ, "hb1"): "https://img.seria.moe/xagKUlBObeSlQFuR.png",
    (Game.ZZZ, "hb2"): "https://img.seria.moe/aLcDReesAnNiAUzU.png",
    (Game.ZZZ, "hb3"): "https://img.seria.moe/chpFFHnUVEQTwqPC.png",
    (Game.ZZZ, "hb4"): "https://img.seria.moe/ODajRXtZUlCmTCks.png",
    (Game.ZZZ, "enka1"): "https://img.seria.moe/drkKMmVfuasAlufI.png",
}
