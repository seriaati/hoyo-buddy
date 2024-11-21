from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import INFO
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import ProfileView
else:
    ProfileView = None


class CardInfoButton(Button[ProfileView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(emoji=INFO, row=row)

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            title=LocaleStr(key="profile.card_info.embed.title"),
            description=LocaleStr(
                key="profile.card_info.embed.description", provider="[Enka.Network](https://api.enka.network/)"
            ),
        )
        await i.response.send_message(embed=embed, ephemeral=True)
