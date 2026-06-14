from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from hoyo_buddy import emojis, ui
from hoyo_buddy.constants import locale_to_hoyo_lang
from hoyo_buddy.l10n import LocaleStr

from ._common import AccountToggleButton

if TYPE_CHECKING:
    from collections.abc import Sequence

    import genshin

    from hoyo_buddy.db.models.hoyo_account import HoyoAccount
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction

    from .view import SettingsView  # noqa: F401


class AccompanyCharacterSelect(ui.PaginatorSelect["SettingsView"]):
    def __init__(
        self,
        *,
        characters: Sequence[genshin.models.AccompanyCharacter],
        current_role_id: int | None,
        page_index: int,
    ) -> None:
        self.characters = characters
        options = [
            ui.SelectOption(
                label=character.info.name,
                value=f"{character.info.role_id}:{character.info.topic_id}",
                default=character.info.role_id == current_role_id,
            )
            for character in characters
        ]
        super().__init__(
            options=options,
            placeholder=LocaleStr(key="accompany_character_select_placeholder"),
            custom_id="accompany_character_select",
        )
        self.page_index = page_index
        self.options = self.process_options()

    async def callback(self, i: Interaction) -> None:
        if "next_page" in self.values:
            self.view.accompany_page_index += 1
            await self.view.update(i)
            return
        if "prev_page" in self.values:
            self.view.accompany_page_index -= 1
            await self.view.update(i)
            return

        role_id_str, topic_id_str = self.values[0].split(":")
        role_id, topic_id = int(role_id_str), int(topic_id_str)
        character = next((c for c in self.characters if c.info.role_id == role_id), None)

        account = self.view.account
        account.accompany_role_id = role_id
        account.accompany_topic_id = topic_id
        account.accompany_character_name = character.info.name if character is not None else None
        await account.save(
            update_fields=("accompany_role_id", "accompany_topic_id", "accompany_character_name")
        )
        await self.view.update(i)


class AccompanySettingsContainer(ui.DefaultContainer["SettingsView"]):
    @classmethod
    async def create(
        cls, *, account: HoyoAccount, locale: Locale, page_index: int
    ) -> AccompanySettingsContainer:
        client = account.client
        games = await client.get_accompany_characters(lang=locale_to_hoyo_lang(locale))

        characters: Sequence[genshin.models.AccompanyCharacter] = []
        for game in games:
            try:
                is_match = game.game == client.game
            except ValueError:
                # The game ID isn't mapped to a known game in genshin.py
                continue
            if is_match:
                characters = game.characters
                break

        return cls(account=account, characters=characters, page_index=page_index)

    def __init__(
        self,
        *,
        account: HoyoAccount,
        characters: Sequence[genshin.models.AccompanyCharacter],
        page_index: int,
    ) -> None:
        super().__init__(
            ui.TextDisplay(
                LocaleStr(
                    custom_str="# {title}\n{desc}",
                    title=LocaleStr(key="accompany_settings_title"),
                    desc=LocaleStr(key="accompany_settings_desc"),
                )
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {emoji} {title}\n{desc}",
                        emoji=emojis.FREE_CANCELLATION,
                        title=LocaleStr(key="accompany_button_label"),
                        desc=LocaleStr(
                            key="accompany_selected_character",
                            character=account.accompany_character_name,
                        )
                        if account.accompany_character_name is not None
                        else LocaleStr(key="accompany_no_character_selected"),
                    )
                ),
                accessory=AccountToggleButton(
                    attr="accompany_checkin",
                    current=account.accompany_checkin,
                    disabled=account.accompany_role_id is None,
                ),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.ActionRow(
                AccompanyCharacterSelect(
                    characters=characters,
                    current_role_id=account.accompany_role_id,
                    page_index=page_index,
                )
            ),
        )
