from typing import List, Optional

import discord
from discord.components import SelectOption
from discord.utils import MISSING

from ..bot import HoyoBuddy, emojis
from ..bot.translator import Translator
from ..db.models import User


class Select(discord.ui.Select):
    def __init__(
        self,
        *,
        custom_id: str = MISSING,
        placeholder: Optional[str] = None,
        min_values: int = 1,
        max_values: int = 1,
        options: List[SelectOption] = MISSING,
        disabled: bool = False,
        row: Optional[int] = None
    ) -> None:
        super().__init__(
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            options=options,
            disabled=disabled,
            row=row,
        )

    async def translate(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        translate_placeholder: bool = True,
        translate_optoin_labels: bool = True,
        translate_option_descriptions: bool = True,
        **kwargs
    ) -> None:
        if self.placeholder and translate_placeholder:
            self.placeholder = translator.translate(self.placeholder, locale, **kwargs)
        for option in self.options:
            if translate_optoin_labels:
                option.label = translator.translate(option.label, locale, **kwargs)
            if option.description and translate_option_descriptions:
                option.description = translator.translate(
                    option.description, locale, **kwargs
                )

    async def set_loading_state(self, i: discord.Interaction[HoyoBuddy]) -> None:
        user = await User.get(id=i.user.id).prefetch_related("settings")
        self.options = [
            SelectOption(
                label="Loading...", value="loading", default=True, emoji=emojis.LOADING
            )
        ]
        self.disabled = True
        self.placeholder = "Loading..."
        await self.translate(user.settings.locale or i.locale, i.client.translator)
        await self.view.absolute_edit(i, view=self.view)  # type: ignore
