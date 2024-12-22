from __future__ import annotations

import contextlib
import itertools
from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal, TypeAlias

import ambr
import discord
from discord.enums import Locale
from seria.utils import create_bullet_list

from hoyo_buddy import ui
from hoyo_buddy.constants import BLOCK_COLORS
from hoyo_buddy.draw.main_funcs import draw_block_list_card
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import ARTIFACT_POS_EMOJIS
from hoyo_buddy.icons import get_element_icon
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.models import DoubleBlock, DrawInput, SingleBlock

if TYPE_CHECKING:
    from discord import Locale

    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.types import Interaction, User

SynergyTeam: TypeAlias = Sequence[
    ambr.GWSynergyNormalCharacter | ambr.GWSynergyElementCharacter | ambr.GWSynergyFlexibleCharacter
]


class GIBuildView(ui.View):
    def __init__(
        self,
        character_id: str,
        guide: ambr.CharacterGuide,
        characters: Sequence[ambr.Character],
        weapons: Sequence[ambr.Weapon],
        artifact_sets: Sequence[ambr.ArtifactSet],
        *,
        dark_mode: bool,
        author: User,
        locale: Locale,
    ) -> None:
        super().__init__(author=author, locale=locale)
        self.character_id = character_id
        self.guide = guide
        self.characters = characters
        self.weapons = weapons
        self.artifact_sets = artifact_sets
        self.dark_mode = dark_mode

        if guide.aza_data is not None:
            self.add_item(PageSelector())

        if guide.gw_data is not None:
            if guide.gw_data.builds:
                self.add_item(BuildSelector(guide.gw_data))
            if guide.gw_data.synergies.teams:
                self.add_item(ShowSynergyButton(guide.gw_data.synergies.teams))
            if guide.gw_data.playstyle is not None:
                self.add_item(ShowPlaystyleButton())

    @property
    def character(self) -> ambr.Character:
        character = next((c for c in self.characters if c.id == self.character_id), None)
        if character is None:
            msg = f"No character found with id {self.character_id}"
            raise ValueError(msg)
        return character

    @property
    def start_embed(self) -> DefaultEmbed:
        character = self.character
        return DefaultEmbed(
            self.locale,
            title=LocaleStr(key="guide_title", name=character.name),
            description=LocaleStr(key="no_guide_available")
            if self.guide.aza_data is None and self.guide.gw_data is None
            else None,
        ).set_thumbnail(url=character.icon)

    def _get_use_rate_embed(self, key: str) -> DefaultEmbed:
        return (
            DefaultEmbed(self.locale, title=LocaleStr(key=key))
            .set_image(url="attachment://use_rate.png")
            .set_author(name=self.character.name, icon_url=self.character.icon)
            .set_footer(text="genshin.aza.gg")
        )

    def get_const_use_rate_embed(self) -> DefaultEmbed:
        aza_data = self.guide.aza_data
        if aza_data is None:
            msg = "No aza data"
            raise ValueError(msg)

        consts = [
            f"C{const}: {rate * 100:.2f}%" for const, rate in aza_data.constellation_usage.items()
        ]
        return (
            DefaultEmbed(
                self.locale,
                title=LocaleStr(key="abyss_stats_const_use_rate"),
                description=create_bullet_list(consts),
            )
            .set_author(name=self.character.name, icon_url=self.character.icon)
            .set_footer(text="genshin.aza.gg")
        )

    def get_teammate_use_rate_embed(self) -> DefaultEmbed:
        return self._get_use_rate_embed("abyss_stats_teammate_use_rate")

    def get_weapon_use_rate_embed(self) -> DefaultEmbed:
        return self._get_use_rate_embed("abyss_stats_weapon_use_rate")

    def get_artifact_use_rate_embed(self) -> DefaultEmbed:
        return self._get_use_rate_embed("abyss_stats_artifact_use_rate")

    async def draw_use_rate_image(
        self,
        items: Sequence[ambr.AzaBestItem],
        bot: HoyoBuddy,
        *,
        type_: Literal["character", "weapon"],
    ) -> discord.File | None:
        blocks: list[SingleBlock] = []

        for item in items:
            if type_ == "character":
                ambr_item = next((c for c in self.characters if c.id == str(item.id)), None)
            else:
                ambr_item = next((w for w in self.weapons if w.id == item.id), None)

            if ambr_item is None:
                continue

            blocks.append(
                SingleBlock(
                    icon=ambr_item.icon,
                    bg_color=BLOCK_COLORS[self.dark_mode][ambr_item.rarity],
                    bottom_text=f"{item.value * 100:.2f}%",
                )
            )

        if not blocks:
            return None

        chunked_blocks = itertools.batched(blocks, 4)
        return await draw_block_list_card(
            DrawInput(
                dark_mode=self.dark_mode,
                locale=self.locale,
                session=bot.session,
                executor=bot.executor,
                loop=bot.loop,
                filename="use_rate.png",
            ),
            [list(chunk) for chunk in chunked_blocks],
        )

    async def draw_artifact_set_use_rate_image(
        self, best_sets: Sequence[ambr.AzaBestArtifactSets], bot: HoyoBuddy
    ) -> discord.File:
        blocks: list[SingleBlock | DoubleBlock] = []

        for sets in best_sets:
            is_double = len(sets.sets) == 2
            if is_double:
                set1 = sets.sets[0]
                ambr_set1 = next((s for s in self.artifact_sets if s.id == set1.id), None)
                if ambr_set1 is None:
                    continue

                set2 = sets.sets[1]
                ambr_set2 = next((s for s in self.artifact_sets if s.id == set2.id), None)
                if ambr_set2 is None:
                    continue

                block = DoubleBlock(
                    icon1=ambr_set1.icon,
                    icon2=ambr_set2.icon,
                    bg_color=BLOCK_COLORS[self.dark_mode][1],
                    flair_text1=str(set1.num),
                    flair_text2=str(set2.num),
                    bottom_text=f"{sets.value * 100:.1f}%",
                )
            else:
                set_ = sets.sets[0]
                ambr_set = next((s for s in self.artifact_sets if s.id == set_.id), None)
                if ambr_set is None:
                    continue

                block = SingleBlock(
                    icon=ambr_set.icon,
                    bg_color=BLOCK_COLORS[self.dark_mode][1],
                    flair_text=str(set_.num),
                    bottom_text=f"{sets.value * 100:.1f}%",
                )

            blocks.append(block)

        chunked_blocks = itertools.batched(blocks, 4)
        return await draw_block_list_card(
            DrawInput(
                dark_mode=self.dark_mode,
                locale=self.locale,
                session=bot.session,
                executor=bot.executor,
                loop=bot.loop,
                filename="use_rate.png",
            ),
            [list(chunk) for chunk in chunked_blocks],
        )

    async def draw_synergy_teams_image(
        self, teams: Sequence[SynergyTeam], bot: HoyoBuddy
    ) -> discord.File:
        block_lists: list[list[SingleBlock]] = []

        for team in teams:
            blocks: list[SingleBlock] = []
            for char in team:
                if isinstance(char, ambr.GWSynergyNormalCharacter):
                    ambr_char = next((c for c in self.characters if c.id == str(char.id)), None)
                    if ambr_char is None:
                        continue
                    blocks.append(
                        SingleBlock(
                            icon=ambr_char.icon,
                            bg_color=BLOCK_COLORS[self.dark_mode][ambr_char.rarity],
                        )
                    )
                elif isinstance(char, ambr.GWSynergyElementCharacter):
                    icon = get_element_icon(char.element)
                    blocks.append(
                        SingleBlock(
                            icon=icon, bg_color=BLOCK_COLORS[self.dark_mode][1], icon_size=102
                        )
                    )
                else:
                    blocks.append(
                        SingleBlock(
                            icon="https://img.seria.moe/atJGEHUTsBlxYDBR.png",
                            bg_color=BLOCK_COLORS[self.dark_mode][1],
                        )
                    )

            block_lists.append(blocks)

        return await draw_block_list_card(
            DrawInput(
                dark_mode=self.dark_mode,
                locale=self.locale,
                session=bot.session,
                executor=bot.executor,
                loop=bot.loop,
                filename="synergy_team.png",
            ),
            block_lists,
        )

    def get_gw_build_embed(self, build: ambr.GWBuild) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale, title=build.title)
        embed.set_footer(text=f"{build.credits}\nGenshin Wizard")

        for info in build.info:
            if info.value is None:
                continue

            value = info.value.replace("|", "\n")
            for pos, emoji in ARTIFACT_POS_EMOJIS.items():
                value = value.replace(f"<{pos}>", emoji)
            embed.add_field(name=info.name, value=value, inline=False)

        embed.set_author(name=self.character.name, icon_url=self.character.icon)
        return embed

    def get_playstyle_embed(self, guide: ambr.CharacterGuide) -> DefaultEmbed:
        assert guide.gw_data is not None
        assert guide.gw_data.playstyle is not None

        playstyle = guide.gw_data.playstyle
        embed = DefaultEmbed(self.locale, title=playstyle.title, description=playstyle.description)
        embed.set_footer(text=f"{playstyle.credits}\nGenshin Wizard")
        embed.set_author(name=self.character.name, icon_url=self.character.icon)
        return embed

    def get_synergy_embed(self) -> DefaultEmbed:
        assert self.guide.gw_data is not None
        synergy = self.guide.gw_data.synergies
        embed = DefaultEmbed(self.locale, title=synergy.title)
        embed.set_footer(text=f"{synergy.credits}\nGenshin Wizard")
        embed.set_image(url="attachment://synergy_team.png")
        embed.set_author(name=self.character.name, icon_url=self.character.icon)

        if synergy.info:
            embed.description = synergy.info[0].value
        return embed

    async def start(self, i: Interaction) -> None:
        await i.followup.send(embed=self.start_embed, view=self)
        self.message = await i.original_response()


