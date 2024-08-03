# Determine button states based on template and game.
# Templates aren't based on enums, games are.
# Templates: hb1, src1, src2, src3, enkacard1, enkacard2, encard1, hattvr1

DISABLE_COLOR = {
    "hb1": False,
    "src1": False,
    "src2": False,
    "src3": False,
    "enkacard1": True,
    "enkacard2": True,
    "encard1": False,
    "hattvr1": True,
}

DISABLE_DARK_MODE = {
    "hb1": False,
    "src1": True,
    "src2": True,
    "src3": True,
    "enkacard1": True,
    "enkacard2": True,
    "encard1": True,
    "hattvr1": True,
}

DISABLE_IMAGE_SELECT = {
    "hb1": False,
    "src1": False,
    "src2": False,
    "src3": False,
    "enkacard1": False,
    "enkacard2": False,
    "encard1": False,
    "hattvr1": True,
}

DISABLE_AI_ART = {
    "hb1": False,
    "src1": False,
    "src2": False,
    "src3": False,
    "enkacard1": False,
    "enkacard2": False,
    "encard1": False,
    "hattvr1": True,
}
