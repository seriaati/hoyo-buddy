from __future__ import annotations

import colorsys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import genshin
import hakushin
import numpy as np
from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import BLACK, WHITE, Drawer
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    import io
    from collections.abc import Iterator

    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import HardChallengeMode

type RGB = tuple[int, int, int]

INK: RGB = (22, 23, 26)


@dataclass(frozen=True, kw_only=True)
class Theme:
    ground: RGB
    text: RGB
    line: RGB
    """Mixed into the band tint for dividers, borders and subtle fills."""
    fallback_colors: tuple[RGB, RGB]
    header_muted: float
    muted: float
    divider: float
    avatar_fill: float
    tag_fill: tuple[RGB, float]
    rarity_tints: dict[int, tuple[RGB, float]]
    level_strip: float
    scrim: RGB | None
    """Color of the fade at the bottom of the enemy art, None to use the band tint."""
    scrim_start: float
    scrim_alpha: int


DARK_THEME = Theme(
    ground=(13, 13, 15),
    text=WHITE,
    line=WHITE,
    fallback_colors=((30, 30, 34), (210, 210, 220)),
    header_muted=0.62,
    muted=0.62,
    divider=0.14,
    avatar_fill=0.1,
    tag_fill=(WHITE, 0.08),
    rarity_tints={4: ((200, 180, 255), 0.14), 5: ((255, 214, 150), 0.16)},
    level_strip=0.28,
    scrim=BLACK,
    scrim_start=0.55,
    scrim_alpha=140,
)
LIGHT_THEME = Theme(
    ground=(246, 245, 243),
    text=INK,
    line=INK,
    fallback_colors=((226, 226, 230), (60, 62, 70)),
    header_muted=0.66,
    muted=0.7,
    divider=0.12,
    avatar_fill=0.06,
    tag_fill=(WHITE, 0.65),
    rarity_tints={4: ((150, 130, 210), 0.22), 5: ((214, 170, 100), 0.22)},
    level_strip=0.06,
    scrim=None,
    scrim_start=0.3,
    scrim_alpha=235,
)

LEYLINE_ICON_KEYWORD = "UI_LeyLineChallenge_Icon"
LEYLINE_ICON_SIZE = (32, 32)
DEFAULT_ICON_SIZE = (28, 28)

CARD_WIDTH = 1600
PADDING_X = 48
PADDING_Y = 56
HEADER_HEIGHT = 140
HEADER_GAP = 32
HEADER_LEFT = PADDING_X + 8
HEADER_RIGHT = CARD_WIDTH - PADDING_X - 8
MEDAL_SIZE = 108

BAND_SIZE = (CARD_WIDTH - PADDING_X * 2, 400)
BAND_GAP = 16
BAND_RADIUS = 28
ART_WIDTH = 440
ART_CROP = (704, 640)
"""Center crop of the 1024px HoYoLAB enemy art, which has a lot of empty space around the enemy."""

CONTENT_X = ART_WIDTH + 16
CONTENT_RIGHT = BAND_SIZE[0] - 40

TILE_SIZE = (116, 148)
TILE_GAP = 12
TILE_RADIUS = 18
TEAM_Y = 142

DIVIDER_X = CONTENT_X + 4 * TILE_SIZE[0] + 3 * TILE_GAP + 32
STATS_TOP = 134
STATS_HEIGHT = 164
STAT_X = DIVIDER_X + 32
STAT_AVATAR_SIZE = 56
STAT_TEXT_X = STAT_X + STAT_AVATAR_SIZE + 14
STAT_CENTER_Y = 171
STAT_ROW_STEP = 90

TAG_Y = 322
TAG_HEIGHT = 42
TAG_GAP = 10
TAG_SIGN_SIZE = 20


def _mix(color: RGB, base: RGB, alpha: float) -> RGB:
    return tuple(round(b * (1 - alpha) + c * alpha) for c, b in zip(color, base, strict=True))  # pyright: ignore[reportReturnType]


def _hls(hue: float, lightness: float, saturation: float) -> RGB:
    return tuple(round(c * 255) for c in colorsys.hls_to_rgb(hue, lightness, saturation))  # pyright: ignore[reportReturnType]


