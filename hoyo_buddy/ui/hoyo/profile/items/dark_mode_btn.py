from typing import TYPE_CHECKING

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.ui.components import ToggleButton

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import INTERACTION

    from ..view import ProfileView  # noqa: F401


class DarkModeButton(ToggleButton["ProfileView"]):
    def __init__(self, current_toggle: bool, disabled: bool) -> None:
        super().__init__(
            current_toggle,
            LocaleStr("Dark Mode", key="profile.dark_mode.button.label"),
            row=2,
            custom_id="profile_dark_mode",
            disabled=disabled,
        )

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_settings is not None

        # Save the new dark mode setting
        await super().callback(i, edit=False)
        self.view._card_settings.dark_mode = self.current_toggle
        await self.view._card_settings.save()

        # Redraw the card
        await self.view.update(i, self, unset_loading_state=False)
