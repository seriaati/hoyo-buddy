from __future__ import annotations

import functools
import math
from typing import TYPE_CHECKING, Literal

import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFilter

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.draw.fonts import NOTO_SANS_FONT_MAPPING
from hoyo_buddy.enums import FiftyFiftyResult, GachaItemKind, Locale
from hoyo_buddy.l10n import LocaleStr, translator

if TYPE_CHECKING:
    from io import BytesIO

    import aiohttp
    from PIL import ImageFont

    from hoyo_buddy.models.gacha_summary import GachaRank, GachaSummary, GachaSummaryItem
    from hoyo_buddy.types import FontStyle

type RGBA = tuple[int, int, int, int]
type Align = Literal["left", "right", "center"]

YATTA_UI = "https://sr.yatta.moe/hsr/assets/UI"

SCALE = 2
WIDTH, HEIGHT = 1600, 1800 // 2
PAD_X, PAD_Y = 64, 52
COL_W = 740

# Noto Sans vertical metrics (em units), used to place text the way CSS line boxes do
ASCENT = 1.069
CONTENT_H = 1.362

WEIGHTS: dict[int, FontStyle] = {
    400: "regular",
    500: "medium",
    600: "medium",
    700: "bold",
    800: "black",
}

BG = (7, 7, 12)
GOLD = (232, 201, 143, 255)
GOLD_LIGHT = (246, 221, 170, 255)
STAR = (246, 199, 91, 255)
PURPLE = (199, 174, 242, 255)
WHITE = (255, 255, 255, 255)
LOST_RED = (242, 154, 133, 255)
TAG_TEXT = (30, 23, 10, 255)


def _s(value: float) -> int:
    return round(value * SCALE)


def _white(opacity: float) -> RGBA:
    return (255, 255, 255, round(255 * opacity))


@functools.cache
def _cmap(font_path: str) -> frozenset[int]:
    return frozenset(TTFont(font_path).getBestCmap() or {})


def _poly_mask(
    size: tuple[int, int], points: list[tuple[float, float]], ss: int = 4
) -> Image.Image:
    """Anti-aliased polygon mask by supersampling."""
    big = Image.new("L", (size[0] * ss, size[1] * ss), 0)
    ImageDraw.Draw(big).polygon([(x * ss, y * ss) for x, y in points], fill=255)
    return big.resize(size, Image.Resampling.LANCZOS)


