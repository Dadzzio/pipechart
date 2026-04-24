import io

import discord
from discord import app_commands
from discord.ext import commands

from cogs.commands.charts_data import prepare_chart_data
from cogs.commands.charts_rendering import build_chart
from objects.context import context


class charts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def _chart_description(cfg: dict, rows_count: int) -> str:
        return (
            f"Type: **{cfg['chart_type']}**\n"
            f"Output: **{cfg['output']}**\n"
            f"Rows: **{rows_count}**"
        )

    @staticmethod
    def _build_chart_file(cfg: dict, labels: list[str], values: list[float]) -> discord.File:
        chart_bytes = build_chart(cfg, labels, values)
        filename = f"pipechart.{cfg['output']}"
        return discord.File(io.BytesIO(chart_bytes), filename=filename)

    async def _render_chart_response(
        self,
        ctx,
        csv_attachment: discord.Attachment,
        json_attachment: discord.Attachment | None,
        chart_type: str | None = None,
        title: str | None = None,
    ):
        cfg, rows, _columns, _x_col, _y_col, labels, values = await prepare_chart_data(
            csv_attachment,
            json_attachment,
            chart_type=chart_type,
        )

        file = self._build_chart_file(cfg, labels, values)

        embed = ctx.simple_embed
        embed.title = title or f"{cfg['chart_type'].title()} chart rendered"
        embed.description = self._chart_description(cfg, len(rows))
        await ctx.reply(embed=embed, file=file)

    async def _render_chart_slash_response(
        self,
        interaction: discord.Interaction,
        csv_file: discord.Attachment,
        config_file: discord.Attachment | None,
        chart_type: str | None = None,
        title: str | None = None,
    ):
        cfg, rows, _columns, _x_col, _y_col, labels, values = await prepare_chart_data(
            csv_file,
            config_file,
            chart_type=chart_type,
        )

        file = self._build_chart_file(cfg, labels, values)
        embed = context.app_simple_embed(interaction)
        embed.title = title or f"{cfg['chart_type'].title()} chart rendered"
        embed.description = self._chart_description(cfg, len(rows))
        await interaction.response.send_message(embed=embed, file=file)

    @commands.command(name="chart_render", aliases=["crender"])
    async def chart_render(self, ctx):
        """Render a chart from CSV + optional JSON config."""
        try:
            if not ctx.message.attachments:
                await ctx.error("Attach CSV file and optional JSON config to render a chart.")
                return

            csv_attachment = next((a for a in ctx.message.attachments if a.filename.lower().endswith(".csv")), None)
            json_attachment = next((a for a in ctx.message.attachments if a.filename.lower().endswith(".json")), None)

            if csv_attachment is None:
                await ctx.error("CSV attachment not found.")
                return

            await self._render_chart_response(
                ctx,
                csv_attachment,
                json_attachment,
                title="Chart rendered",
            )
        except Exception as error:
            await ctx.error(str(error))

    @commands.command(name="bar", aliases=["cbar"])
    async def bar(self, ctx):
        """Render a bar chart from CSV + optional JSON config."""
        try:
            if not ctx.message.attachments:
                await ctx.error("Attach CSV file (and optional JSON config) to render a bar chart.")
                return

            csv_attachment = next((a for a in ctx.message.attachments if a.filename.lower().endswith(".csv")), None)
            json_attachment = next((a for a in ctx.message.attachments if a.filename.lower().endswith(".json")), None)

            if csv_attachment is None:
                await ctx.error("CSV attachment not found.")
                return

            await self._render_chart_response(ctx, csv_attachment, json_attachment, "bar", "Bar chart rendered")
        except Exception as error:
            await ctx.error(str(error))

    @commands.command(name="line", aliases=["cline"])
    async def line(self, ctx):
        """Render a line chart from CSV + optional JSON config."""
        try:
            if not ctx.message.attachments:
                await ctx.error("Attach CSV file (and optional JSON config) to render a line chart.")
                return

            csv_attachment = next((a for a in ctx.message.attachments if a.filename.lower().endswith(".csv")), None)
            json_attachment = next((a for a in ctx.message.attachments if a.filename.lower().endswith(".json")), None)

            if csv_attachment is None:
                await ctx.error("CSV attachment not found.")
                return

            await self._render_chart_response(ctx, csv_attachment, json_attachment, "line", "Line chart rendered")
        except Exception as error:
            await ctx.error(str(error))

    @commands.command(name="pie", aliases=["cpie"])
    async def pie(self, ctx):
        """Render a pie chart from CSV + optional JSON config."""
        try:
            if not ctx.message.attachments:
                await ctx.error("Attach CSV file (and optional JSON config) to render a pie chart.")
                return

            csv_attachment = next((a for a in ctx.message.attachments if a.filename.lower().endswith(".csv")), None)
            json_attachment = next((a for a in ctx.message.attachments if a.filename.lower().endswith(".json")), None)

            if csv_attachment is None:
                await ctx.error("CSV attachment not found.")
                return

            await self._render_chart_response(ctx, csv_attachment, json_attachment, "pie", "Pie chart rendered")
        except Exception as error:
            await ctx.error(str(error))

    @app_commands.command(name="chart_render", description="Render a chart from CSV and optional JSON config")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def chart_render_slash(
        self,
        interaction: discord.Interaction,
        csv_file: discord.Attachment,
        config_file: discord.Attachment | None = None,
    ):
        try:
            await self._render_chart_slash_response(
                interaction,
                csv_file,
                config_file,
                title="Chart rendered",
            )
        except Exception as error:
            await context.app_error(interaction, str(error))

    @app_commands.command(name="bar", description="Render a bar chart from CSV and optional JSON config")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def bar_slash(
        self,
        interaction: discord.Interaction,
        csv_file: discord.Attachment,
        config_file: discord.Attachment | None = None,
    ):
        try:
            await self._render_chart_slash_response(
                interaction,
                csv_file,
                config_file,
                chart_type="bar",
                title="Bar chart rendered",
            )
        except Exception as error:
            await context.app_error(interaction, str(error))

    @app_commands.command(name="line", description="Render a line chart from CSV and optional JSON config")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def line_slash(
        self,
        interaction: discord.Interaction,
        csv_file: discord.Attachment,
        config_file: discord.Attachment | None = None,
    ):
        try:
            await self._render_chart_slash_response(
                interaction,
                csv_file,
                config_file,
                chart_type="line",
                title="Line chart rendered",
            )
        except Exception as error:
            await context.app_error(interaction, str(error))

    @app_commands.command(name="pie", description="Render a pie chart from CSV and optional JSON config")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def pie_slash(
        self,
        interaction: discord.Interaction,
        csv_file: discord.Attachment,
        config_file: discord.Attachment | None = None,
    ):
        try:
            await self._render_chart_slash_response(
                interaction,
                csv_file,
                config_file,
                chart_type="pie",
                title="Pie chart rendered",
            )
        except Exception as error:
            await context.app_error(interaction, str(error))


async def setup(bot):
    await bot.add_cog(charts(bot))
