from __future__ import annotations

import asyncio
import datetime
from itertools import starmap
from typing import TYPE_CHECKING, TypeAlias

import genshin
from discord import ButtonStyle, File, SeparatorSpacing
from discord.ui import Separator
from discord.utils import escape_markdown, format_dt

from hoyo_buddy import ui
from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import AVAILABLE_OPEN_GAMES, get_open_game_url
from hoyo_buddy.db import draw_locale, get_dyk
from hoyo_buddy.draw.main_funcs import draw_gi_notes_card, draw_hsr_notes_card, draw_zzz_notes_card
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import (
    BATTERY_CHARGE_EMOJI,
    BELL_OUTLINE,
    CLOSE,
    GAME_ICON_EMOJIS,
    PT_EMOJI,
    REALM_CURRENCY,
    RESIN,
    TRAILBLAZE_POWER,
    get_game_emoji,
)
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import FeatureNotImplementedError
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.models import DrawInput
from hoyo_buddy.ui import Button, PaginatorSelect, Select, SelectOption
from hoyo_buddy.ui.reminders.view import RemindersView
from hoyo_buddy.utils import capture_exception

if TYPE_CHECKING:
    import io

    from discord import Member, User

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction

NotesWithCard: TypeAlias = (
    genshin.models.Notes | genshin.models.StarRailNote | genshin.models.ZZZNotes
)
AnyNotes: TypeAlias = NotesWithCard | genshin.models.HonkaiNotes

OVERVIEW_VALUE = "overview"
MAX_CONCURRENT_FETCHES = 4


