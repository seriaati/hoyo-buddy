from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from discord.app_commands import locale_str

from hoyo_buddy.enums import Game, Platform

type CommandName = Literal[
    "build genshin",
    "challenge genshin abyss",
    "challenge genshin theater",
    "challenge hsr moc",
    "challenge hsr pure-fiction",
    "challenge hsr apc-shadow",
    "challenge zzz shiyu",
    "challenge zzz assault",
    "characters genshin",
    "characters hsr",
    "characters zzz",
    "characters honkai",
    "farm view",
    "farm add",
    "farm remove",
    "farm reminder",
    "gacha-log import",
    "gacha-log view",
    "gacha-log manage",
    "gacha-log upload",
    "check-in",
    "notes",
    "exploration",
    "redeem",
    "stats",
    "geetest",
    "events",
    "mimo",
    "web-events",
    "lb akasha",
    "lb view",
    "profile genshin",
    "profile hsr",
    "profile zzz",
    "accounts",
    "about",
    "upload",
    "settings",
    "search",
]


@dataclass(kw_only=True)
class CommandConfig:
    games: tuple[Game, ...] | None = None
    platform: Platform | None = None
    description: locale_str


COMMANDS: dict[CommandName, CommandConfig] = {
    "build genshin": CommandConfig(
        description=locale_str(
            "View a Genshin Impact character's builds and guides", key="build_cmd_genshin_desc"
        )
    ),
    "challenge genshin abyss": CommandConfig(
        games=(Game.GENSHIN,),
        description=locale_str("Generate Spiral Abyss card", key="challenge_command_abyss_desc"),
    ),
    "challenge genshin theater": CommandConfig(
        games=(Game.GENSHIN,),
        description=locale_str(
            "Generate Imaginarium Theater card", key="challenge_command_theater_desc"
        ),
    ),
    "challenge hsr moc": CommandConfig(
        games=(Game.STARRAIL,),
        description=locale_str("Generate Memory of Chaos card", key="challenge_command_moc_desc"),
    ),
    "challenge hsr pure-fiction": CommandConfig(
        games=(Game.STARRAIL,),
        description=locale_str("Generate Pure Fiction card", key="challenge_command_pf_desc"),
    ),
    "challenge hsr apc-shadow": CommandConfig(
        games=(Game.STARRAIL,),
        description=locale_str(
            "Generate Apocalyptic Shadow card", key="challenge_command_apc_shadow_desc"
        ),
    ),
    "challenge zzz shiyu": CommandConfig(
        games=(Game.ZZZ,),
        description=locale_str("Generate Shiyu Defense card", key="challenge_command_shiyu_desc"),
    ),
    "challenge zzz assault": CommandConfig(
        games=(Game.ZZZ,),
        description=locale_str(
            "Generate Deadly Assault card", key="challenge_command_assault_desc"
        ),
    ),
    "characters genshin": CommandConfig(
        games=(Game.GENSHIN,),
        description=locale_str(
            "View and filter your Genshin Impact characters", key="characters_cmd_genshin_desc"
        ),
    ),
    "characters hsr": CommandConfig(
        games=(Game.STARRAIL,),
        description=locale_str(
            "View and filter your Honkai Star Rail characters", key="characters_cmd_hsr_desc"
        ),
    ),
    "characters zzz": CommandConfig(
        games=(Game.ZZZ,),
        description=locale_str(
            "View and filter your Zenless Zone Zero agents", key="characters_cmd_zzz_desc"
        ),
    ),
    "characters honkai": CommandConfig(
        games=(Game.HONKAI,),
        description=locale_str(
            "View and filter your Honkai Impact 3rd characters", key="characters_cmd_honkai_desc"
        ),
    ),
    "farm view": CommandConfig(
        games=(Game.GENSHIN,),
        description=locale_str(
            "View farmable domains in Genshin Impact", key="farm_view_command_description"
        ),
    ),
    "farm add": CommandConfig(
        games=(Game.GENSHIN,),
        description=locale_str(
            "Add character/weapon to be notified when its materials are farmable",
            key="farm_add_command_description",
        ),
    ),
    "farm remove": CommandConfig(
        games=(Game.GENSHIN,),
        description=locale_str(
            "Remove character/weapon from farm reminder list", key="farm_remove_command_description"
        ),
    ),
    "farm reminder": CommandConfig(
        games=(Game.GENSHIN,),
        description=locale_str(
            "Notify you when materials of characters/weapons are farmable",
            key="farm_reminder_command_description",
        ),
    ),
    "gacha-log import": CommandConfig(
        games=(Game.GENSHIN, Game.ZZZ, Game.STARRAIL),
        description=locale_str(
            "Import gacha history from the game", key="gacha_import_command_description"
        ),
    ),
    "gacha-log view": CommandConfig(
        games=(Game.GENSHIN, Game.ZZZ, Game.STARRAIL),
        description=locale_str("View imported gacha logs", key="gacha_view_command_description"),
    ),
    "gacha-log manage": CommandConfig(
        games=(Game.GENSHIN, Game.ZZZ, Game.STARRAIL),
        description=locale_str(
            "Manage imported gacha logs", key="gacha_manage_command_description"
        ),
    ),
    "gacha-log upload": CommandConfig(
        games=(Game.GENSHIN, Game.ZZZ, Game.STARRAIL),
        description=locale_str(
            "Upload gacha history file from other sources to import to Hoyo Buddy",
            key="gacha_upload_command_description",
        ),
    ),
    "check-in": CommandConfig(
        description=locale_str("Game daily check-in", key="checkin_command_description")
    ),
    "notes": CommandConfig(
        games=(Game.GENSHIN, Game.STARRAIL, Game.ZZZ, Game.HONKAI),
        description=locale_str("View real-time notes", key="notes_command_description"),
    ),
    "exploration": CommandConfig(
        games=(Game.GENSHIN,),
        description=locale_str(
            "View your exploration statistics in Genshin Impact",
            key="exploration_command_description",
        ),
    ),
    "redeem": CommandConfig(
        games=(Game.GENSHIN, Game.STARRAIL, Game.ZZZ),
        platform=Platform.HOYOLAB,
        description=locale_str(
            "Redeem codes for in-game rewards", key="redeem_command_description"
        ),
    ),
    "geetest": CommandConfig(
        description=locale_str("Complete geetest verification", key="geetest_command_description")
    ),
    "stats": CommandConfig(
        description=locale_str("View game account statistics", key="stats_command_description")
    ),
    "events": CommandConfig(
        games=(Game.GENSHIN, Game.STARRAIL, Game.ZZZ),
        description=locale_str("View ongoing game events", key="events_command_description"),
    ),
    "mimo": CommandConfig(
        games=(Game.GENSHIN, Game.STARRAIL, Game.ZZZ),
        description=locale_str("Traveling Mimo event management", key="mimo_cmd_desc"),
    ),
    "web-events": CommandConfig(
        description=locale_str(
            "View ongoing web events and set notifier", key="web_events_cmd_desc"
        )
    ),
    "lb akasha": CommandConfig(
        games=(Game.GENSHIN,),
        description=locale_str(
            "View Genshin Impact character damage leaderboard (powered by Akasha System)",
            key="leaderboard_akasha_command_description",
        ),
    ),
    "lb view": CommandConfig(
        description=locale_str("View leaderboards", key="lb_view_command_description")
    ),
    "accounts": CommandConfig(
        description=locale_str("Manage your accounts", key="accounts_command_description")
    ),
    "about": CommandConfig(
        description=locale_str("About the bot", key="about_command_description")
    ),
    "upload": CommandConfig(
        description=locale_str(
            "Upload an image and get a link to it, which can be used in custom image in /profile",
            key="upload_cmd_desc",
        )
    ),
    "profile genshin": CommandConfig(
        games=(Game.GENSHIN,),
        description=locale_str(
            "Generate Genshin Impact character build cards and team cards",
            key="profile_command_gi_description",
        ),
    ),
    "profile hsr": CommandConfig(
        games=(Game.STARRAIL,),
        description=locale_str(
            "Generate Honkai Star Rail character build cards and team cards",
            key="profile_command_hsr_description",
        ),
    ),
    "profile zzz": CommandConfig(
        games=(Game.ZZZ,),
        description=locale_str(
            "Generate Zenless Zone Zero character build cards and team cards",
            key="profile_command_zzz_description",
        ),
    ),
    "search": CommandConfig(
        description=locale_str("Search anything game related", key="search_command_description")
    ),
    "settings": CommandConfig(
        description=locale_str("Configure your user settings", key="settings_command_description")
    ),
}
