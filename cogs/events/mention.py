import discord
from discord.ext import commands
from datetime import datetime


class mention(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if self.bot.user.mention == message.content or message.content.startswith(">bot"):
            embed = discord.Embed(
            title=f"Hi **{message.author.display_name}**! You just mentioned Pipechart!",
            description=f"Bot was created <t:1776759775:R> by IBM apprentices <@476450702672265216> and <@1066787377747599381> it is currently in development.\nCurrent bot language - **discord.py**, last boot was <t:{str(self.bot.readyAt)[:-7]}:R>",
            timestamp=datetime.now(),
            color=0x2B2D31,
            )
            embed.set_author(name=f"{self.bot.name}", icon_url=self.bot.avatar)
            embed.set_footer(text=f"invoked by: {message.author.display_name}", icon_url=message.author.display_avatar)
            await message.reply(embed=embed)



async def setup(bot):
    await bot.add_cog(mention(bot))