from typing import Any, Dict, List, Optional, Sequence, Union

import discord
import genshin
from discord.interactions import Interaction
from tortoise.exceptions import IntegrityError

from ...bot import HoyoBuddy, emojis
from ...bot.translator import Translator
from ...db.models import GAME_CONVERTER, GenshinClient, HoyoAccount, User
from ..button import Button, GoBackButton
from ..embeds import DefaultEmbed, ErrorEmbed
from ..modal import Modal
from ..select import Select
from ..view import View


class AccountManager(View):
    def __init__(
        self,
        *,
        author: Union[discord.Member, discord.User],
        locale: discord.Locale,
        translator: Translator,
        user: User,
    ):
        super().__init__(author=author, locale=locale, translator=translator)
        self.user = user
        self.locale = locale

    async def start(self) -> None:
        if self.user.accounts:
            self.selected_account = self.user.accounts[0]
            self.add_item(AccountSelector(await self.get_account_options()))
            self.add_item(AddAccount())
            self.add_item(EditNickname())
            self.add_item(DeleteAccount())
        else:
            self.selected_account = None
            self.add_item(AddAccount())

    def get_account_embed(self) -> DefaultEmbed:
        account = self.selected_account
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title="Account Manager",
            description="You don't have any accounts yet.",
        )
        if account is None:
            return embed

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=str(account),
            translate_title=False,
        )
        embed.add_field(name="Game", value=account.game.value, inline=False)
        embed.add_field(
            name="Server",
            value=account.server,
            inline=False,
        )
        if account.nickname:
            embed.add_field(
                name="Username",
                value=account.username,
                translate_value=False,
                inline=False,
            )
        return embed

    async def get_account_options(self) -> List[discord.SelectOption]:
        return [
            discord.SelectOption(
                label=str(account),
                value=f"{account.uid}_{account.game.value}",
                emoji=emojis.get_game_emoji(account.game),
                default=account == self.selected_account,
            )
            for account in await self.user.accounts.all()
        ]

    async def refresh(self, i: discord.Interaction[HoyoBuddy], *, soft: bool) -> Any:
        if not soft:
            user = await User.get(id=self.user.id).prefetch_related("accounts")
            view = AccountManager(
                author=self.author,
                locale=self.locale,
                translator=self.translator,
                user=user,
            )
            await view.start()
            await self.absolute_edit(i, embed=view.get_account_embed(), view=view)
            view.message = await i.original_response()
        else:
            account_selector = self.get_item("account_selector")
            if isinstance(account_selector, Select):
                account_selector.options = await self.get_account_options()
            await self.absolute_edit(i, embed=self.get_account_embed(), view=self)


class AccountSelector(Select):
    def __init__(self, options: List[discord.SelectOption]):
        options[0].default = True
        super().__init__(
            custom_id="account_selector",
            options=options,
        )

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        uid, game = self.values[0].split("_")
        selected_account = discord.utils.get(
            await self.view.user.accounts.all(), uid=int(uid), game__value=game
        )
        if selected_account is None:
            raise ValueError("Invalid account selected")

        self.view.selected_account = selected_account
        await self.view.refresh(i, soft=True)


class DeleteAccountContinue(Button):
    def __init__(self):
        super().__init__(
            custom_id="delete_account_continue",
            label="Continue",
            emoji=emojis.FORWARD,
            style=discord.ButtonStyle.primary,
        )

    async def callback(self, i: Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        await self.view.refresh(i, soft=False)


class DeleteAccount(Button):
    def __init__(self):
        super().__init__(
            custom_id="delete_account",
            style=discord.ButtonStyle.danger,
            emoji=emojis.DELETE,
            label="Delete selected account",
            row=2,
        )

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        account = self.view.selected_account
        if account is None:
            raise ValueError("No account selected")
        await account.delete()

        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title="Account deleted",
            description="{account} has been deleted.",
            account=str(account),
        )
        self.view.clear_items()
        self.view.add_item(DeleteAccountContinue())
        await i.response.edit_message(embed=embed, view=self.view)


