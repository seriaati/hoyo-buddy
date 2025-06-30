from __future__ import annotations

import bisect
from typing import TYPE_CHECKING

from genshin.models import VideoStoreState, ZZZNotes
from PIL import ImageDraw

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from io import BytesIO

__all__ = ("draw_zzz_notes",)


def get_nearest_battery_level(current: int, max_battery: int) -> int:
    battery_levels = (0, 25, 50, 75, 100)
    percentage = round((current / max_battery) * 100)
    return battery_levels[bisect.bisect_left(battery_levels, percentage)]


def draw_zzz_notes(notes: ZZZNotes, locale: Locale, dark_mode: bool) -> BytesIO:
    battery_level = get_nearest_battery_level(
        notes.battery_charge.current, notes.battery_charge.max
    )

    filename = f"{'dark' if dark_mode else 'light'}_notes_{battery_level}"
    im = Drawer.open_image(f"hoyo-buddy-assets/assets/zzz-notes/{filename}.png")
    draw = ImageDraw.Draw(im)
    drawer = Drawer(draw, folder="zzz-notes", dark_mode=dark_mode, locale=locale, sans=True)

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
        max_lines=3,
    )
    drawer.write(
        f"{notes.battery_charge.current}/{notes.battery_charge.max}",
        size=32,
        style="medium",
        position=(112, 487),
        locale=Locale.american_english
    )

    # Scratch card
    drawer.write(
        LocaleStr(key="card", mi18n_game=Game.ZZZ),
        size=46,
        style="bold",
        position=(598, 230),
        title_case=True,
        max_width=354,
        max_lines=3,
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
        max_lines=3,
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
        max_lines=3,
    )
    drawer.write(
        f"{notes.engagement.current}/{notes.engagement.max}",
        size=32,
        style="medium",
        position=(598, 890),
        locale=Locale.american_english,
    )

    # Bounty commission progress
    comm = notes.hollow_zero.bounty_commission
    drawer.write(
        LocaleStr(key="bounty_commission_progress", mi18n_game=Game.ZZZ),
        size=46,
        style="bold",
        position=(113, 1043),
        title_case=True,
        max_width=354,
        max_lines=3,
    )
    drawer.write(
        f"{comm.cur_completed}/{comm.total}" if comm is not None else "-",
        size=32,
        style="medium",
        position=(113, 1300),
        locale=Locale.american_english,
    )

    # Ridy weekly points
    ridu = notes.weekly_task
    drawer.write(
        LocaleStr(key="weekly_task_point", mi18n_game=Game.ZZZ),
        size=46,
        style="bold",
        position=(598, 1043),
        title_case=True,
        max_width=354,
        max_lines=3,
    )
    drawer.write(
        f"{ridu.cur_point}/{ridu.max_point}" if ridu is not None else "-",
        size=32,
        style="medium",
        position=(598, 1300),
        locale=Locale.american_english,
    )

    return Drawer.save_image(im)
