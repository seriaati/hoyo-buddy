from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import Drawer

if TYPE_CHECKING:
    from collections.abc import Sequence

    from genshin.models import ZZZFullAgent


class ZZZTeamCard:
    def __init__(self, agents: Sequence[ZZZFullAgent]) -> None:
        self._agents = agents

    @staticmethod
    def _draw_card(*, image_url: str, blob_color: tuple[int, int, int]) -> Image.Image:
        card = Image.open("hoyo-buddy-assets/assets/zzz-team-card/card.png")
        draw = ImageDraw.Draw(card)
        drawer = Drawer(draw, folder="zzz-team-card", dark_mode=False)

        # Open images
        pattern = drawer.open_asset("pattern.png")
        right_blob = drawer.open_asset("right_blob.png")
        middle_blob = drawer.open_asset("middle_blob.png")
        left_blob = drawer.open_asset("left_blob.png")

        right_blob = drawer.create_pattern_blob(
            color=blob_color, rotation=30, pattern=pattern, blob=right_blob
        )
        card.alpha_composite(right_blob, (880, -100))
        middle_blob = drawer.create_pattern_blob(
            color=blob_color, rotation=90, pattern=pattern, blob=middle_blob
        )
        card.alpha_composite(middle_blob, (570, -100))
        left_blob = drawer.create_pattern_blob(
            color=blob_color, rotation=0, pattern=pattern, blob=left_blob
        )
        card.alpha_composite(left_blob, (13, -30))

        chara_img = drawer.open_asset("chara_img.png")
        card.alpha_composite(chara_img, (0, 0))

        test_img = drawer.open_static(image_url)
        test_img = drawer.resize_crop(test_img, chara_img.size)
        card.paste(test_img, (0, 0), chara_img)

        top_layer = drawer.open_asset("top_layer.png")
        card.alpha_composite(top_layer, (241, 19))

        return card
