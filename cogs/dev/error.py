import discord
from discord.ext import commands


class errors(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.error('You are not allowed to use this command')
        elif isinstance(error, commands.UserNotFound):
            await ctx.error('User not found')
        elif isinstance(error, commands.MemberNotFound):
            await ctx.error('User not found')
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.error('Missing required argument')
        elif isinstance(error, commands.CommandNotFound):
            pass
        else:
            await ctx.error(error)
async def setup(bot):
    await bot.add_cog(errors(bot))