class NotesView(ui.LayoutView):
    def __init__(
        self,
        account: HoyoAccount,
        accounts: list[HoyoAccount] | None = None,
        *,
        dark_mode: bool,
        author: User | Member | None,
        locale: Locale,
        overview: bool = False,
    ) -> None:
        super().__init__(author=author, locale=locale)
        self.account = account
        self.overview = overview
        self.dark_mode = dark_mode
        self.accounts = accounts
        self.bytes_obj: io.BytesIO | None = None
        self._rows: list[list[Button | Select]] = []
        self.dyk = ""

    def _add_items(self) -> None:
        self._rows = []
        if self.accounts is not None:
            self._rows.append(
                [AccountSwitcher(self.accounts, self.account, overview=self.overview)]
            )
        if self.overview:
            return
        if buttons := self.get_open_game_buttons(self.account):
            self._rows.append(list(buttons))
        self._rows.append([RemindersButton()])

    def render(self, embed: DefaultEmbed) -> None:
        self.clear_items()
        self.add_item(ui.EmbedContainer(embed, *starmap(ui.ActionRow, self._rows)))
        if self.dyk:
            self.add_item(ui.TextDisplay(self.dyk))

    def _render_overview(self, lines: list[str]) -> None:
        self.clear_items()
        self.add_item(
            ui.DefaultContainer(
                ui.TextDisplay("\n\n".join(lines)),
                Separator(spacing=SeparatorSpacing.large),
                *starmap(ui.ActionRow, self._rows),
            )
        )
        if self.dyk:
            self.add_item(ui.TextDisplay(self.dyk))

    @staticmethod
    async def _get_notes(account: HoyoAccount) -> AnyNotes:
        if account.game is Game.GENSHIN:
            return await account.client.get_genshin_notes()
        if account.game is Game.ZZZ:
            return await account.client.get_zzz_notes()
        if account.game is Game.STARRAIL:
            return await account.client.get_starrail_notes()
        if account.game is Game.HONKAI:
            return await account.client.get_honkai_notes()

        raise FeatureNotImplementedError(platform=account.platform, game=account.game)

    async def _get_overview_lines(self, accounts: list[HoyoAccount]) -> list[str]:
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

        async def fetch(account: HoyoAccount) -> AnyNotes:
            async with semaphore:
                return await self._get_notes(account)

        results = await asyncio.gather(*map(fetch, accounts), return_exceptions=True)

        lines: list[str] = []
        for account, result in zip(accounts, results, strict=True):
            header = f"### {GAME_ICON_EMOJIS[account.game_icon]} {escape_markdown(account.blurred_display)}"
            if isinstance(result, Exception):
                embed, recognized = get_error_embed(result, self.locale)
                if not recognized:
                    capture_exception(result)
                lines.append(f"{header}\n{CLOSE} {embed.title}")
            elif isinstance(result, BaseException):
                raise result
            else:
                lines.append(f"{header}\n{self._get_stamina_line(result)}")
        return lines

    def _get_stamina_line(self, notes: AnyNotes) -> str:
        if isinstance(notes, genshin.models.Notes):
            emoji, cur, max_ = RESIN, notes.current_resin, notes.max_resin
            seconds = notes.remaining_resin_recovery_time.total_seconds()
        elif isinstance(notes, genshin.models.StarRailNote):
            emoji, cur, max_ = TRAILBLAZE_POWER, notes.current_stamina, notes.max_stamina
            seconds = notes.stamina_recover_time.total_seconds()
        elif isinstance(notes, genshin.models.ZZZNotes):
            emoji, cur, max_ = (
                BATTERY_CHARGE_EMOJI,
                notes.battery_charge.current,
                notes.battery_charge.max,
            )
            seconds = notes.battery_charge.seconds_till_full
        else:
            emoji, cur, max_ = "", notes.current_stamina, notes.max_stamina
            seconds = notes.stamina_recover_time

        if seconds > 0:
            full_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=seconds)
            status = LocaleStr(key="notes_overview.full_time", time=format_dt(full_at, "R"))
        else:
            status = LocaleStr(key="note_already_full", mi18n_game=Game.STARRAIL)

        prefix = f"{emoji} " if emoji else ""
        return f"{prefix}**{cur}/{max_}** · {status.translate(self.locale)}"

    async def _draw_notes_card(self, notes: NotesWithCard, draw_input: DrawInput) -> io.BytesIO:
        if isinstance(notes, genshin.models.Notes):
            return await draw_gi_notes_card(draw_input, notes)
        if isinstance(notes, genshin.models.ZZZNotes):
            return await draw_zzz_notes_card(draw_input, notes)
        return await draw_hsr_notes_card(draw_input, notes)

    def _get_notes_embed(
        self,
        notes: genshin.models.Notes
        | genshin.models.StarRailNote
        | genshin.models.ZZZNotes
        | genshin.models.HonkaiNotes,
    ) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale)

        if isinstance(notes, genshin.models.Notes):
            if notes.remaining_resin_recovery_time.total_seconds() > 0:
                embed.add_description(
                    LocaleStr(
                        key="notes.item_full_in_time",
                        emoji=RESIN,
                        in_time=notes.remaining_resin_recovery_time,
                    )
                )
            if notes.remaining_realm_currency_recovery_time.total_seconds() > 0:
                embed.add_description(
                    LocaleStr(
                        key="notes.item_full_in_time",
                        emoji=REALM_CURRENCY,
                        in_time=notes.remaining_realm_currency_recovery_time,
                    )
                )
            if (
                notes.remaining_transformer_recovery_time is not None
                and notes.remaining_transformer_recovery_time.total_seconds() > 0
            ):
                embed.add_description(
                    LocaleStr(
                        key="notes_available",
                        emoji=PT_EMOJI,
                        in_time=notes.remaining_transformer_recovery_time,
                    )
                )
        elif isinstance(notes, genshin.models.ZZZNotes):
            if (recover := notes.battery_charge.seconds_till_full) > 0:
                embed.add_description(
                    LocaleStr(
                        key="notes.item_full_in_time",
                        emoji=BATTERY_CHARGE_EMOJI,
                        in_time=datetime.timedelta(seconds=recover),
                    )
                )
        elif isinstance(notes, genshin.models.HonkaiNotes):
            embed.add_description(
                LocaleStr(
                    key="notes.stamina",
                    time=datetime.timedelta(seconds=notes.stamina_recover_time),
                    cur=notes.current_stamina,
                    max=notes.max_stamina,
                )
            )
            embed.add_description(
                LocaleStr(key="notes.train_score", cur=notes.current_train_score, max=600)
            )

            embed.add_field(
                name=LocaleStr(key="notes.superstring_dimension"),
                value=LocaleStr(
                    key="notes.superstring_dimension_value",
                    score=notes.ultra_endless.challenge_score,
                ),
                inline=False,
            )
            if notes.battle_field is not None:
                embed.add_field(
                    name=LocaleStr(key="notes.memorial_arena"),
                    value=LocaleStr(
                        key="notes.memorial_arena_value",
                        rewards_cur=notes.battle_field.current_reward,
                        rewards_max=notes.battle_field.max_reward,
                        sss_cur=notes.battle_field.current_sss_reward,
                        sss_max=notes.battle_field.max_sss_reward,
                    ),
                    inline=False,
                )
            embed.add_field(
                name=LocaleStr(key="notes.elysian_realm"),
                value=LocaleStr(
                    key="notes.elysian_realm_value",
                    cur=notes.god_war.current_reward,
                    max=notes.god_war.max_reward,
                ),
                inline=False,
            )
        else:  # StarRailNotes
            if notes.stamina_recover_time.total_seconds() > 0:
                embed.add_description(
                    LocaleStr(
                        key="notes.item_full_in_time",
                        emoji=TRAILBLAZE_POWER,
                        in_time=notes.stamina_recover_time,
                    )
                )
            if notes.have_bonus_synchronicity_points:
                embed.add_description(
                    LocaleStr(
                        key="notes.bonus_sync_points",
                        cur=notes.current_bonus_synchronicity_points,
                        max=notes.max_bonus_synchronicity_points,
                    )
                )

        return embed.set_image(url="attachment://notes.webp").add_acc_info(self.account)

    async def start(self, i: Interaction, *, acc_select: AccountSwitcher | None = None) -> None:
        self._add_items()
        if acc_select is None:
            self.dyk = await get_dyk(i)

        if self.overview and self.accounts is not None:
            self._render_overview(await self._get_overview_lines(self.accounts))
            files: list[File] = []
        else:
            files = await self._render_account(i)

        if acc_select is not None:
            acc_select._update_view(self)
            await acc_select.unset_loading_state(i, attachments=files)
        else:
            await i.followup.send(view=self, files=files)

        self.message = await i.original_response()

    async def _render_account(self, i: Interaction) -> list[File]:
        notes = await self._get_notes(self.account)
        embed = self._get_notes_embed(notes)

        if isinstance(notes, NotesWithCard):
            draw_input = DrawInput(
                dark_mode=self.dark_mode,
                locale=draw_locale(self.locale, self.account),
                session=i.client.session,
                filename="notes.webp",
                executor=i.client.executor,
                loop=i.client.loop,
            )
            self.bytes_obj = await self._draw_notes_card(notes, draw_input)
            self.bytes_obj.seek(0)
            file_ = File(self.bytes_obj, filename="notes.webp")
        else:
            file_ = None
            embed.set_image(url=None)

        self.render(embed)
        return [file_] if file_ is not None else []

    @staticmethod
    def get_open_game_buttons(account: HoyoAccount, *, row: int = 0) -> list[Button]:
        result: list[Button] = []

        platform, game = account.platform, account.game
        available_games = AVAILABLE_OPEN_GAMES.get(platform)

        if available_games is not None:
            buttons = available_games.get(game)
            if buttons is not None:
                for label_enum, region, game in buttons:
                    url = get_open_game_url(region=region, game=game)
                    result.append(
                        Button(label=LocaleStr(key=label_enum.value), url=str(url), row=row)
                    )

        return result


