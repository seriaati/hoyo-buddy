from typing import Literal, Optional, Tuple

import discord
from PIL import Image, ImageDraw, ImageFont

from ..bot.translator import Translator, locale_str
from .fonts import (
    GENSENROUNDEDTW_BOLD,
    GENSENROUNDEDTW_LIGHT,
    GENSENROUNDEDTW_MEDIUM,
    GENSENROUNDEDTW_REGULAR,
    MPLUSROUNDED1C_BOLD,
    MPLUSROUNDED1C_LIGHT,
    MPLUSROUNDED1C_MEDIUM,
    MPLUSROUNDED1C_REGULAR,
    NUNITO_BOLD,
    NUNITO_LIGHT,
    NUNITO_MEDIUM,
    NUNITO_REGULAR,
)
from .static import STATIC_FOLDER

__all__ = ("Drawer",)

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
HIGH_EMPHASIS_OPACITY = 221
MEDIUM_EMPHASIS_OPACITY = 153
LOW_EMPHASIS_OPACITY = 96


class Drawer:
    def __init__(
        self,
        draw: ImageDraw.ImageDraw,
        *,
        folder: str,
        dark_mode: bool,
        locale: discord.Locale = discord.Locale.american_english,
        translator: Optional[Translator] = None,
    ):
        self.draw = draw
        self.folder = folder
        self.dark_mode = dark_mode
        self.locale = locale
        self.translator = translator

    def _get_text_color(
        self,
        color: Optional[Tuple[int, int, int, int]],
        emphasis: Literal["high", "medium", "low"],
    ) -> Tuple[int, int, int, int]:
        if color is not None:
            return color

        if emphasis == "high":
            if self.dark_mode:
                return WHITE + (HIGH_EMPHASIS_OPACITY,)
            return BLACK + (HIGH_EMPHASIS_OPACITY,)
        if emphasis == "medium":
            if self.dark_mode:
                return WHITE + (MEDIUM_EMPHASIS_OPACITY,)
            return BLACK + (MEDIUM_EMPHASIS_OPACITY,)
        if emphasis == "low":
            if self.dark_mode:
                return WHITE + (LOW_EMPHASIS_OPACITY,)
            return BLACK + (LOW_EMPHASIS_OPACITY,)
        raise ValueError(f"Invalid emphasis: {emphasis}")

    def _get_font(
        self, size: int, style: Literal["light", "regular", "medium", "bold"]
    ) -> ImageFont.FreeTypeFont:
        if self.locale in (discord.Locale.taiwan_chinese, discord.Locale.chinese):
            if style == "light":
                font = GENSENROUNDEDTW_LIGHT
            elif style == "regular":
                font = GENSENROUNDEDTW_REGULAR
            elif style == "medium":
                font = GENSENROUNDEDTW_MEDIUM
            elif style == "bold":
                font = GENSENROUNDEDTW_BOLD
            else:
                raise ValueError(f"Invalid font style: {style}")
        elif self.locale == discord.Locale.japanese:
            if style == "light":
                font = MPLUSROUNDED1C_LIGHT
            elif style == "regular":
                font = MPLUSROUNDED1C_REGULAR
            elif style == "medium":
                font = MPLUSROUNDED1C_MEDIUM
            elif style == "bold":
                font = MPLUSROUNDED1C_BOLD
            else:
                raise ValueError(f"Invalid font style: {style}")
        else:
            if style == "light":
                font = NUNITO_LIGHT
            elif style == "regular":
                font = NUNITO_REGULAR
            elif style == "medium":
                font = NUNITO_MEDIUM
            elif style == "bold":
                font = NUNITO_BOLD
            else:
                raise ValueError(f"Invalid font style: {style}")

        return ImageFont.truetype(font, size)

    def write(
        self,
        *,
        text: locale_str,
        size: int,
        position: Tuple[int, int],
        color: Optional[Tuple[int, int, int, int]] = None,
        style: Literal["light", "regular", "medium", "bold"] = "regular",
        emphasis: Literal["high", "medium", "low"] = "high",
        anchor: Optional[str] = None,
    ) -> None:
        if self.translator is None:
            raise RuntimeError("Translator is not set")

        translated_text = self.translator.translate(text, self.locale)
        self.draw.text(
            position,
            translated_text,
            font=self._get_font(size, style),
            fill=self._get_text_color(color, emphasis),
            anchor=anchor,
        )

    def plain_write(
        self,
        *,
        text: str,
        size: int,
        position: Tuple[int, int],
        color: Optional[Tuple[int, int, int, int]] = None,
        style: Literal["light", "regular", "medium", "bold"] = "regular",
        emphasis: Literal["high", "medium", "low"] = "high",
        anchor: Optional[str] = None,
    ) -> None:
        self.draw.text(
            position,
            text,
            font=self._get_font(size, style),
            fill=self._get_text_color(color, emphasis),
            anchor=anchor,
        )

    def get_static_image(self, url: str, *, folder: Optional[str] = None) -> Image.Image:
        filename = url.split("/")[-1]
        folder = folder or self.folder
        image = Image.open(f"{STATIC_FOLDER}/{folder}/{filename}")
        image = image.convert("RGBA")
        return image
