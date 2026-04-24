import discord
from discord.ext import commands
import os


class activity(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        beta_enabled = os.getenv("beta", "false").strip().lower() == "true"

        if beta_enabled:
            await self.bot.change_presence(status=discord.Status.dnd, activity=discord.Game("beta... \\\\chart_render"))
            print("beta started")
        else:
            await self.bot.change_presence(
                status=discord.Status.online,
                activity=discord.Game("Render your own chart in discord! \\chart_render"),
            )
        print(f"\n{len(self.bot.commands)} commands loaded", end=" ")
        print(f"on {len(self.bot.guilds)} servers...")
        print("\nPipechart is Online!")

async def setup(bot):
    await bot.add_cog(activity(bot))