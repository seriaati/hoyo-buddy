from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from hoyo_buddy.constants import (
    FREE_ACCOUNT_LIMIT,
    FREE_AI_IMAGE_DAILY_LIMIT,
    FREE_CUSTOM_IMAGE_LIMIT,
    SPONSOR_ACCOMPANY_CHARACTER_LIMIT,
)
from hoyo_buddy.db.utils import is_supporter
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction

__all__ = ("SponsorPerksView", "get_sponsor_perks_message")

DONATE_URL = "https://link.seria.moe/donate"


async def get_sponsor_perks_message(
    user_id: int, locale: Locale
) -> tuple[DefaultEmbed, discord.ui.View]:
    perks = (
        LocaleStr(key="supporter_embed.perk_auto_task_priority"),
        LocaleStr(key="supporter_embed.perk_accounts", limit=FREE_ACCOUNT_LIMIT),
        LocaleStr(key="supporter_embed.perk_custom_images", limit=FREE_CUSTOM_IMAGE_LIMIT),
        LocaleStr(key="supporter_embed.perk_animated_image"),
        LocaleStr(key="supporter_embed.perk_ai_images", limit=FREE_AI_IMAGE_DAILY_LIMIT),
        LocaleStr(key="supporter_embed.perk_auto_gacha_import"),
        LocaleStr(
            key="supporter_embed.perk_multi_accompany", limit=SPONSOR_ACCOMPANY_CHARACTER_LIMIT
        ),
        LocaleStr(key="supporter_embed.perk_discord_role"),
        LocaleStr(key="supporter_embed.perk_discord_channel"),
    )
    description = LocaleStr(key="supporter_embed.description").translate(locale)
    description += "\n" + "\n".join(f"- {perk.translate(locale)}" for perk in perks)
    description += f"\n\n{LocaleStr(key='supporter_embed.how_to').translate(locale)}"

    status_key = (
        "supporter_embed.status_supporter"
        if await is_supporter(user_id)
        else "supporter_embed.status_not_supporter"
    )
    description += f"\n\n**{LocaleStr(key=status_key).translate(locale)}**"

    embed = DefaultEmbed(
        locale=locale, title=LocaleStr(key="supporter_embed.title"), description=description
    )
    view = discord.ui.View()
    view.add_item(
        discord.ui.Button(
            label=LocaleStr(key="about_command.support").translate(locale), url=DONATE_URL
        )
    )
    return embed, view


class SponsorPerksButton(discord.ui.Button["SponsorPerksView"]):
    def __init__(self, locale: Locale) -> None:
        super().__init__(
            label=LocaleStr(key="sponsor_perks_button_label").translate(locale),
            style=discord.ButtonStyle.blurple,
        )
        self.locale = locale

    async def callback(self, i: Interaction) -> None:
        embed, view = await get_sponsor_perks_message(i.user.id, self.locale)
        await i.response.send_message(embed=embed, view=view, ephemeral=True)


class SponsorPerksView(discord.ui.View):
    """Attached to sponsor perk prompts so users can see every perk they'd get."""

    def __init__(self, locale: Locale) -> None:
        super().__init__()
        self.add_item(SponsorPerksButton(locale))
