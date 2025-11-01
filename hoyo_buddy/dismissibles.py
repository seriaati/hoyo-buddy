from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from hoyo_buddy.db.models import User
from hoyo_buddy.db.utils import get_locale
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils.misc import is_hb_birthday

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction


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
SETTINGS_V2_DISMISSIBLE = Dismissible(
    id="settings_v2",
    description=LocaleStr(
        key="dismissible_settings_v2", image="https://img.seria.moe/YoHNGyavlcaesNof.png"
    ),
)


async def show_dismissible(i: Interaction, dismissible: Dismissible) -> None:
    user = await User.get(id=i.user.id)
    if dismissible.id in user.dismissibles:
        return

    locale = await get_locale(i)
    embed = dismissible.to_embed(locale)

    if i.response.is_done():
        await i.followup.send(embed=embed, ephemeral=True)
    else:
        await i.response.send_message(embed=embed, ephemeral=True)

    user.dismissibles.append(dismissible.id)
    user.dismissibles = list(set(user.dismissibles))
    await user.save(update_fields=("dismissibles",))


async def show_anniversary_dismissible(i: Interaction) -> bool:
    if is_hb_birthday():
        await show_dismissible(i, BIRTHDAY_DISMISSIBLE)
        return True
    return False