class NicknameModal(Modal):
    nickname = discord.ui.TextInput(
        label="Nickname",
        placeholder="Main account, Asia account...",
        required=False,
        style=discord.TextStyle.short,
        max_length=32,
    )

    def __init__(self, current_nickname: Optional[str] = None):
        super().__init__(title="Edit nickname")
        self.nickname.default = current_nickname


class EditNickname(Button):
    def __init__(self):
        super().__init__(
            custom_id="edit_nickname",
            emoji=emojis.EDIT,
            label="Edit nickname",
        )

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        account = self.view.selected_account
        if account is None:
            raise ValueError("No account selected")

        modal = NicknameModal(account.nickname)
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        account.nickname = modal.nickname.value
        await account.save()
        await self.view.refresh(i, soft=True)


class CookiesModal(Modal):
    cookies = discord.ui.TextInput(
        label="Cookies",
        placeholder="Paste your cookies here...",
        style=discord.TextStyle.paragraph,
    )


class DevToolCookiesModal(Modal):
    ltuid_v2 = discord.ui.TextInput(label="ltuid_v2")
    ltoken_v2 = discord.ui.TextInput(label="ltoken_v2")


class SelectAccountsToAdd(Select):
    def __init__(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        accounts: Sequence[genshin.models.GenshinAccount],
        cookies: str,
    ):
        options = [
            discord.SelectOption(
                label=f"[{account.uid}] {account.nickname}",
                description=f"Lv. {account.level} | {translator.translate(account.server_name, locale)}",
                value=f"{account.uid}_{account.game.value}",
                emoji=emojis.get_game_emoji(account.game),
            )
            for account in accounts
            if isinstance(account.game, genshin.Game)
        ]
        super().__init__(
            custom_id="select_accounts_to_add",
            options=options,
            max_values=len(options),
            placeholder="Select the accounts you want to add...",
        )

        self.accounts = accounts
        self.cookies = cookies

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        for value in self.values:
            uid, game = value.split("_")
            account = discord.utils.get(self.accounts, uid=int(uid), game__value=game)
            if account is None:
                raise ValueError("Invalid account selected")
            try:
                await HoyoAccount.create(
                    uid=account.uid,
                    username=account.nickname,
                    game=GAME_CONVERTER[account.game],
                    cookies=self.cookies,
                    user=self.view.user,
                    server=account.server_name,
                )
            except IntegrityError:
                pass

        self.view.user.temp_data.pop("cookies", None)
        await self.view.user.save()
        await self.view.refresh(i, soft=False)


class EnterCookies(Button):
    def __init__(self, *, dev_tools: bool = False):
        super().__init__(
            label="Enter Cookies",
            style=discord.ButtonStyle.primary,
            emoji=emojis.COOKIE,
        )
        self.dev_tools = dev_tools

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager

        if self.dev_tools:
            modal = DevToolCookiesModal(title="Enter Cookies")
        else:
            modal = CookiesModal(title="Enter Cookies")
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        if isinstance(modal, DevToolCookiesModal):
            if not all((modal.ltuid_v2.value, modal.ltoken_v2.value)):
                return
            cookies = f"ltuid_v2={modal.ltuid_v2.value.strip()}; ltoken_v2={modal.ltoken_v2.value.strip()}"
        else:
            if modal.cookies.value is None:
                return
            cookies = modal.cookies.value

        await self.set_loading_state(i)
        client = GenshinClient(cookies)
        client.set_lang(self.view.locale)
        try:
            game_accounts = await client.get_game_accounts()
        except genshin.InvalidCookies:
            await self.unset_loading_state(i)
            embed = ErrorEmbed(
                self.view.locale,
                self.view.translator,
                title="Invalid Cookies",
                description="Try again with other methods, if none of them work, contact [Support](https://discord.gg/ryfamUykRw)",
            )
            await i.edit_original_response(embed=embed)
        else:
            go_back_button = GoBackButton(self.view.children, self.view.get_embed(i))
            self.view.clear_items()
            self.view.add_item(
                SelectAccountsToAdd(
                    self.view.locale,
                    self.view.translator,
                    accounts=game_accounts,
                    cookies=cookies,
                ),
                translate=False,
            )
            self.view.add_item(go_back_button)
            await i.edit_original_response(embed=None, view=self.view)


