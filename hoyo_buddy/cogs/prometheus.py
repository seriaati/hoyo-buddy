"""
Copied from https://github.com/KT-Yeh/Genshin-Discord-Bot/blob/master/utility/prometheus.py
and https://github.com/KT-Yeh/Genshin-Discord-Bot/blob/2ff43ff5a4092afb3a8112d1aad2d48c94e223eb/cogs/prometheus/cog.py
"""

from __future__ import annotations

from typing import Final

import psutil
from discord import AutoShardedClient, Guild, Interaction, InteractionType
from discord.ext import commands, tasks
from prometheus_client import Counter, Gauge

from hoyo_buddy.db.models import User


class Metrics:
    """定義各項用來傳送給 Prometheus Server 的 Metric"""

    PREFIX: Final[str] = "discordbot_"
    """Metric 名字的前綴"""

    IS_CONNECTED: Final[Gauge] = Gauge(PREFIX + "connected", "機器人是否連接到 Discord", ["shard"])
    """機器人是否連接到 Discord, 值為 1 或 0"""

    LATENCY: Final[Gauge] = Gauge(
        PREFIX + "latency_seconds", "機器人連接到 Discord 的延遲", ["shard"]
    )
    """機器人連接到 Discord 的延遲 (單位: 秒)"""

    GUILDS: Final[Gauge] = Gauge(PREFIX + "guilds_total", "機器人所在的伺服器總數量")
    """機器人所在的伺服器總數量"""

    USERS: Final[Gauge] = Gauge(PREFIX + "users_total", "機器人已註冊的使用者總數量")
    """機器人已註冊的使用者總數量"""

    COMMANDS: Final[Gauge] = Gauge(PREFIX + "commands_total", "機器人能使用的指令的總數量")
    """機器人能使用的指令的總數量"""

    INTERACTION_EVENTS: Final[Counter] = Counter(
        PREFIX + "on_interaction_events",
        "互動指令 (Interaction) 被呼叫的次數",
        ["shard", "interaction", "command"],
    )
    """互動指令 (Interaction) 被呼叫的次數"""

    COMMAND_EVENTS: Final[Counter] = Counter(
        PREFIX + "on_command_events", "文字指令被呼叫的次數", ["shard", "command"]
    )
    """文字指令被呼叫的次數"""

    CPU_USAGE: Final[Gauge] = Gauge(PREFIX + "cpu_usage_percent", "系統的 CPU 使用率")
    """系統的 CPU 使用率 (0 ~ 100%)"""

    MEMORY_USAGE: Final[Gauge] = Gauge(PREFIX + "memory_usage_percent", "機器人程序的記憶體使用率")
    """機器人程序的記憶體使用率 (0 ~ 100%)"""

    PROCESS_START_TIME: Final[Gauge] = Gauge(
        PREFIX + "process_start_time_seconds", "機器人程序啟動時當下的時間"
    )
    """機器人程序啟動時當下的時間 (UNIX Timestamp)"""


class PrometheusCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.set_metrics_loop.start()
        self.set_metrics_loop_users.start()

    async def cog_unload(self) -> None:
        self.set_metrics_loop.cancel()
        self.set_metrics_loop_users.cancel()

    @tasks.loop(seconds=5)
    async def set_metrics_loop(self) -> None:
        """循環更新延遲、CPU、記憶體使用率"""
        if isinstance(self.bot, AutoShardedClient):
            for shard_id, latency in self.bot.latencies:
                Metrics.LATENCY.labels(shard_id).set(latency)
        else:
            Metrics.LATENCY.labels(None).set(self.bot.latency)

        if isinstance(cpu_percent := psutil.cpu_percent(), float):
            Metrics.CPU_USAGE.set(cpu_percent)
        if isinstance(memory_percent := psutil.Process().memory_percent(), float):
            Metrics.MEMORY_USAGE.set(memory_percent)

    @tasks.loop(seconds=300)
    async def set_metrics_loop_users(self) -> None:
        """循環更新使用者總數量"""
        num_of_users = await User.all().count()
        Metrics.USERS.set(num_of_users)

    @set_metrics_loop.before_loop
    @set_metrics_loop_users.before_loop
    async def before_set_metrics_loop_users(self) -> None:
        await self.bot.wait_until_ready()

    def set_guild_gauges(self) -> None:
        """更新伺服器總數量"""
        num_of_guilds = len(self.bot.guilds)
        Metrics.GUILDS.set(num_of_guilds)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """當機器人準備好時, 設定伺服器數量、連線狀態、可使用指令總數"""
        self.set_guild_gauges()

        Metrics.IS_CONNECTED.labels(None).set(1)

        num_of_commands = len([*self.bot.walk_commands(), *self.bot.tree.walk_commands()])
        Metrics.COMMANDS.set(num_of_commands)

        process = psutil.Process()
        Metrics.PROCESS_START_TIME.set(process.create_time())

    # -------------------------------------------------------------
    # 機器人指令呼叫相關監控
    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context) -> None:
        """當文字指令被呼叫時, 設定 Metric"""
        shard_id = ctx.guild.shard_id if ctx.guild else None
        command_name = ctx.command.name if ctx.command else None
        Metrics.COMMAND_EVENTS.labels(shard_id, command_name).inc()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: Interaction) -> None:
        """當 Interaction 被呼叫時, 設定 Metric"""
        shard_id = interaction.guild.shard_id if interaction.guild else None

        if interaction.type == InteractionType.application_command:
            command_name = interaction.command.name if interaction.command else None
        else:  # 從 View (例如 Button, Dropdown...) 被呼叫
            command_name = None

        Metrics.INTERACTION_EVENTS.labels(shard_id, interaction.type.name, command_name).inc()

    @commands.Cog.listener()
    async def on_connect(self) -> None:
        Metrics.IS_CONNECTED.labels(None).set(1)

    @commands.Cog.listener()
    async def on_resumed(self) -> None:
        Metrics.IS_CONNECTED.labels(None).set(1)

    @commands.Cog.listener()
    async def on_disconnect(self) -> None:
        Metrics.IS_CONNECTED.labels(None).set(0)

    @commands.Cog.listener()
    async def on_shard_ready(self, shard_id: int) -> None:
        Metrics.IS_CONNECTED.labels(shard_id).set(1)

    @commands.Cog.listener()
    async def on_shard_connect(self, shard_id: int) -> None:
        Metrics.IS_CONNECTED.labels(shard_id).set(1)

    @commands.Cog.listener()
    async def on_shard_resumed(self, shard_id: int) -> None:
        Metrics.IS_CONNECTED.labels(shard_id).set(1)

    @commands.Cog.listener()
    async def on_shard_disconnect(self, shard_id: int) -> None:
        Metrics.IS_CONNECTED.labels(shard_id).set(0)

    @commands.Cog.listener()
    async def on_guild_join(self, _: Guild) -> None:
        self.set_guild_gauges()

    @commands.Cog.listener()
    async def on_guild_remove(self, _: Guild) -> None:
        self.set_guild_gauges()


async def setup(client: commands.Bot) -> None:
    await client.add_cog(PrometheusCog(client))
