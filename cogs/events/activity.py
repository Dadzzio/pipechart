import discord
from discord.ext import commands
import os
import logging


class activity(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log = logging.getLogger(__name__)

    @staticmethod
    def _debug_enabled() -> bool:
        return os.getenv("DEBUG", "false").strip().lower() == "true"

    @commands.Cog.listener()
    async def on_ready(self):
        beta_enabled = os.getenv("beta", "false").strip().lower() == "true"
        debug_enabled = self._debug_enabled()
        prefix_hint = f"/chart_render"

        if beta_enabled:
            await self.bot.change_presence(status=discord.Status.dnd, activity=discord.Game(f"beta... {prefix_hint}"))
        else:
            await self.bot.change_presence(
                status=discord.Status.online,
                activity=discord.Game(f"Render your own chart in discord! {prefix_hint}"),
            )
        if debug_enabled:
            if beta_enabled:
                self.log.debug("beta started")
            self.log.debug("%s commands loaded on %s servers", len(self.bot.commands), len(self.bot.guilds))
        await self.bot.tree.sync()
        
        self.log.info("Pipechart is Online!")

async def setup(bot):
    await bot.add_cog(activity(bot))