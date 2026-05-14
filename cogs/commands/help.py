import discord
from discord.ext import commands


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help", aliases=["h"])
    async def help(self, ctx):
        prefix = ctx.clean_prefix

        embed = ctx.simple_embed
        embed.title = "PipeChart Help"
        embed.description = (
            "Create charts from CSV attachments with optional JSON configuration. "
            "Use the guided flow for interactive setup or render directly with a chart command."
        )
        embed.add_field(
            name="Guided flow",
            value=f"`{prefix}chart_render` - interactive chart setup and rendering",
            inline=False,
        )
        embed.add_field(
            name="Direct renders",
            value=(
                f"`{prefix}bar` - render a bar chart\n"
                f"`{prefix}line` - render a line chart\n"
                f"`{prefix}pie` - render a pie chart"
            ),
            inline=False,
        )
        embed.add_field(
            name="What to attach",
            value=(
                "A `.csv` file is required. A `.json` file is optional and can set chart type, "
                "axis labels, pie colors, output format, figure size, style, and advanced options like "
                "mean_line, mean_color, mean_style, grid, line_width, marker, bar_width, alpha, startangle, and y_columns."
            ),
            inline=False,
        )
        embed.add_field(
            name="Multi-series charts",
            value=(
                "For `bar` and `line`, set `y_columns` to a comma-separated list in the UI or a JSON array in the config. "
                "Each column becomes its own series on the same chart."
            ),
            inline=False,
        )
        embed.add_field(
            name="Slash commands",
            value="`/chart_render`, `/bar`, `/line`, `/pie`",
            inline=False,
        )
        embed.add_field(
            name="GitHub repo",
            value="[github.com/Dadzzio/pipechart](https://github.com/Dadzzio/pipechart)",
            inline=False,
        )

        await ctx.reply(embed=embed)

    
async def setup(bot):
    await bot.add_cog(Help(bot))