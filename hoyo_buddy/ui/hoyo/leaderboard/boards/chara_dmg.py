from typing import TYPE_CHECKING

from hoyo_buddy.ui import Select, SelectOption

from ..view import LeaderboardView

if TYPE_CHECKING:
    import akasha


class CalcSelector(Select[LeaderboardView]):
    def __init__(self, user_calcs: list["akasha.UserCalc"]) -> None:
        super().__init__(
            options=[
                SelectOption(label=calc.name, value=str(calc.calculations[0].id))
                for calc in user_calcs
                if calc.calculations
            ]
        )
