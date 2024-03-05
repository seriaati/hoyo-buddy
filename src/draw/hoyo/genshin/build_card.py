import io
from typing import TYPE_CHECKING

from cachetools import LRUCache, cached
from discord import Locale
from enka.enums import FightPropType
from PIL import Image, ImageDraw

from src.utils import timer

from ...draw import Drawer

if TYPE_CHECKING:
    from enka.models import Character


def cache_key(
    locale: Locale,
    dark_mode: bool,
    character: "Character",
    image_url: str,
) -> str:
    return f"{character!r}-{locale}-{dark_mode}-{image_url}"


@timer
@cached(cache=LRUCache(maxsize=100), key=cache_key)
def draw_genshin_card(
    locale: Locale,
    dark_mode: bool,
    character: "Character",
    image_url: str,
) -> io.BytesIO:
    mode = "dark" if dark_mode else "light"
    text_color = (241, 241, 241) if dark_mode else (33, 33, 33)

    # main card
    im: Image.Image = Image.open(
        f"hoyo-buddy-assets/assets/gi-build-card/backgrounds/{mode}_{character.element.name.title()}.png"
    )
    draw = ImageDraw.Draw(im)
    drawer = Drawer(
        draw, folder="gi-build-card", dark_mode=dark_mode, locale=Locale.american_english
    )

    # character image
    character_im = drawer.open_static(image_url)
    mask = drawer.open_asset("mask.png")
    character_im = drawer.modify_image_for_build_card(
        character_im, target_width=472, target_height=839
    )
    im.paste(character_im, (51, 34), mask)

    # stats
    fight_props_to_draw = [
        FightPropType.FIGHT_PROP_MAX_HP,
        FightPropType.FIGHT_PROP_CUR_DEFENSE,
        FightPropType.FIGHT_PROP_CUR_ATTACK,
        FightPropType.FIGHT_PROP_CRITICAL,
        FightPropType.FIGHT_PROP_CRITICAL_HURT,
        FightPropType.FIGHT_PROP_CHARGE_EFFICIENCY,
        FightPropType.FIGHT_PROP_ELEMENT_MASTERY,
    ]

    add_hurt_fight_prop = character.highest_dmg_bonus_stat.type
    add_hurt_icon = drawer.open_asset(f"fight-props/{mode}_{add_hurt_fight_prop.name}.png")
    im.paste(add_hurt_icon, (590, 812), add_hurt_icon)

    fight_props_to_draw.append(add_hurt_fight_prop)

    draw = ImageDraw.Draw(im)
    for index, fight_prop_type in enumerate(fight_props_to_draw):
        fight_prop = character.stats[fight_prop_type]
        offset = (
            157
            if fight_prop.type
            in {FightPropType.FIGHT_PROP_MAX_HP, FightPropType.FIGHT_PROP_CUR_DEFENSE}
            else 159
        )
        drawer.write(
            fight_prop.formatted_value,
            size=45,
            style="medium",
            position=(660, offset + 93 * index),
            color=text_color,
        )

    # weapon
    weapon = character.weapon
    weapon_icon = drawer.open_static(weapon.icon, size=(160, 160))
    im.paste(weapon_icon, (947, 151), weapon_icon)

    x_offset = 1135
    drawer.locale = locale
    drawer.write(
        weapon.name,
        size=40,
        color=text_color,
        style="medium",
        position=(x_offset, 151),
        max_width=x_offset - 819,
    )
    drawer.locale = Locale.american_english

    main_stat = weapon.stats[0]
    icon = drawer.open_asset(f"fight-props/{mode}_{main_stat.type.name}.png", size=(36, 36))
    im.paste(icon, (x_offset + 8, 220), icon)
    textbbox = drawer.write(
        main_stat.formatted_value,
        size=35,
        style="medium",
        position=(x_offset + icon.width + 8 + 15, 213),
        color=text_color,
    )

    if len(weapon.stats) > 1:
        sub_stat = weapon.stats[1]
        sub_x_offset = textbbox[2] + 20
        sub_stat_icon = drawer.open_asset(
            f"fight-props/{mode}_{sub_stat.type.name}.png", size=(36, 36)
        )
        im.paste(sub_stat_icon, (sub_x_offset, 220), sub_stat_icon)
        drawer.write(
            sub_stat.formatted_value,
            size=35,
            style="medium",
            position=(sub_x_offset + sub_stat_icon.width + 15, 213),
            color=text_color,
        )

    text = f"R{weapon.refinement}"
    textbbox = drawer.write(
        text, size=35, style="medium", position=(x_offset, 275), color=text_color
    )
    drawer.write(
        f"Lv.{weapon.level}/{weapon.max_level}",
        size=35,
        style="medium",
        position=(textbbox[2] + 30, 275),
        color=text_color,
    )

    # constellations
    # start pos (1025, 380)
    # 3x2 grid, x offset between each item is 137, y offset is 106
    for index, const in enumerate(character.constellations):
        icon_color = (255, 255, 255) if dark_mode else (67, 67, 67)
        const_icon = drawer.open_static(
            const.icon, size=(80, 80), mask_color=icon_color, opacity=1.0 if const.unlocked else 0.1
        )
        im.paste(const_icon, (1025 + 137 * (index % 3), 380 + 106 * (index // 3)), const_icon)

    # talents
    # start pos (1025, 636)
    # 3x1 grid, x offset between each item is 137
    # text is 92 below the icon
    talent_order = character.talent_order
    talents = [
        next(t for t in character.talents if t.id == talent_id) for talent_id in talent_order
    ]
    for index, talent in enumerate(talents):
        x_pos = 1025 + 137 * index
        icon_color = (255, 255, 255) if dark_mode else (67, 67, 67)
        talent_icon = drawer.open_static(talent.icon, size=(80, 80), mask_color=icon_color)
        im.paste(talent_icon, (x_pos, 636), talent_icon)

        drawer.write(
            str(talent.level),
            size=35,
            style="medium",
            position=(x_pos + talent_icon.width // 2, 748),
            color=text_color,
            anchor="mm",
        )

    # friendship level
    drawer.write(
        str(character.friendship_level),
        size=30,
        style="medium",
        position=(1132, 840),
        color=text_color,
    )

    # level
    drawer.write(
        f"Lv.{character.level}/{character.max_level}",
        size=30,
        style="medium",
        position=(1215, 840),
        color=text_color,
    )

    # artifacts
    # start pos (68, 970)
    # 5x1 grid, x offset between each item is 296
    for index, artifact in enumerate(character.artifacts):
        x_pos = 68 + 296 * index

        # icon
        artifact_icon = drawer.open_static(artifact.icon, size=(90, 90))
        im.paste(artifact_icon, (x_pos, 970), artifact_icon)

        # rarity
        rarity_x_dict = {1: 36, 2: 25, 3: 16, 4: 6, 5: -4}
        rarity_icon = drawer.open_asset(f"stars/{mode}_{artifact.rarity}.png")
        im.paste(rarity_icon, (x_pos + rarity_x_dict[artifact.rarity], 1066), rarity_icon)

        # main stat
        main_stat = artifact.main_stat
        main_stat_icon = drawer.open_asset(
            f"fight-props/{mode}_{main_stat.type.name}.png", size=(32, 32), mask_color=text_color
        )
        textbbox = drawer.write(
            main_stat.formatted_value,
            size=30,
            style="medium",
            position=(x_pos + 247, 1080),
            color=text_color,
            anchor="rs",
        )
        im.paste(
            main_stat_icon,
            (textbbox[0] - main_stat_icon.width - 8, 1052),
            main_stat_icon,
        )

        # level
        drawer.write(
            f"+{artifact.level}",
            size=30,
            style="medium",
            position=(x_pos + 247, 1034),
            color=text_color,
            anchor="rs",
        )

        # sub stats
        # 2x2 grid
        for sub_index, sub_stat in enumerate(artifact.sub_stats):
            sub_x_offset = x_pos + 30 + 116 * (sub_index % 2)
            sub_y_offset = 1120 + 54 * (sub_index // 2)
            icon_color = (255, 255, 255) if dark_mode else (67, 67, 67)
            sub_stat_icon = drawer.open_asset(
                f"fight-props/{mode}_{sub_stat.type.name}.png",
                size=(27, 27),
                mask_color=icon_color,
            )
            im.paste(sub_stat_icon, (sub_x_offset, sub_y_offset), sub_stat_icon)
            drawer.write(
                sub_stat.formatted_value,
                size=23,
                style="light",
                position=(sub_x_offset + 35, sub_y_offset - 2),
                color=text_color,
            )

    fp = io.BytesIO()
    im.save(fp, format="WEBP", loesless=True)
    return fp
