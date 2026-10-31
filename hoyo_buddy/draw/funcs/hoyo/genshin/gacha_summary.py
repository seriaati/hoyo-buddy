from __future__ import annotations

import functools
import itertools
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal

import aiohttp
import hakushin
import numpy as np
from loguru import logger
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.draw.fonts import (
    DEFAULT_FONT_MAPPING,
    NUNITO_BOLD,
    NUNITO_MEDIUM,
    SUPPORTED_BY_NUNITO,
)
from hoyo_buddy.enums import FiftyFiftyResult, GachaItemKind, Locale
from hoyo_buddy.l10n import LocaleStr, translator

if TYPE_CHECKING:
    from collections.abc import Sequence
    from io import BytesIO

    from hoyo_buddy.models.gacha_summary import GachaRank, GachaSummary, GachaSummaryItem
    from hoyo_buddy.types import FontStyle

type RGB = tuple[int, int, int]
type RGBA = tuple[int, int, int, int]

FOLDER = "gacha-summary"
WIDTH, HEIGHT = 3200, 1800

BG: Final[RGB] = (11, 13, 28)
WHITE: Final[RGB] = (255, 255, 255)
GOLD: Final[RGB] = (211, 188, 142)
GOLD_LIGHT: Final[RGB] = (242, 212, 139)
STAR: Final[RGB] = (255, 204, 50)
LOST: Final[RGB] = (240, 165, 140)
PURPLE_LABEL: Final[RGB] = (199, 169, 240)
PURPLE_BAR: Final[RGB] = (169, 139, 219)
CARD_STRIP: Final[RGB] = (236, 229, 216)
CARD_NUMBER: Final[RGB] = (59, 66, 85)
AVATAR_PLACEHOLDER: Final[RGB] = (42, 49, 87)
ITEM_GRADIENT: Final[tuple[tuple[float, RGB], ...]] = (
    (0.0, (110, 74, 58)),
    (0.55, (184, 122, 63)),
    (1.0, (225, 165, 78)),
)
PITY_GRADIENT: Final[tuple[tuple[float, RGB], ...]] = ((0.0, (184, 137, 74)), (1.0, GOLD_LIGHT))

# Nunito's vertical metrics in em, used to place baselines the way CSS line boxes do
ASCENT, DESCENT = 1.011, 0.353
CONTENT = ASCENT + DESCENT

NUNITO_SEMIBOLD = "hoyo-buddy-assets/fonts/Nunito/Nunito-SemiBold.ttf"
NUNITO_EXTRABOLD = "hoyo-buddy-assets/fonts/Nunito/Nunito-ExtraBold.ttf"
WEIGHT_STYLES: Final[dict[int, FontStyle]] = {600: "medium", 700: "bold", 800: "bold", 900: "black"}
NUNITO_WEIGHT_OVERRIDES: Final[dict[tuple[str, int], str]] = {
    (NUNITO_MEDIUM, 600): NUNITO_SEMIBOLD,
    (NUNITO_BOLD, 800): NUNITO_EXTRABOLD,
}
CJK_LOCALES = {Locale.chinese, Locale.taiwan_chinese, Locale.japanese, Locale.korean}

# Hero
HERO_X = 128
HERO_BOTTOM = 1672
HERO_ROW_HEIGHT = 112
HERO_STARS_HEIGHT = 56
HERO_CENTER = (840, 760)
CHARACTER_ART_POS = (-1360, -292)
CHARACTER_ART_WIDTH = 4400
FADE_END = 1920
WEAPON_ART_HEIGHT = 1720
WEAPON_ART_ANGLE = 32

# Stats column
COL_X, COL_RIGHT = 1800, 3072
COL_WIDTH = COL_RIGHT - COL_X
COL_GAP = 52
PITY_CARD_TOP, PITY_CARD_HEIGHT = 392, 390
GRID_TOP = PITY_CARD_TOP + PITY_CARD_HEIGHT + COL_GAP
GRID_GAP = 40
GRID_CELL_HEIGHT = 174
PREVIOUS_TOP = GRID_TOP + GRID_CELL_HEIGHT * 2 + GRID_GAP + COL_GAP
ITEM_SIZE, ITEM_STRIP, ITEM_GAP = 224, 56, 38


@dataclass(frozen=True, slots=True)
class _Stat:
    label: str
    value: str
    sub: str
    currency_icon: bool = False


@functools.lru_cache(maxsize=128)
def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _baseline(top: float, size: float, line_height: float = CONTENT) -> float:
    """Baseline of a line box that starts at top, line_height is relative to the font size."""
    return top + (line_height - CONTENT) * size / 2 + ASCENT * size


