from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import BLACK, WHITE, Drawer
from hoyo_buddy.draw.funcs.hoyo.hsr.common import (
    get_character_skills,
    get_character_stats,
    get_stat_icon,
)

if TYPE_CHECKING:
    import io

    import enka

    import hoyo_buddy.models as hb_models
    from hoyo_buddy.enums import Locale


def draw_hsr_build_card(
    character: enka.hsr.Character | hb_models.HoyolabHSRCharacter,
    locale: Locale,
    dark_mode: bool,
    image_url: str,
    primary_hex: str,
) -> io.BytesIO:
    primary = Drawer.hex_to_rgb(primary_hex)
    if dark_mode:
        # blend with dark gray
        primary = Drawer.blend_color(primary, (32, 36, 33), 0.88)

    dark_primary = Drawer.blend_color(primary, WHITE if dark_mode else BLACK, 0.6)
    light_primary = Drawer.blend_color(
        primary, BLACK if dark_mode else WHITE, 0.23 if dark_mode else 0.18
    )

    im = Image.new("RGBA", (2244, 1297), primary)
    draw = ImageDraw.Draw(im)
    drawer = Drawer(draw, folder="hsr-build-card", dark_mode=dark_mode)

    # character image
    character_im = drawer.open_static(image_url)
    character_im = drawer.modify_image_for_build_card(
        character_im,
        target_width=640,
        target_height=1138,
        mask=drawer.open_asset("img/mask.png"),
        background_color=dark_primary,
    )
    im.paste(character_im, (0, 159), character_im)

    # base card
    card = drawer.open_asset("base/dark_card.png" if dark_mode else "base/light_card.png")
    width = 1540
    height = 1260
    shadow_width = card.width - width
    shadow_height = card.height - height
    real_pos = (704, 37)
    pos = (real_pos[0] - shadow_width, real_pos[1] - shadow_height)
    im.paste(card, pos, card)

    # character name
    name_textbbox = drawer.write(
        character.name.upper(),
        size=128,
        position=(770, (252 - real_pos[1]) // 2 + real_pos[1]),
        color=primary,
        style="bold",
        anchor="lm",
        max_width=870,
        locale=locale,
    )

    # character level
    padding = 50
    width = 337
    height = name_textbbox[3] - name_textbbox[1]
    radius = 30

    box_x = name_textbbox[2] + padding
    box_y = name_textbbox[1]
    draw.rounded_rectangle((box_x, box_y, box_x + width, box_y + height), radius, primary)
    box_right_pos = box_x + width

    # write in the middle of the rectangle
    level_str = f"Lv.{character.level}/{character.max_level}"
    drawer.write(
        level_str,
        size=64,
        position=(box_x + width / 2, box_y + height / 2),
        color=BLACK if dark_mode else WHITE,
        style="medium",
        anchor="mm",
    )

    # character eldolon
    padding = 36
    width = 135
    box_x = box_right_pos + padding
    draw.rounded_rectangle((box_x, box_y, box_x + width, box_y + height), radius, primary)

    # write in the middle of the rectangle
    drawer.write(
        f"E{character.eidolons_unlocked}",
        size=64,
        position=(box_x + width / 2, box_y + height / 2),
        color=BLACK if dark_mode else WHITE,
        style="medium",
        anchor="mm",
    )

    # traces
    width = 564
    height = 377
    radius = 25
    box_x = 770
    box_y = 252
    draw.rounded_rectangle((box_x, box_y, box_x + width, box_y + height), radius, light_primary)

    trace_bk = drawer.open_asset("base/trace_bk.png", mask_color=primary)
    x = 825
    y = 273
    padding = 16

    traces, main_bubbles, sub_bubbles = get_character_skills(character)

    for trace_id, trace in traces.items():
        if trace is None:
            continue

        # trace bubble
        icon = drawer.open_static(
            trace.icon, size=(65, 65), mask_color=BLACK if dark_mode else WHITE
        )
        im.paste(trace_bk, (x, y), trace_bk)
        im.paste(icon, (x + 7, y + 4), icon)
        drawer.write(
            str(trace.level),
            position=(x + 109, y + 35),
            size=48,
            color=BLACK if dark_mode else WHITE,
            style="medium",
            anchor="mm",
        )

        # main bubble
        circle_height = 72
        circle_x = x + 178
        main_bubble = main_bubbles[trace_id]
        if main_bubble:
            icon = drawer.open_static(
                main_bubble.icon, size=(60, 60), mask_color=BLACK if dark_mode else WHITE
            )
            draw.ellipse((circle_x, y, circle_x + circle_height, y + circle_height), fill=primary)
            im.paste(icon, (circle_x + 6, y + 6), icon)

        # sub bubbles
        circle_x += circle_height + 14
        sub_circle_height = 50
        circle_y = y + (circle_height - sub_circle_height) // 2
        sub_bubbles_ = sub_bubbles[trace_id]
        for sub_bubble in sub_bubbles_:
            if sub_bubble is None:
                continue
            # draw a line in the middle of the circle
            width = 10
            draw.line(
                (circle_x - 15, y + circle_height // 2, circle_x + width, y + circle_height // 2),
                fill=primary,
                width=width,
            )
            draw.ellipse(
                (circle_x, circle_y, circle_x + sub_circle_height, circle_y + sub_circle_height),
                fill=primary,
            )

            icon = drawer.open_static(
                sub_bubble.icon, size=(50, 50), mask_color=BLACK if dark_mode else WHITE
            )
            # place the icon in the middle of the circle
            icon_x = circle_x + (sub_circle_height - icon.width) // 2
            icon_y = circle_y + (sub_circle_height - icon.height) // 2
            im.paste(icon, (icon_x, icon_y), icon)

            circle_x += 64

        y += trace_bk.height + padding

    # character stats
    width = 564
    height = 609
    box_x = 770
    box_y = 653
    radius = 25
    draw.rounded_rectangle((box_x, box_y, box_x + width, box_y + height), radius, light_primary)

    # attributes
    attributes, _ = get_character_stats(character)

    x = 804
    y = 685
    text_padding = 14
    padding = 13

    for index, (icon, value) in enumerate(attributes.items()):
        icon_ = get_stat_icon(filename=icon, size=(80, 80), mask_color=dark_primary)
        im.paste(icon_, (x, y), icon_)

        drawer.write(
            value,
            position=(x + icon_.width + text_padding, round(icon_.height / 2) + y - 1),
            size=40,
            color=dark_primary,
            style="medium",
            anchor="lm",
        )

        if index == 5:
            x = 1070
            y = 685
        else:
            y += icon_.height + padding

    # light cone
    cone = character.light_cone
    width = 837
    height = 377
    box_x = 1375
    box_y = 252
    radius = 25
    draw.rounded_rectangle((box_x, box_y, box_x + width, box_y + height), radius, light_primary)

    if cone is not None:
        # light cone icon
        icon = drawer.open_static(cone.icon.image, size=(221, 314))
        im.paste(icon, (box_x + 27, box_y + 25), icon)
        light_cone_icon_right_pos = box_x + 27 + icon.width
        icon_top_pos = box_y + 25

        # light cone name
        max_width = 459
        textbbox = drawer.write(
            cone.name,
            size=48,
            position=(light_cone_icon_right_pos + 28, icon_top_pos + 45),
            color=primary,
            style="bold",
            max_width=max_width,
            max_lines=2,
            anchor="lm",
            locale=locale,
        )
        text_bottom_pos = textbbox[3]
        text_left_pos = textbbox[0]

        # level
        width = 182
        height = 55
        radius = 10
        box_x = text_left_pos
        box_y = text_bottom_pos + 20
        draw.rounded_rectangle((box_x, box_y, box_x + width, box_y + height), radius, primary)
        level_str = f"Lv.{cone.level}/{cone.max_level}"
        drawer.write(
            level_str,
            size=36,
            position=(box_x + width / 2, box_y + height / 2),
            color=BLACK if dark_mode else WHITE,
            anchor="mm",
            style="medium",
        )
        box_right_pos = box_x + width

        # superimpose
        width = 82
        height = 55
        radius = 10
        box_x = box_right_pos + 20
        draw.rounded_rectangle((box_x, box_y, box_x + width, box_y + height), radius, primary)
        drawer.write(
            f"S{cone.superimpose}",
            size=36,
            position=(box_x + width / 2, box_y + height / 2),
            color=BLACK if dark_mode else WHITE,
            anchor="mm",
            style="medium",
        )

        box_bottom_pos = box_y + height
        x = text_left_pos
        y = box_bottom_pos + 20
        text_padding = 17
        second_attr_x = 0
        for i, stat in enumerate((cone.stats)[:4]):
            icon = get_stat_icon(stat, size=(50, 50), mask_color=dark_primary)
            im.paste(icon, (x, y), icon)

            textbbox = drawer.write(
                stat.formatted_value,
                size=32,
                position=(x + icon.width + 2, round(icon.height / 2) + y - 1),
                color=dark_primary,
                anchor="lm",
            )

            if i == 1:
                x = text_left_pos
                y += icon.height + 20
            elif i == 2:
                x = second_attr_x
            else:
                second_attr_x = x = textbbox[2] + text_padding

    # relic
    relics = character.relics
    x = 1374
    y = 653
    width = 399
    height = 187
    radius = 25
    x_padding = 40
    y_padding = 24

    for index in range(7):
        draw.rounded_rectangle((x, y, x + width, y + height), radius, light_primary)

        relic = next((relic for relic in relics if relic.type.value == index + 1), None)
        if relic is not None:
            # relic icon
            icon = drawer.open_static(relic.icon, size=(128, 128))
            im.paste(icon, (x + 14, y + 15), icon)
            relic_icon_right_pos = x + 14 + icon.width

            # rarity
            star_icon = drawer.open_asset("img/star.png", size=(20, 20), mask_color=primary)
            # align with the middle of relic icon

            pos = (x + 68 + star_icon.height // 2, y + 150 + star_icon.height // 2)
            rarity = relic.rarity
            size = star_icon.size
            upper_left = (pos[0] - rarity / 2 * size[0], pos[1] - size[1] / 2)
            for i in range(rarity):
                im.paste(
                    star_icon, (int(upper_left[0] + i * (size[0])), int(upper_left[1])), star_icon
                )

            # main stat
            icon = get_stat_icon(relic.main_stat, size=(50, 50), mask_color=dark_primary)
            icon_y = y + 15
            im.paste(icon, (relic_icon_right_pos + 5, icon_y), icon)
            # text
            textbbox = drawer.write(
                relic.main_stat.formatted_value,
                position=(
                    relic_icon_right_pos + 5 + icon.width + 2,
                    round(icon.height / 2) + icon_y - 1,
                ),
                size=36,
                color=dark_primary,
                style="medium",
                anchor="lm",
            )
            main_stat_text_height = textbbox[3] - textbbox[1]

            # level
            level_width = 58
            level_height = main_stat_text_height + 10
            radius = 10
            padding = 10
            box_x = relic_icon_right_pos + 183
            box_y = round(main_stat_text_height / 2) - round(level_height / 2) + textbbox[1] - 2
            draw.rounded_rectangle(
                (box_x, box_y, box_x + level_width, box_y + level_height), radius, primary
            )
            drawer.write(
                f"+{relic.level}",
                position=(box_x + level_width / 2, box_y + level_height / 2),
                size=24,
                color=BLACK if dark_mode else WHITE,
                anchor="mm",
                style="medium",
            )

            # sub stats
            stat_x = relic_icon_right_pos + 8  # main stat icon right pos
            stat_y = icon_y + icon.height + 10  # main stat icon bottom pos
            stat_y_padding = 10

            for i, stat in enumerate(relic.sub_stats):
                icon = get_stat_icon(stat, size=(40, 40), mask_color=dark_primary)
                im.paste(icon, (stat_x, stat_y), icon)
                sub_stat_icon_right_pos = stat_x + icon.width

                text = stat.formatted_value

                drawer.write(
                    text,
                    position=(sub_stat_icon_right_pos + 5, stat_y + 3),
                    size=24,
                    color=dark_primary,
                )
                stat_x = sub_stat_icon_right_pos + 81
                if i == 1:
                    stat_x = relic_icon_right_pos + 8
                    stat_y += icon.height + stat_y_padding

        x += width + x_padding
        if index in {1, 3}:
            x = 1374
            y += height + y_padding

    # logo
    # filename = "dark_logo.png" if dark_mode else "light_logo.png"
    # logo = drawer.open_asset(f"img/{filename}")
    # im.paste(logo, (2075, 84), logo)

    return Drawer.save_image(im)
