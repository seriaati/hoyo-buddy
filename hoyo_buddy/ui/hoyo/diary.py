from __future__ import annotations

import calendar
import dataclasses
import datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

import discord
import genshin
from discord.utils import format_dt
from loguru import logger
from seria.utils import split_list_to_chunks

from hoyo_buddy import ui
from hoyo_buddy.constants import HB_GAME_TO_GPY_GAME, SERVER_RESET_HOURS
from hoyo_buddy.db import DiaryHistory
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import BACK, GAME_ICON_EMOJIS, POLYCHROME_EMOJI, PRIMOGEM_EMOJI
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr, translator
from hoyo_buddy.utils.misc import get_now

if TYPE_CHECKING:
    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction, User

ROWS_PER_PAGE = 20
ZZZ_LOG_PAGE_SIZE = 100

TITLES: dict[Game, LocaleStr] = {
    Game.GENSHIN: LocaleStr(key="genshin_tool_travelers_note", mi18n_game=Game.GENSHIN),
    Game.ZZZ: LocaleStr(key="note_book", mi18n_game=Game.ZZZ),
}
SOURCES_TITLES: dict[Game, LocaleStr] = {
    Game.GENSHIN: LocaleStr(key="diary_primogem_sources"),
    Game.ZZZ: LocaleStr(key="income_composition", mi18n_game=Game.ZZZ),
}
GI_CURRENCY_NAMES: dict[str, LocaleStr] = {
    str(genshin.models.DiaryType.PRIMOGEMS.value): LocaleStr(key="diary_primogems"),
    str(genshin.models.DiaryType.MORA.value): LocaleStr(key="diary_mora"),
}
CURRENCY_EMOJIS: dict[str, str] = {
    str(genshin.models.DiaryType.PRIMOGEMS.value): PRIMOGEM_EMOJI,
    genshin.models.ZZZCurrencyType.POLYCHROME.value: POLYCHROME_EMOJI,
}


@dataclass(kw_only=True)
class Currency:
    id: str
    name: str
    """Currency name from the API, Genshin currencies use `GI_CURRENCY_NAMES` instead."""
    amount: int
    last_amount: int | None = None
    today: int | None = None


@dataclass(kw_only=True)
class IncomeSource:
    name: str
    """Action name from the API for Genshin, `PolychromeIncomeType` value for ZZZ."""
    amount: int
    percent: int


@dataclass(kw_only=True)
class DiarySummary:
    month: str
    """Formatted as YYYYMM."""
    days: int
    """Number of days of the month the amounts cover."""
    currencies: list[Currency]
    sources: list[IncomeSource]

    def to_dict(self) -> dict[str, Any]:
        data = dataclasses.asdict(self)
        for currency in data["currencies"]:
            # Today's amount is stale once saved
            currency["today"] = None
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            month=data["month"],
            days=data["days"],
            currencies=[Currency(**c) for c in data["currencies"]],
            sources=[IncomeSource(**s) for s in data["sources"]],
        )


@dataclass(kw_only=True)
class LogEntry:
    name: LocaleStr | str
    time: datetime.datetime
    amount: int


def _month_name(month: str) -> LocaleStr:
    return LocaleStr(
        custom_str="{month} {year}",
        month=LocaleStr(key=f"month_{int(month[4:])}", mi18n_game=Game.ZZZ),
        year=month[:4],
    )


def _prev_month(month: str) -> str:
    year, month_ = int(month[:4]), int(month[4:])
    return f"{year - 1}12" if month_ == 1 else f"{year}{month_ - 1:02d}"


def _days_in_month(month: str) -> int:
    return calendar.monthrange(int(month[:4]), int(month[4:]))[1]


def _rate(current: float, last: float) -> str | None:
    if last == 0:
        return None
    rate = round((current - last) / last * 100)
    return f"▲ {rate}%" if rate >= 0 else f"▼ {-rate}%"


def _server_today(account: HoyoAccount) -> datetime.date:
    server = genshin.utility.recognize_server(account.uid, HB_GAME_TO_GPY_GAME[account.game])
    # Servers reset at 4 AM local time, SERVER_RESET_HOURS are in UTC+8
    offset = 12 - SERVER_RESET_HOURS.get(server, 4)
    return get_now(datetime.timezone(datetime.timedelta(hours=offset))).date()


