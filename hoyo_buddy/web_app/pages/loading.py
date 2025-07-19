from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from hoyo_buddy.l10n import LocaleStr, translator

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale

__all__ = ("LoadingPage",)


class LoadingPage(ft.View):
    def __init__(self, *, title: LocaleStr, description: LocaleStr, locale: Locale) -> None:
        self._locale = locale

        super().__init__(
            route="/loading",
            controls=[
                ft.SafeArea(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.ProgressRing(
                                        width=16,
                                        height=16,
                                        stroke_width=2,
                                        color=ft.Colors.ON_SURFACE,
                                    ),
                                    ft.Text(translator.translate(title, locale), size=24),
                                ]
                            ),
                            ft.Text(translator.translate(description, locale)),
                        ]
                    )
                )
            ],
        )
