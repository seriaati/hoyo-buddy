from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from hoyo_buddy import emojis, ui
from hoyo_buddy.l10n import LocaleStr

from ._common import AccountToggleButton

if TYPE_CHECKING:
    from hoyo_buddy.db.models.hoyo_account import HoyoAccount
    from hoyo_buddy.types import Interaction

    from .view import SettingsView  # noqa: F401


class MinimumMimoPointModal(ui.Modal):
    points = ui.Label(
        text=LocaleStr(key="mimo_minimum_point_label"), component=ui.TextInput(is_digit=True)
    )


class MinimumPointsButton(ui.Button["SettingsView"]):
    def __init__(self, *, current: int) -> None:
        super().__init__(style=discord.ButtonStyle.blurple, label=str(current))
        self.current = current

    async def callback(self, i: Interaction) -> None:
        modal = MinimumMimoPointModal(title=LocaleStr(key="mimo_minimum_point_modal_title"))
        modal.points.default = str(self.current)
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)

        timed_out = await modal.wait()
        if timed_out:
            return

        points = int(modal.points.value)
        self.current = points

        self.view.account.mimo_minimum_point = points
        await self.view.account.save(update_fields=("mimo_minimum_point",))

        await self.view.update(i)


class AccountSettingsContainer(ui.DefaultContainer["SettingsView"]):
    def __init__(self, *, account: HoyoAccount) -> None:
        super().__init__(
            ui.TextDisplay(
                LocaleStr(
                    custom_str="# {title}\n{desc}",
                    title=LocaleStr(key="account_settings_title"),
                    desc=LocaleStr(key="account_settings_desc"),
                )
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {emoji} {desc}",
                        emoji=emojis.LANGUAGE,
                        desc=LocaleStr(key="public_account_desc"),
                    )
                ),
                accessory=AccountToggleButton(attr="public", current=account.public),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {emoji} {desc}",
                        emoji=emojis.FREE_CANCELLATION,
                        desc=LocaleStr(key="daily_checkin_desc"),
                    )
                ),
                accessory=AccountToggleButton(attr="daily_checkin", current=account.daily_checkin),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {emoji} {desc}",
                        emoji=emojis.REDEEM_GIFT,
                        desc=LocaleStr(key="redeem_code_desc"),
                    )
                ),
                accessory=AccountToggleButton(
                    attr="auto_redeem",
                    current=account.auto_redeem,
                    disabled=not account.can_redeem_code,
                ),
            ),
        )


class MimoSettingsContainer(ui.DefaultContainer["SettingsView"]):
    def __init__(self, *, account: HoyoAccount) -> None:
        super().__init__(
            ui.TextDisplay(LocaleStr(custom_str="# {title}", title=LocaleStr(key="mimo_title"))),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {emoji} {title}\n{desc}",
                        emoji=emojis.GIFT_OUTLINE,
                        title=LocaleStr(key="mimo_auto_finish_and_claim_button_label"),
                        desc=LocaleStr(key="mimo_auto_finish_and_claim_desc"),
                    )
                ),
                accessory=AccountToggleButton(
                    attr="mimo_auto_task", current=account.mimo_auto_task
                ),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {emoji} {title}\n{desc}",
                        emoji=emojis.SHOPPING_CART,
                        title=LocaleStr(key="mimo_auto_buy_button_label"),
                        desc=LocaleStr(key="mimo_auto_buy_desc"),
                    )
                ),
                accessory=AccountToggleButton(attr="mimo_auto_buy", current=account.mimo_auto_buy),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {emoji} {title}\n{desc}",
                        emoji=emojis.PAYMENTS,
                        title=LocaleStr(key="mimo_auto_draw_button_label"),
                        desc=LocaleStr(key="mimo_auto_draw_desc"),
                    )
                ),
                accessory=AccountToggleButton(
                    attr="mimo_auto_draw", current=account.mimo_auto_draw
                ),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {emoji} {title}\n{desc}",
                        emoji=emojis.PUBLISH,
                        title=LocaleStr(key="mimo_minimum_point_label"),
                        desc=LocaleStr(key="mimo_minimum_point_desc"),
                    )
                ),
                accessory=MinimumPointsButton(current=account.mimo_minimum_point),
            ),
        )
