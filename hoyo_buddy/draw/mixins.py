from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.draw.drawer import WHITE, Drawer

if TYPE_CHECKING:
    from PIL import Image


class HSRChallengeUIDMixin:
    _uid: int | None
    _drawer: Drawer
    _im: Image.Image

    def _write_uid(self) -> None:
        if self._uid is None:
            return

        self._drawer.write(
            f"UID: {self._uid}",
            size=18,
            position=(self._im.width - 29, 20),
            style="bold",
            color=WHITE,
            anchor="rt",
        )
