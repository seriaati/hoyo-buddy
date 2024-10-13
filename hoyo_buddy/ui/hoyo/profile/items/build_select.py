from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Select, SelectOption

if TYPE_CHECKING:
    import enka

    from hoyo_buddy.types import Interaction

    from ..view import ProfileView
else:
    ProfileView = None


class BuildSelect(Select[ProfileView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(
            placeholder=LocaleStr(key="profile.build.select.placeholder"),
            options=[SelectOption(label="Placeholder", value="0")],
            disabled=True,
            custom_id="profile_build_select",
            row=row,
        )
        self._builds: list[enka.gi.Build] | list[enka.hsr.Build] = []

    @property
    def build(self) -> enka.hsr.Build | enka.gi.Build:
        return next(build for build in self._builds if build.id == int(self.values[0]))

    def set_options(self, builds: list[enka.gi.Build] | list[enka.hsr.Build]) -> None:
        self._builds = builds
        self.options = [
            SelectOption(
                label=build.name or LocaleStr(key="profile.build.current.label"),
                value=str(build.id),
                default=self.view._build_id == build.id,
            )
            for build in builds
        ] or [SelectOption(label="Placeholder", value="0")]
        self.disabled = not builds

    async def callback(self, i: Interaction) -> None:
        self.view._build_id = int(self.values[0])
        await self.set_loading_state(i)
        await self.view.update(i, self, character=self.build.character)
