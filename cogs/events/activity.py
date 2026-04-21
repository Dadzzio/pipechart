import discord
from discord.ext import commands


class activity(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.change_presence(status=discord.Status.dnd, activity=discord.Game("beta..."))
        print(f"\n{len(self.bot.commands)} commands loaded", end=" ")
        print(f"on {len(self.bot.guilds)} servers...")
        print("\nPipechart is Online!")

async def setup(bot):
    await bot.add_cog(activity(bot))