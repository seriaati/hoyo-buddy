# Determine button states based on template and game.
# Templates aren't based on enums, games are.
# Templates: hb1, src1, src2, src3, enkacard1, enkacard2, encard1, hattvr1
from __future__ import annotations

DISABLE_COLOR = {"hb2", "enkacard1", "enkacard2", "hattvr1"}
DISABLE_DARK_MODE = {"src1", "src2", "src3", "enkacard1", "enkacard2", "encard1", "hattvr1"}
DISABLE_IMAGE = {"hattvr1"}
ZZZ_DISABLE_IMAGE = {"hb1", "hb2"}
