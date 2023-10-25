from typing import Any, List, Optional, Sequence, Union

import discord
import genshin
from discord.interactions import Interaction

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
        if user.accounts:
            self.selected_account = user.accounts[0]
            self.add_item(AccountSelector(self.get_account_options()))
            self.add_item(EditNickname())
            self.add_item(DeleteAccount())
        else:
            self.selected_account = None
            self.add_item(AddAccount())
        self.locale = locale

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

        embed.description = None
        embed.add_field(name="Game", value=account.game.value)
        embed.add_field(
            name="Username",
            value=account.username,
            translate_value=False,
        )
        embed.add_field(
            name="UID",
            value=str(account.uid),
            translate_value=False,
        )
        if account.nickname:
            embed.add_field(
                name="Nickname",
                value=account.nickname,
                translate_value=False,
            )
        return embed

    def get_account_options(self) -> List[discord.SelectOption]:
        return [
            discord.SelectOption(
                label=account.game.name,
                value=f"{account.uid}_{account.game.value}",
            )
            for account in self.user.accounts
        ]


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
        embed = self.view.get_account_embed()
        await i.response.edit_message(embed=embed)


class DeleteAccount(Button):
    def __init__(self):
        super().__init__(
            custom_id="delete_account",
            style=discord.ButtonStyle.danger,
            emoji=emojis.DELETE,
        )

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        account = self.view.selected_account
        if account is None:
            raise ValueError("No account selected")
        await self.view.user.accounts.remove(account)
        await self.view.user.save()
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title="Account deleted",
            description="The account {account} has been deleted.",
            account=str(account),
        )
        await i.response.edit_message(embed=embed, view=None)

        await self.view.user.refresh_from_db()
        view = AccountManager(
            author=self.view.author,
            user=self.view.user,
            locale=self.view.locale,
            translator=self.view.translator,
        )
        embed = view.get_account_embed()
        await i.followup.send(embed=embed, view=view)


class NicknameModal(Modal):
    nickname = discord.ui.TextInput(
        label="Nickname", placeholder="Main account, Asia account..."
    )

    def __init__(self, current_nickname: Optional[str] = None):
        super().__init__(title="Edit nickname")
        self.nickname.default = current_nickname

    async def on_submit(self, i: discord.Interaction) -> None:
        await i.response.defer()
        self.stop()


class EditNickname(Button):
    def __init__(self):
        super().__init__(
            custom_id="edit_nickname",
            emoji=emojis.EDIT,
        )

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager
        modal = NicknameModal()
        await modal.translate(
            self.view.user.settings.locale or i.locale, i.client.translator
        )
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.nickname.value:
            account = self.view.selected_account
            if account is None:
                raise ValueError("No account selected")
            account.nickname = modal.nickname.value
            await account.save()

            embed = self.view.get_account_embed()
            await i.edit_original_response(embed=embed)


class CookiesModal(Modal):
    cookies = discord.ui.TextInput(
        label="Cookies",
        placeholder="Paste your cookies here...",
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, i: Interaction) -> None:
        await i.response.defer()
        self.stop()


class SelectAccountsToAdd(Select):
    def __init__(self, accounts: Sequence[genshin.models.GenshinAccount], cookies: str):
        super().__init__(
            custom_id="select_accounts_to_add",
            options=[
                discord.SelectOption(
                    label=f"[{account.uid}] {account.nickname}",
                    value=f"{account.uid}_{account.game.value}",
                    emoji=emojis.get_game_emoji(account.game),
                )
                for account in accounts
            ],
            max_values=len(accounts),
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
            hoyo_account, _ = await HoyoAccount.get_or_create(
                uid=account.uid,
                username=account.nickname,
                game=GAME_CONVERTER[account.game],
                cookies=self.cookies,
            )
            await self.view.user.accounts.add(hoyo_account)
        await self.view.user.save()

        await self.view.user.refresh_from_db()
        view = AccountManager(
            author=self.view.author,
            locale=self.view.locale,
            user=self.view.user,
            translator=self.view.translator,
        )
        embed = view.get_account_embed()
        await i.response.edit_message(embed=embed, view=view)


class SubmitCookies(Button):
    def __init__(self):
        super().__init__(label="Submit Cookies", style=discord.ButtonStyle.primary)

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: AccountManager

        modal = CookiesModal(title="Submit Cookies")
        await modal.translate(
            self.view.user.settings.locale or i.locale, i.client.translator
        )
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.cookies.value is None:
            return

        await self.set_loading_state(i)
        client = GenshinClient(modal.cookies.value)
        client.set_lang(self.view.user.settings.locale or i.locale)
        try:
            game_accounts = await client.get_game_accounts()
        except genshin.InvalidCookies:
            await self.unset_loading_state(i)
            embed = ErrorEmbed(
                self.view.locale,
                self.view.translator,
                title="Invalid Cookies",
                description="Try logging out and log back in again. If that doesn't work, try the other 2 methods.",
            )
            await i.edit_original_response(embed=embed)
        else:
            go_back_button = GoBackButton(self.view.children, self.view.get_embed(i))
            self.view.clear_items()
            self.view.add_item(SelectAccountsToAdd(game_accounts, modal.cookies.value))
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