class AccountSwitcher(PaginatorSelect[NotesView]):
    def __init__(
        self, accounts: list[HoyoAccount], account: HoyoAccount, *, overview: bool
    ) -> None:
        options = [
            SelectOption(
                label=acc.blurred_display,
                value=f"{acc.uid}_{acc.game}",
                emoji=get_game_emoji(acc.game),
                default=not overview and acc == account,
            )
            for acc in accounts
        ]
        if len(accounts) > 1:
            options.insert(
                0,
                SelectOption(
                    label=LocaleStr(key="notes_overview_option_label"),
                    value=OVERVIEW_VALUE,
                    default=overview,
                ),
            )
        super().__init__(placeholder=LocaleStr(key="account_select_placeholder"), options=options)

    async def callback(self, i: Interaction) -> None:
        assert self.view.accounts is not None

        if self.update_page():
            await i.response.edit_message(view=self.view)
            return

        await self.set_loading_state(i)
        view = self.view
        if self.values[0] == OVERVIEW_VALUE:
            view.overview = True
            await view.start(i, acc_select=self)
            return

        uid, game = self.values[0].split("_")
        account = next(
            (acc for acc in self.view.accounts if acc.uid == int(uid) and acc.game == game), None
        )
        if account is None:
            msg = f"Account not found for {uid} in {game}"
            raise ValueError(msg)

        view.overview = False
        view.account = account
        await view.start(i, acc_select=self)


class RemindersButton(Button[NotesView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="reminders_button_label"),
            emoji=BELL_OUTLINE,
            style=ButtonStyle.blurple,
        )

    async def callback(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=True, thinking=True)
        view = RemindersView(author=i.user, locale=self.view.locale, account=self.view.account)
        await view.update(i)
