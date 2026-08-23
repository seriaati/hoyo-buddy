from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import ImageDraw

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from io import BytesIO

    from genshin.models import StarRailNote

    from hoyo_buddy.enums import Locale

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

    return Drawer.save_image(im)
