from __future__ import annotations

from typing import TYPE_CHECKING, Any

import genshin

from ...constants import GEETEST_SERVERS
from ...db.models import HoyoAccount, User, get_dyk
from ...embeds import DefaultEmbed
from ...emojis import get_game_emoji
from ...enums import GeetestNotifyType, Platform
from ...exceptions import NoGameAccountsError, TryOtherMethodError
from ...l10n import EnumStr, LocaleStr, Translator
from ...models import LoginNotifPayload
from .. import SelectOption
from ..components import Button, GoBackButton, View
from .items.acc_select import AccountSelect
from .items.acc_settings import AccountPublicToggle, AutoCheckinToggle, AutoRedeemToggle
from .items.add_acc_btn import AddAccountButton
from .items.add_acc_select import AddAccountSelect
from .items.del_acc_btn import DeleteAccountButton
from .items.edit_nickname_btn import EditNicknameButton
from .items.enter_email_pswd import EnterEmailVerificationCode
from .items.enter_mobile import EnterVerificationCode

if TYPE_CHECKING:
    from collections.abc import Sequence

    import discord

    from ...types import Interaction


class AccountManager(View):
    def __init__(
        self,
        *,
        author: discord.User | discord.Member | None,
        locale: discord.Locale,
        translator: Translator,
        user: User,
        accounts: Sequence[HoyoAccount],
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.user = user
        self.locale = locale
        self.accounts = accounts
        self.selected_account: HoyoAccount | None = None

    @property
    def _acc_embed(self) -> DefaultEmbed:
        account = self.selected_account

        if account is None:
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=LocaleStr(key="account_manager_title"),
                description=LocaleStr(key="account_manager_no_accounts_description"),
            )
            return embed

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=str(account),
        )
        embed.add_field(
            name=LocaleStr(key="search_command_game_param_name"),
            value=EnumStr(account.game),
        )
        if account.nickname:
            embed.add_field(
                name=LocaleStr(key="account_username"),
                value=account.username,
            )
        embed.set_footer(text=LocaleStr(key="account_manager_footer"))
        return embed

    def _add_items(self) -> None:
        if self.accounts:
            self.selected_account = (
                next((a for a in self.accounts if a.current), None) or self.accounts[0]
            )
            self.add_item(AccountSelect(self._get_account_options()))
            self.add_item(AddAccountButton())
            self.add_item(EditNicknameButton())
            self.add_item(DeleteAccountButton())
            self.add_item(AutoRedeemToggle(self.selected_account.auto_redeem))
            self.add_item(AutoCheckinToggle(self.selected_account.daily_checkin))
            self.add_item(AccountPublicToggle(self.selected_account.public))
        else:
            self.add_item(AddAccountButton())

    def _get_account_options(self) -> list[SelectOption]:
        return [
            SelectOption(
                label=str(account),
                value=f"{account.uid}_{account.game.value}",
                emoji=get_game_emoji(account.game),
                default=account == self.selected_account,
            )
            for account in self.accounts
        ]

    async def start(self, i: Interaction) -> None:
        self._add_items()
        embed = self._acc_embed
        await i.response.defer(ephemeral=True)
        self.message = await i.edit_original_response(
            embed=embed, view=self, content=await get_dyk(i)
        )

    async def refresh(self, i: Interaction, *, soft: bool) -> Any:
        """Refresh the account manager view.

        Args:
            i: The interaction object.
            soft: Whether to refetch account data from the database.
        """
        if not soft:
            accounts = await HoyoAccount.filter(user=self.user).all()
            view = AccountManager(
                author=self.author,
                locale=self.locale,
                translator=self.translator,
                user=self.user,
                accounts=accounts,
            )
            await view.start(i)
        else:
            assert self.selected_account is not None
            auto_redeem_toggle: AutoRedeemToggle = self.get_item("auto_redeem_toggle")
            auto_redeem_toggle.current_toggle = self.selected_account.auto_redeem
            auto_redeem_toggle.update_style()

            auto_checkin_toggle: AutoCheckinToggle = self.get_item("auto_checkin_toggle")
            auto_checkin_toggle.current_toggle = self.selected_account.daily_checkin
            auto_checkin_toggle.update_style()

            acc_public_toggle: AccountPublicToggle = self.get_item("public_account_toggle")
            acc_public_toggle.current_toggle = self.selected_account.public
            acc_public_toggle.update_style()

            await self.absolute_edit(i, embed=self._acc_embed, view=self)

    async def finish_cookie_setup(
        self, cookies: dict[str, Any], *, platform: Platform, interaction: Interaction
    ) -> None:
        if platform is Platform.HOYOLAB and ("stoken" in cookies or "stoken_v2" in cookies):
            # Get ltoken_v2 and cookie_token_v2
            cookie = await genshin.fetch_cookie_with_stoken_v2(cookies, token_types=[2, 4])
            cookies.update(cookie)

        client = genshin.Client(
            cookies,
            region=genshin.Region.OVERSEAS
            if platform is Platform.HOYOLAB
            else genshin.Region.CHINESE,
        )

        try:
            accounts = await client.get_record_cards()
        except genshin.errors.InvalidCookies as e:
            raise TryOtherMethodError from e

        if not accounts:
            raise NoGameAccountsError(platform)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr(key="select_account.embed.title"),
            description=LocaleStr(key="select_account.embed.description"),
        )

        device_id = cookies.pop("x-rpc-device_id", None)
        device_fp = cookies.pop("x-rpc-device_fp", None)

        self.clear_items()
        self.add_item(
            AddAccountSelect(
                self.locale,
                self.translator,
                accounts=accounts,
                cookies="; ".join(f"{k}={v}" for k, v in cookies.items()),
                platform=platform,
                device_id=device_id,
                device_fp=device_fp,
            )
        )

        await interaction.edit_original_response(embed=embed, view=self)

    async def prompt_user_to_solve_geetest(
        self,
        i: Interaction,
        *,
        for_code: bool,
        gt_version: int = 3,
        api_server: str = "api-na.geetest.com",
    ) -> None:
        """Prompt the user to solve CAPTCHA before sending the verification code or logging in.

        Args:
            i: The interaction object.
            for_code: Whether the CAPTCHA is triggered for sending the verification code.
            gt_version: The version of the geetest CAPTCHA (3 or 4).
            api_server: The server to request the CAPTCHA from.
            proxy_geetest: Whether to proxy the geetest CAPTCHA.
        """
        assert i.channel

        # geetest info is trasmitted through user.temp_data
        payload = LoginNotifPayload(
            user_id=i.user.id,
            guild_id=i.guild.id if i.guild is not None else None,
            channel_id=i.channel.id,
            message_id=i.message.id if i.message is not None else None,
            gt_version=gt_version,
            api_server=api_server,
        )
        url = f"{GEETEST_SERVERS[i.client.env]}/captcha?{payload.to_query_string()}&gt_type={GeetestNotifyType.LOGIN.value}"

        go_back_button = GoBackButton(self.children, self.get_embeds(i.message))
        self.clear_items()
        self.add_item(Button(label=LocaleStr(key="complete_captcha_button_label"), url=url))
        self.add_item(go_back_button)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr(key="email-geetest.embed.title")
            if for_code
            else LocaleStr(key="geetest.embed.title"),
            description=LocaleStr(key="captcha.embed.description"),
        )
        await i.edit_original_response(embed=embed, view=self)

    async def prompt_user_to_enter_email_code(
        self,
        i: Interaction,
        *,
        email: str,
        password: str,
        action_ticket: genshin.models.ActionTicket,
    ) -> None:
        """Prompt the user to enter the email verification code."""
        go_back_button = GoBackButton(self.children, self.get_embeds(i.message))
        self.clear_items()
        self.add_item(EnterEmailVerificationCode(email, password, action_ticket))
        self.add_item(go_back_button)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr(key="email-verification.embed.title"),
            description=LocaleStr(key="email-verification.embed.description"),
        )

        await i.edit_original_response(embed=embed, view=self)

    async def prompt_user_to_enter_mobile_otp(self, i: Interaction, mobile: str) -> None:
        """Prompt the user to enter the mobile OTP code.

        Args:
            i: The interaction object.
            mobile: The mobile number to send the OTP to.
        """
        go_back_button = GoBackButton(self.children, self.get_embeds(i.message))
        self.add_item(go_back_button)
        self.clear_items()
        self.add_item(EnterVerificationCode(mobile))

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr(key="add_miyoushe_acc.verification_code_sent"),
            description=LocaleStr(key="add_miyoushe_acc.verification_code_sent_description"),
        )
        await i.edit_original_response(embed=embed, view=self)
