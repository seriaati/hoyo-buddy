from __future__ import annotations

from typing import TYPE_CHECKING

import discord
import hakushin
import szgf

from hoyo_buddy import emojis, ui
from hoyo_buddy.db.utils import get_locale
from hoyo_buddy.draw.card_data import CARD_DATA
from hoyo_buddy.utils.misc import create_bullet_list

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction, User


def replace_emojis(text: str) -> str:
    for name, emoji in emojis.ZZZ_STAT_EMOJIS.items():
        text = text.replace(f"<{name}>", emoji)
    for name, emoji in emojis.ZZZ_GUIDE_SKILL_TYPE_EMOJIS.items():
        text = text.replace(f"<{name}>", emoji)
    return text


def build_extra_sections(
    sections: list[szgf.Section],
) -> list[ui.TextDisplay | discord.ui.Separator]:
    if not sections:
        return []

    items = []
    items.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large))
    for section in sections:
        text = ui.TextDisplay(
            f"## {replace_emojis(section.title)}\n{replace_emojis(section.description)}"
        )
        items.extend((text, discord.ui.Separator()))
    items.pop()  # Remove last separator
    return items


def set_guide_color(guide: szgf.ParsedGuide, container: ui.Container) -> None:
    card_data = CARD_DATA.zzz.get(str(guide.character.id))
    if card_data is not None:
        container.accent_color = int(card_data.color.lstrip("#"), 16)


def get_rarity_emoji(guide: szgf.ParsedGuide) -> str:
    rarity = guide.character.rarity
    if rarity == 5:
        return emojis.ZZZ_RANK_S
    return emojis.ZZZ_RANK_A


class ContainerButton(ui.Button):
    def __init__(self, label: str, container: ui.Container, guide: szgf.ParsedGuide) -> None:
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.container = container
        self.guide = guide

    async def callback(self, i: Interaction) -> None:
        view = ui.LayoutView(author=i.user, locale=await get_locale(i))
        set_guide_color(self.guide, self.container)
        view.add_item(self.container)
        view.add_item(ui.ActionRow(ZZZBuildMenuButton(self.guide)))
        await i.response.edit_message(view=view)


class ZZZBuildDiscContainer(ui.Container):
    def __init__(self, guide: szgf.ParsedGuide) -> None:
        discs = guide.discs
        if discs is None:
            discs = szgf.DiscSection(four_pieces=[], two_pieces=[], extra_sections=[])

        super().__init__(
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=guide.character.banner or "")),
            ui.TextDisplay(
                f"# {get_rarity_emoji(guide)} {guide.character.name} | {emojis.ZZZ_DISC_ICON} Drive Disc Set(s)"
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            ui.TextDisplay("## 4-Pc Drive Disc Sets"),
            *self.build_sets(discs.four_pieces),
            discord.ui.Separator(spacing=discord.SeparatorSpacing.large),
            ui.TextDisplay("## 2-Pc Drive Disc Sets"),
            *self.build_sets(discs.two_pieces),
            *build_extra_sections(discs.extra_sections),
        )

    def build_sets(
        self, pieces: list[szgf.DiscSetSection]
    ) -> list[ui.TextDisplay | discord.ui.Separator]:
        items = []
        if not pieces:
            return [ui.TextDisplay("No drive disc set information available.")]

        for disc_set in pieces:
            if disc_set.icon is None:
                item = ui.TextDisplay(
                    f"### {disc_set.name}\n{replace_emojis(disc_set.description)}"
                )
            else:
                item = ui.Section(
                    ui.TextDisplay(f"### {disc_set.name}\n{replace_emojis(disc_set.description)}"),
                    accessory=discord.ui.Thumbnail(media=disc_set.icon),
                )
            items.extend((item, discord.ui.Separator(spacing=discord.SeparatorSpacing.large)))
        items.pop()  # Remove last separator
        return items


class ZZZBuildWeaponContainer(ui.Container):
    def __init__(self, guide: szgf.ParsedGuide) -> None:
        weapons = guide.weapons
        super().__init__(
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=guide.character.banner or "")),
            ui.TextDisplay(
                f"# {get_rarity_emoji(guide)} {guide.character.name} | {emojis.ZZZ_WENGINE_ICON} W-Engines"
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            *self.build_weapons(weapons),
        )

    def build_weapons(
        self, sections: Sequence[szgf.ParsedWeaponSection | szgf.WeaponSection]
    ) -> list[ui.TextDisplay | discord.ui.Separator]:
        if not sections:
            return [ui.TextDisplay("No weapon information available.")]

        items = []
        for section in sections:
            if section.icon is not None:
                item = ui.Section(
                    ui.TextDisplay(f"## {section.name}\n{replace_emojis(section.description)}"),
                    accessory=discord.ui.Thumbnail(media=section.icon),
                )
            else:
                item = ui.TextDisplay(f"## {section.name}\n{replace_emojis(section.description)}")
            items.extend((item, discord.ui.Separator(spacing=discord.SeparatorSpacing.large)))
        items.pop()  # Remove last separator
        return items