def _rounded_rect(
    size: tuple[int, int],
    *,
    radius: int,
    fill: RGB | tuple[int, int, int, int],
    outline: RGB | None = None,
    width: int = 0,
) -> Image.Image:
    """Draw an anti-aliased rounded rectangle by supersampling."""
    scale = 4
    big = Image.new("RGBA", (size[0] * scale, size[1] * scale))
    ImageDraw.Draw(big).rounded_rectangle(
        (0, 0, big.width - 1, big.height - 1),
        radius=radius * scale,
        fill=fill,
        outline=outline,
        width=width * scale,
    )
    return big.resize(size, Image.Resampling.LANCZOS)


def _round_corners(image: Image.Image, radius: int) -> Image.Image:
    mask = _rounded_rect(image.size, radius=radius, fill=WHITE).getchannel("A")
    image.putalpha(mask)
    return image


def _linear_mask(
    size: tuple[int, int], *, horizontal: bool, start: float, max_alpha: int
) -> Image.Image:
    """Alpha ramp from 0 at `start` (fraction of the axis) to `max_alpha` at the end."""
    length = size[0] if horizontal else size[1]
    ramp = np.clip((np.linspace(0, 1, length) - start) / (1 - start), 0, 1) * max_alpha
    arr = np.tile(ramp, (size[1], 1)) if horizontal else np.tile(ramp[:, None], (1, size[0]))
    return Image.fromarray(arr.astype(np.uint8), "L")


def _extract_hue(art: Image.Image) -> tuple[float, float] | None:
    """Return the dominant hue and mean saturation of the enemy art.

    Only fully opaque pixels are sampled so the translucent swirl behind the enemy is ignored.
    """
    thumb = art.copy()
    thumb.thumbnail((128, 128))
    opaque = np.asarray(thumb.getchannel("A")) > 250
    if not opaque.any():
        return None

    hsv = np.asarray(thumb.convert("RGB").convert("HSV"), dtype=np.float64) / 255
    hue, sat, val = (hsv[..., i][opaque] for i in range(3))
    weight = sat * (val > 0.2)
    if weight.sum() == 0:
        return None

    angle = hue * 2 * np.pi
    mean_hue = (
        float(
            np.arctan2((np.sin(angle) * weight).sum(), (np.cos(angle) * weight).sum()) / (2 * np.pi)
        )
        % 1
    )
    return mean_hue, float(sat.mean())


def _get_band_colors(art: Image.Image, theme: Theme) -> tuple[RGB, RGB]:
    """Return the band tint and the accent color for text on it, based on the enemy art."""
    extracted = _extract_hue(art)
    if extracted is None:
        return theme.fallback_colors

    hue, sat = extracted
    if theme is DARK_THEME:
        return _hls(hue, 0.13, min(sat, 0.4)), _hls(hue, 0.78, min(max(sat * 2, 0.25), 0.7))
    return _hls(hue, 0.89, min(max(sat * 1.2, 0.4), 0.7)), _hls(
        hue, 0.3, min(max(sat * 1.2, 0.5), 0.75)
    )


