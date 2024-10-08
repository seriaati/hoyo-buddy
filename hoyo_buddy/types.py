from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, TypeAlias

import discord
import enka
import genshin

from . import models
from .bot import HoyoBuddy
from .enums import Game
from .hoyo.clients import ambr, hakushin, yatta

Challenge: TypeAlias = (
    genshin.models.StarRailChallenge
    | genshin.models.SpiralAbyss
    | genshin.models.StarRailPureFiction
    | genshin.models.StarRailAPCShadow
    | genshin.models.ImgTheaterData
    | genshin.models.ShiyuDefense
)
ChallengeWithLang: TypeAlias = (
    models.StarRailChallenge
    | models.SpiralAbyss
    | models.StarRailPureFiction
    | models.StarRailAPCShadow
    | models.ImgTheaterData
    | models.ShiyuDefense
)
ChallengeWithBuff: TypeAlias = (
    genshin.models.StarRailAPCShadow
    | genshin.models.ImgTheaterData
    | genshin.models.StarRailPureFiction
    | genshin.models.ShiyuDefense
)
Buff: TypeAlias = (
    genshin.models.TheaterBuff | genshin.models.ChallengeBuff | genshin.models.ShiyuDefenseBuff
)

Interaction: TypeAlias = discord.Interaction[HoyoBuddy]
User: TypeAlias = discord.User | discord.Member | None
Builds: TypeAlias = dict[str, list[enka.gi.Build]] | dict[str, list[enka.hsr.Build]]

ItemCategory: TypeAlias = (
    ambr.ItemCategory | yatta.ItemCategory | hakushin.ItemCategory | hakushin.ZZZItemCategory
)
AutocompleteChoices: TypeAlias = defaultdict[
    Game,
    defaultdict[ItemCategory, defaultdict[discord.Locale, list[discord.app_commands.Choice[str]]]],
]
BetaAutocompleteChoices: TypeAlias = defaultdict[
    Game, defaultdict[discord.Locale, list[discord.app_commands.Choice[str]]]
]
Tasks: TypeAlias = defaultdict[
    Game, defaultdict[ItemCategory, dict[discord.Locale, asyncio.Task[list[Any]]]]
]
