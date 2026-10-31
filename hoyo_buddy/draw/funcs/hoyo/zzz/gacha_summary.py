from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, NamedTuple

import aiohttp
import hakushin
import numpy as np
from loguru import logger
from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import WHITE, Drawer
from hoyo_buddy.enums import FiftyFiftyResult, GachaItemKind, Game, Locale
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from io import BytesIO

    from PIL import ImageFont

    from hoyo_buddy.models.gacha_summary import GachaRank, GachaSummary, GachaSummaryItem
    from hoyo_buddy.types import FontStyle

type RGB = tuple[int, int, int]
type Box = tuple[float, float, float, float]

# The design is laid out in CSS px on a 1600x900 canvas and rendered at 2x
SCALE = 2
WIDTH, HEIGHT = 1600, 900
SUPERSAMPLE = 4

# Nunito metrics (per em), used to place text the way a browser does
ASCENT = 1.011
NORMAL_LINE_HEIGHT = 1.364

BG: RGB = (11, 11, 11)
PANEL: RGB = (24, 24, 24)
PANEL_BORDER: RGB = (46, 46, 46)
CHIP: RGB = (34, 34, 34)
CHIP_BORDER: RGB = (58, 58, 58)
PLATE: RGB = (30, 30, 30)
AVATAR_BG: RGB = (42, 42, 42)
ACCENT: RGB = (220, 255, 61)
S_RANK_COLOR: RGB = (255, 177, 59)
A_RANK_COLOR: RGB = (197, 139, 255)
LOST_COLOR: RGB = (255, 138, 110)

LEFT = 64
CONTENT_WIDTH = 800
CONTENT_RIGHT = LEFT + CONTENT_WIDTH
STRIPE_ANGLE = math.radians(14)

KIND_KEYS: dict[GachaItemKind, str] = {
    GachaItemKind.CHARACTER: "agent",
    GachaItemKind.WEAPON: "roles_weapon",
    GachaItemKind.BANGBOO: "bangboo",
}

ASSET_FOLDER = "gacha-summary"


def _s(value: float) -> int:
    return round(value * SCALE)


def _baseline(top: float, size: float, line_height: float = NORMAL_LINE_HEIGHT) -> float:
    """Baseline of a line box that starts at `top`."""
    return top + ((line_height - NORMAL_LINE_HEIGHT) / 2 + ASCENT) * size


def _center_baseline(center_y: float, size: float) -> float:
    """Baseline of a line box that is vertically centered on `center_y`."""
    return center_y + (ASCENT - NORMAL_LINE_HEIGHT / 2) * size


def _mix(color: RGB, opacity: float, background: RGB = BG) -> RGB:
    return Drawer.blend_color(color, background, opacity)


def _rgba(color: RGB, alpha: int = 255) -> tuple[int, int, int, int]:
    return (*color, alpha)


def _scale_alpha(mask: Image.Image, factor: float) -> Image.Image:
    return Image.fromarray((np.asarray(mask) * factor).astype(np.uint8))


def _fit(image: Image.Image, width: int, height: int) -> Image.Image:
    ratio = min(width / image.width, height / image.height)
    size = (max(1, round(image.width * ratio)), max(1, round(image.height * ratio)))
    return image.resize(size, Image.Resampling.LANCZOS)


def _sticker(image: Image.Image, *, outline: int, shadow: tuple[int, int]) -> Image.Image:
    """Add a white outline and a hard drop shadow, returns an image padded by outline + shadow."""
    pad = outline + max(shadow)
    alpha = np.pad(np.asarray(image.getchannel("A")), pad)
    dilated = alpha.copy()
    for dx in range(-outline, outline + 1):
        for dy in range(-outline, outline + 1):
            if (dx or dy) and dx * dx + dy * dy <= outline * outline:
                dilated = np.maximum(dilated, np.roll(alpha, (dy, dx), axis=(0, 1)))

    height, width = dilated.shape
    sx, sy = shadow
    shadow_alpha = np.zeros_like(dilated)
    shadow_alpha[sy:, sx:] = dilated[: height - sy, : width - sx]

    result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    result.putalpha(Image.fromarray((shadow_alpha * 0.5).astype(np.uint8)))
    border = Image.new("RGBA", (width, height), _rgba(WHITE))
    border.putalpha(Image.fromarray((dilated * 0.85).astype(np.uint8)))
    result.alpha_composite(border)
    result.alpha_composite(image, (pad, pad))
    return result


