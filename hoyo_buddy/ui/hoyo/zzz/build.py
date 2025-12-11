from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from hoyo_buddy import ui

if TYPE_CHECKING:
    from collections.abc import Sequence

    import szgf


class ZZZBuildDiscContainer(ui.Container):
    def __init__(self, guide: szgf.ParsedGuide) -> None:
        discs = guide.discs
        assert discs is not None
        self.discs = discs
        super().__init__(
            ui.TextDisplay(f"# {guide.character.name} | Drive Disc Set(s)"),
            discord.ui.Separator(),
            ui.TextDisplay("## 4-Pc Drive Disc Sets"),
            *self.build_sets(self.discs.four_pieces),
            ui.TextDisplay("## 2-Pc Drive Disc Sets"),
            *self.build_sets(self.discs.two_pieces),
            *self.build_extra_sections(self.discs.extra_sections),
        )

    def build_sets(
        self, pieces: list[szgf.DiscSetSection]
    ) -> list[ui.TextDisplay | discord.ui.Separator]:
        items = []
        for disc_set in pieces:
            text = ui.TextDisplay(f"### {disc_set.name}\n{disc_set.description}")
            items.extend((text, discord.ui.Separator()))
        return items

    def build_extra_sections(
        self, sections: list[szgf.Section]
    ) -> list[ui.TextDisplay | discord.ui.Separator]:
        items = []
        for section in sections:
            text = ui.TextDisplay(f"### {section.title}\n{section.description}")
            items.extend((text, discord.ui.Separator()))
        return items


class ZZZBuildWeaponContainer(ui.Container):
    def __init__(self, guide: szgf.ParsedGuide) -> None:
        weapons = guide.weapons
        assert weapons is not None
        super().__init__(
            ui.TextDisplay(f"# {guide.character.name} | Weapons"),
            discord.ui.Separator(),
            *self.build_weapons(weapons),
        )

    def build_weapons(
        self, sections: Sequence[szgf.ParsedWeaponSection | szgf.WeaponSection]
    ) -> list[ui.TextDisplay | discord.ui.Separator]:
        items = []
        for section in sections:
            if section.icon is not None:
                item = ui.Section(
                    ui.TextDisplay(f"## {section.title}\n{section.description}"),
                    accessory=discord.ui.Thumbnail(media=section.icon),
                )
            else:
                item = ui.TextDisplay(f"## {section.title}\n{section.description}")
            items.append(item)
        return items
