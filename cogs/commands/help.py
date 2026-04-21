import discord
from discord.ext import commands
import time

class help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def help(self, ctx):
        embed = ctx.simple_embed
        embed.description = "# Skibidi help"
        embed.set_footer(text=f"invoked by: {ctx.author.display_name}", icon_url=ctx.author.display_avatar)
        embed.description ="skibidi help in progress"
        await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(help(bot))