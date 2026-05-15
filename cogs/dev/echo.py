import discord
from discord.ext import commands

class echo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.is_owner()
    @commands.command()
    async def echo(self,ctx,  *, message):
        await ctx.send(message)
        await ctx.message.delete()

async def setup(bot):
    await bot.add_cog(echo(bot))