def _center_baseline(center_y: float, size: float) -> float:
    return center_y + (ASCENT - DESCENT) / 2 * size


def _rgba(color: RGB, alpha: float = 1.0) -> RGBA:
    return (*color, round(alpha * 255))


def _rounded_mask(
    size: tuple[int, int], radius: float, *, br_radius: float | None = None
) -> Image.Image:
    ss = 3
    big_size = (size[0] * ss, size[1] * ss)
    box = (0, 0, big_size[0] - 1, big_size[1] - 1)
    mask = Image.new("L", big_size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius * ss, fill=255)
    if br_radius is not None:
        corner = Image.new("L", big_size, 0)
        ImageDraw.Draw(corner).rounded_rectangle(
            box, radius=br_radius * ss, fill=255, corners=(False, False, True, False)
        )
        mask = ImageChops.darker(mask, corner)
    return mask.resize(size, Image.Resampling.LANCZOS)


def _ellipse_mask(diameter: int, *, width: int | None = None) -> Image.Image:
    ss = 3
    mask = Image.new("L", (diameter * ss, diameter * ss), 0)
    box = (0, 0, diameter * ss - 1, diameter * ss - 1)
    if width is None:
        ImageDraw.Draw(mask).ellipse(box, fill=255)
    else:
        ImageDraw.Draw(mask).ellipse(box, outline=255, width=width * ss)
    return mask.resize((diameter, diameter), Image.Resampling.LANCZOS)


def _linear_gradient(
    size: tuple[int, int], angle: float, stops: Sequence[tuple[float, RGB]]
) -> Image.Image:
    """CSS linear-gradient(angle, stops)."""
    w, h = size
    rad = math.radians(angle)
    dx, dy = math.sin(rad), -math.cos(rad)
    length = abs(w * dx) + abs(h * dy)
    ys, xs = np.mgrid[0:h, 0:w]
    t = ((xs - w / 2) * dx + (ys - h / 2) * dy) / length + 0.5
    positions = [p for p, _ in stops]
    channels = [np.interp(t, positions, [c[i] for _, c in stops]) for i in range(3)]
    return Image.fromarray(np.dstack(channels).astype(np.uint8), "RGB")


def _radial_background() -> Image.Image:
    """CSS radial-gradient(ellipse 60% 75% at 26% 46%, ...), computed small then upscaled."""
    w, h = WIDTH // 4, HEIGHT // 4
    ys, xs = np.mgrid[0:h, 0:w]
    t = np.sqrt(((xs - 0.26 * w) / (0.6 * w)) ** 2 + ((ys - 0.46 * h) / (0.75 * h)) ** 2)
    stops = ((0.0, (44, 59, 124)), (0.5, (23, 28, 61)), (0.85, BG))
    positions = [p for p, _ in stops]
    channels = [np.interp(t, positions, [c[i] for _, c in stops]) for i in range(3)]
    small = Image.fromarray(np.dstack(channels).astype(np.uint8), "RGB")
    return small.resize((WIDTH, HEIGHT), Image.Resampling.BICUBIC)


def _radial_mask(radius: int, stops: Sequence[tuple[float, float]]) -> Image.Image:
    """Alpha mask of a radial glow, stops are (distance in px, opacity)."""
    ys, xs = np.mgrid[0 : radius * 2, 0 : radius * 2]
    dist = np.hypot(xs - radius, ys - radius)
    alpha = np.interp(dist, [d for d, _ in stops], [a * 255 for _, a in stops])
    return Image.fromarray(alpha.astype(np.uint8), "L")


def _scale_alpha(mask: Image.Image, alpha: float) -> Image.Image:
    return ImageChops.multiply(mask, Image.new("L", mask.size, round(alpha * 255)))


def _open(url: str, *, size: tuple[int, int] | None = None) -> Image.Image | None:
    """Open a downloaded image, None if it's missing."""
    if not url:
        return None
    image = Drawer.open_static(url, size=size)
    return image if image.getbbox() is not None else None