def _shape_mask(size: tuple[int, int], draw_shape: _ShapeDrawer) -> Image.Image:
    """Draw an anti-aliased L mask by supersampling."""
    mask = Image.new("L", (size[0] * SUPERSAMPLE, size[1] * SUPERSAMPLE), 0)
    draw_shape(ImageDraw.Draw(mask), SUPERSAMPLE)
    return mask.resize(size, Image.Resampling.BOX)


class _ShapeDrawer:
    """Draws a shape scaled by a factor onto a mask."""

    def __init__(self, kind: str, points: list[tuple[float, float]], radius: float = 0) -> None:
        self.kind = kind
        self.points = points
        self.radius = radius

    def __call__(self, draw: ImageDraw.ImageDraw, factor: int) -> None:
        points = [(x * factor, y * factor) for x, y in self.points]
        if self.kind == "polygon":
            draw.polygon(points, fill=255)
        else:
            (x0, y0), (x1, y1) = points
            draw.rounded_rectangle((x0, y0, x1 - 1, y1 - 1), radius=self.radius * factor, fill=255)


class _Stat(NamedTuple):
    label: str
    value: str
    extra: str | None = None
    extra_color: RGB = ACCENT
    currency: bool = False


async def resolve_zzz_gacha_summary_art(
    summary: GachaSummary, session: aiohttp.ClientSession
) -> None:
    """Fill art_url and icon_url of summary.latest and summary.previous."""
    items = [summary.latest, *summary.previous] if summary.latest else list(summary.previous)
    if not items:
        return

    kinds = {item.kind for item in items}
    urls: dict[tuple[GachaItemKind, int], tuple[str, str]] = {}

    try:
        async with hakushin.HakushinAPI(hakushin.Game.ZZZ, session=session) as api:
            if GachaItemKind.CHARACTER in kinds:
                for agent in await api.fetch_characters():
                    urls[GachaItemKind.CHARACTER, agent.id] = (agent.image, agent.icon)
            if GachaItemKind.WEAPON in kinds:
                for weapon in await api.fetch_weapons():
                    urls[GachaItemKind.WEAPON, weapon.id] = (weapon.icon, weapon.icon)
            if GachaItemKind.BANGBOO in kinds:
                for bangboo in await api.fetch_bangboos():
                    urls[GachaItemKind.BANGBOO, bangboo.id] = (bangboo.icon, bangboo.icon)
    except (hakushin.errors.HakushinError, aiohttp.ClientError, TimeoutError):
        logger.exception("Failed to fetch ZZZ gacha summary art")

    for item in items:
        item_urls = urls.get((item.kind, item.item_id))
        if item_urls is not None:
            item.art_url, item.icon_url = item_urls


