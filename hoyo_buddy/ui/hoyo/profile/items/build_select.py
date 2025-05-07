from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.types import Character
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
        self._builds: dict[str, enka.gi.Build | enka.hsr.Build | Character] = {}

    @property
    def build(self) -> enka.hsr.Build | enka.gi.Build | Character:
        selected = self.values[0]
        build = self._builds.get(selected)

        if build is None:
            msg = f"Build with id {selected!r} not found"
            raise ValueError(msg)
        return build

    def set_options(
        self, builds: list[enka.gi.Build] | list[enka.hsr.Build], current: Character | None
    ) -> None:
        for build in builds:
            self._builds[str(build.id)] = build

        self.options = [
            SelectOption(
                label=build.name or LocaleStr(key="profile.build.current.label"),
                value=str(build.id),
                default=self.view._build_id == build.id,
            )
            for build in builds
        ] or [SelectOption(label="Placeholder", value="0")]

        if current is not None:
            # Set other options' default to False
            for option in self.options:
                option.default = False

            # Add current build to the top of the list and set as default
            self.options.insert(
                0,
                SelectOption(
                    label=LocaleStr(key="profile.build.current.label"),
                    value="current",
                    default=True,
                ),
            )
            self._builds["current"] = current
            self.view._build_id = "current"

        self.disabled = not self._builds

    async def callback(self, i: Interaction) -> None:
        await self.set_loading_state(i)

        selected = self.values[0]
        if selected == "current":
            self.view._build_id = "current"
        else:
            self.view._build_id = int(self.values[0])

        build = self.build

        if isinstance(build, Character):
            await self.view.update(i, self, character=build)
            return

        await self.view.update(i, self, character=build.character)
