from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord
import genshin
from discord.utils import format_dt
from seria.utils import split_list_to_chunks

from hoyo_buddy import ui
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import BACK, GAME_ICON_EMOJIS, POLYCHROME_EMOJI, PRIMOGEM_EMOJI
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr, translator

if TYPE_CHECKING:
    import datetime

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction, User

ROWS_PER_PAGE = 20
ZZZ_LOG_PAGE_SIZE = 100

TITLES: dict[Game, LocaleStr] = {
    Game.GENSHIN: LocaleStr(key="genshin_tool_travelers_note", mi18n_game=Game.GENSHIN),
    Game.ZZZ: LocaleStr(key="note_book", mi18n_game=Game.ZZZ),
}


@dataclass(kw_only=True)
class Currency:
    id: str
    name: LocaleStr | str
    amount: int
    emoji: str | None = None
    last_amount: int | None = None
    today: int | None = None


@dataclass(kw_only=True)
class IncomeSource:
    name: LocaleStr | str
    amount: int
    percent: int


@dataclass(kw_only=True)
class DiarySummary:
    month: str
    months: list[str]
    currencies: list[Currency]
    sources_title: LocaleStr
    sources: list[IncomeSource]


@dataclass(kw_only=True)
class LogEntry:
    name: LocaleStr | str
    time: datetime.datetime
    amount: int


def _month_name(month: str) -> LocaleStr:
    """Month is "10" for Genshin and "202610" for ZZZ."""
    return LocaleStr(key=f"month_{int(month[-2:])}", mi18n_game=Game.ZZZ)


def _zzz_prev_month(month: str) -> str:
    year, month_ = int(month[:4]), int(month[4:])
    return f"{year - 1}12" if month_ == 1 else f"{year}{month_ - 1:02d}"


def _rate(current: int, last: int) -> str | None:
    if last == 0:
        return None
    rate = round((current - last) / last * 100)
    return f"▲ {rate}%" if rate >= 0 else f"▼ {-rate}%"