class HardChallengeCard:
    def __init__(
        self,
        data: genshin.models.HardChallenge,
        uid: str,
        locale: Locale,
        *,
        mode: HardChallengeMode,
        stygian_detail: hakushin.gi.StygianDetail,
        dark_mode: bool,
    ) -> None:
        self._data = data
        self._uid = uid
        self._locale = locale
        self._mode = mode
        self._dark_mode = dark_mode
        self._theme = DARK_THEME if dark_mode else LIGHT_THEME
        self._enemy_recommendations = {
            enemy_id: enemy.recommendation
            for level in stygian_detail.levels.values()
            for enemy_id, enemy in level.enemies.items()
            if enemy.recommendation is not None
        }
        self._difficulty_names = {
            level.difficulty_config.level: level.difficulty_config.name
            for level in stygian_detail.levels.values()
        }

    @property
    def _record(self) -> genshin.models.HardChallengeData:
        return self._data.single_player if self._mode == "single" else self._data.multi_player

    def _new_drawer(self, image: Image.Image) -> Drawer:
        return Drawer(
            ImageDraw.Draw(image),
            folder="hard-challenge",
            dark_mode=self._dark_mode,
            locale=self._locale,
        )

    def _draw_best_record(self, drawer: Drawer, im: Image.Image) -> None:
        best_record = self._record.best_record
        if best_record is None:
            return

        medal = drawer.open_asset(f"{best_record.icon}.png", size=(MEDAL_SIZE, MEDAL_SIZE))
        center_y = PADDING_Y + HEADER_HEIGHT // 2
        im.alpha_composite(medal, (HEADER_LEFT, center_y - MEDAL_SIZE // 2))

        mode_key = "hard_challenge_type_1" if self._mode == "single" else "hard_challenge_type_2"
        difficulty = self._difficulty_names.get(best_record.difficulty)
        label = LocaleStr(
            custom_str="{title} · {mode}"
            if difficulty is None
            else "{title} · {mode} · {difficulty}",
            title=LocaleStr(key="role_combat_best_record", mi18n_game=Game.GENSHIN),
            mode=LocaleStr(key=mode_key, mi18n_game=Game.GENSHIN),
            difficulty=difficulty,
        )

        text_x = HEADER_LEFT + MEDAL_SIZE + 24
        drawer.write(
            label,
            size=26,
            style="medium",
            sans=True,
            position=(text_x, center_y - 41),
            color=_mix(self._theme.text, self._theme.ground, self._theme.header_muted),
            anchor="ls",
        )
        drawer.write(
            f"{best_record.time_used}s",
            size=96,
            style="black",
            position=(text_x, center_y + 50),
            color=self._theme.text,
            anchor="ls",
        )

    def _draw_season(self, drawer: Drawer) -> None:
        season = self._data.season
        center_y = PADDING_Y + HEADER_HEIGHT // 2
        drawer.write(
            season.name,
            size=38,
            style="bold",
            position=(HEADER_RIGHT, center_y - 9),
            color=self._theme.text,
            anchor="rs",
            max_width=760,
            dynamic_fontsize=True,
        )
        period = f"{season.start_at:%Y.%m.%d} - {season.end_at:%Y.%m.%d}"
        drawer.write(
            f"{period} · UID {self._uid}",
            size=26,
            sans=True,
            position=(HEADER_RIGHT, center_y + 38),
            color=_mix(self._theme.text, self._theme.ground, self._theme.header_muted),
            anchor="rs",
        )

    def _draw_art(
        self, drawer: Drawer, band: Image.Image, art: Image.Image, tint: RGB, time_used: int
    ) -> None:
        art = Drawer.resize_crop(art, (ART_WIDTH, BAND_SIZE[1]))
        band.alpha_composite(art)

        theme = self._theme
        scrim = Image.new("RGBA", art.size, theme.scrim or tint)
        scrim.putalpha(
            _linear_mask(
                art.size, horizontal=False, start=theme.scrim_start, max_alpha=theme.scrim_alpha
            )
        )
        band.alpha_composite(scrim)

        fade = Image.new("RGBA", art.size, tint)
        fade.putalpha(_linear_mask(art.size, horizontal=True, start=0.45, max_alpha=255))
        band.alpha_composite(fade)

        drawer.write(
            f"{time_used}s",
            size=112,
            style="black",
            position=(32, BAND_SIZE[1] - 43),
            color=theme.text,
            anchor="ls",
        )

    def _write_band_title(
        self,
        drawer: Drawer,
        challenge: genshin.models.HardChallengeChallenge,
        index: int,
        highlight: RGB,
    ) -> None:
        label = LocaleStr(
            custom_str="{challenge} · Lv.{level}",
            challenge=LocaleStr(key="hard_challenge_challenge_index", index=index + 1),
            level=challenge.enemy.level,
        )
        drawer.write(
            label,
            size=22,
            style="bold",
            sans=True,
            position=(CONTENT_X, 58),
            color=highlight,
            anchor="ls",
        )
        drawer.write(
            challenge.enemy.name,
            size=34,
            style="bold",
            position=(CONTENT_X, 103),
            color=self._theme.text,
            anchor="ls",
            max_width=CONTENT_RIGHT - CONTENT_X,
            dynamic_fontsize=True,
        )

    def _draw_character_tile(
        self, character: genshin.models.HardChallengeCharacter, tint: RGB
    ) -> Image.Image:
        rarity_color, rarity_alpha = self._theme.rarity_tints[4 if character.rarity == 4 else 5]
        base = _mix(rarity_color, tint, rarity_alpha)
        width, height = TILE_SIZE

        tile = Image.new("RGBA", TILE_SIZE, base)
        draw = ImageDraw.Draw(tile)
        draw.rectangle((0, width, width, height), fill=_mix(BLACK, base, self._theme.level_strip))
        tile.alpha_composite(Drawer.open_static(character.icon, size=(width, width)))

        drawer = self._new_drawer(tile)
        drawer.write(
            f"Lv.{character.level}",
            size=20,
            style="bold",
            sans=True,
            position=(width / 2, width + (height - width) / 2),
            color=self._theme.text,
            anchor="mm",
        )

        const = str(character.constellation)
        tbox = drawer.write(const, size=20, style="bold", sans=True, position=(0, 0), no_write=True)
        box_size = (max(28, tbox.width + 16), 29)
        box = _rounded_rect(box_size, radius=8, fill=(0, 0, 0, 178))
        box_pos = (width - 6 - box_size[0], 6)
        tile.alpha_composite(box, box_pos)
        drawer.write(
            const,
            size=20,
            style="bold",
            sans=True,
            position=(box_pos[0] + box_size[0] / 2, box_pos[1] + box_size[1] / 2),
            color=WHITE,
            anchor="mm",
        )

        return _round_corners(tile, TILE_RADIUS)

    def _draw_stat(
        self,
        drawer: Drawer,
        band: Image.Image,
        challenge: genshin.models.HardChallengeChallenge,
        best: genshin.models.HardChallengeBestCharacter,
        tint: RGB,
    ) -> None:
        is_strike = best.type is genshin.models.HardChallengeBestCharacterType.STRIKE
        center_y = STAT_CENTER_Y + (0 if is_strike else STAT_ROW_STEP)

        avatar_pos = (STAT_X, center_y - STAT_AVATAR_SIZE // 2)
        avatar_size = (STAT_AVATAR_SIZE, STAT_AVATAR_SIZE)
        band.alpha_composite(
            _rounded_rect(
                avatar_size,
                radius=STAT_AVATAR_SIZE // 2,
                fill=_mix(self._theme.line, tint, self._theme.avatar_fill),
            ),
            avatar_pos,
        )
        icon_url = next((c.icon for c in challenge.team if c.id == best.id), None)
        if icon_url is not None:
            icon = Drawer.circular_crop(Drawer.open_static(icon_url, size=avatar_size))
            band.alpha_composite(icon, avatar_pos)

        label = LocaleStr(
            key="hard_challenge_strongest_strike" if is_strike else "hard_challenge_damage_dealt"
        )
        drawer.write(
            label,
            size=22,
            sans=True,
            position=(STAT_TEXT_X, center_y - 15),
            color=_mix(self._theme.text, tint, self._theme.muted),
            anchor="ls",
            max_width=CONTENT_RIGHT - STAT_TEXT_X,
            dynamic_fontsize=True,
        )
        drawer.write(
            f"{int(best.value):,}",
            size=40,
            style="bold",
            position=(STAT_TEXT_X, center_y + 28),
            color=self._theme.text,
            anchor="ls",
        )

    def _iter_tags(
        self, recommendation: hakushin.gi.StygianEnemyRecommendation
    ) -> Iterator[tuple[str, list[Image.Image], bool]]:
        for text, is_advantage in (
            (recommendation.recommend, True),
            (recommendation.dont_recommend, False),
        ):
            if text is None:
                continue

            for rec in text.split(" | "):
                rec_text = rec
                icons: list[Image.Image] = []
                for keyword, icon_url in hakushin.utils.extract_sprite_presets(rec):
                    rec_text = rec_text.replace("{" + keyword + "}", "")
                    if not icon_url:
                        continue
                    size = (
                        LEYLINE_ICON_SIZE if LEYLINE_ICON_KEYWORD in icon_url else DEFAULT_ICON_SIZE
                    )
                    icons.append(Drawer.open_static(icon_url, size=size))
                yield rec_text.strip(), icons, is_advantage

    def _create_tag(
        self,
        drawer: Drawer,
        text: str,
        icons: list[Image.Image],
        *,
        is_advantage: bool,
        tint: RGB,
        highlight: RGB,
    ) -> Image.Image:
        theme = self._theme
        muted = _mix(theme.text, tint, theme.muted)
        text_color = theme.text if is_advantage else muted
        tbox = drawer.write(text, size=22, style="bold", sans=True, position=(0, 0), no_write=True)
        gap = 8
        width = 16 + TAG_SIGN_SIZE + gap + sum(icon.width + gap for icon in icons) + tbox.width + 16

        fill_color, fill_alpha = theme.tag_fill
        tag = _rounded_rect(
            (width, TAG_HEIGHT),
            radius=TAG_HEIGHT // 2,
            fill=_mix(fill_color, tint, fill_alpha) if is_advantage else tint,
            outline=_mix(theme.line, tint, theme.divider),
            width=2,
        )
        center_y = TAG_HEIGHT // 2
        sign = drawer.open_asset(
            "thumbs_up.png" if is_advantage else "thumbs_down.png",
            size=(TAG_SIGN_SIZE, TAG_SIGN_SIZE),
            mask_color=highlight if is_advantage else muted,
        )
        tag.alpha_composite(sign, (16, center_y - TAG_SIGN_SIZE // 2))

        x = 16 + TAG_SIGN_SIZE + gap
        for icon in icons:
            tag.alpha_composite(icon, (x, center_y - icon.height // 2))
            x += icon.width + gap

        self._new_drawer(tag).write(
            text,
            size=22,
            style="bold",
            sans=True,
            position=(x, center_y),
            color=text_color,
            anchor="lm",
        )
        return tag

    def _draw_tags(
        self,
        drawer: Drawer,
        band: Image.Image,
        recommendation: hakushin.gi.StygianEnemyRecommendation,
        tint: RGB,
        highlight: RGB,
    ) -> None:
        x = CONTENT_X
        for text, icons, is_advantage in self._iter_tags(recommendation):
            tag = self._create_tag(
                drawer, text, icons, is_advantage=is_advantage, tint=tint, highlight=highlight
            )
            if x + tag.width > CONTENT_RIGHT:
                break
            band.alpha_composite(tag, (x, TAG_Y))
            x += tag.width + TAG_GAP

    def _draw_band(
        self, challenge: genshin.models.HardChallengeChallenge, index: int
    ) -> Image.Image:
        art = Drawer.middle_crop(Drawer.open_static(challenge.enemy.icon), ART_CROP)
        tint, highlight = _get_band_colors(art, self._theme)

        band = Image.new("RGBA", BAND_SIZE, tint)
        drawer = self._new_drawer(band)

        self._draw_art(drawer, band, art, tint, challenge.time_used)
        self._write_band_title(drawer, challenge, index, highlight)

        for i, character in enumerate(challenge.team):
            tile = self._draw_character_tile(character, tint)
            band.alpha_composite(tile, (CONTENT_X + i * (TILE_SIZE[0] + TILE_GAP), TEAM_Y))

        drawer.draw.line(
            (DIVIDER_X, STATS_TOP, DIVIDER_X, STATS_TOP + STATS_HEIGHT),
            fill=_mix(self._theme.line, tint, self._theme.divider),
            width=1,
        )
        for best in challenge.best_characters:
            self._draw_stat(drawer, band, challenge, best, tint)

        recommendation = self._enemy_recommendations.get(challenge.enemy.id)
        if recommendation is not None:
            self._draw_tags(drawer, band, recommendation, tint, highlight)

        return _round_corners(band, BAND_RADIUS)

    def draw(self) -> io.BytesIO:
        challenges = self._record.challenges
        bands_height = len(challenges) * (BAND_SIZE[1] + BAND_GAP) - BAND_GAP if challenges else 0
        gap = HEADER_GAP if challenges else 0
        height = PADDING_Y * 2 + HEADER_HEIGHT + gap + bands_height

        im = Image.new("RGBA", (CARD_WIDTH, height), self._theme.ground)
        drawer = self._new_drawer(im)

        self._draw_best_record(drawer, im)
        self._draw_season(drawer)

        y = PADDING_Y + HEADER_HEIGHT + HEADER_GAP
        for i, challenge in enumerate(challenges):
            im.alpha_composite(self._draw_band(challenge, i), (PADDING_X, y))
            y += BAND_SIZE[1] + BAND_GAP

        return drawer.save_image(im)
