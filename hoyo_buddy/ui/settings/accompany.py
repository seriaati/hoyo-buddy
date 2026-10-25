from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from hoyo_buddy import emojis, ui
from hoyo_buddy.constants import SPONSOR_ACCOMPANY_CHARACTER_LIMIT, locale_to_hoyo_lang
from hoyo_buddy.l10n import LocaleStr

from ._common import AccountToggleButton

if TYPE_CHECKING:
    from collections.abc import Sequence

    import genshin

    from hoyo_buddy.db.models.hoyo_account import HoyoAccount
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction

    from .view import SettingsView  # ruff:ignore[unused-import]


class AccompanyCharacterSelect(ui.PaginatorSelect["SettingsView"]):
    def __init__(
        self,
        *,
        characters: Sequence[genshin.models.AccompanyCharacter],
        selected_role_ids: Sequence[int],
        max_values: int,
        page_index: int,
    ) -> None:
        self.characters = characters
        options = [
            ui.SelectOption(
                label=character.info.name,
                value=f"{character.info.role_id}:{character.info.topic_id}",
                default=character.info.role_id in selected_role_ids,
            )
            for character in characters
        ]
        super().__init__(
            options=options,
            placeholder=LocaleStr(key="accompany_character_select_placeholder")
            if max_values == 1
            else LocaleStr(key="accompany_characters_select_placeholder", limit=max_values),
            custom_id="accompany_character_select",
            max_values=min(max_values, len(options)),
        )
        self.page_index = page_index
        self.options = self.process_options()

    async def callback(self, i: Interaction) -> None:
        if "next_page" in self.values:
            self.view.accompany_page_index += 1
        elif "prev_page" in self.values:
            self.view.accompany_page_index -= 1

        selected: list[dict[str, int]] = []
        for value in self.selected_values:
            role_id, topic_id = value.split(":")
            selected.append({"role_id": int(role_id), "topic_id": int(topic_id)})

        if selected:
            account = self.view.account
            # Keep the existing order so the first character stays first
            kept = [c for c in account.accompany_characters if c in selected]
            account.accompany_characters = kept + [c for c in selected if c not in kept]
            await account.save(update_fields=("accompany_characters",))

        await self.view.update(i)


class AccompanySettingsContainer(ui.DefaultContainer["SettingsView"]):
    @classmethod
    async def create(
        cls, *, account: HoyoAccount, locale: Locale, page_index: int, is_supporter: bool
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

        return cls(
            account=account, characters=characters, page_index=page_index, is_supporter=is_supporter
        )

    def __init__(
        self,
        *,
        account: HoyoAccount,
        characters: Sequence[genshin.models.AccompanyCharacter],
        page_index: int,
        is_supporter: bool,
    ) -> None:
        selected_role_ids = [
            c["role_id"] for c in account.get_accompany_characters(is_supporter=is_supporter)
        ]
        characters_by_id = {c.info.role_id: c for c in characters}
        selected = [characters_by_id[r] for r in selected_role_ids if r in characters_by_id]
        header = ui.TextDisplay(
            LocaleStr(
                custom_str="# {title}\n{desc}",
                title=LocaleStr(key="accompany_settings_title"),
                desc=LocaleStr(key="accompany_settings_desc"),
            )
        )
        super().__init__(
            ui.Section(header, accessory=discord.ui.Thumbnail(media=selected[0].profile.icon))
            if selected
            else header,
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {emoji} {title}\n{desc}",
                        emoji=emojis.FREE_CANCELLATION,
                        title=LocaleStr(key="accompany_button_label"),
                        desc=LocaleStr(
                            key="accompany_selected_character",
                            character=", ".join(c.info.name for c in selected),
                        )
                        if selected
                        else LocaleStr(key="accompany_no_character_selected"),
                    )
                ),
                accessory=AccountToggleButton(
                    attr="accompany_checkin",
                    current=account.accompany_checkin,
                    disabled=not account.accompany_characters,
                ),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.ActionRow(
                AccompanyCharacterSelect(
                    characters=characters,
                    selected_role_ids=selected_role_ids,
                    max_values=SPONSOR_ACCOMPANY_CHARACTER_LIMIT if is_supporter else 1,
                    page_index=page_index,
                )
            ),
        )