class DiaryView(ui.LayoutPaginatorView):
    def __init__(self, account: HoyoAccount, *, author: User, locale: Locale) -> None:
        super().__init__([], author=author, locale=locale)
        self.account = account
        self.client = account.client
        self.client.set_lang(locale)

        self.month = ""
        self._summaries: dict[str, DiarySummary] = {}
        self._logs: dict[tuple[str, str], list[LogEntry]] = {}

    @property
    def summary(self) -> DiarySummary:
        return self._summaries[self.month]

    def _translate(self, string: LocaleStr | str) -> str:
        return translator.translate(string, self.locale)

    async def _fetch_gi_summary(self, month: str | None) -> DiarySummary:
        data = await self.client.request_ledger(
            self.account.uid, game=genshin.Game.GENSHIN, month=int(month) if month else None
        )
        diary = genshin.models.Diary(**data)
        months = [str(m) for m in sorted(data["optional_month"], reverse=True)]
        is_current = str(diary.month) == months[0]

        return DiarySummary(
            month=str(diary.month),
            months=months,
            currencies=[
                Currency(
                    id=str(genshin.models.DiaryType.PRIMOGEMS.value),
                    name=LocaleStr(key="diary_primogems"),
                    emoji=PRIMOGEM_EMOJI,
                    amount=diary.data.current_primogems,
                    last_amount=diary.data.last_primogems,
                    today=diary.day_data.current_primogems if is_current else None,
                ),
                Currency(
                    id=str(genshin.models.DiaryType.MORA.value),
                    name=LocaleStr(key="diary_mora"),
                    amount=diary.data.current_mora,
                    last_amount=diary.data.last_mora,
                    today=diary.day_data.current_mora if is_current else None,
                ),
            ],
            sources_title=LocaleStr(key="diary_primogem_sources"),
            sources=[
                IncomeSource(name=c.name, amount=c.amount, percent=c.percentage)
                for c in diary.data.categories
            ],
        )

    async def _fetch_zzz_summary(self, month: str | None) -> DiarySummary:
        diary = await self.client.get_zzz_diary(self.account.uid, month=month)

        last_amounts: dict[genshin.models.ZZZCurrencyType, int] = {}
        prev_month = _zzz_prev_month(diary.data_month)
        if prev_month in diary.month_options:
            prev_diary = await self.client.get_zzz_diary(self.account.uid, month=prev_month)
            last_amounts = {c.type: c.num for c in prev_diary.income.currencies}

        return DiarySummary(
            month=diary.data_month,
            months=list(diary.month_options),
            currencies=[
                Currency(
                    id=c.type.value,
                    name=c.name,
                    emoji=POLYCHROME_EMOJI
                    if c.type is genshin.models.ZZZCurrencyType.POLYCHROME
                    else None,
                    amount=c.num,
                    last_amount=last_amounts.get(c.type),
                )
                for c in diary.income.currencies
            ],
            sources_title=LocaleStr(key="income_composition", mi18n_game=Game.ZZZ),
            sources=[
                IncomeSource(
                    name=LocaleStr(key=s.source.value, mi18n_game=Game.ZZZ),
                    amount=s.num,
                    percent=s.percent,
                )
                for s in diary.income.polychrome_incomes
            ],
        )

    async def fetch_summary(self, month: str | None = None) -> None:
        if month is None or month not in self._summaries:
            if self.account.game is Game.GENSHIN:
                summary = await self._fetch_gi_summary(month)
            else:
                summary = await self._fetch_zzz_summary(month)
            self._summaries[summary.month] = summary
            month = summary.month
        self.month = month

    async def _fetch_gi_log(self, currency_id: str) -> list[LogEntry]:
        actions = await self.client.genshin_diary_log(
            self.account.uid, type=genshin.models.DiaryType(int(currency_id)), month=int(self.month)
        ).flatten()
        return [LogEntry(name=a.action, time=a.time, amount=a.amount) for a in actions]

    async def _fetch_zzz_log(self, currency_id: str) -> list[LogEntry]:
        items: list[genshin.models.ZZZDiaryDetailItem] = []
        page = 1
        while True:
            detail = await self.client.get_zzz_diary_detail(
                self.month,
                type=genshin.models.ZZZCurrencyType(currency_id),
                page=page,
                page_size=ZZZ_LOG_PAGE_SIZE,
                uid=self.account.uid,
            )
            items.extend(detail.items)
            if not detail.items or len(items) >= detail.total:
                break
            page += 1

        return [
            LogEntry(
                name=LocaleStr(key=item.source.value, mi18n_game=Game.ZZZ),
                time=item.time,
                amount=item.num,
            )
            for item in items
        ]

    async def _fetch_log(self, currency_id: str) -> list[LogEntry]:
        key = (self.month, currency_id)
        if key not in self._logs:
            if self.account.game is Game.GENSHIN:
                self._logs[key] = await self._fetch_gi_log(currency_id)
            else:
                self._logs[key] = await self._fetch_zzz_log(currency_id)
        return self._logs[key]

    def _currency_text(self, currency: Currency) -> str:
        name = self._translate(currency.name)
        emoji = f"{currency.emoji} " if currency.emoji else ""
        lines = [f"{emoji}**{name}**: {currency.amount:,}"]

        details: list[str] = []
        if currency.last_amount is not None:
            if rate := _rate(currency.amount, currency.last_amount):
                details.append(rate)
            details.append(
                self._translate(
                    LocaleStr(key="diary_last_month", amount=f"{currency.last_amount:,}")
                )
            )
        if currency.today is not None:
            today = self._translate(LocaleStr(key="note_today", mi18n_game=Game.ZZZ))
            details.append(f"{today}: {currency.today:,}")
        if details:
            lines.append(f"-# {' · '.join(details)}")

        return "\n".join(lines)

    def show_summary(self) -> None:
        summary = self.summary
        title = self._translate(TITLES[self.account.game])
        month = self._translate(_month_name(self.month))
        currencies = "\n".join(self._currency_text(c) for c in summary.currencies)
        sources = "\n".join(
            f"{s.percent}% · {self._translate(s.name)} · {s.amount:,}" for s in summary.sources
        )

        header = f"{GAME_ICON_EMOJIS[self.account.game_icon]} {self.account.blurred_display}"

        self.clear_items()
        self.add_item(
            ui.DefaultContainer(
                ui.TextDisplay(f"### {header}"),
                ui.TextDisplay(f"# {title} · {month}\n{currencies}"),
                discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
                ui.TextDisplay(f"## {self._translate(summary.sources_title)}\n{sources}"),
                discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
                ui.ActionRow(MonthSelect(summary.months, self.month)),
                ui.ActionRow(LogButton()),
            )
        )

    def _get_log_pages(self, currency: Currency, entries: list[LogEntry]) -> list[ui.Page]:
        title = f"{self._translate(currency.name)} · {self._translate(_month_name(self.month))}"
        chunks = split_list_to_chunks(entries, ROWS_PER_PAGE) or [[]]

        pages: list[ui.Page] = []
        for index, chunk in enumerate(chunks):
            lines = [
                f"`+{e.amount:,}` {self._translate(e.name)} · "
                f"{format_dt(e.time, 'd')} {format_dt(e.time, 't')}"
                for e in chunk
            ]
            description = "\n".join(lines) or LocaleStr(key="no_data", mi18n_game=Game.GENSHIN)
            embed = (
                DefaultEmbed(self.locale, title=title, description=description)
                .add_acc_info(self.account)
                .set_footer(
                    text=LocaleStr(
                        key="page_footer", current_page=index + 1, total_pages=len(chunks)
                    )
                )
            )
            pages.append(ui.Page(embed=embed))
        return pages

    async def show_log(self, i: Interaction, currency_id: str) -> None:
        currency = next(c for c in self.summary.currencies if c.id == currency_id)
        entries = await self._fetch_log(currency_id)

        self.pages = self._get_log_pages(currency, entries)
        self.current_page = 0
        self.rows = [
            [CurrencySelect(self.summary.currencies, currency_id)],
            [BackToSummaryButton()],
        ]
        await self._update_page(i, None)

    async def start(self, i: Interaction) -> None:
        await self.fetch_summary()
        self.show_summary()
        self.message = await i.edit_original_response(view=self)


