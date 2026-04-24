from discord.ext import commands
import os

class dev(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _normalize_extension(self, module: str) -> str:
        module = module.strip().removeprefix("cogs.")
        return f"cogs.{module}"

    async def _load_extension(self, ctx, extension: str):
        try:
            await self.bot.load_extension(extension)
            await ctx.ok(f"You successfully loaded `{extension}` module!")
        except commands.errors.NoEntryPointError:
            await ctx.error(f"Extension `{extension}` has no `setup` function and cannot be loaded.")
   
    @commands.is_owner()
    @commands.command(aliases=['l'])
    async def load(self, ctx, module):
        try:
            extension = self._normalize_extension(module)
            await self._load_extension(ctx, extension)
        except Exception as e:
            await ctx.error(e)
    
    
    @commands.is_owner()
    @commands.command(aliases=['uload', 'ul'])
    async def unload(self, ctx, module):
        try:
            extension = self._normalize_extension(module)
            if extension in self.bot.extensions:
                await self.bot.unload_extension(extension)
                await ctx.ok(f"You successfully unloaded `{extension}` module!")
            else:
                await ctx.error(f"Extension `{extension}` was never loaded!")
        except Exception as e:
            await ctx.error(e)
    
    
    @commands.is_owner()
    @commands.command(aliases=['reset','r'])
    async def restart(self, ctx):
        try:
            for dir in os.listdir('./cogs'):
                for file in os.listdir(f'./cogs/{dir}'):
                    if file.endswith('.py') and not file.endswith('dev.py'):
                        extension = f"cogs.{dir}.{file[:-3]}"
                        if extension in self.bot.extensions:
                            await self.bot.unload_extension(extension)
                        try:
                            await self.bot.load_extension(extension)
                        except commands.errors.NoEntryPointError:
                            continue
            await ctx.ok(f"You successfully reloaded all modules!")
        except Exception as e:
            await ctx.error(e)

    @commands.is_owner()
    @commands.command(aliases=['rel', 'rload'])
    async def reload(self, ctx, module):
        try:
            extension = self._normalize_extension(module)
            if extension in self.bot.extensions:
                await self.bot.unload_extension(extension)
                await self._load_extension(ctx, extension)
            else:
                await self._load_extension(ctx, extension)
        except Exception as e:
            await ctx.error(e)


async def setup(bot):
    await bot.add_cog(dev(bot))