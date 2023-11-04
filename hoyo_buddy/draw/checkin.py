import io
from typing import Tuple

import genshin
from cachetools import LRUCache, cached
from PIL import Image, ImageDraw

from . import Drawer


def cache_key(
    daily_rewards: Tuple[genshin.models.DailyReward, ...], dark_mode: bool
) -> str:
    rewards_key = "_".join(
        f"{daily_reward.name}_{daily_reward.amount}" for daily_reward in daily_rewards
    )
    return f"{rewards_key}_{dark_mode}"


@cached(cache=LRUCache(maxsize=100), key=cache_key)
def draw_card(
    daily_rewards: Tuple[genshin.models.DailyReward, ...],
    dark_mode: bool,
) -> io.BytesIO:
    def get_color(dark_mode: bool, i: int, first_set: bool) -> str:
        if i in (2, 3):
            return "#FFFFFF" if dark_mode else "#282B3C"
        return "#BEBEBE" if dark_mode else ("#8A8B97" if first_set else "#6A6C7C")

    if dark_mode:
        im = Image.open("hoyo-buddy-assets/assets/check-in/DARK_1.png")
        check = Image.open("hoyo-buddy-assets/assets/check-in/DARK_CHECK.png")
        mask = Image.open("hoyo-buddy-assets/assets/check-in/DARK_MASK.png")
    else:
        im = Image.open("hoyo-buddy-assets/assets/check-in/LIGHT_1.png")
        check = Image.open("hoyo-buddy-assets/assets/check-in/LIGHT_CHECK.png")
        mask = Image.open("hoyo-buddy-assets/assets/check-in/LIGHT_MASK.png")

    draw = ImageDraw.Draw(im)
    drawer = Drawer(draw, folder="check-in")

    x, y = (44, 36)
    for i, daily_reward in enumerate(daily_rewards):
        icon = drawer.get_static_image(daily_reward.icon)
        icon = icon.resize((110, 110))
        im.paste(icon, (x, y), icon)
        try:
            status, index = daily_reward.name.split("_")
        except ValueError:
            status = "unclaimed"
            index = daily_reward.name

        if status == "claimed":
            im.paste(mask, (x - 19, y - 11), mask)
            im.paste(check, (x + 1, y + 1), check)

        color = get_color(dark_mode, i, True)
        drawer.plain_write(
            text=f"x{daily_reward.amount}",
            size=36,
            color=color,
            position=(x + 56, y + 153),
            style="medium" if i in (2, 3) else "regular",
            anchor="mm",
        )

        color = get_color(dark_mode, i, False)
        drawer.plain_write(
            text=index,
            size=18,
            color=color,
            position=(x + 55, y + 195),
            style="regular" if i in (2, 3) else "light",
            anchor="mm",
        )

        if i == 2:
            x += 166 + icon.width
        else:
            x += 64 + icon.width

    bytes_io = io.BytesIO()
    im.save(bytes_io, format="PNG")

    return bytes_io
