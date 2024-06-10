from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import INFO
from hoyo_buddy.ui.components import Button

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import Interaction

    from ..view import ProfileView  # noqa: F401


class CardSettingsInfoButton(Button["ProfileView"]):
    def __init__(self) -> None:
        super().__init__(emoji=INFO, row=2)

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("About Card Settings", key="profile.info.embed.title"),
        )
        embed.add_field(
            name=LocaleStr("Primary Color", key="profile.info.embed.primary_color.name"),
            value=LocaleStr(
                "- Only hex color codes are supported.",
                key="profile.info.embed.primary_color.value",
            ),
            inline=False,
        )
        embed.add_field(
            name=LocaleStr("Dark Mode", key="profile.info.embed.dark_mode.name"),
            value=LocaleStr(
                "- This setting is independent from the one in </settings>, defaults to light mode.\n"
                "- Light mode cards tend to look better because the colors are not optimized for dark mode.\n"
                "- Suggestions for dark mode colors are welcome!",
                key="profile.info.embed.dark_mode.value",
            ),
            inline=False,
        )
        embed.add_field(
            name=LocaleStr("Custom Images", key="profile.info.embed.custom_images.name"),
            value=LocaleStr(
                "- Hoyo Buddy comes with some preset arts that I liked, but you can add your own images too.\n"
                "- Only direct image URLs are supported, and they must be publicly accessible; GIFs are not supported.\n"
                "- For Hoyo Buddy's templates, vertical images are recommended.\n"
                "- For server owners, I am not responsible for any NSFW images that you or your members add.\n"
                "- The red button removes the current custom image and reverts to the default one.",
                key="profile.info.embed.custom_images.value",
            ),
            inline=False,
        )
        embed.add_field(
            name=LocaleStr("Templates", key="profile.info.embed.templates.name"),
            value=LocaleStr(
                "- Hoyo Buddy has its own template made by me, but I also added templates made by other developers.\n"
                "- Code of 3rd party templates are not maintained by me, so I cannot guarantee their quality; I am also not responsible for any issues with them.\n"
                "- 3rd party templates may have feature limitations compared to Hoyo Buddy's.\n"
                "- Cached data characters can only use Hoyo Buddy's templates.",
                key="profile.info.embed.templates.value",
            ),
            inline=False,
        )
        await i.response.send_message(embed=embed, ephemeral=True)