async def resolve_gi_gacha_summary_art(
    summary: GachaSummary, session: aiohttp.ClientSession
) -> None:
    """Fill art_url and icon_url of summary.latest and summary.previous."""
    items = [summary.latest, *summary.previous] if summary.latest is not None else []
    if not items:
        return

    kinds = {item.kind for item in items}
    icons: dict[str, str] = {}
    try:
        async with hakushin.HakushinAPI(hakushin.Game.GI, session=session) as api:
            if GachaItemKind.CHARACTER in kinds:
                icons.update({c.id: c.icon for c in await api.fetch_characters()})
            if GachaItemKind.WEAPON in kinds:
                icons.update({str(w.id): w.icon for w in await api.fetch_weapons()})
    except (hakushin.errors.HakushinError, aiohttp.ClientError, TimeoutError) as e:
        logger.warning(f"Failed to fetch GI gacha summary art: {e}")
        return

    for item in items:
        icon = icons.get(str(item.item_id))
        if icon is None:
            continue
        item.icon_url = icon
        if item.kind is GachaItemKind.CHARACTER:
            item.art_url = icon.replace("UI_AvatarIcon_", "UI_Gacha_AvatarImg_")
        else:
            item.art_url = icon.replace("UI_EquipIcon_", "UI_Gacha_EquipIcon_")


class GIGachaSummaryCard:
    def __init__(self, summary: GachaSummary, *, locale: Locale) -> None:
        self.summary = summary
        self.locale = locale

    def draw(self) -> BytesIO:
        return _Renderer(self.summary, self.locale).render()


