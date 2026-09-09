from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFilter

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.enums import Locale
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    import io

    import genshin

__all__ = ("LUNAR_ARCANA_NUMERALS", "LunarArcanaCollectionCard")

LUNAR_ARCANA_NUMERALS = (
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI",
    "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "XXI", "XXII",
)  # fmt: skip

CARD_W, CARD_H = 170, 440
COLS = 11
GAP_X, GAP_Y = 22, 40
MARGIN = 60
HEADER_H = 150
LABEL_H = 64
GOLD = (233, 200, 130)


class LunarArcanaCollectionCard:
    def __init__(self, collection: genshin.models.LunarArcanaCollection, locale: str) -> None:
        self._collection = collection
        self._locale = Locale(locale)

        rows = -(-len(collection.cards) // COLS)
        self._width = MARGIN * 2 + COLS * CARD_W + (COLS - 1) * GAP_X
        self._height = (
            MARGIN + HEADER_H + rows * (CARD_H + LABEL_H) + (rows - 1) * GAP_Y + MARGIN // 2
        )

    @staticmethod
    def _shadow(card: Image.Image) -> Image.Image:
        pad = 30
        shadow = Image.new("RGBA", (card.width + pad * 2, card.height + pad * 2), (0, 0, 0, 0))
        shadow.paste(Image.new("RGBA", card.size, (0, 0, 0, 140)), (pad, pad), card.getchannel("A"))
        return shadow.filter(ImageFilter.GaussianBlur(12))

    def _draw_header(self) -> None:
        drawer, draw = self._drawer, self._draw
        unlocked, total = self._collection.unlocked, self._collection.total

        drawer.write(
            LocaleStr(key="lunar_arcana_collection_title"),
            size=60,
            position=(MARGIN, MARGIN),
            style="bold",
        )
        drawer.write(
            LocaleStr(key="img_theater_large_block_title"),
            size=28,
            position=(MARGIN, MARGIN + 78),
            emphasis="medium",
        )

        right = self._width - MARGIN
        drawer.write(
            str(unlocked),
            size=72,
            position=(right - 110, MARGIN - 6),
            style="bold",
            anchor="ra",
            color=GOLD,
        )
        drawer.write(
            f"/ {total}", size=36, position=(right, MARGIN + 30), anchor="ra", emphasis="medium"
        )

        bar_w, bar_h = 420, 14
        bx, by = right - bar_w, MARGIN + 100
        draw.rounded_rectangle((bx, by, bx + bar_w, by + bar_h), radius=7, fill=(255, 255, 255, 40))
        if unlocked > 0:
            filled = max(bar_h, int(bar_w * unlocked / total))
            draw.rounded_rectangle((bx, by, bx + filled, by + bar_h), radius=7, fill=GOLD)

    def _draw_unlocked(self, card: genshin.models.LunarArcanaCard, pos: tuple[int, int]) -> None:
        x, y = pos
        art = self._drawer.open_static(card.icon, size=(CARD_W, CARD_H))
        self._im.alpha_composite(self._shadow(art), (x - 30, y - 20))
        self._im.alpha_composite(art, (x, y))

        if card.unlock_count > 1:
            bw, bh = 62, 34
            bx, by = x + CARD_W - bw + 6, y + 40
            self._draw.rounded_rectangle((bx, by, bx + bw, by + bh), radius=17, fill=GOLD)
            self._drawer.write(
                f"×{card.unlock_count}",  # ruff:ignore[ambiguous-unicode-character-string]
                size=22,
                position=(bx + bw / 2, by + bh / 2),
                anchor="mm",
                style="bold",
                color=(40, 30, 20),
            )

    def _draw_card(self, index: int, card: genshin.models.LunarArcanaCard) -> None:
        col, row = index % COLS, index // COLS
        x = MARGIN + col * (CARD_W + GAP_X)
        y = MARGIN + HEADER_H + row * (CARD_H + LABEL_H + GAP_Y)

        if card.unlocked:
            self._draw_unlocked(card, (x, y))
        else:
            self._im.alpha_composite(self._locked, (x, y))

        cx = x + CARD_W / 2
        numeral = LUNAR_ARCANA_NUMERALS[index] if index < len(LUNAR_ARCANA_NUMERALS) else ""
        self._drawer.write(
            numeral,
            size=20,
            position=(cx, y + CARD_H + 14),
            anchor="ma",
            emphasis="medium" if card.unlocked else "low",
            color=GOLD if card.unlocked else None,
        )
        self._drawer.write(
            card.name,
            size=22,
            position=(cx, y + CARD_H + 40),
            anchor="ma",
            style="bold",
            emphasis="high" if card.unlocked else "low",
            max_width=CARD_W + 10,
            dynamic_fontsize=True,
        )

    def draw(self) -> io.BytesIO:
        self._im = Drawer.draw_gradient_background(
            self._width, self._height, (28, 22, 54), (62, 40, 96), (0, 0), (1, 1)
        ).convert("RGBA")
        self._draw = ImageDraw.Draw(self._im)
        self._drawer = Drawer(
            self._draw, folder="lunar-arcana", dark_mode=True, locale=self._locale
        )
        self._locked = self._drawer.open_asset("card_locked.png", size=(CARD_W, CARD_H))

        self._draw_header()
        for index, card in enumerate(self._collection.cards):
            self._draw_card(index, card)

        return Drawer.save_image(self._im)
