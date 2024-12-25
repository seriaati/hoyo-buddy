from __future__ import annotations

import bisect
from io import BytesIO

import discord
from genshin.models import VideoStoreState, ZZZNotes
from PIL import ImageDraw

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr

__all__ = ("draw_zzz_notes",)


def get_nearest_battery_level(current: int, max_battery: int) -> int:
    battery_levels = (0, 25, 50, 75, 100)
    percentage = round((current / max_battery) * 100)
    return battery_levels[bisect.bisect_left(battery_levels, percentage)]


def draw_zzz_notes(notes: ZZZNotes, locale_: str, dark_mode: bool) -> BytesIO:
    battery_level = get_nearest_battery_level(
        notes.battery_charge.current, notes.battery_charge.max
    )

    filename = f"{'dark' if dark_mode else 'light'}_notes_{battery_level}"
    im = Drawer.open_image(f"hoyo-buddy-assets/assets/zzz-notes/{filename}.png")
    draw = ImageDraw.Draw(im)
    drawer = Drawer(
        draw, folder="zzz-notes", dark_mode=dark_mode, locale=discord.Locale(locale_), sans=True
    )

    # Title
    drawer.write(
        LocaleStr(key="daily_note", mi18n_game=Game.ZZZ),
        size=84,
        style="black_italic",
        position=(76, 44),
        dynamic_fontsize=True,
        max_width=899,
    )

    # Battery charge
    drawer.write(
        LocaleStr(key="battery_num", mi18n_game=Game.ZZZ),
        size=46,
        style="bold",
        position=(112, 230),
        title_case=True,
        max_width=354,
        max_lines=2,
    )
    drawer.write(
        f"{notes.battery_charge.current}/{notes.battery_charge.max}",
        size=32,
        style="medium",
        position=(112, 487),
    )

    # Scratch card
    drawer.write(
        LocaleStr(key="card", mi18n_game=Game.ZZZ),
        size=46,
        style="bold",
        position=(598, 230),
        title_case=True,
        max_width=354,
        max_lines=2,
    )
    text = LocaleStr(
        key="scratch_card.incomplete"
        if not notes.scratch_card_completed
        else "notes-card.gi.completed"
    )

    drawer.write(text, size=32, style="medium", position=(598, 487))

    # Video store management
    drawer.write(
        LocaleStr(key="vhs_sale", mi18n_game=Game.ZZZ),
        size=46,
        style="bold",
        position=(112, 633),
        title_case=True,
        max_width=354,
        max_lines=2,
    )
    if notes.video_store_state is VideoStoreState.CURRENTLY_OPEN:
        key = "sales_doing"
    elif notes.video_store_state is VideoStoreState.REVENUE_AVAILABLE:
        key = "sales_done"
    else:
        key = "sales_no"

    drawer.write(
        LocaleStr(key=key, mi18n_game=Game.ZZZ), size=32, style="medium", position=(112, 890)
    )

    # Engagement
    drawer.write(
        LocaleStr(key="zzz_engagement_button.label"),
        size=46,
        style="bold",
        position=(598, 633),
        title_case=True,
        max_width=354,
        max_lines=2,
    )
    drawer.write(
        f"{notes.engagement.current}/{notes.engagement.max}",
        size=32,
        style="medium",
        position=(598, 890),
    )

    # Save image
    buffer = BytesIO()
    im.save(buffer, format="PNG")
    return buffer
