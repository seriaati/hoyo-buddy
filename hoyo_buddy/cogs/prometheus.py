"""
Copied from https://github.com/KT-Yeh/Genshin-Discord-Bot/blob/master/utility/prometheus.py
and https://github.com/KT-Yeh/Genshin-Discord-Bot/blob/2ff43ff5a4092afb3a8112d1aad2d48c94e223eb/cogs/prometheus/cog.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import prometheus_client
import psutil
from discord import Guild, Interaction, InteractionType, app_commands
from discord.ext import commands, tasks
from loguru import logger
from prometheus_client import Counter, Gauge

from hoyo_buddy.config import CONFIG
from hoyo_buddy.db.models import HoyoAccount

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import HoyoBuddy


class Metrics:
    """定義各項用來傳送給 Prometheus Server 的 Metric"""

    PREFIX: Final[str] = "discordbot_"
    """Metric's prefix"""

    IS_CONNECTED: Final[Gauge] = Gauge(
        PREFIX + "connected", "Whether the bot is connected to Discord", ["shard"]
    )
    """Whether the bot is connected to Discord, 1 for connected, 0 for disconnected"""

    LATENCY: Final[Gauge] = Gauge(
        PREFIX + "latency_seconds", "Delay between the bot and Discord", ["shard"]
    )
    """Delay between the bot and Discord (unit: seconds)"""

    GUILDS: Final[Gauge] = Gauge(PREFIX + "guilds_total", "Number of guilds the bot is in")
    """Number of guilds the bot is in"""

    USER_INSTALLS: Final[Gauge] = Gauge(PREFIX + "user_installs_total", "Number of user installs")
    """Number of user installs"""

    ACCOUNTS: Final[Gauge] = Gauge(PREFIX + "accounts_total", "Number of accounts linked")
    """Number of accounts linked"""

    SLASH_COMMANDS: Final[Counter] = Counter(
        PREFIX + "on_slash_command",
        "Number of times slash commands are called",
        ["shard", "command"],
    )
    """Number of times slash commands are called"""

    CPU_USAGE: Final[Gauge] = Gauge(PREFIX + "cpu_usage_percent", "System CPU usage")
    """System CPU usage (0 ~ 100%)"""

    MEMORY_USAGE: Final[Gauge] = Gauge(PREFIX + "memory_usage", "Bot memory usage")
    """Bot memory usage (unit: MB)"""

    PROCESS_START_TIME: Final[Gauge] = Gauge(
        PREFIX + "process_start_time_seconds", "Time when the bot process started"
    )
    """Time when the bot process started (UNIX Timestamp)"""


class PrometheusCog(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await self.start_prometheus_server()

        self.set_metrics_loop.start()
        self.set_metrics_loop_user_installs.start()
        self.set_metrics_loop_accounts.start()

    async def cog_unload(self) -> None:
        self.set_metrics_loop.cancel()
        self.set_metrics_loop_user_installs.cancel()
        self.set_metrics_loop_accounts.cancel()

    async def start_prometheus_server(self) -> None:
        port = CONFIG.prometheus_port
        if port is None:
            logger.warning("Prometheus port is not set in the settings, skipping server start")
            return

        try:
            prometheus_client.start_http_server(port)
        except OSError as e:
            if e.errno == 98:  # Address already in use
                logger.warning(f"Prometheus server is already running on port {port}")
            else:
                logger.error(f"Failed to start Prometheus server: {e}")
        else:
            logger.info(f"Prometheus server started on port {port}")

    @tasks.loop(seconds=5)
    async def set_metrics_loop(self) -> None:
        """Periodically update CPU usage, memory usage, and latency"""
        for shard_id, latency in self.bot.latencies:
            Metrics.LATENCY.labels(shard_id).set(latency)

        if isinstance(cpu_percent := psutil.cpu_percent(), float):
            Metrics.CPU_USAGE.set(cpu_percent)

        Metrics.MEMORY_USAGE.set(self.bot.ram_usage)

    @tasks.loop(seconds=300)
    async def set_metrics_loop_user_installs(self) -> None:
        """Periodically update the number of user installs"""
        app_info = await self.bot.application_info()
        user_count = app_info.approximate_user_install_count
        if user_count is not None:
            Metrics.USER_INSTALLS.set(user_count)

    @tasks.loop(seconds=300)
    async def set_metrics_loop_accounts(self) -> None:
        """Periodically update the number of accounts linked"""
        account_count = await HoyoAccount.all().count()
        Metrics.ACCOUNTS.set(account_count)

    @set_metrics_loop.before_loop
    @set_metrics_loop_user_installs.before_loop
    @set_metrics_loop_accounts.before_loop
    async def before_set_metrics_loop_users(self) -> None:
        await self.bot.wait_until_ready()

    def set_guild_gauges(self) -> None:
        """Update the number of guilds the bot is in"""
        Metrics.GUILDS.set(len(self.bot.guilds))

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self.set_guild_gauges()

        Metrics.IS_CONNECTED.labels(None).set(1)

        process = psutil.Process()
        Metrics.PROCESS_START_TIME.set(process.create_time())

    @commands.Cog.listener()
    async def on_interaction(self, i: Interaction) -> None:
        shard_id = i.guild.shard_id if i.guild else None
        command_name = None

        if i.type is InteractionType.application_command:
            if isinstance(i.command, app_commands.Command):
                parameters = i.namespace.__dict__
                command_name = self.bot.get_command_name(i.command)
                logger.info(f"[Command][{i.user.id}] {command_name}", parameters=parameters)
            elif isinstance(i.command, app_commands.ContextMenu):
                command_name = i.command.name

        if command_name is not None:
            Metrics.SLASH_COMMANDS.labels(shard_id, command_name).inc()

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


async def setup(client: HoyoBuddy) -> None:
    await client.add_cog(PrometheusCog(client))
