from typing import Literal, Optional, Tuple

import discord
from PIL import ImageDraw, ImageFont

from ..bot.translator import Translator, locale_str
from .fonts import *


class Drawer:
    def __init__(
        self,
        draw: ImageDraw.ImageDraw,
        *,
        locale: discord.Locale,
        translator: Translator,
    ):
        self.draw = draw
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
        translated_text = self.translator.translate(text, self.locale)
        self.draw.text(
            position,
            translated_text,
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
                font = GENSENROUNDEDTW_MEDIUM
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

        font.size = size
        return font
