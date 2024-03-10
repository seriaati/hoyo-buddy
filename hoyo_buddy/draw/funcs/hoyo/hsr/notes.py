from io import BytesIO
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from hoyo_buddy.bot.translator import LocaleStr, Translator
from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.utils import format_timedelta

if TYPE_CHECKING:
    from discord import Locale
    from genshin.models import StarRailNote

__all__ = ("draw_hsr_notes_card",)


def draw_hsr_notes_card(
    notes: "StarRailNote", locale: "Locale", translator: Translator, dark_mode: bool
) -> BytesIO:
    filename = f"{'dark' if dark_mode else 'light'}-hsr"
    im = Image.open(f"hoyo-buddy-assets/assets/notes/{filename}.png")
    draw = ImageDraw.Draw(im)
    drawer = Drawer(draw, folder="hsr-notes", dark_mode=dark_mode, translator=translator)

    drawer.write(
        LocaleStr("Real-Time Notes", key="notes-card.gi.realtime-notes"),
        size=64,
        position=(76, 67),
        style="bold",
    )

    drawer.write(
        LocaleStr("Daily Training", key="notes-card.hsr.daily-training"),
        size=35,
        position=(110, 400),
        style="light",
        locale=locale,
    )
    drawer.write(
        f"{notes.current_train_score}/{notes.max_train_score}",
        size=60,
        position=(110, 460),
        style="medium",
    )

    drawer.write(
        LocaleStr("Trailblaze Power", key="notes-card.hsr.trailblaze-power"),
        size=35,
        position=(110, 800),
        style="light",
        locale=locale,
    )
    drawer.write(
        f"{notes.current_stamina}/{notes.max_stamina}",
        size=60,
        position=(110, 860),
        style="medium",
    )

    drawer.write(
        LocaleStr("Echo of War Discounts", key="notes-card.hsr.echo-of-war-discounts"),
        size=35,
        position=(596, 400),
        style="light",
        locale=locale,
    )
    textbbox = drawer.write(
        f"{notes.remaining_weekly_discounts}/{notes.max_weekly_discounts}",
        size=60,
        position=(596, 460),
        style="medium",
    )
    drawer.write(
        LocaleStr("Remaining", key="notes-card.gi.remaining"),
        size=30,
        position=(textbbox[2] + 20, textbbox[3] - 5),
        anchor="ls",
    )

    drawer.write(
        LocaleStr("Reserved Power", key="notes-card.hsr.reserved-power"),
        size=35,
        position=(596, 800),
        style="light",
        locale=locale,
    )
    textbbox = drawer.write(
        f"{notes.current_reserve_stamina}/2400",
        size=60,
        position=(596, 860),
        style="medium",
    )

    exped_padding = 201
    icon_pos = (1060, 231)
    text_x_padding = 20

    for index, exped in enumerate(notes.expeditions):
        pos = (icon_pos[0], index * exped_padding + icon_pos[1])

        icon = drawer.open_static(exped.item_url, size=(100, 100))
        icon = drawer.circular_crop(icon)
        im.paste(icon, pos, icon)

        text = (
            LocaleStr(
                "Finished",
                key="notes-card.gi.expedition-finished",
            )
            if exped.finished
            else LocaleStr(
                "{time} Remaining",
                key="notes-card.gi.expedition-remaining",
                time=format_timedelta(exped.remaining_time),
            )
        )

        drawer.write(
            text,
            size=40,
            position=(icon_pos[0] + icon.width + text_x_padding, 280 + index * exped_padding),
            anchor="lm",
        )

    buffer = BytesIO()
    im.save(buffer, format="WEBP", loseless=True)

    return buffer
