from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from loguru import logger

from hoyo_buddy import ui
from hoyo_buddy.constants import locale_to_hoyo_lang
from hoyo_buddy.emojis import CHECK, CLOSE
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils.misc import is_valid_hex_color, shorten_preserving_newlines

if TYPE_CHECKING:
    from collections.abc import Sequence

    import genshin

    from hoyo_buddy.db.models.hoyo_account import HoyoAccount
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction, User
    from hoyo_buddy.ui.discord.container import ContainerItem

MAX_GALLERY_ITEMS = 10
MAX_VIDEO_LINKS = 5
MAX_VOICE_TEXT_LENGTH = 500


class AccompanyView(ui.LayoutView):
    def __init__(
        self,
        *,
        account: HoyoAccount,
        characters: Sequence[genshin.models.AccompanyCharacter],
        character: genshin.models.AccompanyCharacter,
        author: User,
        locale: Locale,
    ) -> None:
        super().__init__(author=author, locale=locale)

        self.account = account
        self.characters = characters
        self.character = character
        self.details: genshin.models.AccompanyCharacterDetails | None = None

        self.character_page_index = 0
        self.voice_lang: str | None = None
        self.voice_index = 0
        self.voice_page_index = 0

    async def _fetch_details(self) -> None:
        try:
            self.details = await self.account.client.get_accompany_character_details(
                topic_id=self.character.info.topic_id, lang=locale_to_hoyo_lang(self.locale)
            )
        except Exception as e:
            logger.debug(f"Failed to fetch accompany character details for {self.account}: {e}")
            self.details = None

        self.voice_lang = next(iter(self.details.voice_scripts), None) if self.details else None
        self.voice_index = 0
        self.voice_page_index = 0

    def _rebuild(self) -> None:
        self.clear_items()
        self.add_item(
            AccompanyContainer(
                account=self.account,
                characters=self.characters,
                character=self.character,
                details=self.details,
                voice_lang=self.voice_lang,
                voice_index=self.voice_index,
                voice_page_index=self.voice_page_index,
                character_page_index=self.character_page_index,
            )
        )

    async def start(self, i: Interaction) -> None:
        await self._fetch_details()
        self._rebuild()
        self.message = await i.edit_original_response(view=self)

    async def update(self, i: Interaction, *, refetch: bool = False) -> None:
        if not i.response.is_done():
            await i.response.defer()

        if refetch:
            await self._fetch_details()
        self._rebuild()
        self.message = await i.edit_original_response(view=self)


