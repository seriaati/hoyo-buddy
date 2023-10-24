from typing import Any, List, Optional

import discord

from ..bot import HoyoBuddy, emojis
from ..bot.translator import Translator


class Button(discord.ui.Button):
    def __init__(
        self,
        *,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
        label: Optional[str] = None,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        url: Optional[str] = None,
        emoji: Optional[str] = None,
        row: Optional[int] = None
    ):
        super().__init__(
            style=style,
            label=label,
            disabled=disabled,
            custom_id=custom_id,
            url=url,
            emoji=emoji,
            row=row,
        )
        self.original_label = label
        self.original_emoji = emoji

    def translate(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        translate_label: bool = True,
        **kwargs
    ):
        if self.label and translate_label:
            self.label = translator.translate(self.label, locale, **kwargs)

    async def set_loading_state(self, i: discord.Interaction[HoyoBuddy]) -> None:
        self.disabled = True
        self.emoji = emojis.LOADING
        self.label = "Loading..."
        self.translate(self.view.locale, self.view.translator)  # type: ignore
        await self.view.absolute_edit(i, view=self.view)  # type: ignore

    async def unset_loading_state(self, i: discord.Interaction[HoyoBuddy]) -> None:
        self.disabled = False
        self.emoji = self.original_emoji
        self.label = self.original_label
        self.translate(self.view.locale, self.view.translator)  # type: ignore
        await self.view.absolute_edit(i, view=self.view)  # type: ignore


class GoBackButton(Button):
    def __init__(
        self,
        original_children: List[discord.ui.Item],
        embed: Optional[discord.Embed] = None,
    ):
        super().__init__(emoji=emojis.BACK, row=4)
        self.original_children = original_children.copy()
        self.embed = embed

    async def callback(self, i: discord.Interaction) -> Any:
        self.view.clear_items()  # type: ignore
        for item in self.original_children:
            self.view.add_item(item)  # type: ignore

        if self.embed:
            await i.response.edit_message(embed=self.embed, view=self.view)
        else:
            await i.response.edit_message(view=self.view)
