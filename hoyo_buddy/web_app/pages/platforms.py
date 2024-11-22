from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import flet as ft

from ...enums import Platform
from ...l10n import EnumStr, LocaleStr, translator

if TYPE_CHECKING:
    from discord import Locale

    from ..schema import Params

__all__ = ("PlatformsPage",)

PLATFORM_IMAGES: Final[dict[Platform, str]] = {
    Platform.HOYOLAB: "/images/hoyolab.webp",
    Platform.MIYOUSHE: "/images/miyoushe.webp",
}


class PlatformsPage(ft.View):
    def __init__(self, *, params: Params, locale: Locale) -> None:
        self._params = params

        self._locale = locale
        super().__init__(
            route="/platforms",
            controls=[
                ft.SafeArea(
                    ft.Column(
                        [
                            ft.Text(
                                translator.translate(
                                    LocaleStr(key="adding_accounts_title"), locale
                                ),
                                size=24,
                            ),
                            ft.Markdown(
                                translator.translate(
                                    LocaleStr(key="adding_accounts_description"), locale
                                ),
                                auto_follow_links=True,
                                auto_follow_links_target=ft.UrlTarget.BLANK.value,
                            ),
                            ft.Container(
                                ft.Row(self.platform_groups, spacing=20),
                                margin=ft.margin.only(top=20),
                            ),
                        ]
                    )
                )
            ],
        )

    @property
    def platform_groups(self) -> list[PlatformGroup]:
        return [
            PlatformGroup(params=self._params, platform=platform, locale=self._locale)
            for platform in Platform
        ]


class PlatformGroup(ft.Column):
    """A platform image and a button."""

    def __init__(self, *, params: Params, platform: Platform, locale: Locale) -> None:
        self._params = params
        self._platform = platform
        self._platform_name = translator.translate(EnumStr(platform), locale)
        super().__init__(
            controls=[self.image, self.button],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20,
        )

    @property
    def image(self) -> ft.Image:
        return ft.Image(
            src=PLATFORM_IMAGES[self._platform], tooltip=self._platform_name, width=100, height=100
        )

    @property
    def button(self) -> PlatformButton:
        return PlatformButton(
            params=self._params, platform=self._platform, label=self._platform_name
        )


class PlatformButton(ft.FilledTonalButton):
    def __init__(self, *, params: Params, platform: Platform, label: str) -> None:
        self._params = params
        self._platform = platform
        super().__init__(text=label, on_click=self.on_btn_click)

    async def on_btn_click(self, e: ft.ControlEvent) -> Any:
        page: ft.Page = e.page
        params = self._params.model_copy(update={"platform": self._platform})
        await page.go_async(f"/methods?{params.to_query_string()}")