class DiaryView(ui.LayoutPaginatorView):
    def __init__(self, account: HoyoAccount, *, author: User, locale: Locale) -> None:
        super().__init__([], author=author, locale=locale)
        self.account = account
        self.client = account.client
        self.client.set_lang(locale)

        self.month = ""
        self.months: list[str] = []
        self._today = _server_today(account)
        self._api_months: list[str] = []
        self._summaries: dict[str, DiarySummary] = {}
        self._stored: dict[str, DiarySummary] = {}
        self._logs: dict[tuple[str, str], list[LogEntry]] = {}

    @property
    def summary(self) -> DiarySummary:
        return self._summaries[self.month]

    def _translate(self, string: LocaleStr | str) -> str:
        return translator.translate(string, self.locale)

    def _gi_month_key(self, month: int) -> str:
        year = self._today.year if month <= self._today.month else self._today.year - 1
        return f"{year}{month:02d}"

    def _days(self, month: str) -> int:
        if month == f"{self._today:%Y%m}":
            return self._today.day
        return _days_in_month(month)

    def _complete_summary(self, month: str) -> DiarySummary | None:
        summary = self._summaries.get(month) or self._stored.get(month)
        if summary is None or summary.days < _days_in_month(month):
            return None
        return summary

    async def _fetch_gi_summary(self, month: str | None) -> DiarySummary:
        data = await self.client.request_ledger(
            self.account.uid, game=genshin.Game.GENSHIN, month=int(month[4:]) if month else None
        )
        diary = genshin.models.Diary(**data)
        self._api_months = [self._gi_month_key(m) for m in data["optional_month"]]
        month = self._gi_month_key(diary.month)
        is_current = month == max(self._api_months)

        return DiarySummary(
            month=month,
            days=self._days(month),
            currencies=[
                Currency(
                    id=str(genshin.models.DiaryType.PRIMOGEMS.value),
                    name="",
                    amount=diary.data.current_primogems,
                    last_amount=diary.data.last_primogems,
                    today=diary.day_data.current_primogems if is_current else None,
                ),
                Currency(
                    id=str(genshin.models.DiaryType.MORA.value),
                    name="",
                    amount=diary.data.current_mora,
                    last_amount=diary.data.last_mora,
                    today=diary.day_data.current_mora if is_current else None,
                ),
            ],
            sources=[
                IncomeSource(name=c.name, amount=c.amount, percent=c.percentage)
                for c in diary.data.categories
            ],
        )

    async def _get_zzz_last_amounts(self, month: str) -> dict[str, int]:
        if (summary := self._complete_summary(month)) is not None:
            return {c.id: c.amount for c in summary.currencies}
        if month not in self._api_months:
            return {}

        diary = await self.client.get_zzz_diary(self.account.uid, month=month)
        return {c.type.value: c.num for c in diary.income.currencies}

    async def _fetch_zzz_summary(self, month: str | None) -> DiarySummary:
        diary = await self.client.get_zzz_diary(self.account.uid, month=month)
        self._api_months = list(diary.month_options)
        last_amounts = await self._get_zzz_last_amounts(_prev_month(diary.data_month))

        return DiarySummary(
            month=diary.data_month,
            days=self._days(diary.data_month),
            currencies=[
                Currency(
                    id=c.type.value,
                    name=c.name,
                    amount=c.num,
                    last_amount=last_amounts.get(c.type.value),
                )
                for c in diary.income.currencies
            ],
            sources=[
                IncomeSource(name=s.source.value, amount=s.num, percent=s.percent)
                for s in diary.income.polychrome_incomes
            ],
        )

    async def _fetch_api_summary(self, month: str | None) -> DiarySummary:
        if self.account.game is Game.GENSHIN:
            summary = await self._fetch_gi_summary(month)
        else:
            summary = await self._fetch_zzz_summary(month)

        self._summaries[summary.month] = summary
        await DiaryHistory.update_or_create(
            uid=self.account.uid,
            game=self.account.game,
            month=summary.month,
            defaults={"data": summary.to_dict()},
        )
        return summary

    async def fetch_summary(self, month: str | None = None) -> None:
        if month is None:
            month = (await self._fetch_api_summary(None)).month
        elif month not in self._summaries:
            if month in self._api_months:
                await self._fetch_api_summary(month)
            else:
                self._summaries[month] = self._stored[month]
        self.month = month

    async def _load_stored(self) -> None:
        histories = await DiaryHistory.filter(uid=self.account.uid, game=self.account.game)
        self._stored = {h.month: DiarySummary.from_dict(h.data) for h in histories}

    async def _backfill_history(self) -> None:
        """Save past months HoYoLAB still has before they become unavailable."""
        for month in sorted(self._api_months):
            if month in self._summaries or self._complete_summary(month) is not None:
                continue
            try:
                await self._fetch_api_summary(month)
            except Exception as e:
                logger.warning(f"Failed to backfill diary of {self.account} for {month}: {e}")
                return

    async def _fetch_gi_log(self, currency_id: str) -> list[LogEntry]:
        actions = await self.client.genshin_diary_log(
            self.account.uid,
            type=genshin.models.DiaryType(int(currency_id)),
            month=int(self.month[4:]),
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

    def _source_name(self, source: IncomeSource) -> LocaleStr | str:
        if self.account.game is Game.ZZZ:
            return LocaleStr(key=source.name, mi18n_game=Game.ZZZ)
        return source.name

    def _per_day(self, amount: float) -> str:
        return self._translate(LocaleStr(key="diary_per_day", amount=f"{amount:,.0f}"))

    def _currency_text(self, currency: Currency) -> str:
        name = self._translate(GI_CURRENCY_NAMES.get(currency.id, currency.name))
        emoji = CURRENCY_EMOJIS.get(currency.id)
        per_day = currency.amount / self.summary.days
        lines = [f"{f'{emoji} ' if emoji else ''}**{name}**: {currency.amount:,}"]

        details = [self._per_day(per_day)]
        last_line: str | None = None
        if currency.last_amount is not None:
            last_per_day = currency.last_amount / _days_in_month(_prev_month(self.month))
            if rate := _rate(per_day, last_per_day):
                details.append(rate)
            last_month = self._translate(
                LocaleStr(key="diary_last_month", amount=f"{currency.last_amount:,}")
            )
            last_line = f"-# {last_month} · {self._per_day(last_per_day)}"
        if currency.today is not None:
            today = self._translate(LocaleStr(key="note_today", mi18n_game=Game.ZZZ))
            details.append(f"{today}: {currency.today:,}")

        lines.append(f"-# {' · '.join(details)}")
        if last_line is not None:
            lines.append(last_line)
        return "\n".join(lines)

    def show_summary(self) -> None:
        summary = self.summary
        title = self._translate(TITLES[self.account.game])
        month = self._translate(_month_name(self.month))
        currencies = "\n".join(self._currency_text(c) for c in summary.currencies)
        sources = "\n".join(
            f"{s.percent}% · {self._translate(self._source_name(s))} · {s.amount:,}"
            for s in summary.sources
        )
        sources_title = self._translate(SOURCES_TITLES[self.account.game])

        header = f"{GAME_ICON_EMOJIS[self.account.game_icon]} {self.account.display}"

        self.clear_items()
        self.add_item(
            ui.DefaultContainer(
                ui.TextDisplay(f"### {header}"),
                ui.TextDisplay(f"# {title} · {month}\n{currencies}"),
                discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
                ui.TextDisplay(f"## {sources_title}\n{sources}"),
                discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
                ui.ActionRow(MonthSelect(self.months, self.month)),
                # Logs are only available for months HoYoLAB still has
                ui.ActionRow(LogButton(disabled=self.month not in self._api_months)),
            )
        )

    def _get_log_pages(self, currency: Currency, entries: list[LogEntry]) -> list[ui.Page]:
        name = self._translate(GI_CURRENCY_NAMES.get(currency.id, currency.name))
        title = f"{name} · {self._translate(_month_name(self.month))}"
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
        await self._load_stored()
        await self.fetch_summary()
        self.months = sorted({*self._api_months, *self._stored}, reverse=True)
        self.show_summary()
        self.message = await i.edit_original_response(view=self)
        await self._backfill_history()


class MonthSelect(ui.PaginatorSelect[DiaryView]):
    def __init__(self, months: list[str], current: str) -> None:
        super().__init__(
            options=[
                ui.SelectOption(label=_month_name(month), value=month, default=month == current)
                for month in months
            ]
        )
        self.set_page_based_on_value(current)
        self.options = self.process_options()

    async def callback(self, i: Interaction) -> None:
        if self.update_page():
            await i.response.edit_message(view=self.view)
            return

        view = self.view
        await self.set_loading_state(i)
        await view.fetch_summary(self.values[0])
        view.show_summary()
        await i.edit_original_response(view=view)


class LogButton(ui.Button[DiaryView]):
    def __init__(self, *, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr(key="detail", mi18n_game=Game.GENSHIN),
            style=discord.ButtonStyle.blurple,
            disabled=disabled,
        )

    async def callback(self, i: Interaction) -> None:
        view = self.view
        await self.set_loading_state(i)
        await view.show_log(i, view.summary.currencies[0].id)


class CurrencySelect(ui.Select[DiaryView]):
    def __init__(self, currencies: list[Currency], current: str) -> None:
        super().__init__(
            options=[
                ui.SelectOption(
                    label=GI_CURRENCY_NAMES.get(c.id, c.name),
                    value=c.id,
                    emoji=CURRENCY_EMOJIS.get(c.id),
                    default=c.id == current,
                )
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
