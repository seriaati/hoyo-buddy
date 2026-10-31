"""Render a gacha summary card from fixture data, for checking card designs without the bot.

Usage: uv run scripts/render_gacha_summary.py <gi|hsr|zzz> <character|weapon> <output.png> [locale]
"""

from __future__ import annotations

import asyncio
import datetime
import sys
from pathlib import Path
from typing import Any

# Read our args before any hoyo_buddy imports, because hoyo_buddy.config uses
# pydantic-settings with cli_parse_args=True which would hijack sys.argv.
_ARGS = sys.argv[1:]
sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiohttp
from PIL import Image

from hoyo_buddy.draw import funcs
from hoyo_buddy.draw.static import download_images
from hoyo_buddy.enums import FiftyFiftyResult, Game, Locale
from hoyo_buddy.hoyo.gacha_summary import get_item_kind
from hoyo_buddy.l10n import translator
from hoyo_buddy.models.gacha_summary import GachaRank, GachaSummary, GachaSummaryItem

W = FiftyFiftyResult.WON
L = FiftyFiftyResult.LOST
G = FiftyFiftyResult.GUARANTEED

# (item_id, name, pulls, result, date)
type ItemFixture = tuple[int, str, int, FiftyFiftyResult, str]

FIXTURES: dict[tuple[str, str], dict[str, Any]] = {
    ("gi", "character"): {
        "game": Game.GENSHIN,
        "banner_type": 301,
        "banner_name": "Character Event Wish",
        "nickname": "Lumine",
        "uid": 812345678,
        "avatar_url": "https://enka.network/ui/UI_AvatarIcon_PlayerGirl.png",
        "pity": (34, 90, 74, 3),
        "title": "50/50",
        "pulls": (862, 1284),
        "totals": (13, 104),
        "wins": (4, 7),
        "ranks": (12.4, 38.2, 51.6, 29.8),
        "items": [
            (10000089, "Furina", 74, W, "2026-10-12"),
            (10000087, "Neuvillette", 68, G, "2026-08-03"),
            (10000016, "Diluc", 88, L, "2026-07-15"),
            (10000052, "Raiden Shogun", 45, W, "2026-05-28"),
            (10000073, "Nahida", 77, W, "2026-04-02"),
            (10000060, "Yelan", 81, W, "2026-02-11"),
        ],
    },
    ("gi", "weapon"): {
        "game": Game.GENSHIN,
        "banner_type": 302,
        "banner_name": "Weapon Event Wish",
        "nickname": "Lumine",
        "uid": 812345678,
        "avatar_url": "https://enka.network/ui/UI_AvatarIcon_PlayerGirl.png",
        "pity": (12, 80, 63, 5),
        "title": "75/25",
        "pulls": (414, 1284),
        "totals": (7, 49),
        "wins": (5, 6),
        "ranks": (12.4, 33.9, 48.8, 20.7),
        "items": [
            (11509, "Mistsplitter Reforged", 61, W, "2026-10-14"),
            (14509, "Kagura's Verity", 54, G, "2026-08-20"),
            (12502, "Wolf's Gravestone", 66, L, "2026-07-02"),
            (13509, "Engulfing Lightning", 48, W, "2026-05-30"),
            (15508, "Aqua Simulacra", 58, W, "2026-03-18"),
            (13501, "Staff of Homa", 63, W, "2026-01-09"),
        ],
    },
    ("hsr", "character"): {
        "game": Game.STARRAIL,
        "banner_type": 11,
        "banner_name": "Character Event Warp",
        "nickname": "Stelle",
        "uid": 801234567,
        "avatar_url": "https://sr.yatta.moe/hsr/assets/UI/avatar/8002.png",
        "pity": (22, 90, 74, 6),
        "title": "50/50",
        "pulls": (731, 1106),
        "totals": (11, 89),
        "wins": (5, 8),
        "ranks": (15.7, 41.3, 47.9, 24.1),
        "items": [
            (1310, "Firefly", 78, W, "2026-10-09"),
            (1308, "Acheron", 57, G, "2026-08-21"),
            (1004, "Welt", 82, L, "2026-07-30"),
            (1303, "Ruan Mei", 70, W, "2026-06-12"),
            (1005, "Kafka", 76, W, "2026-04-24"),
            (1212, "Jingliu", 66, W, "2026-03-06"),
        ],
    },
    ("hsr", "weapon"): {
        "game": Game.STARRAIL,
        "banner_type": 12,
        "banner_name": "Light Cone Event Warp",
        "nickname": "Stelle",
        "uid": 801234567,
        "avatar_url": "https://sr.yatta.moe/hsr/assets/UI/avatar/8002.png",
        "pity": (9, 80, 66, 2),
        "title": "75/25",
        "pulls": (379, 1106),
        "totals": (6, 46),
        "wins": (4, 5),
        "ranks": (15.7, 30.2, 47.1, 21.5),
        "items": [
            (23025, "Whereabouts Should Dreams Rest", 66, W, "2026-10-10"),
            (23024, "Along the Passing Shore", 58, G, "2026-08-22"),
            (23000, "Night on the Milky Way", 71, L, "2026-07-31"),
            (23019, "Past Self in Mirror", 52, W, "2026-06-13"),
            (23006, "Patience Is All You Need", 63, W, "2026-04-25"),
            (23014, "I Shall Be My Own Sword", 60, W, "2026-03-07"),
        ],
    },
    ("zzz", "character"): {
        "game": Game.ZZZ,
        "banner_type": 2,
        "banner_name": "Exclusive Channel",
        "nickname": "Wise",
        "uid": 1300456789,
        "avatar_url": "https://static.nanoka.cc/assets/zzz/IconRoleCrop01.webp",
        "pity": (17, 90, 74, 4),
        "title": "50/50",
        "pulls": (652, 1018),
        "totals": (10, 81),
        "wins": (6, 8),
        "ranks": (18.2, 39.5, 50.8, 11.6),
        "items": [
            (1091, "Miyabi", 69, W, "2026-10-03"),
            (1221, "Yanagi", 74, W, "2026-08-14"),
            (1261, "Jane", 58, G, "2026-07-05"),
            (1141, "Lycaon", 85, L, "2026-05-22"),
            (1241, "Zhu Yuan", 72, W, "2026-04-01"),
            (1191, "Ellen", 63, W, "2026-02-19"),
        ],
    },
    ("zzz", "weapon"): {
        "game": Game.ZZZ,
        "banner_type": 3,
        "banner_name": "W-Engine Channel",
        "nickname": "Wise",
        "uid": 1300456789,
        "avatar_url": "https://static.nanoka.cc/assets/zzz/IconRoleCrop01.webp",
        "pity": (23, 80, 64, 7),
        "title": "75/25",
        "pulls": (382, 1018),
        "totals": (6, 47),
        "wins": (4, 5),
        "ranks": (18.2, 35.8, 49.6, 19.4),
        "items": [
            (14109, "Hailstorm Shrine", 57, W, "2026-10-04"),
            (14122, "Timeweaver", 61, W, "2026-08-15"),
            (14126, "Sharpened Stinger", 49, G, "2026-07-06"),
            (14102, "Steel Cushion", 70, L, "2026-05-23"),
            (14124, "Riot Suppressor Mark VI", 64, W, "2026-04-02"),
            (14119, "Deep Sea Visitor", 58, W, "2026-02-20"),
        ],
    },
}


