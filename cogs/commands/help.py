import discord
from discord import app_commands
from discord.ext import commands

from objects.context import context


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _build_help_embed(self, prefix: str, author_name: str, author_avatar) -> discord.Embed:
        embed = context.build_simple_embed(author_name, author_avatar)
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

        return embed

    @commands.command(name="help", aliases=["h"])
    async def help(self, ctx):
        embed = self._build_help_embed(ctx.clean_prefix, ctx.author.display_name, ctx.author.display_avatar)
        await ctx.reply(embed=embed)

    @app_commands.command(name="help", description="Show PipeChart help")
    async def help_app(self, interaction: discord.Interaction):
        user = interaction.user
        author_name = getattr(user, "display_name", getattr(user, "name", "Unknown"))
        author_avatar = getattr(user, "display_avatar", None)
        embed = self._build_help_embed("/", author_name, author_avatar)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    
async def setup(bot):
    await bot.add_cog(Help(bot))