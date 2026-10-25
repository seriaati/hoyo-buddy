from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import discord

if TYPE_CHECKING:
    from discord.types.components import FileUploadComponent as FileUploadComponentPayload

__all__ = ("FileUpload",)


# discord.py doesn't support the `file_types` field yet, remove this subclass once
# https://github.com/Rapptz/discord.py/pull/10494 is released.
class FileUpload(discord.ui.FileUpload):
    def __init__(self, *, file_types: list[str], required: bool = True) -> None:
        super().__init__(required=required)
        self.file_types = file_types

    def to_component_dict(self) -> FileUploadComponentPayload:
        data = cast("dict[str, Any]", super().to_component_dict())
        data["file_types"] = self.file_types
        return cast("FileUploadComponentPayload", data)
