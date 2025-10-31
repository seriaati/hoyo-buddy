from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale


@dataclass(kw_only=True)
class Dismissible:
    id: str

    title: LocaleStr | None = None
    description: LocaleStr
    image: str | None = None
    thumbnail: str | None = None
    footer: LocaleStr | None = None

    def to_embed(self, locale: Locale) -> DefaultEmbed:
        return (
            DefaultEmbed(
                locale,
                title=self.title or LocaleStr(key="dismissible_default_title"),
                description=self.description,
            )
            .set_image(url=self.image)
            .set_thumbnail(url=self.thumbnail)
            .set_footer(text=self.footer or LocaleStr(key="dismissible_default_footer"))
        )


BIRTHDAY_DISMISSIBLE = Dismissible(
    id="one_year_anniversary",
    title=LocaleStr(key="dismissible_one_year_anniversary_title"),
    description=LocaleStr(key="dismissible_one_year_anniversary_desc"),
    image="https://one.hb.seria.moe/preview.png",
)
M3_ART_DISMISSIBLE = Dismissible(
    id="m3_art",
    description=LocaleStr(key="dismissible_m3_art_desc"),
    image="https://img.seria.moe/kVbCOBrqEMHlQsVd.png",
)
HSR_TEMP2_DISMISSIBLE = Dismissible(
    id="hsr_temp2",
    description=LocaleStr(key="dismissible_hsr_temp2_desc"),
    image="https://img.seria.moe/HLHoTSwcXvAPHzJB.png",
)
