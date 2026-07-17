from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Literal

from discord import InteractionType, NotFound, app_commands

from hoyo_buddy.db import get_locale
from hoyo_buddy.db.models.settings import Settings
from hoyo_buddy.db.models.user import User
from hoyo_buddy.utils import should_ignore_error

from .error_handler import get_error_embed

if TYPE_CHECKING:
    from ..types import Interaction

__all__ = ("CommandTree",)


class CommandTree(app_commands.CommandTree):
    async def interaction_check(self, i: Interaction) -> Literal[True]:
        if i.type not in {InteractionType.application_command, InteractionType.autocomplete}:
            return True

        try:
            # Set user's language if not set
            await Settings.filter(user_id=i.user.id, lang__isnull=True).update(lang=i.locale.value)
        except Exception as e:
            i.client.capture_exception(e)

        if i.user.id in i.client.user_ids:
            return True

        try:
            await User.get_or_create(id=i.user.id)
            await Settings.get_or_create(user_id=i.user.id, defaults={"lang": i.locale.value})
            i.client.user_ids.add(i.user.id)
        except Exception as e:
            i.client.capture_exception(e)

        return True

    async def on_error(self, i: Interaction, e: app_commands.AppCommandError) -> None:
        error = e.original if isinstance(e, app_commands.errors.CommandInvokeError) else e

        if should_ignore_error(error):
            return

        locale = await get_locale(i)
        embed, recognized = get_error_embed(error, locale)
        if not recognized:
            i.client.capture_exception(error)

        with contextlib.suppress(NotFound):
            if i.response.is_done():
                await i.followup.send(embed=embed, ephemeral=True)
            else:
                await i.response.send_message(embed=embed, ephemeral=True)