class ZZZBuildSkillMindscapeContainer(ui.Container):
    def __init__(self, guide: szgf.ParsedGuide) -> None:
        skill_priority = guide.skill_priority
        mindscapes = guide.mindscapes

        super().__init__(
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=guide.character.banner or "")),
            ui.TextDisplay(
                f"# {get_rarity_emoji(guide)} {guide.character.name} | {emojis.ZZZ_SKILL_TYPE_CORE} Ability & Mindscape Priority"
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            ui.TextDisplay("## Ability Priority"),
            *self.build_skill_priority(skill_priority),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
            ui.TextDisplay("## Mindscapes"),
            *self.build_minscapes(mindscapes),
        )

    def build_skill_priority(
        self, skill_priority: szgf.SkillPrioritySection | None
    ) -> list[ui.TextDisplay]:
        if skill_priority is None:
            return [ui.TextDisplay("No skill priority information available.")]

        priority_strs = []
        for priority_group in skill_priority.priorities:
            priority_level_strs = []
            for skill_type in priority_group:
                emoji = emojis.ZZZ_GUIDE_SKILL_TYPE_EMOJIS.get(skill_type.value, "")
                priority_level_strs.append(f"{emoji} {skill_type.value.capitalize()}")
            priority_strs.append(" = ".join(priority_level_strs).strip())

        texts = [ui.TextDisplay(create_bullet_list(priority_strs, prefix="1. "))]
        if skill_priority.description:
            texts.append(ui.TextDisplay(replace_emojis(skill_priority.description)))
        return texts

    def build_minscapes(self, mindscapes: list[szgf.MindscapeSection]) -> list[ui.TextDisplay]:
        if not mindscapes:
            return [ui.TextDisplay("No mindscape information available.")]

        items = []
        for mindscape in mindscapes:
            text = ui.TextDisplay(f"### M{mindscape.num}\n{replace_emojis(mindscape.description)}")
            items.extend((text, discord.ui.Separator(visible=False)))
        return items


class ZZZBuildSkillContainer(ui.Container):
    def __init__(self, guide: szgf.ParsedGuide) -> None:
        skills = guide.skills
        super().__init__(
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=guide.character.banner or "")),
            ui.TextDisplay(f"# {get_rarity_emoji(guide)} {guide.character.name} | Gameplay Guide"),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            *self.build_skills(skills),
        )

    def build_skills(
        self, skills: Sequence[szgf.Skill]
    ) -> list[ui.TextDisplay | discord.ui.Separator]:
        if not skills:
            return [ui.TextDisplay("No skill information available.")]

        items = []
        for skill in skills:
            if skill.demo is not None:
                text = ui.Section(
                    ui.TextDisplay(
                        f"## {skill.title}\n{replace_emojis(skill.description)}\n\n{replace_emojis(skill.explanation)}"
                    ),
                    accessory=discord.ui.Thumbnail(media=skill.demo),
                )
            else:
                text = ui.TextDisplay(
                    f"## {skill.title}\n{replace_emojis(skill.description)}\n\n{replace_emojis(skill.explanation)}"
                )
            items.extend(
                (text, discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large))
            )
        items.pop()  # Remove last separator
        return items


class ZZZBuildTeamContainer(ui.Container):
    def __init__(self, guide: szgf.ParsedGuide) -> None:
        team = guide.team
        if team is None:
            team = szgf.ParsedTeamSection(teams=[], extra_sections=[])
        super().__init__(
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=guide.character.banner or "")),
            ui.TextDisplay(f"# {get_rarity_emoji(guide)} {guide.character.name} | Teams"),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            *self.build_teams(team),
            *build_extra_sections(team.extra_sections),
        )

    def build_teams(
        self, team_section: szgf.ParsedTeamSection
    ) -> list[ui.TextDisplay | discord.ui.Separator]:
        if not team_section.teams:
            return [ui.TextDisplay("No team information available.")]

        items = []
        for team in team_section.teams:
            members = ", ".join(member.name for member in team.characters)
            text = ui.TextDisplay(f"## {team.name}\nMembers: {members}\n\n{team.description or ''}")
            items.extend(
                (text, discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small))
            )
        items.pop()  # Remove last separator
        return items