class WithJavaScript(Button):
    def __init__(self):
        super().__init__(
            label="With JavaScript (Recommended)", style=discord.ButtonStyle.primary
        )

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title="Instructions",
            description=(
                "1. Login to [HoYoLAB](https://www.hoyolab.com/home) or [Miyoushe](https://www.miyoushe.com/ys/) (for CN players)\n"
                "2. Copy the code below\n"
                "3. Click on the address bar and type `java`\n"
                "4. Paste the code and press enter\n"
                "5. Select all and copy the text that appears\n"
                "6. Click the button below and paste the text in the box\n"
            ),
        )
        embed.set_image(url="https://i.imgur.com/PxO0Wr6.gif")
        code = "script:document.write(document.cookie)"
        go_back_button = GoBackButton(self.view.children, self.view.get_embed(i))
        self.view.clear_items()
        self.view.add_item(EnterCookies())
        self.view.add_item(go_back_button)
        await i.response.edit_message(embed=embed, view=self.view)
        await i.followup.send(code)


class WithDevTools(Button):
    def __init__(self):
        super().__init__(label="With DevTools (Desktop Only)")

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title="Instructions",
            description=(
                "1. Login to [HoYoLAB](https://www.hoyolab.com/home) or [Miyoushe](https://www.miyoushe.com/ys/) (if your account is in the CN server)\n"
                "2. Open the DevTools by pressing F12 or Ctrl+Shift+I\n"
                "3. Press the >> icon on the top navigation bar\n"
                "4. Click on the `Application` tab\n"
                "5. Click on `Cookies` on the left sidebar\n"
                "6. Click on the website you're on (e.g. `https://www.hoyolab.com`)\n"
                "7. Type `ltoken` in the `Filter` box\n"
                "8. Copy the `Value` of `ltoken_v2`\n"
                "9. Type `ltuid` in the `Filter` box\n"
                "10. Copy the `Value` of `ltuid_v2`\n"
                "11. Click the button below and paste the values you copied in the corresponding boxes\n"
            ),
        )
        embed.set_image(url="https://i.imgur.com/oSljaFQ.gif")
        go_back_button = GoBackButton(self.view.children, self.view.get_embed(i))
        self.view.clear_items()
        self.view.add_item(EnterCookies(dev_tools=True))
        self.view.add_item(go_back_button)
        await i.response.edit_message(embed=embed, view=self.view)


class EmailPasswordContinueButton(Button):
    def __init__(self):
        super().__init__(
            custom_id="email_password_continue",
            label="Continue",
            emoji=emojis.FORWARD,
            style=discord.ButtonStyle.primary,
        )

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        user = self.view.user
        await user.refresh_from_db()
        cookies: Optional[Dict[str, Any]] = user.temp_data.get("cookies")
        if cookies is None:
            embed = ErrorEmbed(
                self.view.locale,
                self.view.translator,
                title="Cookies not found",
                description="Please complete the CAPTCHA before continuing.",
            )
            self.label = "Refresh"
            self.emoji = emojis.REFRESH
            return await i.response.edit_message(embed=embed, view=self.view)

        if retcode := cookies.get("retcode"):
            if str(retcode) == "-3208":
                embed = ErrorEmbed(
                    self.view.locale,
                    self.view.translator,
                    title="Invalid email or password",
                    description="Either your email or password is incorrect, please try again by pressing the back button.",
                )
                self.view.remove_item(self)
                return await i.response.edit_message(embed=embed, view=self.view)
            else:
                embed = ErrorEmbed(
                    self.view.locale,
                    self.view.translator,
                    title="Unknown error",
                    description=f"Error code: {retcode}\nMessage: {cookies.get('message')}",
                )
                return await i.response.edit_message(embed=embed, view=self.view)

        await self.set_loading_state(i)
        str_cookies = "; ".join(f"{key}={value}" for key, value in cookies.items())
        client = GenshinClient(str_cookies)
        client.set_lang(self.view.locale)
        game_accounts = await client.get_game_accounts()

        go_back_button = GoBackButton(self.view.children, self.view.get_embed(i))
        self.view.clear_items()
        self.view.add_item(
            SelectAccountsToAdd(
                self.view.locale,
                self.view.translator,
                accounts=game_accounts,
                cookies=str_cookies,
            ),
            translate=False,
        )
        self.view.add_item(go_back_button)
        await i.edit_original_response(embed=None, view=self.view)


