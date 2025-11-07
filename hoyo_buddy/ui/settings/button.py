from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from hoyo_buddy import dismissibles, emojis, ui
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction


class FakeSettingsButton(ui.Button):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="fake_settings_button_label"),
            emoji=emojis.SETTINGS,
            style=discord.ButtonStyle.blurple,
            row=4,
        )

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            title=LocaleStr(key="fake_settings_button_title"),
            description=dismissibles.SETTINGS_V2.description,
        )
        await i.response.send_message(embed=embed, ephemeral=True)
