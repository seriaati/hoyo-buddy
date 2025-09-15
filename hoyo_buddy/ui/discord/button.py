from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import discord
from seria.utils import clean_url

from hoyo_buddy import emojis
from hoyo_buddy.l10n import LocaleStr, translator

from .select import Select

if TYPE_CHECKING:
    import io
    from collections.abc import Sequence

    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction

    from .view import View

__all__ = ("Button", "GoBackButton", "ToggleButton", "ToggleUIButton")


class Button[V_co: View](discord.ui.Button):
    def __init__(
        self,
        *,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
        label: LocaleStr | str | None = None,
        disabled: bool = False,
        custom_id: str | None = None,
        url: str | None = None,
        emoji: str | None = None,
        row: int | None = None,
    ) -> None:
        super().__init__(
            style=style, disabled=disabled, custom_id=custom_id, url=url, emoji=emoji, row=row
        )

        self.locale_str_label = label
        self.original_label: str | None = None
        self.original_emoji: str | None = None
        self.original_disabled: bool | None = None

        self.view: V_co

    def translate(self, locale: Locale) -> None:
        if self.locale_str_label:
            self.label = translator.translate(self.locale_str_label, locale)

    async def set_loading_state(self, i: Interaction, **kwargs) -> None:
        self.original_label = self.label[:] if self.label else None
        self.original_emoji = str(self.emoji) if self.emoji else None
        self.original_disabled = self.disabled

        self.view.disable_items()

        self.disabled = True
        self.emoji = emojis.LOADING
        self.label = translator.translate(LocaleStr(key="loading_text"), self.view.locale)

        await self.view.absolute_edit(i, view=self.view, **kwargs)

    async def unset_loading_state(self, i: Interaction, **kwargs) -> None:
        if self.original_disabled is None:
            msg = "unset_loading_state called before set_loading_state"
            raise RuntimeError(msg)

        self.view.enable_items()

        self.disabled = self.original_disabled
        self.emoji = self.original_emoji
        self.label = self.original_label

        await self.view.absolute_edit(i, view=self.view, **kwargs)


class GoBackButton[V_co: View](Button):
    def __init__(
        self,
        original_children: list[discord.ui.Item[Any]],
        embeds: Sequence[discord.Embed] | None = None,
        byte_obj: io.BytesIO | None = None,
        row: int = 4,
    ) -> None:
        super().__init__(emoji=emojis.BACK, row=row)
        self.original_children = original_children.copy()
        self.embeds = embeds
        self.byte_obj = byte_obj

        self.view: V_co

    async def callback(self, i: Interaction) -> Any:
        self.view.clear_items()
        for item in self.original_children:
            if isinstance(item, Button | Select):
                self.view.add_item(item, translate=False)

        kwargs: dict[str, Any] = {"view": self.view}
        if self.embeds is not None:
            kwargs["embeds"] = self.embeds

        if self.byte_obj is not None:
            self.byte_obj.seek(0)

            original_image = None
            for embed in self.embeds or []:
                original_image = (
                    clean_url(embed.image.url).split("/")[-1]
                    if embed.image.url is not None
                    else None
                )
                if original_image is not None:
                    embed.set_image(url=f"attachment://{original_image}")

            original_image = original_image or "image.png"
            kwargs["attachments"] = [discord.File(self.byte_obj, filename=original_image)]

        await i.response.edit_message(**kwargs)


class ToggleButton[V_co: View](Button):
    def __init__(self, current_toggle: bool, toggle_label: LocaleStr, **kwargs) -> None:
        self.current_toggle = current_toggle
        self.toggle_label = toggle_label
        kwargs["row"] = kwargs.get("row", 1)
        super().__init__(
            style=self._get_style(),
            label=self._get_label(),
            emoji=emojis.TOGGLE_EMOJIS[current_toggle],
            **kwargs,
        )

        self.view: V_co

    def _get_label(self) -> LocaleStr:
        return LocaleStr(
            custom_str="{toggle_label}: {status_str}",
            toggle_label=self.toggle_label,
            status_str=self._get_status_str(),
        )

    def _get_style(self) -> discord.ButtonStyle:
        return discord.ButtonStyle.green if self.current_toggle else discord.ButtonStyle.gray

    def _get_status_str(self) -> LocaleStr:
        return (
            LocaleStr(key="on_button_label")
            if self.current_toggle
            else LocaleStr(key="off_button_label")
        )

    def update_style(self) -> None:
        self.style = self._get_style()
        self.locale_str_label = self._get_label()
        self.emoji = emojis.TOGGLE_EMOJIS[self.current_toggle]

        self.translate(self.view.locale)

    async def callback(self, i: Interaction, *, edit: bool = True, **kwargs) -> Any:
        self.current_toggle = not self.current_toggle
        self.update_style()
        if edit:
            await i.response.edit_message(view=self.view, **kwargs)


class ToggleUIButton[V_co: View](Button):
    def __init__(self, *, row: int = 4) -> None:
        super().__init__(
            style=discord.ButtonStyle.gray,
            label=LocaleStr(key="hide_ui_button_label"),
            emoji=emojis.HIDE_UI,
            row=row,
        )
        self._items: Sequence[Button | Select] = []
        self._mode: Literal["show", "hide"] = "hide"
        self.view: V_co

    def _set_style(self) -> None:
        self.emoji = emojis.HIDE_UI if self._mode == "hide" else emojis.SHOW_UI
        self.style = (
            discord.ButtonStyle.gray if self._mode == "hide" else discord.ButtonStyle.blurple
        )
        self.locale_str_label = LocaleStr(
            key="hide_ui_button_label" if self._mode == "hide" else "show_ui_button_label"
        )

    async def callback(self, i: Interaction) -> None:
        message = i.message
        if message is None:
            return

        if self._mode == "hide":
            children = self.view.children.copy()
            children.remove(self)
            self._items = children  # pyright: ignore[reportAttributeAccessIssue]
            self.view.clear_items()

            self._mode = "show"
            self._set_style()
            self.view.add_item(self)
        else:
            self.view.clear_items()
            self.view.add_items(self._items)

            self._mode = "hide"
            self._set_style()
            self.view.add_item(self)

        await i.response.edit_message(view=self.view)