class AccompanyContainer(ui.Container["AccompanyView"]):
    def __init__(
        self,
        *,
        account: HoyoAccount,
        characters: Sequence[genshin.models.AccompanyCharacter],
        character: genshin.models.AccompanyCharacter,
        details: genshin.models.AccompanyCharacterDetails | None,
        voice_lang: str | None,
        voice_index: int,
        voice_page_index: int,
        character_page_index: int,
    ) -> None:
        info, profile = character.info, character.profile
        items: list[ContainerItem] = [
            self._build_header(info, details),
            self._build_gallery(profile),
        ]

        if (videos := self._build_videos(profile, details)) is not None:
            items.append(videos)

        if details is not None:
            items.extend(
                (
                    discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
                    self._build_accompany_info(details.accompany_info),
                    discord.ui.Separator(spacing=discord.SeparatorSpacing.small, visible=False),
                    ui.ActionRow(AccompanyNowButton(details=details)),
                )
            )

        voice_items = self._build_voice_lines(details, voice_lang, voice_index, voice_page_index)
        if voice_items:
            items.append(discord.ui.Separator(spacing=discord.SeparatorSpacing.large))
            items.extend(voice_items)

        items.extend(
            (
                discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
                *self._build_set_character_items(account, characters, character),
                discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
                ui.ActionRow(
                    CharacterSwitchSelect(
                        characters=characters,
                        current_role_id=info.role_id,
                        page_index=character_page_index,
                    )
                ),
            )
        )

        super().__init__(
            *items,
            accent_color=profile.card_color if is_valid_hex_color(profile.card_color) else None,
        )

    @staticmethod
    def _build_header(
        info: genshin.models.AccompanyCharacterInfo,
        details: genshin.models.AccompanyCharacterDetails | None,
    ) -> ui.TextDisplay:
        if details is None:
            desc: LocaleStr | str = info.game_name
        else:
            desc = LocaleStr(
                key="accompany_header_stats",
                posts=details.feed_info.total_posts,
                fan_arts=details.feed_info.fan_art_posts,
            )
            if details.stats is not None:
                desc = LocaleStr(
                    custom_str="{stats} · {members}",
                    stats=desc,
                    members=LocaleStr(
                        key="accompany_header_members", members=details.stats.members
                    ),
                )

        return ui.TextDisplay(LocaleStr(custom_str="# {name}\n{desc}", name=info.name, desc=desc))

    @staticmethod
    def _build_gallery(
        profile: genshin.models.AccompanyCharacterProfile,
    ) -> discord.ui.MediaGallery:
        gallery = discord.ui.MediaGallery()
        gallery.add_item(media=profile.card_image)
        return gallery

    @staticmethod
    def _build_videos(
        profile: genshin.models.AccompanyCharacterProfile,
        details: genshin.models.AccompanyCharacterDetails | None,
    ) -> ui.TextDisplay | None:
        video_urls = [profile.video]
        if details is not None:
            video_urls.extend(video.video_url for video in details.videos)

        links = " · ".join(
            f"[{index + 1}]({url})"
            for index, url in enumerate(url for url in video_urls[:MAX_VIDEO_LINKS] if url)
        )
        if not links:
            return None
        return ui.TextDisplay(
            LocaleStr(
                custom_str="{label}: {links}",
                label=LocaleStr(key="accompany_videos_label"),
                links=links,
            )
        )

    @staticmethod
    def _build_accompany_info(accompany_info: genshin.models.AccompanyInfo) -> ui.TextDisplay:
        return ui.TextDisplay(
            LocaleStr(
                custom_str="### {title}\n{body}",
                title=LocaleStr(key="accompany_info_title"),
                body=LocaleStr(
                    key="accompany_info_body",
                    days=accompany_info.days,
                    points=accompany_info.points,
                    available_points=accompany_info.available_points,
                    today=CHECK if accompany_info.accompanied_today else CLOSE,
                ),
            )
        )

    @staticmethod
    def _build_voice_lines(
        details: genshin.models.AccompanyCharacterDetails | None,
        voice_lang: str | None,
        voice_index: int,
        voice_page_index: int,
    ) -> list[ContainerItem]:
        if details is None or voice_lang is None:
            return []

        lines = details.voice_scripts.get(voice_lang)
        if not lines:
            return []

        line = lines[min(voice_index, len(lines) - 1)]
        items: list[ContainerItem] = [
            ui.TextDisplay(
                LocaleStr(
                    custom_str="### {title}\n{text}\n\n[{audio}]({url})",
                    title=LocaleStr(key="accompany_voice_lines_title"),
                    text=shorten_preserving_newlines(line.text, MAX_VOICE_TEXT_LENGTH),
                    audio=LocaleStr(key="accompany_voice_audio_label"),
                    url=line.voice_url,
                )
            )
        ]
        if len(details.voice_scripts) > 1:
            items.append(
                ui.ActionRow(VoiceLangSelect(langs=list(details.voice_scripts), current=voice_lang))
            )
        items.append(
            ui.ActionRow(
                VoiceLineSelect(lines=lines, current_index=voice_index, page_index=voice_page_index)
            )
        )
        return items

    @staticmethod
    def _build_set_character_items(
        account: HoyoAccount,
        characters: Sequence[genshin.models.AccompanyCharacter],
        character: genshin.models.AccompanyCharacter,
    ) -> tuple[ui.TextDisplay, discord.ui.Separator, ui.ActionRow]:
        current_character = next(
            (c for c in characters if c.info.role_id == account.accompany_role_id), None
        )
        return (
            ui.TextDisplay(
                LocaleStr(
                    custom_str="### {title}\n{desc}",
                    title=LocaleStr(key="accompany_settings_title"),
                    desc=LocaleStr(
                        key="accompany_selected_character", character=current_character.info.name
                    )
                    if current_character is not None
                    else LocaleStr(key="accompany_view_no_character_set"),
                )
            ),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.small, visible=False),
            ui.ActionRow(
                SetAccompanyCharacterButton(
                    disabled=account.accompany_role_id == character.info.role_id
                )
            ),
        )


