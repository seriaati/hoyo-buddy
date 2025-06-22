from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import ImageDraw

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import format_timedelta

if TYPE_CHECKING:
    from io import BytesIO

    from genshin.models import StarRailNote

__all__ = ("draw_hsr_notes_card",)


def draw_hsr_notes_card(notes: StarRailNote, locale: Locale, dark_mode: bool) -> BytesIO:
    filename = f"{'dark' if dark_mode else 'light'}-hsr"
    im = Drawer.open_image(f"hoyo-buddy-assets/assets/notes/{filename}.png")
    draw = ImageDraw.Draw(im)
    drawer = Drawer(draw, folder="hsr-notes", dark_mode=dark_mode)

    drawer.write(
        LocaleStr(key="real_time_notes"), size=64, position=(76, 67), style="bold", locale=locale
    )

    drawer.write(
        LocaleStr(key="hsr_note_daily_training", mi18n_game=Game.STARRAIL),
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
        LocaleStr(key="hsr_note_stamina", mi18n_game=Game.STARRAIL),
        size=35,
        position=(110, 800),
        style="light",
        locale=locale,
    )
    drawer.write(
        f"{notes.current_stamina}/{notes.max_stamina}", size=60, position=(110, 860), style="medium"
    )

    drawer.write(
        LocaleStr(key="notes-card.hsr.echo-of-war-discounts"),
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
        LocaleStr(key="notes-card.gi.remaining"),
        size=30,
        position=(textbbox[2] + 20, textbbox[3] - 5),
        anchor="ls",
        locale=locale,
    )

    drawer.write(
        LocaleStr(key="notes-card.hsr.reserved-power"),
        size=35,
        position=(596, 800),
        style="light",
        locale=locale,
    )
    textbbox = drawer.write(
        f"{notes.current_reserve_stamina}/2400", size=60, position=(596, 860), style="medium"
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
            LocaleStr(key="notes-card.gi.expedition-finished")
            if exped.finished
            else LocaleStr(
                key="notes-card.gi.expedition-remaining",
                time=format_timedelta(exped.remaining_time),
            )
        )

        drawer.write(
            text,
            size=40,
            position=(icon_pos[0] + icon.width + text_x_padding, 280 + index * exped_padding),
            anchor="lm",
            locale=locale,
        )

    return Drawer.save_image(im)