class ZZZGachaSummaryCard:
    _im: Image.Image
    _drawer: Drawer

    def __init__(self, summary: GachaSummary, *, locale: Locale) -> None:
        self.summary = summary
        self.locale = locale

    def draw(self) -> BytesIO:
        self._im = Image.new("RGBA", (_s(WIDTH), _s(HEIGHT)), _rgba(BG))
        self._drawer = self._make_drawer(self._im)

        self._draw_backdrop()
        self._draw_hero()
        self._draw_watermark()
        self._draw_header()

        bottom = self._draw_title_block(124)
        bottom = self._draw_pity_panels(bottom + 20)
        self._draw_stats(bottom + 20)
        self._draw_previous()

        return Drawer.save_image(self._im.convert("RGB"))

    # Helpers

    def _make_drawer(self, image: Image.Image) -> Drawer:
        return Drawer(
            ImageDraw.Draw(image), folder=ASSET_FOLDER, dark_mode=True, locale=self.locale
        )

    def _t(self, key: str, **kwargs: Any) -> str:
        return LocaleStr(key=key, **kwargs).translate(self.locale)

    @property
    def _s_rank(self) -> str:
        return self._t("gacha_summary.s_rank")

    @property
    def _a_rank(self) -> str:
        return self._t("gacha_summary.a_rank")

    @staticmethod
    def _font_locale(text: str) -> Locale:
        """Digits and symbols should use the Latin display font, not the user locale's."""
        return Drawer.detect_locale_from_text(text) or Locale.american_english

    def _font(self, text: str, size: float, style: FontStyle) -> ImageFont.FreeTypeFont:
        return self._drawer.get_font(_s(size), style, locale=self._font_locale(text))

    def _width(self, text: str, size: float, style: FontStyle) -> float:
        return self._font(text, size, style).getlength(text) / SCALE

    def _write(
        self,
        text: str,
        *,
        x: float,
        baseline: float,
        size: float,
        style: FontStyle,
        color: RGB = WHITE,
        anchor: str = "ls",
        max_width: float | None = None,
        shrink: bool = True,
        drawer: Drawer | None = None,
    ) -> float:
        """Write a line of text and return its right edge (pen position) in CSS px."""
        dynamic = shrink and max_width is not None
        bbox = (drawer or self._drawer).write(
            text,
            size=_s(size),
            position=(x * SCALE, baseline * SCALE),
            color=color,
            style=style,
            anchor=anchor,
            max_width=_s(max_width) if max_width is not None else None,
            dynamic_fontsize=dynamic,
            locale=self._font_locale(text),
        )
        if max_width is not None or anchor != "ls":
            return bbox.right / SCALE
        return x + self._width(text, size, style)

    def _write_tracked(
        self,
        text: str,
        *,
        x: float,
        baseline: float,
        size: float,
        color: RGB,
        tracking: float,
        style: FontStyle = "black_italic",
    ) -> float:
        """Write text with letter spacing (in em) and return its right edge in CSS px."""
        spacing = size * tracking * SCALE
        cursor = x * SCALE
        for char in text:
            font = self._font(char, size, style)
            self._drawer.draw.text(
                (cursor, baseline * SCALE), char, font=font, fill=color, anchor="ls"
            )
            cursor += font.getlength(char) + spacing
        return (cursor - spacing) / SCALE

    def _paste(self, image: Image.Image, x: float, y: float) -> None:
        """Alpha composite an image at device px, allowing negative offsets."""
        left, top = round(x), round(y)
        crop_x, crop_y = max(0, -left), max(0, -top)
        if crop_x >= image.width or crop_y >= image.height:
            return
        if crop_x or crop_y:
            image = image.crop((crop_x, crop_y, image.width, image.height))
        self._im.alpha_composite(image, (left + crop_x, top + crop_y))

    def _fill_mask(self, color: RGB, origin: tuple[int, int], mask: Image.Image) -> None:
        self._im.paste(_rgba(color), origin, mask)

    def _rounded_rect(
        self,
        box: Box,
        radius: float,
        fill: RGB,
        *,
        border: RGB | None = None,
        border_width: float = 0,
        opacity: float = 1.0,
    ) -> None:
        x0, y0, x1, y1 = (v * SCALE for v in box)
        ix, iy = math.floor(x0), math.floor(y0)
        size = (math.ceil(x1) - ix, math.ceil(y1) - iy)

        def mask(inset: float) -> Image.Image:
            inset *= SCALE
            shape = _ShapeDrawer(
                "rect",
                [(x0 - ix + inset, y0 - iy + inset), (x1 - ix - inset, y1 - iy - inset)],
                radius=max(0, radius * SCALE - inset),
            )
            result = _shape_mask(size, shape)
            if opacity < 1:
                result = _scale_alpha(result, opacity)
            return result

        if border is not None:
            self._fill_mask(border, (ix, iy), mask(0))
            self._fill_mask(fill, (ix, iy), mask(border_width))
        else:
            self._fill_mask(fill, (ix, iy), mask(0))

    def _rank_text(self, rank: GachaRank | None) -> str | None:
        if rank is None:
            return None
        percent = max(round(rank.percent, 1), 0.1)
        return self._t("top_percent", percent=f"{percent:g}")

    def _result_text(self, result: FiftyFiftyResult, *, with_title: bool) -> str:
        title = self.summary.win_rate_title
        if result is FiftyFiftyResult.GUARANTEED:
            return self._t("gacha_summary.guaranteed")
        if with_title and title is not None:
            key = "won_title" if result is FiftyFiftyResult.WON else "lost_title"
            return self._t(f"gacha_summary.{key}", title=title)
        return self._t(f"gacha_summary.{result.value}")

    @staticmethod
    def _result_color(result: FiftyFiftyResult) -> RGB:
        if result is FiftyFiftyResult.WON:
            return ACCENT
        if result is FiftyFiftyResult.LOST:
            return LOST_COLOR
        return WHITE

    # Right side

    def _draw_backdrop(self) -> None:
        dots = Image.new("L", self._im.size, 0)
        draw = ImageDraw.Draw(dots)
        step, radius = _s(14), 2.3 * SCALE
        alpha = round(255 * 0.09)
        for cx in range(_s(820) + step // 2, self._im.width, step):
            for cy in range(step // 2, self._im.height, step):
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=alpha)
        self._im.paste(_rgba(WHITE), (0, 0), dots)

        self._draw_stripe(1060, 300)
        self._draw_stripe(1010, 18)

    def _draw_stripe(self, left: float, width: float) -> None:
        """A 1400px tall stripe starting at y=-200, rotated 14deg around its center."""
        cx, cy = (left + width / 2) * SCALE, 500 * SCALE
        ys, xs = np.mgrid[0 : self._im.height, 0 : self._im.width].astype(np.float32)
        dist = (xs - cx) * math.cos(STRIPE_ANGLE) + (ys - cy) * math.sin(STRIPE_ANGLE)
        coverage = np.clip(width * SCALE / 2 - np.abs(dist) + 0.5, 0, 1)
        self._fill_mask(ACCENT, (0, 0), Image.fromarray((coverage * 255).astype(np.uint8)))

    def _draw_outlined_text(self, text: str, *, top: float, size: float) -> None:
        font = self._font(text, size, "black_italic")
        mask = Image.new("L", self._im.size, 0)
        ImageDraw.Draw(mask).text(
            (_s(820), _s(_baseline(top, size, 1))),
            text,
            font=font,
            fill=0,
            stroke_width=4,
            stroke_fill=255,
            anchor="ls",
        )
        self._fill_mask(WHITE, (0, 0), _scale_alpha(mask, 0.14))

    def _draw_hero(self) -> None:
        latest = self.summary.latest
        if latest is None:
            return

        if latest.kind is GachaItemKind.CHARACTER:
            self._draw_outlined_text(latest.name.upper(), top=600, size=300)
            box = (900, -10, 684, 960)
        else:
            kind = self._t(KIND_KEYS[latest.kind], mi18n_game=Game.ZZZ)
            self._draw_outlined_text(kind.upper(), top=640, size=230)
            self._draw_glow(1240, 380, 210)
            box = (1005, 145, 470, 470)

        art = Drawer.open_static(latest.art_url)
        if art.getbbox() is None:
            return

        x, y, width, height = box
        art = _fit(art, _s(width), _s(height))
        left = _s(x) + (_s(width) - art.width) / 2
        top = _s(y) + (_s(height) - art.height) / 2
        sticker = _sticker(art, outline=_s(2), shadow=(_s(5), _s(6)))
        pad = _s(2) + _s(6)
        self._paste(sticker, left - pad, top - pad)

    def _draw_glow(self, cx: float, cy: float, radius: float) -> None:
        """Radial dark glow, from 55% black at the center to transparent at 70% of the radius."""
        size = _s(radius * 2)
        ys, xs = np.mgrid[0:size, 0:size].astype(np.float32)
        dist = np.hypot(xs - size / 2, ys - size / 2) / (size / 2 * math.sqrt(2) * 0.7)
        alpha = np.clip(1 - dist, 0, 1) * 0.55 * 255
        glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        glow.putalpha(Image.fromarray(alpha.astype(np.uint8)))
        self._paste(glow, _s(cx - radius), _s(cy - radius))

    def _draw_watermark(self) -> None:
        text = "Hoyo Buddy"
        font = self._drawer.get_font(_s(20), "black_italic", locale=Locale.american_english)
        logo = self._drawer.open_asset("hb_logo.png", size=(_s(44), _s(48)))
        text_x = logo.width + _s(10)
        group = Image.new(
            "RGBA", (text_x + math.ceil(font.getlength(text)) + _s(4), _s(48)), (0, 0, 0, 0)
        )
        group.alpha_composite(logo)
        ImageDraw.Draw(group).text(
            (text_x, _s(_center_baseline(24, 20))), text, font=font, fill=WHITE, anchor="ls"
        )
        group.putalpha(_scale_alpha(group.getchannel("A"), 0.7))
        self._paste(group, _s(WIDTH - 48) - group.width + _s(4), _s(HEIGHT - 40 - 48))

    # Left side

    def _draw_header(self) -> None:
        cy = 72
        self._draw_avatar(LEFT, cy - 24)

        chip_text = self.summary.banner_name
        text_width = min(self._width(chip_text, 16, "bold"), 320)
        chip_left = CONTENT_RIGHT - text_width - 36
        self._rounded_rect(
            (chip_left, cy - 18, CONTENT_RIGHT, cy + 18),
            18,
            CHIP,
            border=CHIP_BORDER,
            border_width=2,
        )
        self._write(
            chip_text,
            x=chip_left + 18,
            baseline=_center_baseline(cy, 16),
            size=16,
            style="bold",
            max_width=text_width,
        )

        uid = f"UID {self.summary.uid}"
        right = self._write(
            self.summary.nickname,
            x=124,
            baseline=_center_baseline(cy, 20),
            size=20,
            style="bold",
            max_width=chip_left - 124 - 24 - self._width(uid, 16, "bold"),
            shrink=False,
        )
        self._write(
            uid,
            x=right + 12,
            baseline=_center_baseline(cy, 16),
            size=16,
            style="bold",
            color=_mix(WHITE, 0.6),
        )

    def _draw_avatar(self, x: float, y: float) -> None:
        ring = _ShapeDrawer("rect", [(0, 0), (_s(48), _s(48))], radius=_s(24))
        self._fill_mask(ACCENT, (_s(x), _s(y)), _shape_mask((_s(48), _s(48)), ring))
        inner = _s(42)
        inner_shape = _ShapeDrawer("rect", [(0, 0), (inner, inner)], radius=inner / 2)
        inner_mask = _shape_mask((inner, inner), inner_shape)
        self._fill_mask(AVATAR_BG, (_s(x + 3), _s(y + 3)), inner_mask)

        avatar = Drawer.open_static(self.summary.avatar_url)
        if avatar.getbbox() is None:
            return
        avatar = Drawer.resize_crop(avatar, (inner, inner))
        avatar.putalpha(
            Image.fromarray(np.minimum(np.asarray(avatar.getchannel("A")), np.asarray(inner_mask)))
        )
        self._paste(avatar, _s(x + 3), _s(y + 3))

    def _draw_title_block(self, top: float) -> float:
        """Draw the latest pull, return the bottom y."""
        title_top = top + 16 * NORMAL_LINE_HEIGHT + 6
        latest = self.summary.latest
        if latest is None:
            return title_top + 104 * 0.95 + 16 + 52

        kind = self._t(KIND_KEYS[latest.kind], mi18n_game=Game.ZZZ)
        self._write_tracked(
            self._t("gacha_summary.latest", rarity=f"{self._s_rank} {kind}").upper(),
            x=LEFT,
            baseline=_baseline(top, 16),
            size=16,
            color=ACCENT,
            tracking=0.14,
        )

        if latest.kind is GachaItemKind.CHARACTER:
            bottom = self._draw_title(latest.name, title_top, size=104, line_height=0.95)
        else:
            bottom = self._draw_title(latest.name, title_top, size=84, line_height=1)
        return self._draw_latest_row(latest, bottom + 16)

    def _draw_title(self, name: str, top: float, *, size: float, line_height: float) -> float:
        min_size = 64
        while size > min_size and self._width(name, size, "black_italic") > CONTENT_WIDTH:
            size -= 2

        lines = [name]
        if self._width(name, size, "black_italic") > CONTENT_WIDTH:
            size = 60
            lines = Drawer.wrap_text(
                name,
                max_width=_s(CONTENT_WIDTH),
                max_lines=2,
                font=self._font(name, size, "black_italic"),
                locale=self._font_locale(name),
            ).split("\n")

        for i, line in enumerate(lines):
            self._write(
                line,
                x=LEFT,
                baseline=_baseline(top + i * size * line_height, size, line_height),
                size=size,
                style="black_italic",
            )
        return top + len(lines) * size * line_height

    def _draw_rank_icon(self, top: float) -> None:
        icon = self._drawer.open_asset("zzz_rank_s.png", size=(_s(50), _s(52)))
        self._paste(icon, _s(LEFT), _s(top))

    def _draw_latest_row(self, latest: GachaSummaryItem, top: float) -> float:
        cy = top + 26
        self._draw_rank_icon(top)

        right = self._write(
            str(latest.pulls),
            x=LEFT + 50 + 16,
            baseline=_center_baseline(cy, 52),
            size=52,
            style="black_italic",
            color=ACCENT,
        )
        right = self._write(
            self._t("gacha_summary.pulls"),
            x=right + 8,
            baseline=_center_baseline(cy, 52),
            size=20,
            style="bold",
            color=_mix(WHITE, 0.75),
        )
        if latest.result is not None:
            right = self._draw_result_sticker(latest.result, right + 16, cy)
        self._write(
            latest.time.strftime("%Y-%m-%d"),
            x=right + 16,
            baseline=_center_baseline(cy, 16),
            size=16,
            style="bold",
            color=_mix(WHITE, 0.6),
        )
        return top + 52

    def _draw_result_sticker(self, result: FiftyFiftyResult, x: float, cy: float) -> float:
        text = self._result_text(result, with_title=True).upper()
        size, padding, height = 18, 18, 40
        width = self._width(text, size, "black_italic") + padding * 2

        shape = _ShapeDrawer("rect", [(0, 0), (_s(width), _s(height))], radius=_s(8))
        sticker = Image.new("RGBA", (_s(width), _s(height)), _rgba(self._result_color(result)))
        sticker.putalpha(_shape_mask(sticker.size, shape))
        self._write(
            text,
            x=padding,
            baseline=_center_baseline(height / 2, size),
            size=size,
            style="black_italic",
            color=BG,
            drawer=self._make_drawer(sticker),
        )

        rotated = sticker.rotate(4, resample=Image.Resampling.BICUBIC, expand=True)
        center_x, center_y = (x + width / 2) * SCALE, cy * SCALE
        self._paste(rotated, center_x - rotated.width / 2, center_y - rotated.height / 2)
        return x + width

    def _next_text(self) -> str | None:
        if self.summary.guaranteed:
            return self._t("gacha_summary.next_is_guaranteed", rarity=self._s_rank)
        if self.summary.win_rate_title is None:
            return None
        return self._t(
            "gacha_summary.next_is", rarity=self._s_rank, title=self.summary.win_rate_title
        )

    def _draw_pity_panels(self, top: float) -> float:
        height = 108.5
        gap = 16
        s_width = (CONTENT_WIDTH - gap) * 3 / 5
        s_box = (LEFT, top, LEFT + s_width, top + height)
        a_box = (LEFT + s_width + gap, top, CONTENT_RIGHT, top + height)

        for box, rarity, color, pity, max_pity, soft_pity in (
            (
                s_box,
                self._s_rank,
                S_RANK_COLOR,
                self.summary.five_star_pity,
                self.summary.five_star_max_pity,
                self.summary.five_star_soft_pity,
            ),
            (
                a_box,
                self._a_rank,
                A_RANK_COLOR,
                self.summary.four_star_pity,
                self.summary.four_star_max_pity,
                None,
            ),
        ):
            self._rounded_rect(box, 18, PANEL, border=PANEL_BORDER, border_width=3)
            inner_left, inner_right = box[0] + 25, box[2] - 25
            header_baseline = _baseline(top + 19, 15)
            label_right = self._write_tracked(
                self._t("gacha_summary.pity", rarity=rarity).upper(),
                x=inner_left,
                baseline=header_baseline,
                size=15,
                color=color,
                tracking=0.1,
            )
            next_text = self._next_text()
            if box is s_box and next_text is not None:
                self._write(
                    next_text,
                    x=inner_right,
                    baseline=header_baseline,
                    size=15,
                    style="bold",
                    color=_mix(WHITE, 0.7, PANEL),
                    anchor="rs",
                    max_width=inner_right - label_right - 16,
                )
            self._draw_pity_row(
                inner_left, inner_right, top + 69.5, pity, max_pity, soft_pity, color
            )

        return top + height

    def _draw_pity_row(
        self,
        left: float,
        right: float,
        cy: float,
        pity: int,
        max_pity: int,
        soft_pity: int | None,
        color: RGB,
    ) -> None:
        baseline = _center_baseline(cy, 40)
        text_right = self._write(
            str(pity), x=left, baseline=baseline, size=40, style="black_italic"
        )
        text_right = self._write(
            f"/{max_pity}",
            x=text_right,
            baseline=baseline,
            size=20,
            style="black_italic",
            color=_mix(WHITE, 0.5, PANEL),
        )

        bar_left = text_right + 16
        bar_width = right - bar_left
        self._rounded_rect((bar_left, cy - 6, right, cy + 6), 6, PANEL_BORDER)
        fill_width = bar_width * min(pity / max_pity, 1) if max_pity else 0
        if fill_width > 0:
            radius = min(6, fill_width / 2)
            self._rounded_rect((bar_left, cy - 6, bar_left + fill_width, cy + 6), radius, color)
        if soft_pity is not None and max_pity:
            marker_x = bar_left + bar_width * soft_pity / max_pity
            self._rounded_rect((marker_x, cy - 11, marker_x + 3, cy + 11), 1.5, WHITE, opacity=0.5)

    def _stats(self) -> list[_Stat]:
        summary = self.summary
        muted = _mix(WHITE, 0.6)
        stats = [
            _Stat(
                self._t("gacha_summary.banner_pulls"),
                f"{summary.banner_pulls:,}",
                f"· {summary.banner_currency:,}" if summary.banner_currency else None,
                muted,
                currency=bool(summary.banner_currency),
            ),
            _Stat(
                self._t("gacha_summary.lifetime_pulls"),
                f"{summary.lifetime_pulls:,}",
                self._rank_text(summary.lifetime_rank),
            ),
        ]
        if summary.win_rate_title is not None:
            label = self._t("gacha_summary.win_rate", title=summary.win_rate_title)
            stats.append(
                _Stat(
                    f"{label} · {summary.fifty_fifty_wins}/{summary.fifty_fifty_total}",
                    f"{round(summary.win_rate, 1):g}%",
                    self._rank_text(summary.win_rate_rank),
                )
            )
        for rarity, avg, total, rank in (
            (
                self._s_rank,
                summary.avg_five_star_pulls,
                summary.total_five_stars,
                summary.five_star_luck_rank,
            ),
            (
                self._a_rank,
                summary.avg_four_star_pulls,
                summary.total_four_stars,
                summary.four_star_luck_rank,
            ),
        ):
            label = self._t("gacha_summary.avg_pulls", rarity=rarity)
            total_text = self._t("gacha_summary.total", total=f"{total:,}")
            stats.append(_Stat(f"{label} · {total_text}", f"{avg:.1f}", self._rank_text(rank)))
        stats.append(
            _Stat(
                self._t("gacha_summary.lifetime_spent"),
                f"{summary.lifetime_currency:,}",
                currency=True,
            )
        )
        return stats

    def _draw_stats(self, top: float) -> None:
        column_width = (CONTENT_WIDTH - 32) / 3
        for i, stat in enumerate(self._stats()):
            row, column = divmod(i, 3)
            x = LEFT + column * (column_width + 16)
            y = top + row * 67.6
            self._draw_stat(stat, x, y, column_width)

    def _draw_stat(self, stat: _Stat, x: float, top: float, width: float) -> None:
        self._write(
            stat.label,
            x=x,
            baseline=_baseline(top, 14),
            size=14,
            style="bold",
            color=_mix(WHITE, 0.6),
            max_width=width,
        )

        baseline = _baseline(top + 14 * NORMAL_LINE_HEIGHT, 30, 1.15)
        right = self._write(stat.value, x=x, baseline=baseline, size=30, style="black_italic")
        icon_gap = 6
        if stat.extra is not None:
            right = self._write(
                stat.extra,
                x=right + self._width(" ", 30, "black_italic"),
                baseline=baseline,
                size=15,
                style="bold",
                color=stat.extra_color,
            )
            icon_gap = 4
        if stat.currency:
            icon = Drawer.open_image(
                "hoyo-buddy-assets/assets/emojis/POLYCHROME.png", size=(_s(22), _s(22))
            )
            self._paste(icon, _s(right + icon_gap), _s(baseline + 3 - 22))

    def _draw_previous(self) -> None:
        items = self.summary.previous[:5]
        if not items:
            return

        top = HEIGHT - 48 - 186.8
        self._write_tracked(
            self._t("gacha_summary.previous", rarity=self._s_rank).upper(),
            x=LEFT,
            baseline=_baseline(top, 15),
            size=15,
            color=ACCENT,
            tracking=0.14,
        )
        icon_top = top + 15 * NORMAL_LINE_HEIGHT + 10
        for i, item in enumerate(items):
            x = LEFT + i * 156
            self._draw_previous_icon(item, x + 6, icon_top)
            self._draw_previous_caption(item, x + 70, icon_top + 125 + 4 + 20 * ASCENT)

    def _draw_previous_icon(self, item: GachaSummaryItem, x: float, top: float) -> None:
        icon = Drawer.open_static(item.icon_url)
        if item.kind is GachaItemKind.CHARACTER and icon.getbbox() is not None:
            self._paste(Drawer.resize_crop(icon, (_s(128), _s(125))), _s(x), _s(top))
            return

        width, height = _s(128), _s(125)
        plate = _ShapeDrawer(
            "polygon", [(width * 0.14, 0), (width, 0), (width * 0.86, height), (0, height)]
        )
        self._fill_mask(PLATE, (_s(x), _s(top)), _shape_mask((width, height), plate))
        if icon.getbbox() is None:
            return
        icon = _fit(icon, _s(112), _s(112))
        self._paste(icon, _s(x) + (width - icon.width) / 2, _s(top) + (height - icon.height) / 2)

    def _draw_previous_caption(self, item: GachaSummaryItem, cx: float, baseline: float) -> None:
        pulls = str(item.pulls)
        if item.result is None:
            parts: list[tuple[str, float, FontStyle, RGB]] = [
                (pulls, 20, "black_italic", WHITE),
                (f" {self._t('gacha_summary.pulls')}", 15, "bold", _mix(WHITE, 0.6)),
            ]
        else:
            parts = [
                (pulls, 20, "black_italic", WHITE),
                (" · ", 15, "bold", WHITE),
                (
                    self._result_text(item.result, with_title=False),
                    15,
                    "bold",
                    self._result_color(item.result),
                ),
            ]

        total = sum(self._width(text, size, style) for text, size, style, _ in parts)
        scale = min(1, 148 / total)
        x = cx - total * scale / 2
        for text, size, style, color in parts:
            x = self._write(
                text, x=x, baseline=baseline, size=size * scale, style=style, color=color
            )