class CharacterSwitchSelect(ui.PaginatorSelect["AccompanyView"]):
    def __init__(
        self,
        *,
        characters: Sequence[genshin.models.AccompanyCharacter],
        current_role_id: int,
        page_index: int,
    ) -> None:
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
            placeholder=LocaleStr(key="accompany_view_character_select_placeholder"),
        )
        self.page_index = page_index
        self.options = self.process_options()

    async def callback(self, i: Interaction) -> None:
        if "next_page" in self.values:
            self.view.character_page_index += 1
            await self.view.update(i)
            return
        if "prev_page" in self.values:
            self.view.character_page_index -= 1
            await self.view.update(i)
            return

        role_id = int(self.values[0].split(":")[0])
        character = next((c for c in self.view.characters if c.info.role_id == role_id), None)
        if character is None:
            return

        self.view.character = character
        await self.view.update(i, refetch=True)


class VoiceLangSelect(ui.Select["AccompanyView"]):
    def __init__(self, *, langs: Sequence[str], current: str) -> None:
        super().__init__(
            options=[
                ui.SelectOption(label=lang, value=lang, default=lang == current)
                for lang in langs[:25]
            ],
            placeholder=LocaleStr(key="accompany_voice_lang_select_placeholder"),
        )

    async def callback(self, i: Interaction) -> None:
        self.view.voice_lang = self.values[0]
        self.view.voice_index = 0
        self.view.voice_page_index = 0
        await self.view.update(i)


class VoiceLineSelect(ui.PaginatorSelect["AccompanyView"]):
    def __init__(
        self,
        *,
        lines: Sequence[genshin.models.AccompanyVoiceLine],
        current_index: int,
        page_index: int,
    ) -> None:
        options = [
            ui.SelectOption(
                label=" ".join(line.text.split())[:100] or str(index + 1),
                value=str(index),
                default=index == current_index,
            )
            for index, line in enumerate(lines)
        ]
        super().__init__(
            options=options, placeholder=LocaleStr(key="accompany_voice_line_select_placeholder")
        )
        self.page_index = page_index
        self.options = self.process_options()

    async def callback(self, i: Interaction) -> None:
        if "next_page" in self.values:
            self.view.voice_page_index += 1
            await self.view.update(i)
            return
        if "prev_page" in self.values:
            self.view.voice_page_index -= 1
            await self.view.update(i)
            return

        self.view.voice_index = int(self.values[0])
        await self.view.update(i)


class AccompanyNowButton(ui.Button["AccompanyView"]):
    def __init__(self, *, details: genshin.models.AccompanyCharacterDetails | None) -> None:
        cant_accompany = details is not None and (
            details.accompany_info.accompanied_today or not details.accompany_info.can_accompany
        )
        super().__init__(
            label=LocaleStr(key="accompany_now_button_label"),
            style=discord.ButtonStyle.success,
            disabled=cant_accompany,
        )

    async def callback(self, i: Interaction) -> None:
        await self.set_loading_state(i)

        account = self.view.account
        character = self.view.character
        result = await account.client.accompany_character(
            role_id=character.info.role_id, topic_id=character.info.topic_id
        )
        embed = account.client.get_accompany_embed(result, character.info.name, self.view.locale)

        await self.view.update(i, refetch=True)
        await i.followup.send(embed=embed, ephemeral=True)


class SetAccompanyCharacterButton(ui.Button["AccompanyView"]):
    def __init__(self, *, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr(key="accompany_set_character_button_label"),
            style=discord.ButtonStyle.primary,
            disabled=disabled,
        )

    async def callback(self, i: Interaction) -> None:
        account = self.view.account
        character = self.view.character
        account.accompany_role_id = character.info.role_id
        account.accompany_topic_id = character.info.topic_id
        await account.save(update_fields=("accompany_role_id", "accompany_topic_id"))
        await self.view.update(i)
