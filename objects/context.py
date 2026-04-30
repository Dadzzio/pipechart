from discord import Message, Embed, Colour
from discord.ext import commands
from datetime import datetime

class context(commands.Context):
    @property
    def color(self):
        return 0x2B2D31

    @staticmethod
    def build_simple_embed(author_name: str, author_avatar, color: int = 0x2B2D31) -> Embed:
        embed = Embed(
            timestamp=datetime.now(),
            color=color,
        )
        embed.set_footer(text=f"invoked by: {author_name}", icon_url=author_avatar)
        return embed
    
    @property
    def simple_embed(self):
        return self.build_simple_embed(super().author.display_name, super().author.display_avatar, self.color)

    @staticmethod
    def app_simple_embed(interaction, color: int = 0x2B2D31) -> Embed:
        user = interaction.user
        author_name = getattr(user, "display_name", getattr(user, "name", "Unknown"))
        author_avatar = getattr(user, "display_avatar", None)
        return context.build_simple_embed(author_name, author_avatar, color)

    @staticmethod
    async def app_embed(interaction, content, reply: bool=True, color: int = 0x2B2D31, ephemeral: bool = False):
        embed = Embed(color=color, description=f"{content}")
        if reply is True:
            if interaction.response.is_done():
                return await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
        return await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    @staticmethod
    async def app_error(interaction, content, reply: bool=True, ephemeral: bool = True):
        embed = Embed(color=0xF54336, description=f"{interaction.client.emotes['main']['no']} {content}")
        if reply is True:
            if interaction.response.is_done():
                return await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
        return await interaction.followup.send(embed=embed, ephemeral=ephemeral)

    @staticmethod
    async def app_ok(interaction, content, reply: bool=True, ephemeral: bool = False):
        embed = Embed(color=0x37EC2A, description=f"{interaction.client.emotes['main']['yes']} {content}")
        if reply is True:
            if interaction.response.is_done():
                return await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            return await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
        return await interaction.followup.send(embed=embed, ephemeral=ephemeral)
    
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