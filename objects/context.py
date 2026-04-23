from discord import Message, Embed, Colour
from discord.ext import commands
from datetime import datetime

class context(commands.Context):
    @property
    def color(self):
        return 0x2B2D31
    
    @property
    def simple_embed(self):
        embed = Embed(
            timestamp=datetime.now(),
            color=self.color,
        )
        embed.set_footer(text=f"invoked by: {super().author.display_name}", icon_url=super().author.display_avatar)
        return embed
    
    #EMBED
    async def embed(self, content, reply: bool=True) -> Message:
        embed = Embed(color=self.color, description=f"{content}")
        if reply is True: await super().reply(embed=embed)
        else: await super().channel.send(embed=embed)
    #ERROR
    async def error(self, content, reply: bool=True) -> Message:
        embed = Embed(color=0xF54336, description=f"{self.bot.emotes['main']['no']} {content}")
        if reply is True: await super().reply(embed=embed)
        else: await super().channel.send(embed=embed)
    
    #SUCCESFULLY
    async def ok(self, content, reply: bool=True) -> Message:
        embed = Embed(color=0x37EC2A, description=f"{self.bot.emotes['main']['yes']} {content}")
        if reply is True: await super().reply(embed=embed)
        else: await super().channel.send(embed=embed)