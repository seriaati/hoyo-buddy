from __future__ import annotations

import asyncio
import os
import secrets
from typing import TYPE_CHECKING, Any

import flet as ft

from hoyo_buddy.l10n import LocaleStr, Translator

if TYPE_CHECKING:
    from discord import Locale

__all__ = ("LoginPage",)


class LoginPage(ft.View):
    def __init__(self, user_data: dict[str, Any] | None, *, translator: Translator, locale: Locale) -> None:
        self.user_data = user_data

        if user_data is None:
            super().__init__(
                "/login",
                [
                    ft.SafeArea(
                        ft.Container(
                            ft.FilledButton(
                                translator.translate(LocaleStr(key="login_button_label"), locale),
                                on_click=self.on_login_button_click,
                                icon=ft.icons.DISCORD,
                            ),
                            margin=ft.margin.all(10),
                        )
                    )
                ],
            )
        else:
            super().__init__(
                "/login",
                [
                    ft.SafeArea(
                        ft.Column(
                            [
                                ft.Text(translator.translate(LocaleStr(key="currently_logged_in_as"), locale), size=16),
                                ft.ListTile(
                                    leading=ft.CircleAvatar(foreground_image_src=self.get_user_avatar_url()),
                                    title=ft.Text(user_data["username"]),
                                ),
                                ft.Container(
                                    ft.Column(
                                        [
                                            ft.FilledButton(
                                                translator.translate(LocaleStr(key="continue_button_label"), locale),
                                                on_click=self.on_continue_button_click,
                                            ),
                                            ft.TextButton(
                                                translator.translate(LocaleStr(key="not_you_label"), locale),
                                                on_click=self.on_login_button_click,
                                            ),
                                        ],
                                        spacing=8,
                                    ),
                                    margin=ft.margin.only(top=8),
                                ),
                            ]
                        )
                    )
                ],
            )

    def get_user_avatar_url(self) -> str:
        assert self.user_data is not None
        user_data = self.user_data

        base_url = "https://cdn.discordapp.com"
        avatar = user_data.get("avatar")
        if avatar is None:
            migrated = user_data["discriminator"] == "0"
            index = (user_data["id"] >> 22) % 6 if migrated else user_data["discriminator"] % 5
            return f"{base_url}/embed/avatars/{index}.webp"

        if avatar.startswith("a_"):
            return f"{base_url}/avatars/{user_data['id']}/{avatar}.gif"
        return f"{base_url}/avatars/{user_data['id']}/{avatar}.webp"

    async def on_continue_button_click(self, e: ft.ControlEvent) -> None:
        assert self.user_data is not None

        page: ft.Page = e.page
        page.session.set("hb.user_id", self.user_data["id"])

        original_route = await page.client_storage.get_async("hb.original_route")
        if original_route:
            asyncio.create_task(page.client_storage.remove_async("hb.original_route"))
            await page.go_async(original_route)

    async def on_login_button_click(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        state = secrets.token_urlsafe(32)
        await page.client_storage.set_async("hb.oauth_state", state)
        redirect_url = (
            "http://localhost:8645/custom_oauth_callback"
            if os.environ["ENV"] == "dev"
            else "https://hb-app.seria.moe/custom_oauth_callback"
        )
        oauth_url = f"https://discord.com/oauth2/authorize?response_type=code&client_id={os.environ['DISCORD_CLIENT_ID']}&redirect_uri={redirect_url}&scope=identify&state={state}"
        await page.launch_url_async(oauth_url, web_window_name=ft.UrlTarget.SELF.value)
