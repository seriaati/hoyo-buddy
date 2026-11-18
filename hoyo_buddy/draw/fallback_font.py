from __future__ import annotations

import itertools
import math
from typing import TYPE_CHECKING, Any

from PIL import Image, ImageFont

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = ("FallbackFont",)

type _Run = tuple[str, ImageFont.FreeTypeFont, float, tuple[float, float, float, float]]


class FallbackFont(ImageFont.FreeTypeFont):
    """Draws the characters in fallback_chars with the fallback font, Pillow has no font fallback.

    Runs are laid out on a shared baseline, anchors use the primary font's metrics.
    """

    def __init__(
        self,
        primary: ImageFont.FreeTypeFont,
        fallback: ImageFont.FreeTypeFont,
        fallback_chars: frozenset[str],
    ) -> None:
        super().__init__(
            primary.path, primary.size, primary.index, primary.encoding, primary.layout_engine
        )
        self.primary = primary
        self.fallback = fallback
        self.fallback_chars = fallback_chars

    def _needs_fallback(self, text: str) -> bool:
        return not self.fallback_chars.isdisjoint(text)

    def _runs(self, text: str) -> Iterator[tuple[str, ImageFont.FreeTypeFont]]:
        for is_fallback, chars in itertools.groupby(text, lambda c: c in self.fallback_chars):
            yield "".join(chars), self.fallback if is_fallback else self.primary

    def _layout(
        self, text: str, anchor: str | None, stroke_width: float, *args: Any
    ) -> tuple[list[_Run], float, float]:
        """Returns the runs with their x and baseline bbox, and the anchor's offset to the origin."""
        runs: list[_Run] = []
        x = 0.0
        for run, font in self._runs(text):
            bbox = font.getbbox(run, *args, stroke_width=stroke_width, anchor="ls")
            runs.append((run, font, x, bbox))
            x += font.getlength(run, *args)

        horizontal, vertical = anchor or "la"
        ascent, descent = self.primary.getmetrics()
        dx = {"l": 0, "m": -x / 2, "r": -x}[horizontal]
        dy = {
            "a": ascent,
            "t": -min(r[3][1] for r in runs),
            "m": (ascent - descent) / 2,
            "s": 0,
            "b": -max(r[3][3] for r in runs),
            "d": -descent,
        }[vertical]
        return runs, dx, dy

    def getlength(
        self,
        text: str | bytes,
        mode: str = "",
        direction: str | None = None,
        features: list[str] | None = None,
        language: str | None = None,
    ) -> float:
        if not isinstance(text, str) or not self._needs_fallback(text):
            return super().getlength(text, mode, direction, features, language)
        return sum(
            font.getlength(run, mode, direction, features, language)
            for run, font in self._runs(text)
        )

    def getbbox(
        self,
        text: str | bytes | bytearray,
        mode: str = "",
        direction: str | None = None,
        features: list[str] | None = None,
        language: str | None = None,
        stroke_width: float = 0,
        anchor: str | None = None,
    ) -> tuple[float, float, float, float]:
        if not isinstance(text, str) or not self._needs_fallback(text):
            return super().getbbox(text, mode, direction, features, language, stroke_width, anchor)

        runs, dx, dy = self._layout(text, anchor, stroke_width, mode, direction, features, language)
        boxes = [(x + dx + b[0], dy + b[1], x + dx + b[2], dy + b[3]) for _, _, x, b in runs]
        return (
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        )

    def getmask2(
        self,
        text: str | bytes,
        mode: str = "",
        direction: str | None = None,
        features: list[str] | None = None,
        language: str | None = None,
        stroke_width: float = 0,
        anchor: str | None = None,
        ink: int = 0,
        start: tuple[float, float] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[Image.core.ImagingCore, tuple[int, int]]:
        if not isinstance(text, str) or not self._needs_fallback(text):
            return super().getmask2(
                text,
                mode,
                direction,
                features,
                language,
                stroke_width,
                anchor,
                ink,
                start,
                *args,
                **kwargs,
            )

        runs, dx, dy = self._layout(text, anchor, stroke_width, mode, direction, features, language)
        start_x, start_y = start or (0, 0)
        pieces: list[tuple[Image.core.ImagingCore, int, int]] = []
        for run, font, x, _ in runs:
            # Masks are positioned relative to the integer origin, the fraction goes to start
            origin_x, origin_y = start_x + dx + x, start_y + dy
            mask, (offset_x, offset_y) = font.getmask2(
                run,
                mode,
                direction,
                features,
                language,
                stroke_width,
                "ls",
                ink,
                (origin_x % 1, origin_y % 1),
                *args,
                **kwargs,
            )
            pieces.append((mask, math.floor(origin_x) + offset_x, math.floor(origin_y) + offset_y))

        left = min(x for _, x, _ in pieces)
        top = min(y for _, _, y in pieces)
        right = max(x + m.size[0] for m, x, _ in pieces)
        bottom = max(y + m.size[1] for m, _, y in pieces)

        combined = Image.core.fill(pieces[0][0].mode, (right - left, bottom - top), 0)
        for mask, x, y in pieces:
            box = (x - left, y - top, x - left + mask.size[0], y - top + mask.size[1])
            combined.paste(mask, box, mask)
        return combined, (left, top)

    def font_variant(
        self,
        font: Any = None,
        size: float | None = None,
        index: int | None = None,
        encoding: str | None = None,
        layout_engine: ImageFont.Layout | None = None,
    ) -> FallbackFont:
        return FallbackFont(
            self.primary.font_variant(font, size, index, encoding, layout_engine),
            self.fallback.font_variant(size=size),
            self.fallback_chars,
        )
