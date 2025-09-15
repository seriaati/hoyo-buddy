from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle, Member, User
from seria.utils import create_bullet_list

from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import GIFT_OUTLINE, LOADING, REDEEM_GIFT
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button, Label, Modal, TextInput, ToggleButton, View

if TYPE_CHECKING:
    import aiohttp
    from genshin import Game

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction


class GiftCodeModal(Modal):
    code_1: Label[TextInput] = Label(
        text=LocaleStr(key="gift_code_modal.code_input.label", num=1),
        component=TextInput(placeholder="https://hsr.hoyoverse.com/gift?code=..."),
    )
    code_2: Label[TextInput] = Label(
        text=LocaleStr(key="gift_code_modal.code_input.label", num=2),
        component=TextInput(placeholder="https://zzz.hoyoverse.com/gift?code=...", required=False),
    )
    code_3: Label[TextInput] = Label(
        text=LocaleStr(key="gift_code_modal.code_input.label", num=3),
        component=TextInput(placeholder="GENSHINGIFT", required=False),
    )
    code_4: Label[TextInput] = Label(
        text=LocaleStr(key="gift_code_modal.code_input.label", num=4),
        component=TextInput(placeholder="HSR2024", required=False),
    )
    code_5: Label[TextInput] = Label(
        text=LocaleStr(key="gift_code_modal.code_input.label", num=5),
        component=TextInput(placeholder="HOYOBUDDY", required=False),
    )


class RedeemUI(View):
    def __init__(
        self,
        account: HoyoAccount,
        available_codes: list[str],
        *,
        author: User | Member | None,
        locale: Locale,
    ) -> None:
        super().__init__(author=author, locale=locale)
        self.account = account
        self.account.client.set_lang(locale)
        self.available_codes = available_codes

        self._add_items()

    @staticmethod
    async def fetch_available_codes(client: aiohttp.ClientSession, *, game: Game) -> list[str]:
        api_url = f"https://hoyo-codes.seria.moe/codes?game={game.value}"
        async with client.get(api_url) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            return [code["code"] for code in data["codes"]]

    @property
    def start_embed(self) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            title=LocaleStr(key="redeem_codes_button.label"),
            description=LocaleStr(key="redeem_command_embed.description"),
        ).add_acc_info(self.account)

        if self.available_codes:
            embed.add_field(
                name=LocaleStr(key="redeem_cmd_available_codes"),
                value=create_bullet_list(self.available_codes),
            )
        return embed

    @property
    def cooldown_embed(self) -> DefaultEmbed:
        return DefaultEmbed(
            self.locale,
            title=LocaleStr(key="redeem_cooldown_embed.title"),
            description=LocaleStr(
                custom_str="{emoji} {desc}",
                emoji=LOADING,
                desc=LocaleStr(key="redeem_cooldown_embed.description"),
            ),
        ).add_acc_info(self.account)

    def _add_items(self) -> None:
        self.add_item(RedeemCodesButton())
        self.add_item(RedeemAllAvailableCodesButton())
        self.add_item(AutoRedeemToggle(current_toggle=self.account.auto_redeem))
        self.add_item(RedeemSuccess(current_toggle=self.account.notif_settings.redeem_success))
        self.add_item(RedeemFailure(current_toggle=self.account.notif_settings.redeem_failure))

    async def redeem_codes(self, i: Interaction, *, codes: list[str], button: Button) -> None:
        await button.set_loading_state(i, embed=self.cooldown_embed)

        embed = await self.account.client.redeem_codes(
            codes, locale=self.locale, skip_redeemed=False
        )
        if embed is None:
            return await button.unset_loading_state(i, embed=self.start_embed)
        await button.unset_loading_state(i, embed=embed)


class RedeemCodesButton(Button[RedeemUI]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="redeem_codes_button.label"),
            emoji=GIFT_OUTLINE,
            style=ButtonStyle.blurple,
        )

    async def callback(self, i: Interaction) -> None:
        modal = GiftCodeModal(title=LocaleStr(key="gift_code_modal.title"))
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)

        timed_out = await modal.wait()
        if timed_out:
            return

        codes = (
            modal.code_1.value,
            modal.code_2.value,
            modal.code_3.value,
            modal.code_4.value,
            modal.code_5.value,
        )
        # Extract codes from urls
        codes = [code.split("code=")[1] if "code=" in code else code for code in codes]
        await self.view.redeem_codes(i, codes=codes, button=self)


class AutoRedeemToggle(ToggleButton[RedeemUI]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(current_toggle, LocaleStr(key="auto_redeem_toggle.label"), row=0)

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        self.view.account.auto_redeem = self.current_toggle
        await self.view.account.save(update_fields=("auto_redeem",))


class RedeemAllAvailableCodesButton(Button[RedeemUI]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="redeem_all_available_codes_button_label"),
            style=ButtonStyle.blurple,
            emoji=REDEEM_GIFT,
        )

    async def callback(self, i: Interaction) -> None:
        await self.view.redeem_codes(i, codes=self.view.available_codes, button=self)


class RedeemSuccess(ToggleButton[RedeemUI]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(
            current_toggle, toggle_label=LocaleStr(key="redeem_success_notify_toggle_label"), row=4
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        self.view.account.notif_settings.redeem_success = self.current_toggle
        await self.view.account.notif_settings.save(update_fields=("redeem_success",))


class RedeemFailure(ToggleButton[RedeemUI]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(
            current_toggle, toggle_label=LocaleStr(key="redeem_failure_notify_toggle_label"), row=4
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        self.view.account.notif_settings.redeem_failure = self.current_toggle
        await self.view.account.notif_settings.save(update_fields=("redeem_failure",))