class PageSelector(ui.Select[GIBuildView]):
    def __init__(self) -> None:
        self.pages = (
            "abyss_stats_const_use_rate",
            "abyss_stats_teammate_use_rate",
            "abyss_stats_weapon_use_rate",
            "abyss_stats_artifact_use_rate",
        )
        super().__init__(
            options=[ui.SelectOption(label=LocaleStr(key=key), value=key) for key in self.pages],
            placeholder=LocaleStr(key="search.agent_page.placeholder"),
            custom_id="page_selector",
        )

    async def callback(self, i: Interaction) -> None:
        await self.set_loading_state(i)

        file_ = None
        page = self.values[0]
        aza_data = self.view.guide.aza_data
        assert aza_data is not None

        if page == "abyss_stats_const_use_rate":
            embed = self.view.get_const_use_rate_embed()

        elif page == "abyss_stats_teammate_use_rate":
            embed = self.view.get_teammate_use_rate_embed()
            characters = list(aza_data.best_characters.values())
            characters.sort(key=lambda x: x.value, reverse=True)
            file_ = await self.view.draw_use_rate_image(
                characters[:16], i.client, type_="character"
            )

        elif page == "abyss_stats_weapon_use_rate":
            embed = self.view.get_weapon_use_rate_embed()
            weapons = list(aza_data.best_weapons.values())
            weapons.sort(key=lambda x: x.value, reverse=True)
            file_ = await self.view.draw_use_rate_image(weapons[:16], i.client, type_="weapon")

        else:
            embed = self.view.get_artifact_use_rate_embed()
            artifact_sets = aza_data.best_artifact_sets
            artifact_sets.sort(key=lambda x: x.value, reverse=True)
            file_ = await self.view.draw_artifact_set_use_rate_image(artifact_sets[:16], i.client)

        self.update_options_defaults()
        with contextlib.suppress(ValueError):
            build_selector: BuildSelector = self.view.get_item("build_selector")
            build_selector.reset_options_defaults()

        await self.unset_loading_state(
            i, embed=embed, attachments=[file_] if file_ is not None else []
        )


