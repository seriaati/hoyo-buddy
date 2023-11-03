from typing import Literal, Optional, Tuple

import discord
from PIL import Image, ImageDraw, ImageFont

from ..bot.translator import Translator, locale_str
from .fonts import *
from .static import STATIC_FOLDER

__all__ = ("Drawer",)


class Drawer:
    def __init__(
        self,
        draw: ImageDraw.ImageDraw,
        *,
        folder: str,
        locale: discord.Locale = discord.Locale.american_english,
        translator: Optional[Translator] = None,
    ):
        self.draw = draw
        self.folder = folder
        self.locale = locale
        self.translator = translator

    def write(
        self,
        *,
        text: locale_str,
        size: int,
        color: str,
        position: Tuple[int, int],
        style: Literal["light", "regular", "medium", "bold"] = "regular",
        anchor: Optional[str] = None,
    ) -> None:
        if self.translator is None:
            raise RuntimeError("Translator is not set")

        translated_text = self.translator.translate(text, self.locale)
        self.draw.text(
            position,
            translated_text,
            font=self._get_font(size, style),
            fill=color,
            anchor=anchor,
        )

    def plain_write(
        self,
        *,
        text: str,
        size: int,
        color: str,
        position: Tuple[int, int],
        style: Literal["light", "regular", "medium", "bold"] = "regular",
        anchor: Optional[str] = None,
    ) -> None:
        self.draw.text(
            position,
            text,
            font=self._get_font(size, style),
            fill=color,
            anchor=anchor,
        )

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

    def get_static_image(
        self, url: str, *, folder: Optional[str] = None
    ) -> Image.Image:
        filename = url.split("/")[-1]
        folder = folder or self.folder
        image = Image.open(f"{STATIC_FOLDER}/{folder}/{filename}")
        image = image.convert("RGBA")
        return image
