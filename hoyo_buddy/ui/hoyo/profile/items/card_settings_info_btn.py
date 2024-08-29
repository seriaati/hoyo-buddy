from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import INFO
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import ProfileView  # noqa: F401


class CardSettingsInfoButton(Button["ProfileView"]):
    def __init__(self) -> None:
        super().__init__(emoji=INFO, row=2)

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale, self.view.translator, title=LocaleStr(key="profile.info.embed.title")
        )
        embed.add_field(
            name=LocaleStr(key="profile.info.embed.primary_color.name"),
            value=LocaleStr(key="profile.info.embed.primary_color.value"),
            inline=False,
        )
        embed.add_field(
            name=LocaleStr(key="dark_mode_button_label"),
            value=LocaleStr(key="profile.info.embed.dark_mode.value"),
            inline=False,
        )
        embed.add_field(
            name=LocaleStr(key="profile.info.embed.custom_images.name"),
            value=LocaleStr(key="profile.info.embed.custom_images.value"),
            inline=False,
        )
        embed.add_field(
            name=LocaleStr(key="profile.info.embed.templates.name"),
            value=LocaleStr(key="profile.info.embed.templates.value"),
            inline=False,
        )
        await i.response.send_message(embed=embed, ephemeral=True)
