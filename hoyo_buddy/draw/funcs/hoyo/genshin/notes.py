from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from discord import Locale
from PIL import ImageDraw

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.l10n import LocaleStr, Translator
from hoyo_buddy.utils import format_timedelta

if TYPE_CHECKING:
    from genshin.models import Notes

__all__ = ("draw_genshin_notes_card",)


def draw_genshin_notes_card(notes: Notes, locale_: str, translator: Translator, dark_mode: bool) -> BytesIO:
    filename = f"{'dark' if dark_mode else 'light'}-gi"
    locale = Locale(locale_)
    im = Drawer.open_image(f"hoyo-buddy-assets/assets/notes/{filename}.png")
    draw = ImageDraw.Draw(im)
    drawer = Drawer(draw, folder="gi-notes", dark_mode=dark_mode, translator=translator)

    drawer.write(LocaleStr(key="real_time_notes"), size=64, position=(76, 67), style="bold", locale=locale)

    drawer.write(LocaleStr(key="notes-card.gi.resin"), size=35, position=(110, 400), style="light", locale=locale)
    drawer.write(f"{notes.current_resin}/{notes.max_resin}", size=60, position=(110, 460), style="medium")

    drawer.write(
        LocaleStr(key="notes-card.gi.daily-commissions"), size=35, position=(110, 800), style="light", locale=locale
    )
    textbbox = drawer.write(
        f"{notes.completed_commissions}/{notes.max_commissions}", size=60, position=(110, 860), style="medium"
    )
    drawer.write(
        LocaleStr(key="notes-card.gi.completed"),
        size=30,
        position=(textbbox[2] + 20, textbbox[3] - 5),
        anchor="ls",
        locale=locale,
    )

    drawer.write(
        LocaleStr(key="notes-card.gi.realm-currency"), size=35, position=(596, 400), style="light", locale=locale
    )
    drawer.write(
        f"{notes.current_realm_currency}/{notes.max_realm_currency}", size=60, position=(596, 460), style="medium"
    )

    drawer.write(
        LocaleStr(key="notes-card.gi.resin-discounts"), size=35, position=(596, 800), style="light", locale=locale
    )
    textbbox = drawer.write(
        f"{notes.remaining_resin_discounts}/{notes.max_resin_discounts}", size=60, position=(596, 860), style="medium"
    )
    drawer.write(
        LocaleStr(key="notes-card.gi.remaining"),
        size=30,
        position=(textbbox[2] + 20, textbbox[3] - 5),
        anchor="ls",
        locale=locale,
    )

    exped_padding = 187
    icon_pos = (1060, 60)
    text_x_padding = 20

    for index, exped in enumerate(notes.expeditions):
        pos = (icon_pos[0], index * exped_padding + icon_pos[1])

        icon = drawer.open_static(exped.character_icon, size=(120, 120))
        icon = drawer.circular_crop(icon)
        im.paste(icon, pos, icon)

        text = (
            LocaleStr(key="notes-card.gi.expedition-finished")
            if exped.finished
            else LocaleStr(key="notes-card.gi.expedition-remaining", time=format_timedelta(exped.remaining_time))
        )

        drawer.write(
            text,
            size=40,
            position=(icon_pos[0] + icon.width + text_x_padding, 143 + index * exped_padding),
            anchor="lm",
            locale=locale,
        )

    buffer = BytesIO()
    im.save(buffer, format="PNG")

    return buffer
