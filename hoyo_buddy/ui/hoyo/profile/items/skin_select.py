from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db.utils import get_card_settings
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Select, SelectOption

if TYPE_CHECKING:
    from collections.abc import Sequence

    import hb_data

    from hoyo_buddy.types import Interaction

    from ..view import ProfileView
else:
    ProfileView = None

type Skin = hb_data.gi.CharacterCostume | hb_data.hsr.CharacterSkin | hb_data.zzz.CharacterSkin

DEFAULT_SKIN_ID = 0


class SkinSelect(Select[ProfileView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(
            placeholder=LocaleStr(key="profile.skin_select.placeholder"),
            options=[SelectOption(label="Placeholder", value="0")],
            disabled=True,
            custom_id="profile_skin_select",
            row=row,
        )

    def set_options(self, skins: Sequence[Skin], *, current: int) -> None:
        self.options = [
            SelectOption(
                label=LocaleStr(key="profile.skin_select.default.label"),
                value=str(DEFAULT_SKIN_ID),
                default=current == DEFAULT_SKIN_ID,
            ),
            *(
                SelectOption(
                    label=LocaleStr(custom_str=skin.name, translate=False),
                    value=str(skin.id),
                    default=current == skin.id,
                )
                for skin in skins
            ),
        ]

    async def callback(self, i: Interaction) -> None:
        await self.set_loading_state(i)

        card_settings = await get_card_settings(
            i.user.id, self.view.character_ids[0], game=self.view.game
        )
        card_settings.skin_id = int(self.values[0])
        await card_settings.save(update_fields=("skin_id",))

        await self.view.update(i, self, character=self.view.current_character)
