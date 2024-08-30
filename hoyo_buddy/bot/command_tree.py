from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Literal

from discord import InteractionType, NotFound, app_commands

from ..db.models import get_locale
from ..utils import get_now
from .error_handler import get_error_embed

if TYPE_CHECKING:
    from ..types import Interaction

__all__ = ("CommandTree",)


class CommandTree(app_commands.CommandTree):
    async def interaction_check(self, i: Interaction) -> Literal[True]:
        if (
            i.type not in {InteractionType.application_command, InteractionType.autocomplete}
            or i.user.id in i.client.user_ids
        ):
            return True

        async with i.client.pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO "user" (id, last_interaction, temp_data) VALUES ($1, $2, $3)'
                "ON CONFLICT (id) DO UPDATE SET last_interaction = $2;",
                i.user.id,
                get_now(),
                "{}",
            )
            await conn.execute(
                'INSERT INTO "settings" (user_id, dark_mode) VALUES ($1, $2)'
                "ON CONFLICT (user_id) DO NOTHING;",
                i.user.id,
                True,
            )
            i.client.user_ids.add(i.user.id)

        return True

    async def on_error(self, i: Interaction, e: app_commands.AppCommandError) -> None:
        error = e.original if isinstance(e, app_commands.errors.CommandInvokeError) else e
        if isinstance(error, app_commands.CheckFailure):
            return

        locale = await get_locale(i)
        embed, recognized = get_error_embed(error, locale, i.client.translator)
        if not recognized:
            i.client.capture_exception(error)

        with contextlib.suppress(NotFound):
            if i.response.is_done():
                await i.followup.send(embed=embed, ephemeral=True)
            else:
                await i.response.send_message(embed=embed, ephemeral=True)
