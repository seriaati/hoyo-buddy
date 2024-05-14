from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from discord import InteractionResponded, InteractionType, app_commands

from ..db.models import Settings
from ..utils import get_now
from .error_handler import get_error_embed

if TYPE_CHECKING:
    from .bot import INTERACTION

__all__ = ("CommandTree",)


class CommandTree(app_commands.CommandTree):
    async def interaction_check(self, i: INTERACTION) -> Literal[True]:
        if i.type not in {InteractionType.application_command, InteractionType.autocomplete}:
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

        return True

    async def on_error(self, i: INTERACTION, e: app_commands.AppCommandError) -> None:
        error = e.original if isinstance(e, app_commands.errors.CommandInvokeError) else e
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        embed, recognized = get_error_embed(error, locale, i.client.translator)
        if not recognized:
            i.client.capture_exception(e)

        try:
            await i.response.send_message(embed=embed, ephemeral=True)
        except InteractionResponded:
            await i.followup.send(embed=embed, ephemeral=True)
        except Exception:
            pass
