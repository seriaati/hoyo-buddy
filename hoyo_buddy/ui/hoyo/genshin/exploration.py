from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from seria.utils import create_bullet_list

from hoyo_buddy import ui
from hoyo_buddy.db import HoyoAccount, draw_locale, get_dyk
from hoyo_buddy.draw.main_funcs import draw_exploration_card
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.models import DrawInput

if TYPE_CHECKING:
    from collections.abc import Sequence

    import genshin

    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction, User


class ExplorationView(ui.View):
    def __init__(
        self, account: HoyoAccount, *, dark_mode: bool, author: User, locale: Locale
    ) -> None:
        super().__init__(author=author, locale=locale)
        self.account = account
        self.dark_mode = dark_mode
        self._genshin_user: genshin.models.PartialGenshinUserStats | None = None

    @property
    def start_embed(self) -> DefaultEmbed:
        return (
            DefaultEmbed(self.locale)
            .add_acc_info(self.account)
            .set_image(url="attachment://exploration.webp")
        )

    @property
    def genshin_user(self) -> genshin.models.PartialGenshinUserStats:
        if self._genshin_user is None:
            msg = "Genshin user is not fetched yet"
            raise ValueError(msg)
        return self._genshin_user

    async def draw_exploration_card(self, bot: HoyoBuddy) -> discord.File:
        return await draw_exploration_card(
            DrawInput(
                dark_mode=self.dark_mode,
                locale=draw_locale(self.locale, self.account),
                session=bot.session,
                filename="exploration.webp",
                executor=bot.executor,
                loop=bot.loop,
            ),
            self.genshin_user,
        )

    async def start(self, i: Interaction) -> None:
        client = self.account.client
        client.set_lang(self.locale)
        self._genshin_user = await client.get_partial_genshin_user(self.account.uid)

        self.add_item(ShowCard())
        self.add_item(ExplorationSelector(self.genshin_user.explorations))

        file_ = await self.draw_exploration_card(i.client)
        await i.followup.send(
            embed=self.start_embed, file=file_, content=await get_dyk(i), view=self
        )

        self.message = await i.original_response()


class ShowCard(ui.Button[ExplorationView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="exploration_show_card_button_label"),
            style=discord.ButtonStyle.blurple,
        )

    async def callback(self, i: Interaction) -> None:
        await self.set_loading_state(i)
        embed = self.view.start_embed
        file_ = await self.view.draw_exploration_card(i.client)
        await self.unset_loading_state(i, embed=embed, attachments=[file_])


class ExplorationSelector(ui.Select[ExplorationView]):
    def __init__(self, explorations: Sequence[genshin.models.Exploration]) -> None:
        options = [
            ui.SelectOption(label=exploration.name, value=str(exploration.id))
            for exploration in explorations
            if exploration.area_exploration_list or exploration.boss_list
        ]
        super().__init__(
            options=options, placeholder=LocaleStr(key="exploration_select_placeholder")
        )
        self.explorations = explorations

    def _get_exploration_embed(self, exploration: genshin.models.Exploration) -> DefaultEmbed:
        embed = DefaultEmbed(self.view.locale, title=exploration.name)
        if areas := exploration.area_exploration_list:
            progress_strs = [f"{a.name}: {a.explored}%" for a in areas]
            embed.add_field(
                name=LocaleStr(key="regional_exploration_degree", mi18n_game=Game.GENSHIN),
                value=create_bullet_list(progress_strs),
            )

        if bosses := exploration.boss_list:
            boss_strs = [f"{b.name}: {b.kills}" for b in bosses]
            embed.add_field(
                name=LocaleStr(key="boss_num", mi18n_game=Game.GENSHIN),
                value=create_bullet_list(boss_strs),
            )

        embed.set_thumbnail(url=exploration.icon)
        return embed

    def _get_exploration(self, value: str) -> genshin.models.Exploration:
        exploration = next((e for e in self.explorations if str(e.id) == value), None)
        if exploration is None:
            msg = f"Exploration with id {value} not found"
            raise ValueError(msg)
        return exploration

    async def callback(self, i: Interaction) -> None:
        exploration = self._get_exploration(self.values[0])
        embed = self._get_exploration_embed(exploration)
        await i.response.edit_message(embed=embed, attachments=[])