class EmailPasswordModal(Modal):
    email = discord.ui.TextInput(label="email or username", placeholder="a@gmail.com")
    password = discord.ui.TextInput(label="password", placeholder="12345678")


class EnterEmailPassword(Button):
    def __init__(self):
        super().__init__(
            label="Enter Email and Password",
            style=discord.ButtonStyle.primary,
            emoji=emojis.PASSWORD,
        )

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager

        modal = EmailPasswordModal(title="Enter Email and Password")
        modal.translate(
            self.view.locale, i.client.translator, translate_input_placeholders=False
        )
        await i.response.send_modal(modal)
        await modal.wait()

        if modal.email.value is None or modal.password.value is None:
            return
        email = modal.email.value
        password = modal.password.value
        self.view.user.temp_data["email"] = email
        self.view.user.temp_data["password"] = password
        await self.view.user.save()

        go_back_button = GoBackButton(self.view.children, self.view.get_embed(i))
        self.view.clear_items()
        web_server_url = (
            "https://geetest-server.seriaati.xyz"
            if i.client.prod
            else "http://localhost:5000"
        )
        self.view.add_item(
            Button(
                label="Complete CAPTCHA", url=f"{web_server_url}/?user_id={i.user.id}"
            )
        )
        self.view.add_item(EmailPasswordContinueButton())
        self.view.add_item(go_back_button)
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title="Instructions",
            description=(
                f"{emojis.INFO} Note: If you don't see the `Login` button after going to the website, it's either because the Mihoyo servers are busy or you entered the wrong email or password.\n\n"
                "1. Click the `Complete CAPTCHA` button below\n"
                "2. You will be redirected to a website, click `Login`\n"
                "3. Complete the CAPTCHA\n"
                "4. After completing, click on the `Continue` button below\n"
            ),
        )
        await i.edit_original_response(embed=embed, view=self.view)


class WithEmailPassword(Button):
    def __init__(self):
        super().__init__(label="With Email and Password")

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title="Instructions",
            description=(
                f"{emojis.INFO} Note: This method is not recommended as it requires you to enter your private information, it only serves as a last resort when the other 2 methods don't work. Your email and password are not saved permanently in the database, you can refer to the [source code](https://github.com/seriaati/hoyo-buddy/blob/3bbd8a9fb42d2bb8db4426fda7d7d3ba6d86e75c/hoyo_buddy/ui/login/accounts.py#L386) if you feel unsafe.\n\n"
                "Click the button below to enter your email and password.\n"
            ),
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embed(i))
        self.view.clear_items()
        self.view.add_item(EnterEmailPassword())
        self.view.add_item(go_back_button)
        await i.response.edit_message(embed=embed, view=self.view)


class AddAccount(Button):
    def __init__(self):
        super().__init__(
            custom_id="add_account",
            emoji=emojis.ADD,
            label="Add accounts",
            style=discord.ButtonStyle.primary,
        )

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title="Adding accounts",
            description="Below are 3 ways you can add accounts; however, it is recommended to try the first one, then work your way through the others if it doesn't work.",
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embed(i))
        self.view.clear_items()
        self.view.add_item(WithJavaScript())
        self.view.add_item(WithDevTools())
        self.view.add_item(WithEmailPassword())
        self.view.add_item(go_back_button)

        await i.response.edit_message(embed=embed, view=self.view)