class MonthSelect(ui.Select[DiaryView]):
    def __init__(self, months: list[str], current: str) -> None:
        super().__init__(
            options=[
                ui.SelectOption(label=_month_name(month), value=month, default=month == current)
                for month in months
            ]
        )

    async def callback(self, i: Interaction) -> None:
        view = self.view
        await self.set_loading_state(i)
        await view.fetch_summary(self.values[0])
        view.show_summary()
        await i.edit_original_response(view=view)


class LogButton(ui.Button[DiaryView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="detail", mi18n_game=Game.GENSHIN),
            style=discord.ButtonStyle.blurple,
        )

    async def callback(self, i: Interaction) -> None:
        view = self.view
        await self.set_loading_state(i)
        await view.show_log(i, view.summary.currencies[0].id)


class CurrencySelect(ui.Select[DiaryView]):
    def __init__(self, currencies: list[Currency], current: str) -> None:
        super().__init__(
            options=[
                ui.SelectOption(label=c.name, value=c.id, emoji=c.emoji, default=c.id == current)
                for c in currencies
            ]
        )

    async def callback(self, i: Interaction) -> None:
        view = self.view
        await self.set_loading_state(i)
        await view.show_log(i, self.values[0])


class BackToSummaryButton(ui.Button[DiaryView]):
    def __init__(self) -> None:
        super().__init__(label=LocaleStr(key="back_btn_label", mi18n_game=Game.GENSHIN), emoji=BACK)

    async def callback(self, i: Interaction) -> None:
        view = self.view
        view.show_summary()
        await i.response.edit_message(view=view)
