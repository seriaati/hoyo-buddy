from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.db.models import Settings
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.ui import Button

from .....enums import Game

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import ProfileView  # noqa: F401


class SetCurTempAsDefaultButton(Button["ProfileView"]):
    """Set current template as default template button."""

    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="profile_view.set_cur_temp_as_default"),
            custom_id="set_cur_temp_as_default",
            row=2,
            style=ButtonStyle.primary,
        )

    async def callback(self, i: Interaction) -> None:
        assert self.view._card_settings is not None

        game_column_map = {
            Game.GENSHIN: "gi_card_temp",
            Game.STARRAIL: "hsr_card_temp",
            Game.ZZZ: "zzz_card_temp",
        }
        column_name = game_column_map.get(self.view.game)
        if column_name is None:
            msg = f"Game {self.view.game!r} does not have a column for card template"
            raise ValueError(msg)

        await Settings.filter(user_id=i.user.id).update(
            **{column_name: self.view._card_settings.template}
        )

        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr(key="set_cur_temp_as_default.done"),
            description=LocaleStr(key="set_cur_temp_as_default.done_desc"),
        )
        await i.response.send_message(embed=embed, ephemeral=True)
