from typing import TYPE_CHECKING, Literal

import discord
from PIL import Image, ImageDraw, ImageFont

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

if TYPE_CHECKING:
    from ..bot.translator import LocaleStr, Translator

__all__ = ("Drawer",)

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
HIGH_EMPHASIS_OPACITY = 221
MEDIUM_EMPHASIS_OPACITY = 153
LOW_EMPHASIS_OPACITY = 96

FONT_MAPPING: dict[
    discord.Locale | None,
    dict[str, str],
] = {
    discord.Locale.chinese: {
        "light": GENSENROUNDEDTW_LIGHT,
        "regular": GENSENROUNDEDTW_REGULAR,
        "medium": GENSENROUNDEDTW_MEDIUM,
        "bold": GENSENROUNDEDTW_BOLD,
    },
    discord.Locale.taiwan_chinese: {
        "light": GENSENROUNDEDTW_LIGHT,
        "regular": GENSENROUNDEDTW_REGULAR,
        "medium": GENSENROUNDEDTW_MEDIUM,
        "bold": GENSENROUNDEDTW_BOLD,
    },
    discord.Locale.japanese: {
        "light": MPLUSROUNDED1C_LIGHT,
        "regular": MPLUSROUNDED1C_REGULAR,
        "medium": MPLUSROUNDED1C_MEDIUM,
        "bold": MPLUSROUNDED1C_BOLD,
    },
    None: {
        "light": NUNITO_LIGHT,
        "regular": NUNITO_REGULAR,
        "medium": NUNITO_MEDIUM,
        "bold": NUNITO_BOLD,
    },
}

EMPHASIS_COLOR_MAPPING = {
    ("high", True): WHITE + (HIGH_EMPHASIS_OPACITY,),
    ("medium", True): WHITE + (MEDIUM_EMPHASIS_OPACITY,),
    ("low", True): WHITE + (LOW_EMPHASIS_OPACITY,),
    ("high", False): BLACK + (HIGH_EMPHASIS_OPACITY,),
    ("medium", False): BLACK + (MEDIUM_EMPHASIS_OPACITY,),
    ("low", False): BLACK + (LOW_EMPHASIS_OPACITY,),
}


class Drawer:
    def __init__(
        self,
        draw: ImageDraw.ImageDraw,
        *,
        folder: str,
        dark_mode: bool,
        locale: discord.Locale = discord.Locale.american_english,
        translator: "Translator | None" = None,
    ) -> None:
        self.draw = draw
        self.folder = folder
        self.dark_mode = dark_mode
        self.locale = locale
        self.translator = translator

    def _get_text_color(
        self,
        color: tuple[int, int, int, int] | None,
        emphasis: Literal["high", "medium", "low"],
    ) -> tuple[int, int, int, int]:
        if color is not None:
            return color

        key = (emphasis, self.dark_mode)
        if key in EMPHASIS_COLOR_MAPPING:
            return EMPHASIS_COLOR_MAPPING[key]

        msg = f"Invalid emphasis: {emphasis}"
        raise ValueError(msg)

    def _get_font(
        self, size: int, style: Literal["light", "regular", "medium", "bold"]
    ) -> ImageFont.FreeTypeFont:
        font = FONT_MAPPING.get(self.locale, FONT_MAPPING[None]).get(style)

        if font is None:
            msg = f"Invalid font style: {style}"
            raise ValueError(msg)

        return ImageFont.truetype(font, size)

    def write(
        self,
        *,
        text: "LocaleStr | str",
        size: int,
        position: tuple[int, int],
        color: tuple[int, int, int, int] | None = None,
        style: Literal["light", "regular", "medium", "bold"] = "regular",
        emphasis: Literal["high", "medium", "low"] = "high",
        anchor: str | None = None,
    ) -> None:
        if isinstance(text, str):
            translated_text = text
        else:
            if self.translator is None:
                msg = "Translator is not set"
                raise RuntimeError(msg)

            translated_text = self.translator.translate(text, self.locale)

        self.draw.text(
            position,
            translated_text,
            font=self._get_font(size, style),
            fill=self._get_text_color(color, emphasis),
            anchor=anchor,
        )

    def get_static_image(self, url: str, *, folder: str | None = None) -> Image.Image:
        filename = url.split("/")[-1]
        folder = folder or self.folder
        image = Image.open(f"{STATIC_FOLDER}/{folder}/{filename}")
        image = image.convert("RGBA")
        return image

    def modify_image(
        self, image: Image.Image, target_width: int, border_radius: int = 15
    ) -> Image.Image:
        # Calculate the target height to maintain the aspect ratio
        aspect_ratio = image.height / image.width
        target_height = int(target_width * aspect_ratio)

        # Crop the image to the targeted width, focusing on the center
        image = image.resize((target_width, target_height), Image.LANCZOS)

        # Apply a dark layer if dark_layer is True
        if self.dark_mode:
            overlay = Image.new("RGBA", image.size, (0, 0, 0, int(255 * 0.2)))  # 20% opacity
            image = Image.alpha_composite(image.convert("RGBA"), overlay)

        # Apply a border radius
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle(((0, 0), image.size), radius=border_radius, fill=255)
        image.putalpha(mask)

        return image
