from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import Drawer

if TYPE_CHECKING:
    import io

    from hoyo_buddy.models import Reward

__all__ = ("draw_checkin_card",)


def draw_checkin_card(daily_rewards: list[Reward], dark_mode: bool) -> io.BytesIO:
    im = (
        Drawer.open_image("hoyo-buddy-assets/assets/check-in/DARK_1.png")
        if dark_mode
        else Drawer.open_image("hoyo-buddy-assets/assets/check-in/LIGHT_1.png")
    )

    text = Image.new("RGBA", im.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(text)
    drawer = Drawer(draw, folder="check-in", dark_mode=dark_mode)

    if dark_mode:
        mask = drawer.open_asset("DARK_MASK.png")
        check = drawer.open_asset("DARK_CHECK.png")
    else:
        mask = drawer.open_asset("LIGHT_MASK.png")
        check = drawer.open_asset("LIGHT_CHECK.png")

    x, y = (44, 36)
    for i, daily_reward in enumerate(daily_rewards):
        icon = drawer.open_static(daily_reward.icon)
        icon = icon.resize((110, 110))
        im.paste(icon, (x, y), icon)

        if daily_reward.claimed:
            im.paste(mask, (x - 19, y - 11), mask)
            im.paste(check, (x + 1, y + 1), check)

        drawer.write(
            text=f"x{daily_reward.amount}",
            size=36,
            position=(x + 56, y + 153),
            style="medium",
            emphasis="high" if i in {2, 3} else "medium",
            anchor="mm",
        )
        drawer.write(
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
    return Drawer.save_image(combined)
