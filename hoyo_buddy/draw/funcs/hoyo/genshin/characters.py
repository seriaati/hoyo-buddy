import io
from typing import TYPE_CHECKING

from cachetools import LRUCache, cached
from PIL import Image, ImageDraw

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.draw.drawer import BLACK, DARK_SURFACE, LIGHT_SURFACE, WHITE, Drawer
from hoyo_buddy.hoyo.clients.gpy_client import GenshinClient
from hoyo_buddy.models import DynamicBKInput

if TYPE_CHECKING:
    from collections.abc import Sequence

    import genshin
    from discord import Locale

    from hoyo_buddy.bot.translator import Translator


def draw_character_card(
    characters: "Sequence[genshin.models.Character]",
    talents: dict[str, str],
    pc_icons: dict[str, str],
    dark_mode: bool,
    translator: "Translator",
    locale: "Locale",
) -> io.BytesIO:
    c_cards: dict[str, Image.Image] = {}
    for character in characters:
        talent = talents.get(GenshinClient.convert_character_id_to_ambr_format(character), "?/?/?")
        card = draw_small_character_card(talent, dark_mode, character, translator, locale)
        c_cards[str(character.id)] = card

    first_card = list(c_cards.values())[0]
    bk_input = DynamicBKInput(
        top_padding=35,
        bottom_padding=5,
        left_padding=10,
        right_padding=5,
        card_width=first_card.width,
        card_height=first_card.height,
        card_x_padding=5,
        card_y_padding=35,
        card_num=len(c_cards),
        background_color=DARK_SURFACE if dark_mode else LIGHT_SURFACE,
        draw_title=False,
    )
    background, max_card_num = Drawer.draw_dynamic_background(bk_input)
    draw = ImageDraw.Draw(background)
    drawer = Drawer(draw, folder="gi-characters", dark_mode=dark_mode)

    for index, card in enumerate(c_cards.values()):
        x = (index // max_card_num) * (
            bk_input.card_width + bk_input.card_x_padding
        ) + bk_input.left_padding
        y = 0
        if isinstance(bk_input.top_padding, int):
            y = (index % max_card_num) * (
                bk_input.card_height + bk_input.card_y_padding
            ) + bk_input.top_padding
        background.paste(card, (x, y), card)
        character_id = list(c_cards.keys())[index]
        pc_icon_url = pc_icons.get(character_id)
        if pc_icon_url:
            icon = drawer.open_static(pc_icon_url, size=(214, 214))
            background.paste(icon, (x, y - 29), icon)

    fp = io.BytesIO()
    background.save(fp, format="WEBP", loseless=True)
    return fp


def cache_key(
    talent_str: str,
    dark_mode: bool,
    character: "genshin.models.Character",
    _: "Translator",
    locale: "Locale",
) -> str:
    return (
        f"{talent_str}_"
        f"{dark_mode}_"
        f"{character.id}_"
        f"{character.level}_"
        f"{character.friendship}_"
        f"{character.constellation}_"
        f"{character.weapon.refinement}_"
        f"{character.weapon.id}_"
        f"{character.element}"
        f"{locale.value}"
    )


@cached(LRUCache(maxsize=128), key=cache_key)
def draw_small_character_card(
    talent_str: str,
    dark_mode: bool,
    character: "genshin.models.Character",
    translator: "Translator",
    locale: "Locale",
) -> Image.Image:
    im: Image.Image = Image.open(
        f"hoyo-buddy-assets/assets/gi-characters/{'dark' if dark_mode else 'light'}_{character.element}.png"
    )
    draw = ImageDraw.Draw(im)
    drawer = Drawer(draw, folder="gi-characters", dark_mode=dark_mode, translator=translator)

    text = LocaleStr(
        "C{const}R{refine}",
        key="const_refine_str",
        const=character.constellation,
        refine=character.weapon.refinement,
    )
    drawer.write(text, size=31, position=(227, 32), locale=locale, style="medium")
    text = LocaleStr("Lv.{level}", key="level_str", level=character.level)
    drawer.write(text, size=31, position=(227, 72), locale=locale, style="medium")

    friend_textbbox = drawer.write(
        str(character.friendship), size=18, position=(287, 154), anchor="mm"
    )
    talent_textbbox = drawer.write(talent_str, size=18, position=(368, 154), anchor="mm")

    size = 4
    x_start = 287 + (friend_textbbox[2] - friend_textbbox[0]) // 2
    x_end = 360 - (talent_textbbox[2] - talent_textbbox[0]) // 2
    x_avg = (x_start + x_end) // 2
    y_start = 156 - size
    draw.ellipse((x_avg, y_start, x_avg + size, y_start + size), fill=WHITE if dark_mode else BLACK)

    weapon_icon = drawer.open_static(character.weapon.icon)
    weapon_icon = weapon_icon.resize((84, 84))
    im.paste(weapon_icon, (332, 30), weapon_icon)

    return im
