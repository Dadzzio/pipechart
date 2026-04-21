import discord
from discord.ext import commands
import os

class dev(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
   
    @commands.is_owner()
    @commands.command(aliases=['l'])
    async def load(self, ctx, module):
        try:
            module = module.replace("!", "cogs")
            await self.bot.load_extension(f"cogs.{module}")
            await ctx.ok(f"You successfully loaded `{module}` module!")
        except Exception as e:
            await ctx.error(e)
    
    
    @commands.is_owner()
    @commands.command(aliases=['uload', 'ul'])
    async def unload(self, ctx, module):
        try:
            if f"cogs.{module}" in self.bot.extensions:
                await self.bot.unload_extension(f"cogs.{module}")
                await ctx.ok(f"You successfully unloaded `{module}` module!")
            else:
                await ctx.error(f"Extension `{module} was never loaded! `")
        except Exception as e:
            await ctx.error(e)
    
    
    @commands.is_owner()
    @commands.command(aliases=['reset','r'])
    async def restart(self, ctx):
        try:
            for dir in os.listdir('./cogs'):
                for file in os.listdir(f'./cogs/{dir}'):
                    if file.endswith('.py') and not file.endswith('dev.py'):
                        if f"cogs.{dir}.{file[:-3]}" in self.bot.extensions:
                            await self.bot.unload_extension(f'cogs.{dir}.{file[:-3]}')
                            await self.bot.load_extension(f'cogs.{dir}.{file[:-3]}')
                        else:
                            await self.bot.load_extension(f'cogs.{dir}.{file[:-3]}')                   
            await ctx.ok(f"You successfully reloaded all modules!")
        except Exception as e:
            await ctx.error(e)

    @commands.is_owner()
    @commands.command(aliases=['rel', 'rload'])
    async def reload(self, ctx, module):
        try:
            if f"cogs.{module}" in self.bot.extensions:
                await self.bot.unload_extension(f"cogs.{module}")
                await self.bot.load_extension(f"cogs.{module}")
            else:
                await self.bot.load_extension(f"cogs.{module}")
            await ctx.ok(f"You successfully reloaded `{module}` module!")
        except Exception as e:
            await ctx.error(e)


async def setup(bot):
    await bot.add_cog(dev(bot))