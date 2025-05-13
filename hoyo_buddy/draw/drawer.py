from __future__ import annotations

import io
import pathlib
from typing import TYPE_CHECKING, Literal, NamedTuple, TypeAlias

from discord import Locale
from fontTools.ttLib import TTFont
from loguru import logger
from PIL import Image, ImageChops, ImageDraw, ImageFont

from hoyo_buddy.constants import DC_MAX_FILESIZE

from ..l10n import translator
from ..models import DynamicBKInput, TopPadding
from ..utils import get_static_img_path
from .fonts import *  # noqa: F403

if TYPE_CHECKING:
    from ..l10n import LocaleStr

__all__ = ("Drawer",)

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)
EMPHASIS_OPACITY: dict[str, float] = {"high": 1.0, "medium": 0.6, "low": 0.37}

# Material design colors
LIGHT_SURFACE = (252, 248, 253)
LIGHT_ON_SURFACE = (27, 27, 31)
LIGHT_ON_SURFACE_CONTAINER_HIGHEST = (70, 70, 79)

DARK_SURFACE = (19, 19, 22)
DARK_ON_SURFACE = (200, 197, 202)
DARK_ON_SURFACE_CONTAINER_HIGHEST = (199, 197, 208)

FontStyle: TypeAlias = Literal[
    "light",
    "regular",
    "medium",
    "bold",
    "black",
    "light_italic",
    "regular_italic",
    "medium_italic",
    "bold_italic",
    "black_italic",
]


class TextBBox(NamedTuple):
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height


SUPPORTED_BY_NUNITO: tuple[Locale, ...] = (
    Locale.american_english,
    Locale.british_english,
    Locale.bulgarian,
    Locale.croatian,
    Locale.czech,
    Locale.indonesian,
    Locale.danish,
    Locale.dutch,
    Locale.finnish,
    Locale.french,
    Locale.german,
    Locale.hungarian,
    Locale.italian,
    Locale.latin_american_spanish,
    Locale.lithuanian,
    Locale.norwegian,
    Locale.polish,
    Locale.brazil_portuguese,
    Locale.romanian,
    Locale.russian,
    Locale.spain_spanish,
    Locale.swedish,
    Locale.turkish,
    Locale.ukrainian,
    Locale.vietnamese,
)
SUPPORTED_BY_GOTHIC: tuple[Locale, ...] = (
    Locale.american_english,
    Locale.british_english,
    Locale.bulgarian,
    Locale.indonesian,
    Locale.danish,
    Locale.dutch,
    Locale.finnish,
    Locale.french,
    Locale.german,
    Locale.italian,
    Locale.latin_american_spanish,
    Locale.norwegian,
    Locale.brazil_portuguese,
    Locale.russian,
    Locale.spain_spanish,
    Locale.swedish,
)

FontMapping: TypeAlias = dict[tuple[Locale, ...] | Locale, dict[FontStyle, str]]

DEFAULT_FONT_MAPPING: FontMapping = {
    (Locale.chinese, Locale.taiwan_chinese): {
        "light": GENSENROUNDEDTW_LIGHT,
        "regular": GENSENROUNDEDTW_REGULAR,
        "medium": GENSENROUNDEDTW_MEDIUM,
        "bold": GENSENROUNDEDTW_BOLD,
    },
    Locale.japanese: {
        "light": MPLUSROUNDED1C_LIGHT,
        "regular": MPLUSROUNDED1C_REGULAR,
        "medium": MPLUSROUNDED1C_MEDIUM,
        "bold": MPLUSROUNDED1C_BOLD,
        "black": MPLUSROUNDED1C_BLACK,
    },
    Locale.korean: {
        "light": NOTOSANSKR_LIGHT,
        "regular": NOTOSANSKR_REGULAR,
        "medium": NOTOSANSKR_MEDIUM,
        "bold": NOTOSANSKR_BOLD,
        "black": NOTOSANSKR_BLACK,
    },
    Locale.thai: {
        "light": NOTOSANSTHAI_LIGHT,
        "regular": NOTOSANSTHAI_REGULAR,
        "medium": NOTOSANSTHAI_MEDIUM,
        "bold": NOTOSANSTHAI_BOLD,
        "black": NOTOSANSTHAI_BLACK,
    },
    Locale.hindi: {
        "light": NOTOSANS_LIGHT,
        "regular": NOTOSANS_BLACK,
        "medium": NOTOSANS_MEDIUM,
        "bold": NOTOSANS_BOLD,
        "black": NOTOSANS_BLACK,
    },
    SUPPORTED_BY_NUNITO: {
        "light": NUNITO_LIGHT,
        "regular": NUNITO_REGULAR,
        "medium": NUNITO_MEDIUM,
        "bold": NUNITO_BOLD,
        "black": NUNITO_BLACK,
        "light_italic": NUNITO_LIGHT_ITALIC,
        "regular_italic": NUNITO_REGULAR_ITALIC,
        "medium_italic": NUNITO_MEDIUM_ITALIC,
        "bold_italic": NUNITO_BOLD_ITALIC,
        "black_italic": NUNITO_BLACK_ITALIC,
    },
}

