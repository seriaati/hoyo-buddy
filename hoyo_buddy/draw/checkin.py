import io
from typing import TYPE_CHECKING

from cachetools import LRUCache, cached
from PIL import Image, ImageDraw

from ..utils import timer
from . import Drawer

if TYPE_CHECKING:
    import genshin

    from ..hoyo.dataclasses import Reward


def cache_key(daily_rewards: tuple["genshin.models.DailyReward", ...], dark_mode: bool) -> str:
    rewards_key = "_".join(
        f"{daily_reward.name}_{daily_reward.amount}" for daily_reward in daily_rewards
    )
    return f"{rewards_key}_{dark_mode}"


@timer
@cached(cache=LRUCache(maxsize=100), key=cache_key)
def draw_card(
    daily_rewards: list["Reward"],
    dark_mode: bool,
) -> io.BytesIO:
    if dark_mode:
        im = Image.open("hoyo-buddy-assets/assets/check-in/DARK_1.png")
        check = Image.open("hoyo-buddy-assets/assets/check-in/DARK_CHECK.png")
        mask = Image.open("hoyo-buddy-assets/assets/check-in/DARK_MASK.png")
    else:
        im = Image.open("hoyo-buddy-assets/assets/check-in/LIGHT_1.png")
        check = Image.open("hoyo-buddy-assets/assets/check-in/LIGHT_CHECK.png")
        mask = Image.open("hoyo-buddy-assets/assets/check-in/LIGHT_MASK.png")

    text = Image.new("RGBA", im.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(text)
    drawer = Drawer(draw, folder="check-in", dark_mode=dark_mode)

    x, y = (44, 36)
    for i, daily_reward in enumerate(daily_rewards):
        icon = drawer.get_static_image(daily_reward.icon)
        icon = icon.resize((110, 110))
        im.paste(icon, (x, y), icon)

        if daily_reward.claimed:
            im.paste(mask, (x - 19, y - 11), mask)
            im.paste(check, (x + 1, y + 1), check)

        drawer.plain_write(
            text=f"x{daily_reward.amount}",
            size=36,
            position=(x + 56, y + 153),
            style="medium",
            emphasis="high" if i in {2, 3} else "medium",
            anchor="mm",
        )
        drawer.plain_write(
            text=f"#{daily_reward.index}",
            size=18,
            position=(x + 55, y + 195),
            style="regular",
            emphasis="high" if i in {2, 3} else "medium",
            anchor="mm",
        )

        if i == 2:
            x += 166 + icon.width
        else:
            x += 64 + icon.width

    combined = Image.alpha_composite(im, text)

    bytes_io = io.BytesIO()
    combined.save(bytes_io, format="PNG")

    return bytes_io
