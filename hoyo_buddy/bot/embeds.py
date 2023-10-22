from typing import Optional

from discord import Embed as E
from discord import Locale

from .translator import Translator


class Embed(E):
    def __init__(
        self,
        *,
        color: Optional[int] = None,
        title: Optional[str] = None,
        url: Optional[str] = None,
        description: Optional[str] = None,
    ):
        super().__init__(
            color=color,
            title=title,
            url=url,
            description=description,
        )

    async def translate(
        self,
        locale: Locale,
        translator: Translator,
        *,
        translate_title: bool = True,
        translate_description: bool = True,
        translate_footer_text: bool = True,
        translate_author_name: bool = True,
        translate_field_names: bool = True,
        translate_field_values: bool = True,
        **kwargs,
    ) -> None:
        if self.title and translate_title:
            self.title = await translator.translate(self.title, locale, **kwargs)
        if self.description and translate_description:
            self.description = await translator.translate(
                self.description, locale, **kwargs
            )
        if self.footer.text and translate_footer_text:
            self.footer.text = await translator.translate(
                self.footer.text, locale, **kwargs
            )
        if self.author.name and translate_author_name:
            self.author.name = await translator.translate(
                self.author.name, locale, **kwargs
            )
        for field in self.fields:
            if field.name and translate_field_names:
                field.name = await translator.translate(field.name, locale, **kwargs)
            if field.value and translate_field_values:
                field.value = await translator.translate(field.value, locale, **kwargs)


class DefaultEmbed(Embed):
    def __init__(
        self,
        *,
        title: Optional[str] = None,
        url: Optional[str] = None,
        description: Optional[str] = None,
    ):
        super().__init__(
            color=0x15576945,
            title=title,
            url=url,
            description=description,
        )
