from typing import Any, Optional, Self

from discord import Embed as E
from discord import Locale

from ..bot.translator import Translator


class Embed(E):
    def __init__(
        self,
        locale: Locale,
        translator: Translator,
        *,
        color: Optional[int] = None,
        title: Optional[str] = None,
        url: Optional[str] = None,
        description: Optional[str] = None,
        translate_title: bool = True,
        translate_description: bool = True,
        **kwargs,
    ):
        if title and translate_title:
            title = translator.translate(title, locale, **kwargs)
        if description and translate_description:
            description = translator.translate(description, locale, **kwargs)

        super().__init__(
            color=color,
            title=title,
            url=url,
            description=description,
        )
        self.locale = locale
        self.translator = translator

    def add_field(
        self,
        *,
        name: str,
        value: str,
        inline: bool = True,
        translate_name: bool = True,
        translate_value: bool = True,
        **kwargs,
    ) -> Self:
        if translate_name:
            name = self.translator.translate(name, self.locale, **kwargs)
        if translate_value:
            value = self.translator.translate(value, self.locale, **kwargs)
        return super().add_field(name=name, value=value, inline=inline)

    def set_author(
        self,
        *,
        name: str,
        url: Optional[str] = None,
        icon_url: Optional[str] = None,
        translate: bool = True,
        **kwargs,
    ) -> Self:
        if translate:
            name = self.translator.translate(name, self.locale, **kwargs)
        return super().set_author(name=name, url=url, icon_url=icon_url)

    def set_footer(
        self,
        *,
        text: Optional[str] = None,
        icon_url: Optional[str] = None,
        translate: bool = True,
        **kwargs,
    ) -> Self:
        if text and translate:
            text = self.translator.translate(text, self.locale, **kwargs)
        return super().set_footer(text=text, icon_url=icon_url)


class DefaultEmbed(Embed):
    def __init__(
        self,
        locale: Locale,
        translator: Translator,
        *,
        title: Optional[str] = None,
        url: Optional[str] = None,
        description: Optional[str] = None,
        translate: bool = True,
        **kwargs,
    ):
        super().__init__(
            locale,
            translator,
            color=6649080,
            title=title,
            url=url,
            description=description,
            translate=translate,
            **kwargs,
        )


class ErrorEmbed(Embed):
    def __init__(
        self,
        locale: Locale,
        translator: Translator,
        *,
        title: Optional[str] = None,
        url: Optional[str] = None,
        description: Optional[str] = None,
        translate: bool = True,
        **kwargs,
    ):
        super().__init__(
            locale,
            translator,
            color=15169131,
            title=title,
            url=url,
            description=description,
            translate=translate,
            **kwargs,
        )