class ZZZBuildStatsContainer(ui.Container):
    def __init__(self, guide: szgf.ParsedGuide) -> None:
        stat = guide.stat
        if stat is None:
            stat = szgf.StatSection(
                main_stats=[], sub_stats="", baseline_stats="", extra_sections=[]
            )

        super().__init__(
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=guide.character.banner or "")),
            ui.TextDisplay(
                f"# {get_rarity_emoji(guide)} {guide.character.name} | Recommended Stats"
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            self.build_main_stats(stat.main_stats),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            self.build_sub_stats(stat.sub_stats),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            self.build_baseline_stats(stat.baseline_stats),
            *build_extra_sections(stat.extra_sections),
        )

    def build_main_stats(self, main_stats: list[szgf.DiscMainStatSection]) -> ui.TextDisplay:
        stats_str = "\n".join(
            f"{emojis.ZZZ_DISC_ICON} {stat.pos}: {replace_emojis(stat.stat_priority)}"
            for stat in main_stats
        )
        return ui.TextDisplay(f"### Main Stats Priority\n{stats_str}")

    def build_sub_stats(self, sub_stats: str) -> ui.TextDisplay:
        return ui.TextDisplay(f"### Sub Stats Priority\n{replace_emojis(sub_stats)}")

    def build_baseline_stats(self, baseline_stats: str) -> ui.TextDisplay:
        return ui.TextDisplay(f"### Baseline Stats\n{replace_emojis(baseline_stats)}")


class ZZZBuildContainer(ui.Container):
    def __init__(self, guide: szgf.ParsedGuide) -> None:
        super().__init__(
            discord.ui.MediaGallery(discord.MediaGalleryItem(media=guide.character.banner or "")),
            ui.TextDisplay(f"# {get_rarity_emoji(guide)} {guide.character.name} | Agent Guide"),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay(
                replace_emojis(
                    f"{guide.description}\n\nAuthor: {guide.author}\nLast Updated: {guide.last_updated}"
                )
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
            ui.Section(
                ui.TextDisplay(
                    f"## {emojis.ZZZ_SKILL_TYPE_EMOJIS[hakushin.enums.ZZZSkillType.CHAIN]} Agent Gameplay Guide"
                ),
                accessory=ContainerButton("View", ZZZBuildSkillContainer(guide), guide),
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
            ui.Section(
                ui.TextDisplay(f"## {emojis.ZZZ_WENGINE_ICON} Best W-Engines"),
                accessory=ContainerButton("View", ZZZBuildWeaponContainer(guide), guide),
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
            ui.Section(
                ui.TextDisplay(f"## {emojis.ZZZ_DISC_ICON} Drive Disc Sets"),
                accessory=ContainerButton("View", ZZZBuildDiscContainer(guide), guide),
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
            ui.Section(
                ui.TextDisplay(f"## {emojis.ZZZ_STAT_EMOJIS['hp']} Recommended Stats"),
                accessory=ContainerButton("View", ZZZBuildStatsContainer(guide), guide),
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
            ui.Section(
                ui.TextDisplay(f"## {emojis.ZZZ_SKILL_TYPE_CORE} Ability & Mindscape Priority"),
                accessory=ContainerButton("View", ZZZBuildSkillMindscapeContainer(guide), guide),
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
            ui.Section(
                ui.TextDisplay(f"## {emojis.ZZZ_CHARACTER_ICON} Team Building Guide"),
                accessory=ContainerButton("View", ZZZBuildTeamContainer(guide), guide),
            ),
        )
        set_guide_color(guide, self)


class ZZZBuildMenuButton(ui.Button):
    def __init__(self, guide: szgf.ParsedGuide) -> None:
        super().__init__(emoji=emojis.LEFT, style=discord.ButtonStyle.secondary)
        self.guide = guide

    async def callback(self, i: Interaction) -> None:
        view = ZZZBuildView(self.guide, author=i.user, locale=await get_locale(i))
        await i.response.edit_message(view=view)


class ContributeButton(ui.Button):
    def __init__(self) -> None:
        super().__init__(label="Contribute", url="https://github.com/seriaati/zzz-guides/")


class ZZZBuildView(ui.LayoutView):
    def __init__(self, guide: szgf.ParsedGuide, *, author: User, locale: Locale) -> None:
        super().__init__(author=author, locale=locale)
        self.add_item(ZZZBuildContainer(guide))
        self.add_item(ui.ActionRow(ContributeButton()))

    async def start(self, i: Interaction) -> None:
        self.message = await i.followup.send(view=self, wait=True)