class _Renderer:
    def __init__(self, summary: GachaSummary, locale: Locale) -> None:
        self.summary = summary
        self.locale = locale
        self.im = _radial_background()
        self.draw = ImageDraw.Draw(self.im, "RGBA")
        self.drawer = Drawer(self.draw, folder=FOLDER, dark_mode=True, locale=locale)

    def render(self) -> BytesIO:
        latest = self.summary.latest
        if latest is not None:
            self._draw_hero_art(latest)
        self._draw_fades()
        if latest is not None:
            self._draw_hero_item(latest)

        self._draw_header()
        self._draw_pity_card()
        self._draw_stats()
        self._draw_previous()
        return Drawer.save_image(self.im)

    # Text

    def _t(self, key: str, **kwargs: Any) -> str:
        return translator.translate(LocaleStr(key=key, **kwargs), self.locale)

    def _font(
        self, text: str, size: int, weight: int, *, star: bool = False
    ) -> ImageFont.FreeTypeFont:
        # Nunito has no ★ glyph
        locale = Locale.japanese if star else Drawer.detect_locale_from_text(text) or self.locale
        mapping = self.drawer.find_font_mapping(locale, DEFAULT_FONT_MAPPING)
        if mapping is None:
            mapping = DEFAULT_FONT_MAPPING[SUPPORTED_BY_NUNITO]

        style = WEIGHT_STYLES[weight]
        if style not in mapping:
            style = "bold"
        path = mapping[style]
        return _load_font(NUNITO_WEIGHT_OVERRIDES.get((path, weight), path), size)

    def _runs(self, text: str, size: int, weight: int) -> list[tuple[str, ImageFont.FreeTypeFont]]:
        font = self._font(text.replace("★", ""), size, weight)
        star_font = self._font("★", size, weight, star=True)
        return [
            ("".join(chars), star_font if is_star else font)
            for is_star, chars in itertools.groupby(text, key=lambda c: c == "★")
        ]

    def _measure(self, text: str, size: int, weight: int, tracking: float = 0) -> float:
        if tracking:
            return sum(
                font.getlength(c) + tracking
                for chunk, font in self._runs(text, size, weight)
                for c in chunk
            )
        return sum(font.getlength(chunk) for chunk, font in self._runs(text, size, weight))

    def _truncate(self, text: str, size: int, weight: int, max_width: float) -> str:
        while text and self._measure(f"{text}...", size, weight) > max_width:
            text = text[:-1]
        return f"{text.rstrip()}..."

    def _fit(
        self, text: str, size: int, weight: int, max_width: float, tracking: float = 0
    ) -> tuple[str, int]:
        """Shrink the text down to 70% of its size to fit max_width, then truncate it."""
        min_size = round(size * 0.7)
        while size > min_size and self._measure(text, size, weight, tracking) > max_width:
            size -= 2
        if self._measure(text, size, weight, tracking) > max_width:
            text = self._truncate(text, size, weight, max_width)
        return text, size

    def text(
        self,
        text: str,
        x: float,
        baseline: float,
        *,
        size: int,
        weight: int,
        color: RGB | RGBA,
        anchor: Literal["l", "m", "r"] = "l",
        tracking: float = 0,
        max_width: float | None = None,
    ) -> float:
        """Draw text with its baseline at y, returns its width."""
        if max_width is not None:
            text, size = self._fit(text, size, weight, max_width, tracking)

        width = self._measure(text, size, weight, tracking)
        if anchor == "r":
            x -= width
        elif anchor == "m":
            x -= width / 2

        for chunk, font in self._runs(text, size, weight):
            if not tracking:
                self._draw_run(chunk, x, baseline, font, color)
                x += font.getlength(chunk)
                continue
            for char in chunk:
                self._draw_run(char, x, baseline, font, color)
                x += font.getlength(char) + tracking
        return width

    def _draw_run(
        self, text: str, x: float, baseline: float, font: ImageFont.FreeTypeFont, color: RGB | RGBA
    ) -> None:
        alpha = color[3] if len(color) == 4 else 255
        if alpha == 255:
            self.draw.text((x, baseline), text, font=font, fill=color[:3], anchor="ls")
            return

        # ImageDraw ignores the fill's alpha for text, so draw it through a mask instead
        left, top, right, bottom = font.getbbox(text, anchor="ls")
        if right <= left or bottom <= top:
            return
        mask = Image.new("L", (int(right - left), int(bottom - top)), 0)
        ImageDraw.Draw(mask).text((-left, -top), text, font=font, fill=alpha, anchor="ls")
        self.im.paste(color[:3], (round(x + left), round(baseline + top)), mask)

    def _wrap(self, text: str, size: int, weight: int, max_width: float) -> list[str]:
        locale = Drawer.detect_locale_from_text(text) or self.locale
        cjk = locale in CJK_LOCALES
        tokens = list(text) if cjk else text.split(" ")
        sep = "" if cjk else " "

        lines: list[str] = []
        line = ""
        for token in tokens:
            candidate = f"{line}{sep}{token}" if line else token
            if not line or self._measure(candidate, size, weight) <= max_width:
                line = candidate
            else:
                lines.append(line)
                line = token
        if line:
            lines.append(line)
        return lines

    def _fit_lines(
        self, text: str, candidates: Sequence[tuple[int, int]], weight: int, max_width: float
    ) -> tuple[list[str], int]:
        """Pick the first (size, max lines) candidate the text fits in."""
        for size, max_lines in candidates:
            lines = self._wrap(text, size, weight, max_width)
            if len(lines) <= max_lines and all(
                self._measure(line, size, weight) <= max_width for line in lines
            ):
                return lines, size

        size, max_lines = candidates[-1]
        lines = self._wrap(text, size, weight, max_width)
        if len(lines) > max_lines:
            lines = [*lines[: max_lines - 1], " ".join(lines[max_lines - 1 :])]
        return [
            line
            if self._measure(line, size, weight) <= max_width
            else self._truncate(line, size, weight, max_width)
            for line in lines
        ], size

    # Shapes

    def _paste(
        self,
        xy: tuple[float, float],
        mask: Image.Image,
        fill: RGB | Image.Image,
        alpha: float = 1.0,
    ) -> None:
        if alpha < 1:
            mask = _scale_alpha(mask, alpha)
        source = fill if isinstance(fill, Image.Image) else Image.new("RGB", mask.size, fill)
        self.im.paste(source, (round(xy[0]), round(xy[1])), mask)

    def _paste_image(
        self, image: Image.Image, xy: tuple[float, float], mask: Image.Image | None = None
    ) -> None:
        alpha = image.getchannel("A")
        if mask is not None:
            alpha = ImageChops.multiply(alpha, mask)
        self.im.paste(image.convert("RGB"), (round(xy[0]), round(xy[1])), alpha)

    def _bar(
        self,
        x: float,
        y: float,
        width: float,
        height: int,
        fill: RGB | Image.Image,
        alpha: float = 1.0,
    ) -> None:
        width = round(width)
        if width < height:
            width = height if width > 0 else 0
        if width == 0:
            return
        if isinstance(fill, Image.Image):
            fill = fill.resize((width, height))
        self._paste((x, y), _rounded_mask((width, height), height / 2), fill, alpha)

    def _tag(self, x: float, center_y: float, text: str, bg: RGB, fg: RGB) -> float:
        size, padding, height = 36, 36, 80
        text, size = self._fit(text, size, 800, 900)
        width = round(self._measure(text, size, 800) + padding * 2)
        self._paste((x, center_y - height / 2), _rounded_mask((width, height), height / 2), bg)
        self.text(
            text, x + padding, _center_baseline(center_y, size), size=size, weight=800, color=fg
        )
        return width

    # Hero

    def _draw_hero_art(self, latest: GachaSummaryItem) -> None:
        art = _open(latest.art_url)
        if art is not None and latest.kind is GachaItemKind.CHARACTER:
            scale = CHARACTER_ART_WIDTH / art.width
            left, top = -CHARACTER_ART_POS[0] / scale, -CHARACTER_ART_POS[1] / scale
            right, bottom = left + FADE_END / scale, top + HEIGHT / scale
            region = art.crop((round(left), round(top), round(right), round(bottom)))
            self._paste_image(region.resize((FADE_END, HEIGHT), Image.Resampling.BICUBIC), (0, 0))
            return

        self._draw_glow()
        if art is not None:
            size = (round(art.width * WEAPON_ART_HEIGHT / art.height), WEAPON_ART_HEIGHT)
            art = art.resize(size, Image.Resampling.LANCZOS)
            art = art.rotate(-WEAPON_ART_ANGLE, Image.Resampling.BICUBIC, expand=True)
        else:
            art = _open(latest.icon_url, size=(640, 640))
        if art is None:
            self._draw_hero_fate()
            return
        self._paste_image(art, (HERO_CENTER[0] - art.width / 2, HERO_CENTER[1] - art.height / 2))

    def _draw_hero_fate(self) -> None:
        icon = self.drawer.open_asset(self._banner_icon(), size=(560, 560))
        self._paste_image(icon, (HERO_CENTER[0] - 280, HERO_CENTER[1] - 280))

    def _draw_glow(self) -> None:
        cx, cy = HERO_CENTER
        glow = _radial_mask(674, ((0, 0.32), (446, 0.08), (674, 0)))
        self._paste((cx - 674, cy - 674), glow, GOLD_LIGHT)
        for radius, width, alpha in ((500, 4, 0.22), (380, 2, 0.14)):
            ring = _ellipse_mask(radius * 2, width=width)
            self._paste((cx - radius, cy - radius), ring, GOLD_LIGHT, alpha)

    def _draw_fades(self) -> None:
        horizontal = np.interp(np.arange(WIDTH) / WIDTH, [0, 0.36, 0.52, 0.6], [0, 0, 0.88, 1])
        vertical = np.interp(np.arange(HEIGHT), [HEIGHT - 720, HEIGHT], [0, 0.95])
        alpha = 1 - (1 - horizontal[None, :]) * (1 - vertical[:, None])
        mask = Image.fromarray((alpha * 255).astype(np.uint8), "L")
        self.im.paste(BG, (0, 0, WIDTH, HEIGHT), mask)

    def _draw_scrim(self, top: float, right: float) -> None:
        """Soft dark backdrop behind the hero text so it stays readable over bright art."""
        scale = 4
        mask = Image.new("L", (WIDTH // scale, HEIGHT // scale), 0)
        box = (-64, top / scale, right / scale, HEIGHT / scale + 64)
        ImageDraw.Draw(mask).rounded_rectangle(box, radius=48, fill=round(255 * 0.7))
        mask = mask.filter(ImageFilter.GaussianBlur(28))
        self.im.paste(BG, (0, 0, WIDTH, HEIGHT), mask.resize((WIDTH, HEIGHT)))

    def _draw_stars(self, top: float) -> None:
        self.text(
            "★" * 5, HERO_X, _baseline(top, 56, 1), size=50, weight=900, color=STAR, tracking=8
        )

    def _draw_hero_item(self, item: GachaSummaryItem) -> None:
        row_top = HERO_BOTTOM - HERO_ROW_HEIGHT
        row_cy = row_top + HERO_ROW_HEIGHT / 2
        stars_top = row_top - 40 - HERO_STARS_HEIGHT

        if item.kind is GachaItemKind.WEAPON:
            candidates = [(s, 2) for s in range(124, 79, -4)]
            max_width, line_height = 1520, 1.05
        else:
            candidates = [(s, 1) for s in range(176, 119, -4)]
            candidates += [(s, 2) for s in range(120, 79, -4)]
            max_width, line_height = 1440, 1.0
        lines, size = self._fit_lines(item.name, candidates, 900, max_width)
        if len(lines) > 1:
            line_height = max(line_height, 1.1)
        line_px = size * line_height
        name_top = stars_top - 24 - line_px * len(lines)

        label = self._t("gacha_summary.latest", rarity="5★").upper()
        label_size = 32
        label_tracking = label_size * 0.18
        label_top = name_top - 24 - CONTENT * label_size
        text_width = max(
            self._measure(label, label_size, 800, label_tracking),
            *(self._measure(line, size, 900) for line in lines),
        )
        self._draw_scrim(label_top - 160, HERO_X + min(text_width, max_width) + 200)

        self.text(
            label,
            HERO_X,
            _baseline(label_top, label_size),
            size=label_size,
            weight=800,
            color=GOLD,
            tracking=label_tracking,
            max_width=max_width,
        )
        for i, line in enumerate(lines):
            baseline = _baseline(name_top + i * line_px, size, line_height)
            self.text(line, HERO_X, baseline, size=size, weight=900, color=WHITE)
        self._draw_stars(stars_top)

        baseline = _baseline(row_top, 112, 1)
        x = HERO_X
        x += self.text(str(item.pulls), x, baseline, size=112, weight=900, color=GOLD_LIGHT) + 16
        pulls = self._t("gacha_summary.pulls")
        x += self.text(pulls, x, baseline, size=44, weight=700, color=_rgba(WHITE, 0.75)) + 40

        title = self.summary.win_rate_title
        if item.result is not None and title is not None:
            x += self._draw_result_tag(x, row_cy, item.result, title) + 40

        date = item.time.strftime("%Y-%m-%d")
        self.text(
            date, x, _center_baseline(row_cy, 36), size=36, weight=600, color=_rgba(WHITE, 0.62)
        )

    def _draw_result_tag(
        self, x: float, center_y: float, result: FiftyFiftyResult, title: str
    ) -> float:
        if result is FiftyFiftyResult.WON:
            text, bg, fg = self._t("gacha_summary.won_title", title=title), GOLD_LIGHT, (46, 35, 16)
        elif result is FiftyFiftyResult.LOST:
            text, bg, fg = self._t("gacha_summary.lost_title", title=title), LOST, (59, 27, 16)
        else:
            text, bg, fg = self._t("gacha_summary.guaranteed"), CARD_STRIP, CARD_NUMBER
        return self._tag(x, center_y, text, bg, fg)

    # Stats column

    def _banner_icon(self) -> str:
        # Beginners' and Standard Wish use Acquaint Fate
        if self.summary.banner_type in {100, 200}:
            return "gi_acquaint_fate.png"
        return "gi_intertwined_fate.png"

    def _draw_header(self) -> None:
        summary = self.summary
        top = 112
        self._paste((COL_X, top), _ellipse_mask(112), GOLD)
        self._paste((COL_X + 4, top + 4), _ellipse_mask(104), AVATAR_PLACEHOLDER)
        avatar = _open(summary.avatar_url, size=(104, 104))
        if avatar is not None:
            self._paste_image(avatar, (COL_X + 4, top + 4), _ellipse_mask(104))

        logo_width = self._draw_logo(top + 56)

        text_x = COL_X + 112 + 28
        text_top = top + (112 - CONTENT * (40 + 30)) / 2
        max_width = COL_RIGHT - logo_width - 40 - text_x
        self.text(
            summary.nickname,
            text_x,
            _baseline(text_top, 40),
            size=40,
            weight=800,
            color=WHITE,
            max_width=max_width,
        )
        self.text(
            f"UID {summary.uid}",
            text_x,
            _baseline(text_top + CONTENT * 40, 30),
            size=30,
            weight=600,
            color=_rgba(WHITE, 0.62),
        )

        title_cy = 296
        icon = self.drawer.open_asset(self._banner_icon(), size=(88, 88))
        self._paste_image(icon, (COL_X, title_cy - 44))
        self.text(
            summary.banner_name,
            COL_X + 88 + 24,
            _center_baseline(title_cy, 76),
            size=76,
            weight=900,
            color=WHITE,
            max_width=COL_RIGHT - COL_X - 112,
        )

    def _draw_logo(self, center_y: float) -> float:
        text_width = self.text(
            "Hoyo Buddy",
            COL_RIGHT,
            _center_baseline(center_y, 36),
            size=36,
            weight=800,
            color=_rgba(WHITE, 0.6),
            anchor="r",
        )
        logo = self.drawer.open_asset("hb_logo.png", size=(74, 80))
        logo.putalpha(_scale_alpha(logo.getchannel("A"), 0.6))
        self._paste_image(logo, (COL_RIGHT - text_width - 20 - 74, center_y - 40))
        return text_width + 20 + 74

    def _draw_pity_card(self) -> None:
        summary = self.summary
        top, height = PITY_CARD_TOP, PITY_CARD_HEIGHT
        outer = _rounded_mask((COL_WIDTH, height), 32)
        inner = _rounded_mask((COL_WIDTH - 4, height - 4), 30)
        self._paste((COL_X, top), outer, GOLD, 0.3)
        self._paste((COL_X + 2, top + 2), inner, BG)
        self._paste((COL_X + 2, top + 2), inner, WHITE, 0.05)

        left, right = COL_X + 50, COL_RIGHT - 50
        y = top + 2 + 44
        label = self._t("gacha_summary.pity", rarity="5★").upper()
        self.text(label, left, _baseline(y, 30), size=30, weight=800, color=GOLD, tracking=3.6)
        number_top = y + CONTENT * 30 + 4
        baseline = _baseline(number_top, 120, 1)
        x = left + self.text(
            str(summary.five_star_pity), left, baseline, size=120, weight=900, color=GOLD_LIGHT
        )
        self.text(
            f"/ {summary.five_star_max_pity}",
            x + 12,
            baseline,
            size=52,
            weight=700,
            color=_rgba(WHITE, 0.55),
        )
        row_bottom = number_top + 120
        self._draw_next_five_star(right, row_bottom)

        bar_top = row_bottom + 32
        max_pity = summary.five_star_max_pity or 1
        self._bar(left, bar_top, right - left, 20, WHITE, 0.1)
        fill = _linear_gradient((256, 20), 90, PITY_GRADIENT)
        self._bar(
            left, bar_top, (right - left) * min(summary.five_star_pity / max_pity, 1), 20, fill
        )
        if summary.five_star_soft_pity is not None:
            marker_x = left + (right - left) * summary.five_star_soft_pity / max_pity
            self.draw.rectangle(
                (marker_x - 2, bar_top - 10, marker_x + 1, bar_top + 29), fill=_rgba(WHITE, 0.5)
            )

        self._draw_four_star_row(left, right, bar_top + 20 + 32 + CONTENT * 36 / 2)

    def _draw_next_five_star(self, right: float, bottom: float) -> None:
        summary = self.summary
        title = summary.win_rate_title
        if title is None and not summary.guaranteed:
            return

        if summary.guaranteed:
            value, color = self._t("gacha_summary.guaranteed"), GOLD_LIGHT
        else:
            value, color = self._t("gacha_summary.next_not_guaranteed", title=title), WHITE
        value_top = bottom - CONTENT * 40
        self.text(
            value,
            right,
            _baseline(value_top, 40),
            size=40,
            weight=800,
            color=color,
            anchor="r",
            max_width=640,
        )
        label = self._t("gacha_summary.next", rarity="5★")
        self.text(
            label,
            right,
            _baseline(value_top - 8 - CONTENT * 30, 30),
            size=30,
            weight=600,
            color=_rgba(WHITE, 0.62),
            anchor="r",
            max_width=640,
        )

    def _draw_four_star_row(self, left: float, right: float, center_y: float) -> None:
        summary = self.summary
        label = self._t("gacha_summary.pity", rarity="4★").upper()
        label_width = self.text(
            label,
            left,
            _center_baseline(center_y, 30),
            size=30,
            weight=800,
            color=PURPLE_LABEL,
            max_width=300,
        )
        baseline = _center_baseline(center_y, 36)
        max_text = f" / {summary.four_star_max_pity}"
        max_width = self.text(
            max_text, right, baseline, size=36, weight=700, color=_rgba(WHITE, 0.55), anchor="r"
        )
        pity_width = self.text(
            str(summary.four_star_pity),
            right - max_width,
            baseline,
            size=36,
            weight=800,
            color=WHITE,
            anchor="r",
        )

        bar_left = left + max(184, label_width) + 32
        bar_width = right - max_width - pity_width - 32 - bar_left
        self._bar(bar_left, center_y - 6, bar_width, 12, WHITE, 0.1)
        ratio = min(summary.four_star_pity / (summary.four_star_max_pity or 1), 1)
        self._bar(bar_left, center_y - 6, bar_width * ratio, 12, PURPLE_BAR)

    def _rank(self, rank: GachaRank | None) -> list[str]:
        if rank is None:
            return []
        return [self._t("top_percent", percent=rank.percent)]

    def _stats(self) -> list[_Stat]:
        s = self.summary
        currency = self._t("diary_primogems")
        banner = _Stat(
            self._t("gacha_summary.banner_pulls"),
            f"{s.banner_pulls:,}",
            f"{s.banner_currency:,}",
            currency_icon=True,
        )
        lifetime = _Stat(
            self._t("gacha_summary.lifetime_pulls"),
            f"{s.lifetime_pulls:,}",
            " · ".join(self._rank(s.lifetime_rank)),
        )
        spent = _Stat(
            self._t("gacha_summary.lifetime_spent"),
            f"{s.lifetime_currency:,}",
            currency,
            currency_icon=True,
        )
        averages = [
            _Stat(
                self._t("gacha_summary.avg_pulls", rarity=f"{rarity}★"),
                f"{avg:.1f}" if total else "-",
                " · ".join([self._t("gacha_summary.total", total=total), *self._rank(rank)]),
            )
            for rarity, avg, total, rank in (
                (5, s.avg_five_star_pulls, s.total_five_stars, s.five_star_luck_rank),
                (4, s.avg_four_star_pulls, s.total_four_stars, s.four_star_luck_rank),
            )
        ]
        if s.win_rate_title is None:
            return [banner, lifetime, spent, *averages]

        win_rate = _Stat(
            self._t("gacha_summary.win_rate", title=s.win_rate_title),
            f"{s.win_rate:.1f}%",
            " · ".join(
                [
                    self._t(
                        "gacha_summary.wins_of_total",
                        wins=s.fifty_fifty_wins,
                        total=s.fifty_fifty_total,
                    ),
                    *self._rank(s.win_rate_rank),
                ]
            ),
        )
        return [banner, lifetime, win_rate, *averages, spent]

    def _draw_stats(self) -> None:
        cell_width = (COL_WIDTH - GRID_GAP * 2) / 3
        icon = self.drawer.open_asset("PRIMOGEM.png", folder="emojis", size=(36, 36))
        for i, stat in enumerate(self._stats()):
            x = COL_X + (i % 3) * (cell_width + GRID_GAP)
            top = GRID_TOP + (i // 3) * (GRID_CELL_HEIGHT + GRID_GAP)
            self.text(
                stat.label,
                x,
                _baseline(top, 30),
                size=30,
                weight=700,
                color=_rgba(WHITE, 0.62),
                max_width=cell_width,
            )
            value_top = top + CONTENT * 30 + 4
            self.text(
                stat.value,
                x,
                _baseline(value_top, 64),
                size=64,
                weight=900,
                color=WHITE,
                max_width=cell_width,
            )
            sub_top = value_top + CONTENT * 64 + 4
            sub_x = x
            if stat.currency_icon:
                self._paste_image(icon, (x, sub_top + CONTENT * 28 / 2 - 18))
                sub_x += 36 + 8
            self.text(
                stat.sub,
                sub_x,
                _baseline(sub_top, 28),
                size=28,
                weight=600 if stat.currency_icon else 700,
                color=_rgba(WHITE, 0.62) if stat.currency_icon else GOLD,
                max_width=x + cell_width - sub_x,
            )

    def _draw_previous(self) -> None:
        items = self.summary.previous
        if not items:
            return

        label = self._t("gacha_summary.previous", rarity="5★").upper()
        self.text(
            label, COL_X, _baseline(PREVIOUS_TOP, 30), size=30, weight=800, color=GOLD, tracking=3.6
        )
        card_top = round(PREVIOUS_TOP + CONTENT * 30 + 24)
        for i, item in enumerate(items[:5]):
            x = COL_X + i * (ITEM_SIZE + ITEM_GAP)
            self._paste_image(self._item_card(item), (x, card_top))

            title = self.summary.win_rate_title
            if item.result is None or title is None:
                continue
            if item.result is FiftyFiftyResult.WON:
                text, color = self._t("gacha_summary.won"), _rgba(GOLD_LIGHT)
            elif item.result is FiftyFiftyResult.LOST:
                text, color = self._t("gacha_summary.lost"), _rgba(LOST)
            else:
                text, color = self._t("gacha_summary.guaranteed"), _rgba(WHITE, 0.8)
            self.text(
                text,
                x + ITEM_SIZE / 2,
                _baseline(card_top + ITEM_SIZE + ITEM_STRIP + 12, 28),
                size=28,
                weight=800,
                color=color,
                anchor="m",
                max_width=ITEM_SIZE + ITEM_GAP - 8,
            )

    def _item_card(self, item: GachaSummaryItem) -> Image.Image:
        height = ITEM_SIZE + ITEM_STRIP
        card = Image.new("RGB", (ITEM_SIZE, height), CARD_STRIP)
        card.paste(_linear_gradient((ITEM_SIZE, ITEM_SIZE), 160, ITEM_GRADIENT), (0, 0))
        icon = _open(item.icon_url, size=(ITEM_SIZE, ITEM_SIZE))
        if icon is not None:
            card.paste(icon, (0, 0), icon)

        card_draw = ImageDraw.Draw(card)
        font = self._font(str(item.pulls), 32, 900)
        card_draw.text(
            (ITEM_SIZE / 2, ITEM_SIZE + ITEM_STRIP / 2),
            str(item.pulls),
            font=font,
            fill=CARD_NUMBER,
            anchor="mm",
        )
        card = card.convert("RGBA")
        card.putalpha(_rounded_mask((ITEM_SIZE, height), 20, br_radius=52))
        return card
