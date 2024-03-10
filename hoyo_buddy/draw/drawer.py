from typing import TYPE_CHECKING, Literal

import discord
from PIL import Image, ImageChops, ImageDraw, ImageFont

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
EMPHASIS_OPACITY: dict[str, float] = {"high": 0.86, "medium": 0.6, "low": 0.37}

# Material design colors
LIGHT_SURFACE = (252, 248, 253)
LIGHT_ON_SURFACE = (27, 27, 31)
LIGHT_ON_SURFACE_VARIANT = (70, 70, 79)

DARK_SURFACE = (19, 19, 22)
DARK_ON_SURFACE = (200, 197, 202)
DARK_ON_SURFACE_VARIANT = (199, 197, 208)

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

    @classmethod
    def blend_color(
        cls, foreground: tuple[int, int, int], background: tuple[int, int, int], opactity: float
    ) -> tuple[int, int, int]:
        opactity = 1 - opactity
        return (
            round((1 - opactity) * foreground[0] + opactity * background[0]),
            round((1 - opactity) * foreground[1] + opactity * background[1]),
            round((1 - opactity) * foreground[2] + opactity * background[2]),
        )

    @classmethod
    def hex_to_rgb(cls, hex_color_code: str) -> tuple[int, int, int]:
        hex_color_code = hex_color_code.lstrip("#")
        return tuple(int(hex_color_code[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore

    @staticmethod
    def apply_color_opacity(
        color: tuple[int, int, int], opacity: float
    ) -> tuple[int, int, int, int]:
        return color + (round(255 * opacity),)

    def _mask_image_with_color(
        self, image: Image.Image, color: tuple[int, int, int], opacity: float
    ) -> Image.Image:
        mask = Image.new("RGBA", image.size, self.apply_color_opacity(color, opacity))
        image = ImageChops.multiply(image, mask)
        return image

    @staticmethod
    def _shorten_text(text: str, max_width: int, font: ImageFont.FreeTypeFont) -> str:
        if font.getlength(text) <= max_width:
            return text
        shortened = text[: max_width - 3] + "..."
        while font.getlength(shortened) > max_width and len(shortened) > 3:
            shortened = shortened[:-4] + "..."
        return shortened

    def _wrap_text(
        self, text: str, max_width: int, max_lines: int, font: ImageFont.FreeTypeFont
    ) -> str:
        lines: list[str] = [""]
        for word in text.split():
            line = f"{lines[-1]} {word}".strip()
            if font.getlength(line) <= max_width:
                lines[-1] = line
            else:
                lines.append(word)
                if len(lines) > max_lines:
                    del lines[-1]
                    lines[-1] = self._shorten_text(lines[-1], max_width, font)
                    break
        return "\n".join(lines)

    def _get_text_color(
        self,
        color: tuple[int, int, int] | None,
        emphasis: Literal["high", "medium", "low"],
    ) -> tuple[int, int, int, int]:
        if color is not None:
            return self.apply_color_opacity(color, EMPHASIS_OPACITY[emphasis])

        return self.apply_color_opacity(
            WHITE if self.dark_mode else BLACK, EMPHASIS_OPACITY[emphasis]
        )

    def _get_font(
        self,
        size: int,
        style: Literal["light", "regular", "medium", "bold"],
        locale: discord.Locale | None,
    ) -> ImageFont.FreeTypeFont:
        font = FONT_MAPPING.get(locale or self.locale, FONT_MAPPING[None]).get(style)

        if font is None:
            msg = f"Invalid font style: {style}"
            raise ValueError(msg)

        return ImageFont.truetype(font, size)

    def _open_image(self, path: str, size: tuple[int, int] | None = None) -> Image.Image:
        image = Image.open(path)
        image = image.convert("RGBA")
        if size:
            image = image.resize(size, Image.LANCZOS)
        return image

    def write(
        self,
        text: "LocaleStr | str",
        *,
        size: int,
        position: tuple[int, int],
        color: tuple[int, int, int] | None = None,
        style: Literal["light", "regular", "medium", "bold"] = "regular",
        emphasis: Literal["high", "medium", "low"] = "high",
        anchor: str | None = None,
        max_width: int | None = None,
        max_lines: int = 1,
        locale: discord.Locale | None = None,
    ) -> tuple[int, int, int, int]:
        """Returns (left, top, right, bottom) of the text bounding box."""
        if isinstance(text, str):
            translated_text = text
        else:
            if self.translator is None:
                msg = "Translator is not set"
                raise RuntimeError(msg)

            translated_text = self.translator.translate(text, locale or self.locale)

        font = self._get_font(size, style, locale)

        if max_width is not None:
            if max_lines == 1:
                translated_text = self._shorten_text(translated_text, max_width, font)
            else:
                translated_text = self._wrap_text(translated_text, max_width, max_lines, font)

        self.draw.text(
            position,
            translated_text,
            font=font,
            fill=self._get_text_color(color, emphasis),
            anchor=anchor,
        )

        textbbox = self.draw.textbbox(
            position, translated_text, font=font, anchor=anchor, font_size=size
        )
        return tuple(round(bbox) for bbox in textbbox)  # type: ignore

    def open_static(
        self,
        url: str,
        *,
        folder: str | None = None,
        size: tuple[int, int] | None = None,
        mask_color: tuple[int, int, int] | None = None,
        opacity: float = 1.0,
    ) -> Image.Image:
        filename = url.split("/")[-1]
        folder = folder or self.folder
        path = f"{STATIC_FOLDER}/{folder}/{filename}"
        image = self._open_image(path, size)
        if mask_color:
            image = self._mask_image_with_color(image, mask_color, opacity)
        return image

    def open_asset(
        self,
        filename: str,
        *,
        folder: str | None = None,
        size: tuple[int, int] | None = None,
        mask_color: tuple[int, int, int] | None = None,
        opacity: float = 1.0,
    ) -> Image.Image:
        folder = folder or self.folder
        path = f"hoyo-buddy-assets/assets/{folder}/{filename}"
        image = self._open_image(path, size)
        if mask_color:
            image = self._mask_image_with_color(image, mask_color, opacity)
        return image

    def circular_crop(self, image: Image.Image) -> Image.Image:
        """Crop an image into a circle."""
        mask = self._open_image("hoyo-buddy-assets/assets/circular_mask.png", image.size)
        empty = Image.new("RGBA", image.size, 0)
        image = Image.composite(image, empty, mask)
        return image

    def modify_image_for_build_card(
        self, image: Image.Image, target_width: int, target_height: int
    ) -> Image.Image:
        # Calculate the target height to maintain the aspect ratio
        width, height = image.size
        ratio = min(width / target_width, height / target_height)

        # Calculate the new size and left/top coordinates for cropping
        new_width = round(width / ratio)
        new_height = round(height / ratio)
        left = round((new_width - target_width) / 2)
        top = round((new_height - target_height) / 2)
        right = round(left + target_width)
        bottom = round(top + target_height)

        image = image.resize((new_width, new_height), resample=Image.LANCZOS)
        image = image.crop((left, top, right, bottom))

        if self.dark_mode:
            overlay = Image.new("RGBA", image.size, self.apply_color_opacity((0, 0, 0), 0.2))
            image = Image.alpha_composite(image.convert("RGBA"), overlay)

        return image
