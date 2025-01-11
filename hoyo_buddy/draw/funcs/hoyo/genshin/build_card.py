from __future__ import annotations

import io
from typing import TYPE_CHECKING

from discord import Locale
from enka.gi import FightPropType, Talent
from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.draw.funcs.hoyo.genshin.common import ARTIFACT_POS, STATS_ORDER
from hoyo_buddy.models import HoyolabGICharacter, HoyolabGITalent

if TYPE_CHECKING:
    from enka.gi import Character


__all__ = ("draw_genshin_card",)


def draw_genshin_card(
    locale_: str,
    dark_mode: bool,
    character: Character | HoyolabGICharacter,
    image_url: str,
    zoom: float,
    rank: str | None,
) -> io.BytesIO:
    locale = Locale(locale_)
    mode = "dark" if dark_mode else "light"
    text_color = (241, 241, 241) if dark_mode else (33, 33, 33)

    # main card
    im: Image.Image = Drawer.open_image(
        f"hoyo-buddy-assets/assets/gi-build-card/backgrounds/{mode}_{character.element.name.title()}.png"
    )
    draw = ImageDraw.Draw(im)
    drawer = Drawer(
        draw, folder="gi-build-card", dark_mode=dark_mode, locale=Locale.american_english
    )

    # character image
    character_im = drawer.open_static(image_url)
    character_im = drawer.modify_image_for_build_card(
        character_im,
        target_width=472,
        target_height=839,
        mask=drawer.open_asset("mask.png"),
        zoom=zoom,
    )
    im.paste(character_im, (51, 34), character_im)

    # stats
    fight_props_to_draw = list(STATS_ORDER).copy()

    add_hurt_fight_prop = character.highest_dmg_bonus_stat.type
    if isinstance(add_hurt_fight_prop, FightPropType):
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
    talents: list[Talent | HoyolabGITalent] = []
    for talent_id in talent_order:
        talent = next((t for t in character.talents if t.id == talent_id), None)
        if talent is None:
            continue
        talents.append(talent)

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
    friendship = drawer.open_asset(f"{mode}_friendship.png")
    im.alpha_composite(friendship, (35, 5))
    drawer.write(
        str(character.friendship_level),
        size=30,
        style="bold",
        position=(113, 50),
        color=text_color,
        anchor="mm",
    )

    # level
    level = drawer.open_asset(f"{mode}_level.png")
    im.alpha_composite(level, (414, 815))
    drawer.write(
        f"Lv.{character.level}",
        size=40,
        style="bold",
        position=(485, 859),
        color=text_color,
        anchor="mm",
    )

    # rank
    if rank is not None:
        drawer.write(
            rank,
            position=(989, 825),
            size=26,
            align_center=True,
            textbox_size=(448, 76),
            max_lines=2,
            locale=locale,
        )

    # artifacts
    # start pos (68, 970)
    # 5x1 grid, x offset between each item is 296
    for index in range(5):
        x_pos = 68 + 296 * index

        if isinstance(character, HoyolabGICharacter):
            artifact = next((a for a in character.artifacts if a.pos == index + 1), None)
        else:
            artifact = next(
                (a for a in character.artifacts if ARTIFACT_POS[a.equip_type] == index + 1), None
            )

        if artifact is None:
            continue

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
        im.paste(main_stat_icon, (textbbox[0] - main_stat_icon.width - 8, 1052), main_stat_icon)

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
                f"fight-props/{mode}_{sub_stat.type.name}.png", size=(27, 27), mask_color=icon_color
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
    im.save(fp, format="PNG", loesless=True)
    return fp