SANS_FONT_MAPPING: FontMapping = {
    Locale.chinese: {
        "light": NOTOSANSSC_LIGHT,
        "regular": NOTOSANSSC_REGULAR,
        "medium": NOTOSANSSC_MEDIUM,
        "bold": NOTOSANSSC_BOLD,
        "black": NOTOSANSSC_BLACK,
    },
    Locale.taiwan_chinese: {
        "light": NOTOSANSTC_LIGHT,
        "regular": NOTOSANSTC_REGULAR,
        "medium": NOTOSANSTC_MEDIUM,
        "bold": NOTOSANSTC_BOLD,
        "black": NOTOSANSTC_BLACK,
    },
    Locale.japanese: {
        "light": NOTOSANSJP_LIGHT,
        "regular": NOTOSANSJP_REGULAR,
        "medium": NOTOSANSJP_MEDIUM,
        "bold": NOTOSANSJP_BOLD,
        "black": NOTOSANSJP_BLACK,
    },
    Locale.korean: {
        "light": NOTOSANSKR_LIGHT,
        "regular": NOTOSANSKR_REGULAR,
        "medium": NOTOSANSKR_MEDIUM,
        "bold": NOTOSANSKR_BOLD,
        "black": NOTOSANSKR_BLACK,
    },
    Locale.thai: {
        "light": NOTOSANSTHAI_LIGHT,
        "regular": NOTOSANSTHAI_REGULAR,
        "medium": NOTOSANSTHAI_MEDIUM,
        "bold": NOTOSANSTHAI_BOLD,
        "black": NOTOSANSTHAI_BLACK,
    },
    SUPPORTED_BY_NUNITO: {
        "light": NUNITO_SANS_LIGHT,
        "regular": NUNITO_SANS_REGULAR,
        "medium": NUNITO_SANS_MEDIUM,
        "bold": NUNITO_SANS_BOLD,
        "black": NUNITO_SANS_BLACK,
        "light_italic": NUNITO_SANS_LIGHT_ITALIC,
        "regular_italic": NUNITO_SANS_REGULAR_ITALIC,
        "medium_italic": NUNITO_SANS_MEDIUM_ITALIC,
        "bold_italic": NUNITO_SANS_BOLD_ITALIC,
        "black_italic": NUNITO_SANS_BLACK_ITALIC,
    },
}

GOTHIC_FONT_MAPPING: FontMapping = {
    SUPPORTED_BY_GOTHIC: {
        "light": ZENMARUGOTHIC_LIGHT,
        "regular": ZENMARUGOTHIC_REGULAR,
        "medium": ZENMARUGOTHIC_MEDIUM,
        "bold": ZENMARUGOTHIC_BOLD,
        "black": ZENMARUGOTHIC_BLACK,
    }
}


