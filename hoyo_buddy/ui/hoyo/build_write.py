from __future__ import annotations

from hoyo_buddy import ui
from hoyo_buddy.l10n import LocaleStr


class AddFieldModal(ui.Modal):
    title = ui.TextInput(label=LocaleStr(key="add_field_modal_title_label"))
    description = ui.TextInput(label=LocaleStr(key="add_field_modal_desc_label"))

    def __init__(self) -> None:
        super().__init__(title=LocaleStr(key="add_field_modal_title"))


class AddWeaponModal(ui.Modal):
    name = ui.TextInput(label=LocaleStr(key="add_weapon_modal_name_label"))

    def __init__(self) -> None:
        super().__init__(title=LocaleStr(key="add_weapon_modal_title"))


class AddTeamModal(ui.Modal):
    def __init__(self) -> None:
        super().__init__(title=LocaleStr(key="add_team_modal_title"))


class AddFourMemberTeamModal(AddTeamModal):
    name_1 = ui.TextInput(label=LocaleStr(key="add_team_modal_name_label", num=1))
    name_2 = ui.TextInput(label=LocaleStr(key="add_team_modal_name_label", num=2))
    name_3 = ui.TextInput(label=LocaleStr(key="add_team_modal_name_label", num=3))
    name_4 = ui.TextInput(label=LocaleStr(key="add_team_modal_name_label", num=4))


class AddThreeMemberTeamModal(AddTeamModal):
    name_1 = ui.TextInput(label=LocaleStr(key="add_team_modal_name_label", num=1))
    name_2 = ui.TextInput(label=LocaleStr(key="add_team_modal_name_label", num=2))
    name_3 = ui.TextInput(label=LocaleStr(key="add_team_modal_name_label", num=3))
