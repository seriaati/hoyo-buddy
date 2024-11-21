from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.db.models import Settings
from hoyo_buddy.emojis import GROUP
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button
from hoyo_buddy.ui.hoyo.profile.team_card_settings import TeamCardSettingsView

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import ProfileView
else:
    ProfileView = None


class TeamCardSettingsButton(Button[ProfileView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(
            label=LocaleStr(key="team_card_settings_button_label"),
            disabled=True,
            custom_id="profile_team_card_settings",
            emoji=GROUP,
            style=ButtonStyle.blurple,
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        settings = await Settings.get(user_id=i.user.id)
        view = TeamCardSettingsView(settings, author=i.user, locale=self.view.locale)
        await view.start(i)