class Drawer:
    def __init__(
        self,
        draw: ImageDraw.ImageDraw,
        *,
        folder: str,
        dark_mode: bool,
        locale: Locale = Locale.american_english,
        sans: bool | None = None,
    ) -> None:
        self.draw = draw
        self.folder = folder
        self.dark_mode = dark_mode
        self.locale = locale
        self.sans = sans

    @classmethod
    def calc_dynamic_fontsize(
        cls, text: str, max_width: int, max_size: int, font: ImageFont.FreeTypeFont
    ) -> int:
        size = max_size
        while font.getlength(text) > max_width:
            size -= 1
            font = ImageFont.truetype(font.path, size)
        return size

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

    @staticmethod
    def resize_crop(image: Image.Image, size: tuple[int, int], *, zoom: float = 1.0) -> Image.Image:
        """Resize an image without changing its aspect ratio."""
        # Calculate the target height to maintain the aspect ratio
        width, height = image.size
        ratio = min(width / size[0], height / size[1])

        # Calculate the new size and left/top coordinates for cropping
        new_width = round(width / (ratio * zoom))
        new_height = round(height / (ratio * zoom))
        left = round((new_width - size[0]) / 2)
        top = round((new_height - size[1]) / 2)
        right = round(left + size[0])
        bottom = round(top + size[1])

        image = image.resize((new_width, new_height), resample=Image.Resampling.LANCZOS)
        return image.crop((left, top, right, bottom))

    @staticmethod
    def ratio_resize(
        image: Image.Image, *, width: int | None = None, height: int | None = None
    ) -> Image.Image:
        """Resize an image to a targeted width/height while maintaining the aspect ratio."""
        if width is not None and height is not None:
            msg = "Can't provide both width and height"
            raise ValueError(msg)

        if width is not None:
            im_height = round(image.height * (width / image.width))
            im_width = width
        elif height is not None:
            im_width = round(image.width * (height / image.height))
            im_height = height
        else:
            msg = "Either width or height must be provided"
            raise ValueError(msg)

        return image.resize((im_width, im_height), resample=Image.Resampling.LANCZOS)

    @staticmethod
    def top_crop(image: Image.Image, height: int) -> Image.Image:
        """Crop an image from the top."""
        left = 0
        top = 0
        right = image.width
        bottom = height
        return image.crop((left, top, right, bottom))

    @staticmethod
    def middle_crop(image: Image.Image, size: tuple[int, int]) -> Image.Image:
        """Crop an image from the center."""
        width, height = image.size
        left = width // 2 - size[0] // 2
        top = height // 2 - size[1] // 2
        right = left + size[0]
        bottom = top + size[1]

        return image.crop((left, top, right, bottom))

    @staticmethod
    def hex_to_rgb(hex_color_code: str) -> tuple[int, int, int]:
        hex_color_code = hex_color_code.lstrip("#")
        return tuple(int(hex_color_code[i : i + 2], 16) for i in (0, 2, 4))  # pyright: ignore [reportReturnType]

    @staticmethod
    def apply_color_opacity(
        color: tuple[int, int, int], opacity: float
    ) -> tuple[int, int, int, int]:
        return (*color, round(255 * opacity))

    @staticmethod
    def draw_dynamic_background(input_: DynamicBKInput) -> tuple[Image.Image, int]:
        """Draw a dynamic background with a variable number of cards."""
        card_num = input_.card_num

        # Determine the maximum number of cards
        if card_num == 1:
            max_card_num = 1
        elif card_num % 2 == 0:
            max_card_num = max(i for i in range(1, card_num) if card_num % i == 0)
        else:
            max_card_num = max(i for i in range(1, card_num) if (card_num - (i - 1)) % i == 0)
        max_card_num = input_.max_card_num or min(max_card_num, 8)

        # Calculate the number of columns
        cols = (
            card_num // max_card_num + 1
            if card_num % max_card_num != 0
            else card_num // max_card_num
        )

        # Calculate the width and height of the image
        width = (
            input_.left_padding
            + input_.right_padding
            + input_.card_width * cols
            + input_.card_x_padding * (cols - 1)
        )
        height = (
            (
                input_.top_padding.with_title
                if input_.draw_title
                else input_.top_padding.without_title
            )
            if isinstance(input_.top_padding, TopPadding)
            else input_.top_padding
        )
        height += (
            input_.bottom_padding
            + input_.card_height * max_card_num
            + input_.card_y_padding * (max_card_num - 1)
        )

        # Create a new image with the calculated dimensions and background color
        im = Image.new("RGBA", (width, height), input_.background_color)

        return im, max_card_num

    @classmethod
    def mask_image_with_color(
        cls, image: Image.Image, color: tuple[int, int, int], *, opacity: float = 1.0
    ) -> Image.Image:
        if opacity != 1.0:
            mask = Image.new("RGBA", image.size, cls.apply_color_opacity(color, opacity))
            return ImageChops.multiply(image, mask)
        colored_image = Image.new("RGBA", image.size, color)
        colored_image.putalpha(image.getchannel("A"))
        return colored_image

    @staticmethod
    def wrap_text(
        text: str, *, max_width: int, max_lines: int, font: ImageFont.FreeTypeFont, locale: Locale
    ) -> str:
        def truncate_line(line: str, width: int, ellipsis: str = "...") -> str:
            if font.getlength(line) <= width:
                return line

            ellipsis_width = font.getlength(ellipsis)
            available_width = width - ellipsis_width

            for i in range(len(line), 0, -1):
                if font.getlength(line[:i]) <= available_width:
                    return line[:i] + ellipsis

            return ellipsis

        if max_lines == 1:
            return truncate_line(text, max_width)

        if locale in {Locale.chinese, Locale.japanese, Locale.korean, Locale.taiwan_chinese}:
            words = list(text)
            space_char = ""
        else:
            words = text.split()
            space_char = " "

        result: list[str] = []
        current_line = ""

        for word in words:
            test_line = word if not current_line else current_line + space_char + word
            is_last_line = len(result) == max_lines - 1

            if font.getlength(test_line) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    if is_last_line:
                        result.append(truncate_line(test_line, max_width))
                    else:
                        result.append(current_line)
                        current_line = word
                else:
                    result.append(truncate_line(word, max_width))

            if len(result) == max_lines:
                break

        if current_line and len(result) < max_lines:
            result.append(truncate_line(current_line, max_width))

        if len(result) > max_lines:
            result = result[:max_lines]
            result[-1] = truncate_line(result[-1], max_width)

        return "\n".join(result)

    def _get_text_color(
        self, color: tuple[int, int, int] | None, emphasis: Literal["high", "medium", "low"]
    ) -> tuple[int, int, int, int]:
        if color is not None:
            return self.apply_color_opacity(color, EMPHASIS_OPACITY[emphasis])

        return self.apply_color_opacity(
            WHITE if self.dark_mode else BLACK, EMPHASIS_OPACITY[emphasis]
        )

    def get_font(
        self,
        size: int,
        style: FontStyle,
        *,
        locale: Locale | None = None,
        sans: bool = False,
        gothic: bool = False,
    ) -> ImageFont.FreeTypeFont:
        sans = self.sans or sans
        locale = locale or self.locale

        if sans and gothic:
            msg = "Cannot use sans and gothic fonts at the same time"
            raise ValueError(msg)

        if sans:
            mapping = SANS_FONT_MAPPING
        elif gothic:
            mapping = GOTHIC_FONT_MAPPING
        else:
            mapping = DEFAULT_FONT_MAPPING

        font_map = self.find_font_mapping(locale, mapping)

        if font_map is None:
            font_map = self.find_font_mapping(locale, DEFAULT_FONT_MAPPING)

        if font_map is None:
            msg = f"Unable to find font mapping for locale={locale}, sans={sans}, gothic={gothic}"
            raise ValueError(msg)

        if style.startswith("black") and style not in font_map:
            # Can't find black variant, use bold instead
            style = style.replace("black", "bold")  # pyright: ignore [reportAssignmentType]
        if style.endswith("_italic") and style not in font_map:
            # Can't find italic variant, use regular instead
            style = style.replace("_italic", "")  # pyright: ignore [reportAssignmentType]

        return ImageFont.truetype(font_map[style], size)

    def find_font_mapping(
        self, locale: Locale, mapping: FontMapping
    ) -> dict[FontStyle, str] | None:
        font_map = None
        for locales, font_map_ in mapping.items():
            if (isinstance(locales, tuple) and locale in locales) or locale == locales:
                font_map = font_map_
                break
        return font_map

    @staticmethod
    def open_image(
        file_path: pathlib.Path | str, size: tuple[int, int] | None = None
    ) -> Image.Image:
        try:
            image = Image.open(file_path)
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            image = Image.new("RGBA", (1, 1), (0, 0, 0, 0))

        if image.mode != "RGBA":
            image = image.convert("RGBA")
        if size is not None:
            image = image.resize(size, Image.Resampling.LANCZOS)
        return image.copy()

    @staticmethod
    def has_glyph(font: TTFont, char: str) -> bool:
        return any(ord(char) in table.cmap for table in font["cmap"].tables)  # pyright: ignore[reportAttributeAccessIssue]

    def write(
        self,
        text: LocaleStr | str,
        *,
        size: int,
        position: tuple[int, int],
        color: tuple[int, int, int] | None = None,
        style: FontStyle = "regular",
        emphasis: Literal["high", "medium", "low"] = "high",
        anchor: str | None = None,
        max_width: int | None = None,
        max_lines: int = 1,
        locale: Locale | None = None,
        no_write: bool = False,
        title_case: bool = False,
        sans: bool = False,
        gothic: bool = False,
        stroke_width: int = 0,
        stroke_color: tuple[int, int, int] | None = None,
        align_center: bool = False,
        textbox_size: tuple[int, int] = (0, 0),
        dynamic_fontsize: bool = False,
    ) -> TextBBox:
        """Returns (left, top, right, bottom) of the text bounding box."""
        if not text:
            return TextBBox(0, 0, 0, 0)

        if isinstance(text, str):
            translated_text = text
        else:
            translated_text = translator.translate(
                text, locale or self.locale, title_case=title_case
            )

        if dynamic_fontsize:
            if max_width is None:
                msg = "max_width must be provided when dynamic_fontsize is True"
                raise ValueError(msg)

            size = self.calc_dynamic_fontsize(
                translated_text,
                max_width=max_width,
                max_size=size,
                font=self.get_font(size, style, locale=locale, sans=sans, gothic=gothic),
            )

        font = self.get_font(size, style, locale=locale, sans=sans, gothic=gothic)
        tt_font = TTFont(font.path)

        if any(not self.has_glyph(tt_font, char) for char in translated_text):
            font = self.get_font(size, style, locale=locale)

        if max_width is not None and not dynamic_fontsize:
            translated_text = self.wrap_text(
                translated_text,
                max_width=max_width,
                max_lines=max_lines,
                font=font,
                locale=locale or self.locale,
            )

        if align_center:
            y_text = position[1]
            lines = translated_text.split("\n")

            for line in lines:
                line_textbbox = self.draw.textbbox(
                    (0, 0), line, font=font, anchor="lt", font_size=size
                )
                line_width, line_height = (
                    line_textbbox[2] - line_textbbox[0],
                    line_textbbox[3] - line_textbbox[1],
                )
                self.draw.text(
                    (position[0] + (textbox_size[0] - line_width) / 2, y_text),
                    line,
                    font=font,
                    fill=self._get_text_color(color, emphasis),
                )
                y_text += line_height + 10
        elif not no_write:
            self.draw.text(
                position,
                translated_text,
                font=font,
                fill=self._get_text_color(color, emphasis),
                anchor=anchor,
                stroke_width=stroke_width,
                stroke_fill=stroke_color,
            )

        textbbox = self.draw.textbbox(
            position, translated_text, font=font, anchor=anchor, font_size=size
        )
        return TextBBox(*(int(i) for i in textbbox))

    def open_static(
        self,
        url: str,
        *,
        folder: str | None = None,
        size: tuple[int, int] | None = None,
        mask_color: tuple[int, int, int] | None = None,
        opacity: float = 1.0,
    ) -> Image.Image:
        folder = folder or self.folder
        image = self.open_image(get_static_img_path(url, folder), size)
        if mask_color:
            image = self.mask_image_with_color(image, mask_color, opacity=opacity)
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
        path = pathlib.Path(f"hoyo-buddy-assets/assets/{folder}/{filename}")
        image = self.open_image(path, size)
        if mask_color:
            image = self.mask_image_with_color(image, mask_color, opacity=opacity)
        return image

    @classmethod
    def circular_crop(cls, image: Image.Image) -> Image.Image:
        """Crop an image into a circle."""
        path = pathlib.Path("hoyo-buddy-assets/assets/circular_mask.png")
        mask = cls.open_image(path, image.size)
        return cls.mask_image_with_image(image, mask)

    def modify_image_for_build_card(
        self,
        image: Image.Image,
        *,
        target_width: int,
        target_height: int,
        mask: Image.Image,
        background_color: tuple[int, int, int] | None = None,
        zoom: float = 1.0,
        top_crop: bool = False,
    ) -> Image.Image:
        if top_crop:
            image = self.ratio_resize(image, width=target_width)
            image = self.top_crop(image, target_height)
        else:
            image = self.resize_crop(image, (target_width, target_height), zoom=zoom)

        if self.dark_mode:
            overlay = Image.new("RGBA", image.size, self.apply_color_opacity((0, 0, 0), 0.1))
            image = Image.alpha_composite(image, overlay)

        if background_color is not None:
            new_im = Image.new("RGBA", (target_width, target_height), background_color)
            new_im.alpha_composite(image)
            return self.mask_image_with_image(new_im, mask)

        return self.mask_image_with_image(image, mask)

    @staticmethod
    def mask_image_with_image(image: Image.Image, mask: Image.Image) -> Image.Image:
        overlay = Image.new("RGBA", mask.size)
        return Image.composite(image, overlay, mask)

    @classmethod
    def create_pattern_blob(
        cls,
        *,
        color: tuple[int, int, int],
        rotation: float,
        pattern: Image.Image,
        blob: Image.Image,
        pattern_opacity: float = 0.97,
    ) -> Image.Image:
        pattern_color = cls.blend_color(color, (0, 0, 0), pattern_opacity)

        # Mask pattern and blob with colors
        colored_pattern = cls.mask_image_with_color(pattern, pattern_color)
        colored_blob = cls.mask_image_with_color(blob, color)

        # Crop pattern to blob size and mask it with blob shape
        colored_pattern = cls.resize_crop(colored_pattern, blob.size)
        colored_pattern = cls.mask_image_with_image(colored_pattern, blob)

        # Paste blob, then pattern
        result = Image.new("RGBA", blob.size)
        result.alpha_composite(colored_blob)
        result.alpha_composite(colored_pattern)
        return result.rotate(rotation, resample=Image.Resampling.BICUBIC, expand=True)

    @staticmethod
    def hex_to_hsl(hex_color: str) -> tuple[int, int, int]:
        # Remove '#' if present
        hex_color = hex_color.lstrip("#")

        # Convert hex to RGB
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0

        # Find min and max values
        cmin = min(r, g, b)
        cmax = max(r, g, b)
        delta = cmax - cmin

        # Calculate hue
        if delta == 0:
            h = 0
        elif cmax == r:
            h = ((g - b) / delta) % 6
        elif cmax == g:
            h = (b - r) / delta + 2
        else:
            h = (r - g) / delta + 4

        h = round(h * 60)
        if h < 0:
            h += 360

        # Calculate lightness
        l = (cmax + cmin) / 2

        # Calculate saturation
        s = 0 if delta == 0 else delta / (1 - abs(2 * l - 1))

        # Convert to percentages
        s = round(s * 100)
        l = round(l * 100)

        return (h, s, l)

    @staticmethod
    def hsl_to_hex(hsl_color: tuple[int, int, int]) -> str:
        h, s, l = hsl_color
        h /= 360
        s /= 100
        l /= 100

        if s == 0:
            r = g = b = l
        else:

            def hue_to_rgb(p: float, q: float, t: float) -> float:
                if t < 0:
                    t += 1
                if t > 1:
                    t -= 1
                if t < 1 / 6:
                    return p + (q - p) * 6 * t
                if t < 1 / 2:
                    return q
                if t < 2 / 3:
                    return p + (q - p) * (2 / 3 - t) * 6
                return p

            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            r = hue_to_rgb(p, q, h + 1 / 3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1 / 3)

        r = round(r * 255)
        g = round(g * 255)
        b = round(b * 255)

        return f"#{r:02x}{g:02x}{b:02x}"

    def get_agent_special_stat_color(self, agent_color: str) -> tuple[int, int, int]:
        agent_color_hsl = self.hex_to_hsl(agent_color)
        agent_special_color_hsl = (agent_color_hsl[0], 40, 50)
        agent_special_color = self.hex_to_rgb(self.hsl_to_hex(agent_special_color_hsl))
        return self.blend_color(agent_special_color, (20, 20, 20), 0.6)

    @staticmethod
    def save_image(img: Image.Image, *, step: float = 0.95) -> io.BytesIO:
        """Save an image to a BytesIO object, resizing it if it exceeds the Discord file size limit."""
        while True:
            bytes_obj = io.BytesIO()
            img.save(bytes_obj, format="PNG")
            size_in_bytes = bytes_obj.tell()

            if size_in_bytes < DC_MAX_FILESIZE:
                break

            width, height = img.size
            img = img.resize((int(width * step), int(height * step)), Image.Resampling.LANCZOS)

        return bytes_obj
