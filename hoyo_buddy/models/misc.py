from __future__ import annotations

from typing import TYPE_CHECKING

from attr import dataclass

from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    import ambr.models

    from hoyo_buddy.enums import Locale

__all__ = ("Dismissible", "FarmData", "Reward")


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


class FarmData:
    def __init__(self, domain: ambr.models.Domain) -> None:
        self.domain = domain
        self.characters: list[ambr.models.Character] = []
        self.weapons: list[ambr.models.Weapon] = []


@dataclass(kw_only=True)
class Reward:
    name: str
    amount: int
    index: int
    claimed: bool
    icon: str
