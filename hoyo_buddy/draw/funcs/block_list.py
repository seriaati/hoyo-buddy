from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.models import DoubleBlock, SingleBlock

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ("BlockListCard",)


class BlockListCard:
    def __init__(
        self, block_lists: Sequence[Sequence[SingleBlock | DoubleBlock]], dark_mode: bool
    ) -> None:
        self.block_lists = block_lists
        self.dark_mode = dark_mode

        self.text_color = (27, 27, 27)
        self.block_padding = (100, 42)
        self.block_margin = (33, 62)
        self.bottom_height = 43
        self.max_rows = 4

    @staticmethod
    def _get_flair_color(bg_color: str) -> tuple[int, int, int]:
        hsl_bg_color = Drawer.hex_to_hsl(bg_color)
        hsl_flair_color = (hsl_bg_color[0], hsl_bg_color[1], hsl_bg_color[2] - 14)
        return Drawer.hex_to_rgb(Drawer.hsl_to_hex(hsl_flair_color))

    def draw_background(self) -> Image.Image:
        block_margin, block_padding = self.block_margin, self.block_padding
        max_rows = self.max_rows
        single_block_size = (204, 204)
        double_block_size = (408, 204)

        card_height = 0
        card_width = 0
        col_height = 0
        col_heights: list[int] = []
        row_widths: list[int] = []

        for row, block_list in enumerate(self.block_lists, start=1):
            row_width = 0
            row_height = 0

            for block in block_list:
                is_single_block = isinstance(block, SingleBlock)
                block_size = single_block_size if is_single_block else double_block_size

                block_width = block_size[0]
                row_width += block_width + block_margin[0]

                block_height = self.bottom_height if block.bottom_text is not None else 0
                block_height += block_size[1]
                row_height = max(row_height, block_height)

            row_widths.append(row_width - block_margin[0])
            col_height += row_height + block_margin[1]

            is_last_row = row == len(self.block_lists)
            if row % max_rows == 0 or is_last_row:
                card_width += max(row_widths) + block_padding[0]
                col_heights.append(col_height - block_margin[1])
                col_height = 0

        card_width += block_padding[0]
        card_height = max(col_heights) + block_padding[1] * 2

        bg_color = (19, 19, 24) if self.dark_mode else (255, 255, 255)
        return Image.new("RGBA", (card_width, card_height), bg_color)

    def draw_block(self, block: SingleBlock | DoubleBlock) -> Image.Image:
        asset_dir = "hoyo-buddy-assets/assets/block-list"
        filename = "single_block" if isinstance(block, SingleBlock) else "double_block"

        if block.bottom_text is None:
            im = Drawer.open_image(f"{asset_dir}/{filename}.png")
            im = Drawer.mask_image_with_color(im, Drawer.hex_to_rgb(block.bg_color))
        else:
            im = Drawer.open_image(f"{asset_dir}/{filename}_back.png")
            front = Drawer.open_image(f"{asset_dir}/{filename}_front.png")
            front = Drawer.mask_image_with_color(front, Drawer.hex_to_rgb(block.bg_color))
            im.alpha_composite(front, (0, 0))

        drawer = Drawer(ImageDraw.Draw(im), folder="block-list", dark_mode=self.dark_mode)

        if isinstance(block, SingleBlock):
            icon = drawer.open_static(block.icon)
            icon = drawer.resize_crop(icon, (block.icon_size, block.icon_size))
            im.alpha_composite(icon, (102 - block.icon_size // 2, 102 - block.icon_size // 2))
        else:
            icon1 = drawer.open_static(block.icon1)
            icon1 = drawer.resize_crop(icon1, (204, 204))
            im.alpha_composite(icon1, (102 - block.icon_size // 2, 102 - block.icon_size // 2))

            icon2 = drawer.open_static(block.icon2)
            icon2 = drawer.resize_crop(icon2, (204, 204))
            im.alpha_composite(icon2, (306 - block.icon_size // 2, 102 - block.icon_size // 2))

        if block.bottom_text is not None:
            drawer.write(
                block.bottom_text,
                size=30,
                position=(im.width // 2, im.height - self.bottom_height // 2),
                color=self.text_color,
                anchor="mm",
                style="bold",
            )

        if isinstance(block, SingleBlock) and block.flair_text is not None:
            flair = drawer.open_asset("flair.png", mask_color=self._get_flair_color(block.bg_color))
            im.alpha_composite(flair, (155, 8))
            drawer.write(
                block.flair_text,
                size=30,
                position=(175, 33),
                color=(255, 255, 255),
                anchor="mm",
                style="bold",
            )
        elif isinstance(block, DoubleBlock) and (
            block.flair_text1 is not None or block.flair_text2 is not None
        ):
            flair = drawer.open_asset("flair.png", mask_color=self._get_flair_color(block.bg_color))

            if block.flair_text1 is not None:
                im.alpha_composite(flair, (155, 8))
                drawer.write(
                    block.flair_text1,
                    size=30,
                    position=(175, 33),
                    color=(255, 255, 255),
                    anchor="mm",
                    style="bold",
                )
            if block.flair_text2 is not None:
                im.alpha_composite(flair, (359, 8))
                drawer.write(
                    block.flair_text2,
                    size=30,
                    position=(379, 33),
                    color=(255, 255, 255),
                    anchor="mm",
                    style="bold",
                )

        return im

    def draw(self) -> BytesIO:
        bg = self.draw_background()
        x, y = self.block_padding
        block_padding = self.block_padding
        block_margin = self.block_margin
        max_rows = self.max_rows

        col_widths: list[int] = []
        row_widths: list[int] = []

        for row, block_list in enumerate(self.block_lists, start=1):
            row_width = 0
            row_height = 0

            for block in block_list:
                block_im = self.draw_block(block)
                bg.alpha_composite(block_im, (x, y))
                x += block_im.size[0] + block_margin[0]

                row_width += block_im.size[0] + block_margin[0]
                row_height = max(row_height, block_im.size[1])

            row_widths.append(row_width - block_margin[0])

            x = block_padding[0] * (row // max_rows + 1)
            if row % max_rows == 0:
                y = block_padding[1]
                col_widths.append(max(row_widths))
            else:
                y += row_height + block_margin[1]
            if row >= max_rows:
                x += sum(col_widths)

        bg = bg.crop((block_padding[0] // 2, 0, bg.width - block_padding[0] // 2, bg.height))

        output = BytesIO()
        bg.save(output, format="PNG")
        return output