def _star_points(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    inner = r * 0.45
    points: list[tuple[float, float]] = []
    for i in range(10):
        radius = r if i % 2 == 0 else inner
        angle = math.pi / 5 * i - math.pi / 2
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def _with_opacity(image: Image.Image, opacity: float) -> Image.Image:
    image = image.copy()
    image.putalpha(image.getchannel("A").point([round(a * opacity) for a in range(256)]))
    return image


def _is_missing(image: Image.Image) -> bool:
    return image.width <= 1 or image.height <= 1


async def resolve_hsr_gacha_summary_art(  # ruff:ignore[unused-async]
    summary: GachaSummary,
    session: aiohttp.ClientSession,  # ruff: ignore[unused-function-argument]
) -> None:
    """Fill art_url and icon_url of summary.latest and summary.previous."""
    items = [summary.latest, *summary.previous] if summary.latest is not None else summary.previous
    for item in items:
        if item.kind is GachaItemKind.CHARACTER:
            item.art_url = f"{YATTA_UI}/avatar/large/{item.item_id}.png"
            item.icon_url = f"{YATTA_UI}/avatar/medium/{item.item_id}.png"
        else:
            item.art_url = item.icon_url = f"{YATTA_UI}/equipment/large/{item.item_id}.png"


class HSRGachaSummaryCard:
    def __init__(self, summary: GachaSummary, *, locale: Locale) -> None:
        self.summary = summary
        self.locale = locale

    def draw(self) -> BytesIO:
        return _Renderer(self.summary, self.locale).render()


class _Renderer:
    def __init__(self, summary: GachaSummary, locale: Locale) -> None:
        self.summary = summary
        self.locale = locale
        self.im = Image.new("RGB", (_s(WIDTH), _s(HEIGHT)), BG)
        self.d = ImageDraw.Draw(self.im, "RGBA")
        self.drawer = Drawer(
            self.d,
            folder="gacha-summary",
            dark_mode=True,
            locale=locale,
            font_mapping=NOTO_SANS_FONT_MAPPING,
        )
        self._fonts: dict[tuple[Locale, int, FontStyle], ImageFont.FreeTypeFont] = {}
        self.is_light_cone = (
            summary.latest is not None and summary.latest.kind is not GachaItemKind.CHARACTER
        )

    def render(self) -> BytesIO:
        self._draw_background()
        latest = self.summary.latest
        if latest is not None:
            if self.is_light_cone:
                self._draw_light_cone_art(latest)
            else:
                self._draw_character_art(latest)
        self._draw_fades()
        self._draw_logo()
        if latest is not None:
            self._draw_latest(latest)

        y = self._draw_header()
        y = self._draw_pity_panel(y + 26)
        y = self._draw_stats(y + 26)
        if self.summary.previous:
            self._draw_previous(y + 26)

        return Drawer.save_image(self.im)

    # Text

    def tr(self, string: LocaleStr) -> str:
        return translator.translate(string, self.locale)

    def _font(self, text: str, px: int, style: FontStyle) -> ImageFont.FreeTypeFont:
        locale = self.drawer.detect_locale_from_text(text, return_english_for_latin=False)
        key = (locale or self.locale, px, style)
        if key not in self._fonts:
            self._fonts[key] = self.drawer.get_font(px, style, locale=key[0])
        return self._fonts[key]

    def _runs(
        self, text: str, px: int, style: FontStyle
    ) -> list[tuple[str, ImageFont.FreeTypeFont]]:
        """Split text into runs by font, falling back to Noto Sans JP for glyphs like ★."""
        font = self._font(text, px, style)
        key = (Locale.japanese, px, style)
        if key not in self._fonts:
            self._fonts[key] = self.drawer.get_font(px, style, locale=Locale.japanese)
        fallback = self._fonts[key]

        cmap = _cmap(str(font.path))
        runs: list[tuple[str, ImageFont.FreeTypeFont]] = []
        for char in text:
            char_font = font if ord(char) in cmap or char.isspace() else fallback
            if runs and runs[-1][1] is char_font:
                runs[-1] = (runs[-1][0] + char, char_font)
            else:
                runs.append((char, char_font))
        return runs

    def _segments(
        self, text: str, px: int, style: FontStyle, tracking: float
    ) -> list[tuple[str, ImageFont.FreeTypeFont]]:
        """Pieces drawn in one call each; tracked text is drawn char by char."""
        runs = self._runs(text, px, style)
        if not tracking:
            return runs
        return [(char, font) for run, font in runs for char in run]

    def measure(self, text: str, size: float, weight: int = 400, *, tracking: float = 0) -> float:
        """Width of text in CSS px."""
        px = _s(size)
        segments = self._segments(text, px, WEIGHTS[weight], tracking)
        width = sum(font.getlength(seg) for seg, font in segments)
        width += tracking * px * max(len(segments) - 1, 0)
        return width / SCALE

    def fit(
        self, text: str, size: float, weight: int, max_width: float, *, tracking: float = 0
    ) -> float:
        """Largest font size <= size at which text fits max_width (never below 60%)."""
        min_size = size * 0.6
        while size > min_size and self.measure(text, size, weight, tracking=tracking) > max_width:
            size -= 0.5
        return size

    def truncate(
        self, text: str, size: float, weight: int, max_width: float, *, tracking: float = 0
    ) -> str:
        if self.measure(text, size, weight, tracking=tracking) <= max_width:
            return text
        while text and self.measure(f"{text}…", size, weight, tracking=tracking) > max_width:
            text = text[:-1]
        return f"{text.rstrip()}…"

    def text(
        self,
        text: str,
        x: float,
        top: float,
        size: float,
        weight: int = 400,
        color: RGBA = WHITE,
        *,
        align: Align = "left",
        line_height: float = CONTENT_H,
        tracking: float = 0,
        max_width: float | None = None,
    ) -> float:
        """Draw a line of text positioned like a CSS line box. Returns the width in CSS px.

        With max_width, the text shrinks (keeping its vertical centre) and is then truncated.
        """
        if max_width is not None:
            fitted = self.fit(text, size, weight, max_width, tracking=tracking)
            top += (size - fitted) * line_height / 2
            size = fitted
            text = self.truncate(text, size, weight, max_width, tracking=tracking)
        px = _s(size)
        width = self.measure(text, size, weight, tracking=tracking)
        if align == "right":
            x -= width
        elif align == "center":
            x -= width / 2

        segments = self._segments(text, px, WEIGHTS[weight], tracking)
        ascent = max(font.getmetrics()[0] for _, font in segments)
        descent = max(font.getmetrics()[1] for _, font in segments)
        pad = px // 2
        mask = Image.new("L", (_s(width) + pad * 2, ascent + descent + pad * 2), 0)
        mask_draw = ImageDraw.Draw(mask)
        cursor = pad
        for seg, font in segments:
            mask_draw.text((cursor, pad + ascent), seg, font=font, fill=color[3], anchor="ls")
            cursor += font.getlength(seg) + tracking * px

        baseline = _s(top + (line_height - CONTENT_H) * size / 2 + ASCENT * size)
        self.fill_mask(color[:3], mask, _s(x) - pad, baseline - ascent - pad)
        return width

    def text_mid(
        self,
        text: str,
        x: float,
        center_y: float,
        size: float,
        weight: int = 400,
        color: RGBA = WHITE,
        **kwargs,
    ) -> float:
        return self.text(text, x, center_y - CONTENT_H * size / 2, size, weight, color, **kwargs)

    def wrap(
        self, text: str, size: float, weight: int, max_width: float, max_lines: int
    ) -> list[str] | None:
        """Greedy word wrap, None if it doesn't fit in max_lines."""
        sep = " " if " " in text else ""
        tokens = text.split(" ") if sep else list(text)
        lines: list[str] = []
        for token in tokens:
            candidate = f"{lines[-1]}{sep}{token}" if lines else token
            if lines and self.measure(candidate, size, weight) <= max_width:
                lines[-1] = candidate
            elif self.measure(token, size, weight) <= max_width:
                lines.append(token)
            else:
                return None
        return lines if len(lines) <= max_lines else None

    # Shapes and images

    def paste(self, image: Image.Image, x: float, y: float) -> None:
        self.im.paste(image, (_s(x), _s(y)), image)

    def fill_mask(
        self, color: tuple[int, int, int], mask: Image.Image, x: int = 0, y: int = 0
    ) -> None:
        self.im.paste(color, (x, y, x + mask.width, y + mask.height), mask)

    def rect(self, x0: float, y0: float, x1: float, y1: float, color: RGBA) -> None:
        self.d.rectangle((_s(x0), _s(y0), _s(x1) - 1, _s(y1) - 1), fill=color)

    def stars(self, right: float, top: float, size: float, count: int = 5) -> None:
        """Star glyph row like `font-size: size; letter-spacing: 4px`."""
        step = size + 4
        radius = size * 0.48
        box_w, box_h = _s(step * count), _s(size)
        mask = Image.new("L", (box_w, box_h), 0)
        for i in range(count):
            cx = _s(step * i + size / 2)
            points = _star_points(cx, box_h / 2 + _s(size * 0.04), _s(radius))
            star = _poly_mask((box_w, box_h), points)
            mask.paste(255, (0, 0), star)
        self.fill_mask(STAR[:3], mask, _s(right - step * count + 4), _s(top))

    def h_gradient(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        start: tuple[int, int, int],
        end: tuple[int, int, int],
    ) -> None:
        width, height = _s(x1) - _s(x0), _s(y1) - _s(y0)
        if width <= 0 or height <= 0:
            return
        t = np.linspace(0, 1, width)[None, :, None]
        row = np.array(start)[None, None, :] * (1 - t) + np.array(end)[None, None, :] * t
        image = Image.fromarray(np.repeat(row, height, axis=0).astype(np.uint8), "RGB")
        self.im.paste(image, (_s(x0), _s(y0)))

    def glow(
        self, cx: float, cy: float, radius: float, color: tuple[int, int, int], opacity: float
    ) -> None:
        """Radial gradient from `opacity` at the centre to 0 at radius."""
        r = _s(radius)
        yy, xx = np.mgrid[-r:r, -r:r]
        dist = np.sqrt(xx**2 + yy**2) / r
        alpha = np.clip(1 - dist, 0, 1) * opacity * 255
        mask = Image.fromarray(alpha.astype(np.uint8), "L")
        self.fill_mask(color, mask, _s(cx) - r, _s(cy) - r)

    # Background and art

    def _draw_background(self) -> None:
        w, h = WIDTH // 2, HEIGHT // 2
        cy = 0.40 if self.is_light_cone else 0.45
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        dist = np.sqrt(((xx - 0.72 * w) / (0.5 * w)) ** 2 + ((yy - cy * h) / (0.7 * h)) ** 2)
        stops = [0, 0.55, 0.9]
        colors = [(42, 35, 80), (18, 16, 31), BG]
        channels = [np.interp(dist, stops, [c[i] for c in colors]) for i in range(3)]
        bg = Image.fromarray(np.stack(channels, axis=-1).astype(np.uint8), "RGB")
        self.im.paste(bg.resize(self.im.size, Image.Resampling.BICUBIC))

    def _draw_character_art(self, item: GachaSummaryItem) -> None:
        art = Drawer.open_static(item.art_url)
        if _is_missing(art):
            return
        art = art.resize((_s(1150), _s(1150)), Image.Resampling.LANCZOS)
        self.paste(art, 605, -130)

    def _draw_tilted_card(
        self, art: Image.Image, cx: float, cy: float, size: tuple[float, float]
    ) -> None:
        w, h = _s(size[0]), _s(size[1])
        border, pad = _s(3), _s(4)
        card = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
        card.paste(GOLD, (pad, pad, pad + w, pad + h))
        card.paste(
            (26, 24, 48, 255), (pad + border, pad + border, pad + w - border, pad + h - border)
        )
        if not _is_missing(art):
            inner = Drawer.resize_crop(art, (w - border * 2, h - border * 2))
            card.paste(inner, (pad + border, pad + border), inner)

        shadow_pad = _s(80)
        shadow = Image.new("L", (w + shadow_pad * 2, h + shadow_pad * 2), 0)
        shadow.paste(round(255 * 0.6), (shadow_pad, shadow_pad, shadow_pad + w, shadow_pad + h))
        shadow = shadow.rotate(-6, resample=Image.Resampling.BICUBIC, expand=True)
        shadow = shadow.filter(ImageFilter.GaussianBlur(_s(30)))
        self.fill_mask(
            (0, 0, 0), shadow, _s(cx) - shadow.width // 2, _s(cy + 30) - shadow.height // 2
        )

        card = card.rotate(-6, resample=Image.Resampling.BICUBIC, expand=True)
        self.im.paste(card, (_s(cx) - card.width // 2, _s(cy) - card.height // 2), card)

    def _draw_light_cone_art(self, item: GachaSummaryItem) -> None:
        self.glow(1150, 330, 285, GOLD_LIGHT[:3], 0.28)
        self._draw_tilted_card(Drawer.open_static(item.art_url), 1150, 330, (316, 440))

    def _draw_fades(self) -> None:
        width, height = self.im.size
        xs = np.linspace(0, 1, width)
        h_alpha = np.interp(xs, [0, 0.47, 0.57, 0.70, 1], [1, 1, 0.6, 0, 0]) * 255
        mask = Image.fromarray(np.tile(h_alpha, (height, 1)).astype(np.uint8), "L")
        self.fill_mask(BG, mask)

        fade_h = _s(340)
        v_alpha = np.linspace(0, 0.95, fade_h) * 255
        mask = Image.fromarray(np.tile(v_alpha[:, None], (1, width)).astype(np.uint8), "L")
        self.fill_mask(BG, mask, 0, height - fade_h)

    def _draw_logo(self) -> None:
        name_w = self.measure("Hoyo Buddy", 18, 700)
        x = WIDTH - PAD_X - name_w - 10 - 37
        logo = self.drawer.open_asset("hb_logo.png", size=(_s(37), _s(40)))
        self.paste(_with_opacity(logo, 0.7), x, PAD_Y)
        self.text_mid("Hoyo Buddy", x + 47, PAD_Y + 20, 18, 700, _white(0.7))

    # Left column

    def _draw_header(self) -> float:
        s = self.summary
        x, y = PAD_X, PAD_Y
        self._draw_avatar(x, y, 48)
        name_w = self.text_mid(s.nickname, x + 60, y + 24, 19, 700, max_width=360)
        self.text_mid(f"UID {s.uid}", x + 60 + name_w + 12, y + 24, 15, 500, _white(0.62))

        y += 48 + 14
        icon = self.drawer.open_asset("hsr_special_pass.png", size=(_s(48), _s(48)))
        self.paste(icon, x, y)
        self.text_mid(s.banner_name, x + 60, y + 24, 38, 800, max_width=COL_W - 60)
        return y + 48

    def _draw_avatar(self, x: float, y: float, size: float) -> None:
        px = _s(size)
        border = _s(2)
        big = Image.new("L", (px * 4, px * 4), 0)
        ImageDraw.Draw(big).ellipse((0, 0, px * 4 - 1, px * 4 - 1), fill=255)
        circle = big.resize((px, px), Image.Resampling.LANCZOS)
        self.fill_mask((232, 201, 143), circle, _s(x), _s(y))

        inner_px = px - border * 2
        inner = circle.resize((inner_px, inner_px), Image.Resampling.LANCZOS)
        avatar = Image.new("RGBA", (inner_px, inner_px), (42, 39, 66, 255))
        art = Drawer.open_static(self.summary.avatar_url)
        if not _is_missing(art):
            ratio = inner_px / min(art.size)
            art = art.resize(
                (round(art.width * ratio), round(art.height * ratio)), Image.Resampling.LANCZOS
            )
            left = (art.width - inner_px) // 2
            art = art.crop((left, 0, left + inner_px, inner_px))
            avatar.paste(art, (0, 0), art)
        avatar.putalpha(inner)
        self.im.paste(avatar, (_s(x) + border, _s(y) + border), avatar)

    def _draw_pity_panel(self, top: float) -> float:
        s = self.summary
        x0, x1 = PAD_X + 26, PAD_X + COL_W - 26
        content_top = top + 2 + 22
        height = 2 + 22 + 80 + 16 + 8 + 16 + 24.5 + 22
        bottom = top + height
        right = PAD_X + COL_W
        self.d.polygon(
            [
                (_s(PAD_X), _s(top)),
                (_s(right), _s(top)),
                (_s(right), _s(bottom - 18)),
                (_s(right - 18), _s(bottom)),
                (_s(PAD_X), _s(bottom)),
            ],
            fill=_white(0.06),
        )
        self.rect(PAD_X, top, right, top + 2, GOLD)

        five = self.tr(LocaleStr(key="gacha_summary.pity", rarity="5★")).upper()
        self.text(five, x0, content_top, 13, 700, GOLD, tracking=0.18)
        num_top = content_top + 17.7 + 2
        num_w = self.text(str(s.five_star_pity), x0, num_top, 60, 800, GOLD_LIGHT, line_height=1)
        max_top = num_top + (1 - CONTENT_H) * 60 / 2 + ASCENT * 60 - ASCENT * 26
        self.text(f"/ {s.five_star_max_pity}", x0 + num_w + 6, max_top, 26, 600, _white(0.55))

        if s.win_rate_title is not None:
            row_bottom = content_top + 80
            value = (
                self.tr(LocaleStr(key="gacha_summary.guaranteed"))
                if s.guaranteed
                else self.tr(
                    LocaleStr(key="gacha_summary.next_not_guaranteed", title=s.win_rate_title)
                )
            )
            self.text(value, x1, row_bottom - 27.2, 20, 700, align="right", max_width=420)
            label = self.tr(LocaleStr(key="gacha_summary.next", rarity="5★"))
            self.text(
                label,
                x1,
                row_bottom - 27.2 - 4 - 20.4,
                15,
                500,
                _white(0.62),
                align="right",
                max_width=420,
            )

        bar_top = content_top + 80 + 16
        max_pity = max(s.five_star_max_pity, 1)
        self.rect(x0, bar_top, x1, bar_top + 8, _white(0.12))
        fill_x = x0 + (x1 - x0) * min(s.five_star_pity / max_pity, 1)
        self.h_gradient(x0, bar_top, fill_x, bar_top + 8, (185, 138, 74), GOLD_LIGHT[:3])
        if s.five_star_soft_pity is not None:
            marker_x = x0 + (x1 - x0) * min(s.five_star_soft_pity / max_pity, 1)
            self.rect(marker_x, bar_top - 6, marker_x + 2, bar_top + 14, _white(0.55))

        self._draw_four_star_row(x0, x1, bar_top + 8 + 16)
        return bottom

    def _draw_four_star_row(self, x0: float, x1: float, top: float) -> None:
        s = self.summary
        center = top + 24.5 / 2
        label = self.tr(LocaleStr(key="gacha_summary.pity", rarity="4★")).upper()
        label_w = self.text_mid(label, x0, center, 13, 700, PURPLE, tracking=0.18, max_width=160)
        label_w = max(label_w, 92)

        max_text = f"/ {s.four_star_max_pity}"
        max_w = self.text_mid(max_text, x1, center, 18, 600, _white(0.55), align="right")
        pity_w = self.measure(f"{s.four_star_pity} ", 18, 700)
        self.text_mid(f"{s.four_star_pity} ", x1 - max_w - pity_w, center, 18, 700)

        bar_x0, bar_x1 = x0 + label_w + 16, x1 - max_w - pity_w - 16
        self.rect(bar_x0, center - 2.5, bar_x1, center + 2.5, _white(0.12))
        ratio = min(s.four_star_pity / max(s.four_star_max_pity, 1), 1)
        self.rect(
            bar_x0,
            center - 2.5,
            bar_x0 + (bar_x1 - bar_x0) * ratio,
            center + 2.5,
            (168, 132, 230, 255),
        )

    def _top_str(self, rank: GachaRank | None) -> str | None:
        if rank is None:
            return None
        percent = f"{max(round(rank.percent, 1), 0.1):g}"
        return self.tr(LocaleStr(key="top_percent", percent=percent))

    def _stat_cells(self) -> list[tuple[str, str, str | None, bool]]:
        """(label, value, sub text, sub has currency icon)."""
        s = self.summary

        def join(*parts: str | None) -> str | None:
            return " · ".join(p for p in parts if p) or None

        def total(count: int) -> str:
            return self.tr(LocaleStr(key="gacha_summary.total", total=f"{count:,}"))

        cells: list[tuple[str, str, str | None, bool]] = [
            (
                self.tr(LocaleStr(key="gacha_summary.banner_pulls")),
                f"{s.banner_pulls:,}",
                f"{s.banner_currency:,}",
                True,
            ),
            (
                self.tr(LocaleStr(key="gacha_summary.lifetime_pulls")),
                f"{s.lifetime_pulls:,}",
                self._top_str(s.lifetime_rank),
                False,
            ),
        ]
        if s.win_rate_title is not None:
            wins = self.tr(
                LocaleStr(
                    key="gacha_summary.wins_of_total",
                    wins=s.fifty_fifty_wins,
                    total=s.fifty_fifty_total,
                )
            )
            cells.append(
                (
                    self.tr(LocaleStr(key="gacha_summary.win_rate", title=s.win_rate_title)),
                    f"{round(s.win_rate, 1):g}%",
                    join(wins, self._top_str(s.win_rate_rank)),
                    False,
                )
            )
        else:
            cells.append(
                (
                    self.tr(LocaleStr(key="gacha_summary.lifetime_spent")),
                    f"{s.lifetime_currency:,}",
                    "",
                    True,
                )
            )
        cells.extend(
            (
                (
                    self.tr(LocaleStr(key="gacha_summary.avg_pulls", rarity="5★")),
                    f"{s.avg_five_star_pulls:.1f}",
                    join(total(s.total_five_stars), self._top_str(s.five_star_luck_rank)),
                    False,
                ),
                (
                    self.tr(LocaleStr(key="gacha_summary.avg_pulls", rarity="4★")),
                    f"{s.avg_four_star_pulls:.1f}",
                    join(total(s.total_four_stars), self._top_str(s.four_star_luck_rank)),
                    False,
                ),
            )
        )
        if s.win_rate_title is not None:
            cells.append(
                (
                    self.tr(LocaleStr(key="gacha_summary.lifetime_spent")),
                    f"{s.lifetime_currency:,}",
                    "",
                    True,
                )
            )
        return cells

    def _draw_stats(self, top: float) -> float:
        cells = self._stat_cells()
        col_w = (COL_W - 24 * 2) / 3
        cell_h = 17.7 + 2 + 43.6 + 2 + 20
        jade = self.drawer.open_asset("JADE.png", folder="emojis", size=(_s(20), _s(20)))

        for i, (label, value, sub, has_icon) in enumerate(cells):
            x = PAD_X + (i % 3) * (col_w + 24)
            y = top + (i // 3) * (cell_h + 22)
            self.rect(x, y, x + 1, y + cell_h, (232, 201, 143, 102))
            tx, text_w = x + 15, col_w - 15

            self.text(label.upper(), tx, y, 13, 700, _white(0.62), tracking=0.14, max_width=text_w)
            self.text(value, tx, y + 19.7, 32, 800, max_width=text_w)

            sub_top = y + 19.7 + 43.6 + 2
            if has_icon:
                self.paste(jade, tx, sub_top)
                if sub:
                    self.text_mid(
                        sub, tx + 24, sub_top + 10, 14, 500, _white(0.62), max_width=text_w - 24
                    )
            elif sub:
                self.text_mid(sub, tx, sub_top + 10, 14, 600, GOLD, max_width=text_w)

        rows = math.ceil(len(cells) / 3)
        return top + rows * cell_h + (rows - 1) * 22

    def _draw_previous(self, top: float) -> None:
        label = self.tr(LocaleStr(key="gacha_summary.previous", rarity="5★")).upper()
        self.text(label, PAD_X, top, 13, 700, GOLD, tracking=0.2)
        card_top = top + 17.7 + 12
        for i, item in enumerate(self.summary.previous[:5]):
            self._draw_previous_card(item, PAD_X + i * (124 + 24), card_top)

    def _draw_previous_card(self, item: GachaSummaryItem, x: float, y: float) -> None:
        w, h, cut = _s(124), _s(169), _s(16)
        t = np.linspace(0, 1, h)[:, None, None]
        grad = (
            np.array((74, 58, 42))[None, None, :] * (1 - t)
            + np.array((201, 145, 74))[None, None, :] * t
        )
        card = Image.fromarray(np.repeat(grad, w, axis=1).astype(np.uint8), "RGB").convert("RGBA")

        art = Drawer.open_static(item.icon_url)
        if not _is_missing(art):
            art = Drawer.resize_crop(art, (w, h))
            card.alpha_composite(art)

        strip = Image.new("RGBA", (w, _s(34)), (7, 7, 12, round(255 * 0.78)))
        card.alpha_composite(strip, (0, h - _s(34)))
        card.putalpha(
            _poly_mask((w, h), [(0, 0), (w - cut, 0), (w, cut), (w, h), (cut, h), (0, h - cut)])
        )
        self.im.paste(card, (_s(x), _s(y)), card)

        self.text_mid(str(item.pulls), x + 62, y + 169 - 17, 18, 800, align="center")

        if item.result is None:
            return
        result_text, color = {
            FiftyFiftyResult.WON: ("gacha_summary.won", GOLD_LIGHT),
            FiftyFiftyResult.LOST: ("gacha_summary.lost", LOST_RED),
            FiftyFiftyResult.GUARANTEED: ("gacha_summary.guaranteed", _white(0.8)),
        }[item.result]
        text = self.tr(LocaleStr(key=result_text))
        self.text(text, x + 62, y + 169 + 6, 14, 700, color, align="center", max_width=124)

    # Hero

    def _hero_name_lines(self, name: str) -> tuple[list[str], float, float, float]:
        """Lines, font size, line height and max width for the hero name."""
        if self.is_light_cone:
            max_size, max_width, line_height, min_single = 56, 660, 1.08, 56
        else:
            max_size, max_width, line_height, min_single = 92, 700, 1.0, 64

        size = float(max_size)
        while size >= min_single:
            if self.measure(name, size, 700) <= max_width:
                return [name], size, line_height, max_width
            size -= 2

        size = float(min_single)
        while size >= 24:
            lines = self.wrap(name, size, 700, max_width, 2)
            if lines is not None:
                return lines, size, line_height, max_width
            size -= 2
        return [name], 24, line_height, max_width

    def _draw_latest(self, item: GachaSummaryItem) -> None:
        right = WIDTH - PAD_X
        row_top = HEIGHT - 56 - 58
        center = row_top + 29

        pulls_label = self.tr(LocaleStr(key="gacha_summary.pulls"))
        number_baseline = row_top + (1 - CONTENT_H) * 58 / 2 + ASCENT * 58
        pulls_w = self.text(
            pulls_label, right, number_baseline - ASCENT * 20, 20, 600, _white(0.75), align="right"
        )
        num_w = self.text(
            str(item.pulls),
            right - pulls_w - 8,
            row_top,
            58,
            800,
            GOLD_LIGHT,
            align="right",
            line_height=1,
        )
        cursor = right - pulls_w - 8 - num_w - 18

        if item.result is not None:
            cursor = self._draw_result_tag(item.result, cursor, center) - 18
        self.text_mid(
            item.time.strftime("%Y-%m-%d"), cursor, center, 17, 500, _white(0.62), align="right"
        )

        stars_top = row_top - 8 - 10 - 26
        self.stars(right, stars_top, 26)

        lines, size, line_height, max_width = self._hero_name_lines(item.name)
        line_box = size * line_height
        name_top = stars_top - 10 - line_box * len(lines)
        for i, line in enumerate(lines):
            self.text(
                line,
                right,
                name_top + i * line_box,
                size,
                700,
                align="right",
                line_height=line_height,
                max_width=max_width,
            )

        label = self.tr(LocaleStr(key="gacha_summary.latest", rarity="5★")).upper()
        self.text(label, right, name_top - 10 - 20.4, 15, 700, GOLD, align="right", tracking=0.2)

    def _draw_result_tag(self, result: FiftyFiftyResult, right: float, center: float) -> float:
        title = self.summary.win_rate_title or ""
        key, bg = {
            FiftyFiftyResult.WON: ("gacha_summary.won_title", GOLD),
            FiftyFiftyResult.LOST: ("gacha_summary.lost_title", LOST_RED),
            FiftyFiftyResult.GUARANTEED: ("gacha_summary.guaranteed", _white(0.85)),
        }[result]
        text = self.tr(LocaleStr(key=key, title=title))
        width = self.measure(text, 17, 800) + 40
        left, top = right - width, center - 19
        w, h, slant = _s(width), _s(38), _s(10)
        mask = _poly_mask((w, h), [(slant, 0), (w, 0), (w - slant, h), (0, h)])
        self.fill_mask(bg[:3], mask, _s(left), _s(top))
        self.text_mid(text, left + width / 2, center, 17, 800, TAG_TEXT, align="center")
        return left