def rank(percent: float) -> GachaRank:
    return GachaRank(rank=round(percent * 10), total=1000)


def build_summary(fixture: dict[str, Any]) -> GachaSummary:
    game: Game = fixture["game"]
    five_pity, five_max, soft_pity, four_pity = fixture["pity"]
    banner_pulls, lifetime_pulls = fixture["pulls"]
    total_five, total_four = fixture["totals"]
    wins, total_5050 = fixture["wins"]
    lifetime_rank, five_rank, four_rank, win_rank = fixture["ranks"]

    items = [
        GachaSummaryItem(
            item_id=item_id,
            name=name,
            kind=get_item_kind(game, item_id),
            pulls=pulls,
            result=result,
            time=datetime.datetime.fromisoformat(date).replace(tzinfo=datetime.UTC),
        )
        for item_id, name, pulls, result, date in fixture["items"]
    ]

    return GachaSummary(
        game=game,
        banner_type=fixture["banner_type"],
        banner_name=fixture["banner_name"],
        nickname=fixture["nickname"],
        uid=fixture["uid"],
        avatar_url=fixture["avatar_url"],
        five_star_pity=five_pity,
        five_star_max_pity=five_max,
        five_star_soft_pity=soft_pity,
        four_star_pity=four_pity,
        four_star_max_pity=10,
        win_rate_title=fixture["title"],
        guaranteed=False,
        banner_pulls=banner_pulls,
        banner_currency=banner_pulls * 160,
        lifetime_pulls=lifetime_pulls,
        lifetime_currency=lifetime_pulls * 160,
        total_five_stars=total_five,
        total_four_stars=total_four,
        avg_five_star_pulls=banner_pulls / total_five,
        avg_four_star_pulls=banner_pulls / total_four,
        fifty_fifty_wins=wins,
        fifty_fifty_total=total_5050,
        lifetime_rank=rank(lifetime_rank),
        five_star_luck_rank=rank(five_rank),
        four_star_luck_rank=rank(four_rank),
        win_rate_rank=rank(win_rank),
        latest=items[0],
        previous=items[1:],
        is_standard_ode=False,
        three_star_pity=0,
        three_star_max_pity=0,
        total_three_stars=0,
        avg_three_star_pulls=0.0,
        three_star_luck_rank=None,
    )


async def main() -> None:
    game_key, banner_kind, output = _ARGS[:3]
    locale = Locale(_ARGS[3]) if len(_ARGS) > 3 else Locale.american_english
    summary = build_summary(FIXTURES[game_key, banner_kind])
    await translator.load()

    async with aiohttp.ClientSession() as session:
        if game_key == "gi":
            await funcs.genshin.resolve_gi_gacha_summary_art(summary, session)
            card = funcs.genshin.GIGachaSummaryCard(summary, locale=locale)
        elif game_key == "hsr":
            await funcs.hsr.resolve_hsr_gacha_summary_art(summary, session)
            card = funcs.hsr.HSRGachaSummaryCard(summary, locale=locale)
        else:
            await funcs.zzz.resolve_zzz_gacha_summary_art(summary, session)
            card = funcs.zzz.ZZZGachaSummaryCard(summary, locale=locale)

        items = [summary.latest, *summary.previous] if summary.latest is not None else []
        urls = [summary.avatar_url]
        for item in items:
            urls.extend((item.art_url, item.icon_url))
        await download_images(urls, session)

    # Cards are saved as WebP, re-encode so the output matches its extension
    Image.open(card.draw()).save(output)
    print(f"Saved {output}")


if __name__ == "__main__":
    asyncio.run(main())