class BuildSelector(ui.Select[GIBuildView]):
    def __init__(self, gw_data: ambr.GWData) -> None:
        options = [
            ui.SelectOption(label=build.title, value=build.title) for build in gw_data.builds
        ]
        super().__init__(
            options=options,
            placeholder=LocaleStr(key="profile.build.select.placeholder"),
            custom_id="build_selector",
        )
        self.builds = gw_data.builds

    async def callback(self, i: Interaction) -> None:
        build = next((b for b in self.builds if b.title == self.values[0]), None)
        if build is None:
            return

        self.update_options_defaults()
        with contextlib.suppress(ValueError):
            page_selector: PageSelector = self.view.get_item("page_selector")
            page_selector.reset_options_defaults()

        embed = self.view.get_gw_build_embed(build)
        await i.response.edit_message(embed=embed, attachments=[], view=self.view)


class ShowPlaystyleButton(ui.Button[GIBuildView]):
    def __init__(self) -> None:
        super().__init__(
            style=discord.ButtonStyle.blurple, label=LocaleStr(key="show_playstyle_button_label")
        )

    async def callback(self, i: Interaction) -> None:
        with contextlib.suppress(ValueError):
            page_selector: PageSelector = self.view.get_item("page_selector")
            page_selector.reset_options_defaults()
            build_selector: BuildSelector = self.view.get_item("build_selector")
            build_selector.reset_options_defaults()

        guide = self.view.guide
        embed = self.view.get_playstyle_embed(guide)
        await i.response.edit_message(embed=embed, attachments=[], view=self.view)


class ShowSynergyButton(ui.Button[GIBuildView]):
    def __init__(self, teams: Sequence[SynergyTeam]) -> None:
        super().__init__(
            style=discord.ButtonStyle.blurple, label=LocaleStr(key="show_synergy_button_label")
        )
        self.teams = teams

    async def callback(self, i: Interaction) -> None:
        await self.set_loading_state(i)
        embed = self.view.get_synergy_embed()
        file_ = await self.view.draw_synergy_teams_image(self.teams, i.client)
        await self.unset_loading_state(i, embed=embed, attachments=[file_])
