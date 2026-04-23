import discord
from discord.ext import commands
import time

class accounts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def oldest_acc(self, ctx):
        members = ctx.guild.members
        embed = ctx.simple_embed
        embed.description = "# The oldest accounts on this server!\n"
        embed.set_footer(text=f"invoked by: {ctx.author.display_name}", icon_url=ctx.author.display_avatar)
        top10=""
        i=1
        for member in members:
            if member.bot==True:
                continue
            if i==11:
                break
            top10= f"{top10}{i}. <@{member.id}> <t:{int(time.mktime(member.created_at.timetuple()))}:R>\n"
            i+=1
        embed.description = embed.description + top10
        await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(accounts(bot))