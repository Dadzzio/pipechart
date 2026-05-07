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
    def _build_chart_file(cfg: dict, labels: list[str], values: list[float]) -> discord.File:
        chart_bytes = build_chart(cfg, labels, values)
        filename = f"pipechart.{cfg['output']}"
        return discord.File(io.BytesIO(chart_bytes), filename=filename)

    def _chart_type_select_view(
        self,
        csv_file: discord.Attachment,
        config_file: discord.Attachment | None = None,
        original_message: discord.Message | None = None,
        session_state: dict | None = None,
        fixed_chart_type: str | None = None,
    ) -> discord.ui.View:
        cog = self
        stored_config = {}  # Store config values for edit functionality
        if session_state is None:
            session_state = {"cancelled": False, "completed": False, "config_messages": []}
        owner_id = session_state.get("owner_id")
        fixed_chart_type = fixed_chart_type.lower() if fixed_chart_type else None

        async def _ensure_owner(interaction: discord.Interaction) -> bool:
            if owner_id is None or interaction.user.id == owner_id:
                return True
            if interaction.response.is_done():
                await interaction.followup.send("❌ Only the command author can use this panel.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Only the command author can use this panel.", ephemeral=True)
            return False

        def _parse_output(value: str | None) -> str:
            output_fmt = value.lower().strip() if value else "png"
            return output_fmt if output_fmt in ["png", "svg", "pdf"] else "png"

        def _create_modal(chart_type: str):
            return PieConfigModal() if chart_type == "pie" else ConfigModal(chart_type)

        def _apply_stored_defaults(modal, chart_type: str):
            if not stored_config or stored_config.get("chart_type") != chart_type:
                return

            modal.title_input.default = stored_config.get("title", "PipeChart")
            if chart_type == "pie" and hasattr(modal, "colors_input"):
                modal.colors_input.default = stored_config.get("colors", "")
            elif chart_type != "pie":
                modal.x_label_input.default = stored_config.get("x_label", "")
                modal.y_label_input.default = stored_config.get("y_label", "")
                modal.color_input.default = stored_config.get("color", "#4E79A7")
            modal.output_input.default = stored_config.get("output", "png")

        class ConfigModal(discord.ui.Modal, title="Configure Your Chart"):
            title_input = discord.ui.TextInput(
                label="Chart Title",
                placeholder="Enter chart title",
                max_length=100,
                required=False,
                default="PipeChart"
            )
            x_label_input = discord.ui.TextInput(
                label="X Axis Label",
                placeholder="Leave empty for default",
                max_length=100,
                required=False
            )
            y_label_input = discord.ui.TextInput(
                label="Y Axis Label",
                placeholder="Leave empty for default",
                max_length=100,
                required=False
            )
            color_input = discord.ui.TextInput(
                label="Color (any matplotlib value)",
                placeholder="#4E79A7, red, 0.5",
                max_length=50,
                required=False,
                default="#4E79A7"
            )
            output_input = discord.ui.TextInput(
                label="Output Format (png/svg/pdf)",
                placeholder="png, svg, or pdf",
                max_length=3,
                required=False,
                default="png"
            )

            def __init__(self, chart_type: str):
                super().__init__()
                self.chart_type = chart_type

            async def on_submit(self, interaction: discord.Interaction):
                if not await _ensure_owner(interaction):
                    return
                if session_state.get("cancelled"):
                    await interaction.response.send_message("❌ Configuration was cancelled. Start /chart_render again.", ephemeral=True)
                    return

                # Immediately defer to prevent timeout
                await interaction.response.defer()
                
                try:
                    cfg, rows, _columns, _x_col, _y_col, labels, values = await prepare_chart_data(
                        csv_file,
                        config_file,
                        chart_type=self.chart_type,
                    )
                    
                    # Apply custom config
                    if self.title_input.value:
                        cfg["title"] = self.title_input.value
                    if self.x_label_input.value:
                        cfg["x_label"] = self.x_label_input.value
                    if self.y_label_input.value:
                        cfg["y_label"] = self.y_label_input.value

                    if self.color_input.value:
                        # Let matplotlib validate accepted color formats.
                        cfg["color"] = self.color_input.value.strip()
                    
                    output_fmt = self.output_input.value.lower().strip() if self.output_input.value else "png"
                    if output_fmt not in ["png", "svg", "pdf"]:
                        output_fmt = "png"
                    cfg["output"] = output_fmt
                    
                    # Store config for edit functionality
                    stored_config.update({
                        "title": self.title_input.value or "PipeChart",
                        "x_label": self.x_label_input.value or "",
                        "y_label": self.y_label_input.value or "",
                        "color": self.color_input.value or "#4E79A7",
                        "output": output_fmt,
                        "chart_type": self.chart_type,
                    })
                    
                    file = cog._build_chart_file(cfg, labels, values)
                    embed = context.chart_embed(
                        chart_type=cfg['chart_type'],
                        rows_count=len(rows),
                        user_name=interaction.user.display_name,
                        user_avatar=interaction.user.display_avatar,
                        config=cfg,
                    )

                    config_done_embed = discord.Embed(
                        title="✅ Chart rendered!",
                        description="Configuration submitted successfully.",
                        color=0x37EC2A,
                    )
                    
                    # Edit the original public message with the final chart
                    public_updated = False
                    if original_message:
                        try:
                            # Add edit button for user convenience
                            edit_view = EditChartView()
                            await original_message.edit(embed=embed, attachments=[file], view=edit_view)
                            public_updated = True
                        except:
                            public_updated = False

                    if not public_updated:
                        # Build a fresh file object for fallback send.
                        fallback_file = cog._build_chart_file(cfg, labels, values)
                        await interaction.followup.send(embed=embed, file=fallback_file)

                    session_state["completed"] = True

                    for config_message in session_state.get("config_messages", []):
                        try:
                            await config_message.edit(embed=config_done_embed, view=None)
                        except:
                            pass
                        
                except Exception as e:
                    await interaction.followup.send(f"❌ Error rendering chart: {str(e)}", ephemeral=True)

        class PieConfigModal(discord.ui.Modal, title="Configure Pie Chart"):
            title_input = discord.ui.TextInput(
                label="Chart Title",
                placeholder="Enter chart title",
                max_length=100,
                required=False,
                default="PipeChart"
            )
            colors_input = discord.ui.TextInput(
                label="Slice colors (comma-separated)",
                placeholder="red, #4E79A7, 0.6, C2",
                max_length=250,
                required=False
            )
            output_input = discord.ui.TextInput(
                label="Output Format (png/svg/pdf)",
                placeholder="png, svg, or pdf",
                max_length=3,
                required=False,
                default="png"
            )

            async def on_submit(self, interaction: discord.Interaction):
                if not await _ensure_owner(interaction):
                    return
                if session_state.get("cancelled"):
                    await interaction.response.send_message("❌ Configuration was cancelled. Start /chart_render again.", ephemeral=True)
                    return

                await interaction.response.defer()

                try:
                    cfg, rows, _columns, _x_col, _y_col, labels, values = await prepare_chart_data(
                        csv_file,
                        config_file,
                        chart_type="pie",
                    )

                    if self.title_input.value:
                        cfg["title"] = self.title_input.value

                    output_fmt = _parse_output(self.output_input.value)
                    cfg["output"] = output_fmt

                    parsed_colors = []
                    if self.colors_input.value:
                        parsed_colors = [c.strip() for c in self.colors_input.value.split(",") if c.strip()]
                        if parsed_colors:
                            cfg["colors"] = parsed_colors

                    stored_config.update({
                        "title": self.title_input.value or "PipeChart",
                        "output": output_fmt,
                        "chart_type": "pie",
                        "colors": self.colors_input.value or "",
                    })

                    file = cog._build_chart_file(cfg, labels, values)
                    embed = context.chart_embed(
                        chart_type=cfg['chart_type'],
                        rows_count=len(rows),
                        user_name=interaction.user.display_name,
                        user_avatar=interaction.user.display_avatar,
                        config=cfg,
                    )

                    config_done_embed = discord.Embed(
                        title="✅ Chart rendered!",
                        description="Configuration submitted successfully.",
                        color=0x37EC2A,
                    )

                    public_updated = False
                    if original_message:
                        try:
                            edit_view = EditChartView()
                            await original_message.edit(embed=embed, attachments=[file], view=edit_view)
                            public_updated = True
                        except:
                            public_updated = False

                    if not public_updated:
                        fallback_file = cog._build_chart_file(cfg, labels, values)
                        await interaction.followup.send(embed=embed, file=fallback_file)

                    session_state["completed"] = True

                    for config_message in session_state.get("config_messages", []):
                        try:
                            await config_message.edit(embed=config_done_embed, view=None)
                        except:
                            pass

                except Exception as e:
                    await interaction.followup.send(f"❌ Error rendering chart: {str(e)}", ephemeral=True)

        class CancelButton(discord.ui.Button):
            def __init__(self):
                super().__init__(style=discord.ButtonStyle.danger, label="✕ Cancel", emoji="❌")
            
            async def callback(self, interaction: discord.Interaction):
                if not await _ensure_owner(interaction):
                    return
                session_state["cancelled"] = True

                if self.view:
                    for item in self.view.children:
                        item.disabled = True

                cancelled_embed = discord.Embed(
                    title="❌ Configuration cancelled",
                    description="This configuration panel is locked. Run /chart_render again to start a new one.",
                    color=0xF54336,
                )
                await interaction.response.edit_message(embed=cancelled_embed, view=self.view)

                for config_message in session_state.get("config_messages", []):
                    try:
                        if interaction.message and config_message.id == interaction.message.id:
                            continue
                        await config_message.edit(embed=cancelled_embed, view=None)
                    except:
                        pass
                
                # Delete the "Building..." message
                if original_message:
                    try:
                        await original_message.delete()
                    except:
                        pass

        class EditButton(discord.ui.Button):
            def __init__(self):
                super().__init__(style=discord.ButtonStyle.secondary, label="✏️ Edit", emoji="📝")
            
            async def callback(self, interaction: discord.Interaction):
                if not await _ensure_owner(interaction):
                    return
                if fixed_chart_type:
                    modal = _create_modal(fixed_chart_type)
                    _apply_stored_defaults(modal, fixed_chart_type)
                    await interaction.response.send_modal(modal)
                    return
                # Show chart type selector again
                chart_options = [
                    discord.SelectOption(label="📊 Bar", value="bar", description="Bar chart visualization"),
                    discord.SelectOption(label="📈 Line", value="line", description="Line chart visualization"),
                    discord.SelectOption(label="🥧 Pie", value="pie", description="Pie chart visualization"),
                ]
                
                class EditChartTypeSelect(discord.ui.Select):
                    def __init__(self):
                        super().__init__(placeholder="Select chart type to reconfigure", min_values=1, max_values=1, options=chart_options)
                    
                    async def callback(self, select_interaction: discord.Interaction):
                        if not await _ensure_owner(select_interaction):
                            return
                        if session_state.get("cancelled"):
                            await select_interaction.response.send_message("❌ Configuration was cancelled. Start /chart_render again.", ephemeral=True)
                            return

                        chart_type = self.values[0]
                        modal = _create_modal(chart_type)
                        # Pre-fill with stored values if available
                        if stored_config:
                            if stored_config.get("chart_type") == chart_type:
                                modal.title_input.default = stored_config.get("title", "PipeChart")
                                if chart_type == "pie":
                                    modal.colors_input.default = stored_config.get("colors", "")
                                else:
                                    modal.x_label_input.default = stored_config.get("x_label", "")
                                    modal.y_label_input.default = stored_config.get("y_label", "")
                                    modal.color_input.default = stored_config.get("color", "#4E79A7")
                                modal.output_input.default = stored_config.get("output", "png")
                        await select_interaction.response.send_modal(modal)
                
                class EditChartTypeView(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=300)
                        self.add_item(EditChartTypeSelect())
                
                embed = discord.Embed(
                    title="📊 Edit Chart",
                    description="Select chart type to reconfigure",
                    color=0x4E79A7,
                )
                await interaction.response.send_message(embed=embed, view=EditChartTypeView(), ephemeral=True)

        class ConfigureButton(discord.ui.Button):
            def __init__(self):
                super().__init__(style=discord.ButtonStyle.primary, label="⚙️ Configure", emoji="🛠️")

            async def callback(self, interaction: discord.Interaction):
                if not await _ensure_owner(interaction):
                    return
                if session_state.get("cancelled"):
                    await interaction.response.send_message("❌ Configuration was cancelled. Run the command again.", ephemeral=True)
                    return

                if not fixed_chart_type:
                    await interaction.response.send_message("❌ Missing chart preset.", ephemeral=True)
                    return

                modal = _create_modal(fixed_chart_type)
                _apply_stored_defaults(modal, fixed_chart_type)
                await interaction.response.send_modal(modal)

        class EditChartView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(EditButton())

        class ChartTypeSelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label="📊 Bar", value="bar", description="Bar chart visualization"),
                    discord.SelectOption(label="📈 Line", value="line", description="Line chart visualization"),
                    discord.SelectOption(label="🥧 Pie", value="pie", description="Pie chart visualization"),
                ]
                super().__init__(placeholder="Select chart type", min_values=1, max_values=1, options=options)

            async def callback(self, interaction: discord.Interaction):
                if not await _ensure_owner(interaction):
                    return
                if session_state.get("cancelled"):
                    await interaction.response.send_message("❌ Configuration was cancelled. Start /chart_render again.", ephemeral=True)
                    return
                chart_type = self.values[0]
                modal = _create_modal(chart_type)
                await interaction.response.send_modal(modal)

        class ChartTypeView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)  # 5 minutes
                if fixed_chart_type:
                    self.add_item(ConfigureButton())
                else:
                    self.add_item(ChartTypeSelect())
                self.add_item(CancelButton())
            
            async def on_timeout(self):
                """Delete the original message if timeout"""
                if session_state.get("completed") or session_state.get("cancelled"):
                    return

                if original_message:
                    try:
                        await original_message.delete()
                    except:
                        pass

        return ChartTypeView()

    async def _start_chart_configuration(
        self,
        interaction: discord.Interaction,
        csv_file: discord.Attachment,
        config_file: discord.Attachment | None = None,
        fixed_chart_type: str | None = None,
    ):
        session_state = {
            "cancelled": False,
            "completed": False,
            "config_messages": [],
            "owner_id": interaction.user.id,
            "preset_chart_type": fixed_chart_type.lower() if fixed_chart_type else None,
        }

        cog = self

        class BuildingEditView(discord.ui.View):
            def __init__(self, csv_attachment, cfg_file, state: dict):
                super().__init__(timeout=300)
                self.csv_file = csv_attachment
                self.config_file = cfg_file
                self.state = state
                self.original_msg = None

            @discord.ui.button(style=discord.ButtonStyle.secondary, label="✏️ Configure", emoji="⚙️")
            async def edit_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if button_interaction.user.id != self.state.get("owner_id"):
                    await button_interaction.response.send_message(
                        "❌ Only the command author can use this panel.",
                        ephemeral=True,
                    )
                    return
                if self.state.get("cancelled"):
                    await button_interaction.response.send_message(
                        "❌ Configuration was cancelled. Run the command again.",
                        ephemeral=True,
                    )
                    return

                config_embed = discord.Embed(
                    title="📊 Chart Wizard",
                    description=(
                        f"Configure the {self.state['preset_chart_type'].title()} chart below."
                        if self.state.get("preset_chart_type")
                        else "Select chart type and configure it in the next step"
                    ),
                    color=0x4E79A7,
                )
                config_embed.add_field(
                    name="⏱️ Timeout",
                    value="Configuration window closes in 5 minutes. If no selection is made, the build message will be deleted.",
                    inline=False,
                )
                await button_interaction.response.defer(ephemeral=True)
                config_message = await button_interaction.followup.send(
                    embed=config_embed,
                    view=cog._chart_type_select_view(
                        self.csv_file,
                        self.config_file,
                        self.original_msg,
                        session_state=self.state,
                        fixed_chart_type=self.state.get("preset_chart_type"),
                    ),
                    ephemeral=True,
                    wait=True,
                )
                if config_message:
                    self.state.setdefault("config_messages", []).append(config_message)

        preset_name = (fixed_chart_type or "chart").title()
        building_embed = discord.Embed(
            title=f"🔨 Building {preset_name}...",
            description="Chart is being prepared. Click Configure to set chart options, or check your private message.",
            color=0xFFA500,
        )
        building_embed.set_footer(text=f"Requested by {interaction.user.display_name}")

        view = BuildingEditView(csv_file, config_file, session_state)
        await interaction.response.send_message(embed=building_embed, view=view)
        original_message = await interaction.original_response()
        view.original_msg = original_message

        config_embed = discord.Embed(
            title="📊 Chart Wizard",
            description=(
                f"Configure the {preset_name} chart below."
                if fixed_chart_type
                else "Select chart type and configure it in the next step"
            ),
            color=0x4E79A7,
        )
        config_embed.add_field(
            name="⏱️ Timeout",
            value="Configuration window closes in 5 minutes. If no selection is made, the build message will be deleted.",
            inline=False,
        )
        config_message = await interaction.followup.send(
            embed=config_embed,
            view=self._chart_type_select_view(
                csv_file,
                config_file,
                original_message,
                session_state=session_state,
                fixed_chart_type=fixed_chart_type,
            ),
            ephemeral=True,
            wait=True,
        )
        if config_message:
            session_state.setdefault("config_messages", []).append(config_message)

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

        embed = context.chart_embed(
            chart_type=cfg['chart_type'],
            rows_count=len(rows),
            user_name=ctx.author.display_name,
            user_avatar=ctx.author.display_avatar,
            config=cfg,
        )
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
        embed = context.chart_embed(
            chart_type=cfg['chart_type'],
            rows_count=len(rows),
            user_name=interaction.user.display_name,
            user_avatar=interaction.user.display_avatar,
            config=cfg,
        )
        await interaction.response.send_message(embed=embed, file=file)

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
            if config_file is None:
                session_state = {
                    "cancelled": False,
                    "config_messages": [],
                    "owner_id": interaction.user.id,
                }

                # Create a view with Edit button for Building message
                cog = self
                
                class BuildingEditView(discord.ui.View):
                    def __init__(self, csv_attachment, cfg_file, state: dict):
                        super().__init__(timeout=300)
                        self.csv_file = csv_attachment
                        self.config_file = cfg_file
                        self.state = state
                        self.original_msg = None
                    
                    @discord.ui.button(style=discord.ButtonStyle.secondary, label="✏️ Configure", emoji="⚙️")
                    async def edit_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                        if button_interaction.user.id != self.state.get("owner_id"):
                            await button_interaction.response.send_message(
                                "❌ Only the command author can use this panel.",
                                ephemeral=True,
                            )
                            return
                        if self.state.get("cancelled"):
                            await button_interaction.response.send_message(
                                "❌ Configuration was cancelled. Run /chart_render again.",
                                ephemeral=True,
                            )
                            return

                        # Show the chart type selector again
                        config_embed = discord.Embed(
                            title="📊 Chart Wizard",
                            description="Select chart type and configure it in the next step",
                            color=0x4E79A7,
                        )
                        config_embed.add_field(
                            name="⏱️ Timeout",
                            value="Configuration window closes in 5 minutes. If no selection is made, the build message will be deleted.",
                            inline=False,
                        )
                        await button_interaction.response.defer(ephemeral=True)
                        config_message = await button_interaction.followup.send(
                            embed=config_embed,
                            view=cog._chart_type_select_view(
                                self.csv_file,
                                self.config_file,
                                self.original_msg,
                                session_state=self.state,
                            ),
                            ephemeral=True,
                            wait=True,
                        )
                        if config_message:
                            self.state.setdefault("config_messages", []).append(config_message)
                
                # Send public "Building chart..." message
                building_embed = discord.Embed(
                    title="🔨 Building chart...",
                    description="Chart is being prepared. Click Configure to set chart options, or check your private message.",
                    color=0xFFA500,
                )
                building_embed.set_footer(text=f"Requested by {interaction.user.display_name}")
                
                view = BuildingEditView(csv_file, config_file, session_state)
                await interaction.response.send_message(embed=building_embed, view=view)
                original_message = await interaction.original_response()
                view.original_msg = original_message
                
                # Send ephemeral message with chart type selector (visible only to author)
                config_embed = discord.Embed(
                    title="📊 Chart Wizard",
                    description="Select chart type and configure it in the next step",
                    color=0x4E79A7,
                )
                config_embed.add_field(
                    name="⏱️ Timeout",
                    value="Configuration window closes in 5 minutes. If no selection is made, the build message will be deleted.",
                    inline=False,
                )
                config_message = await interaction.followup.send(
                    embed=config_embed,
                    view=self._chart_type_select_view(
                        csv_file,
                        config_file,
                        original_message,
                        session_state=session_state,
                    ),
                    ephemeral=True,
                    wait=True,
                )
                if config_message:
                    session_state.setdefault("config_messages", []).append(config_message)
                return

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
            if config_file is None:
                await self._start_chart_configuration(interaction, csv_file, config_file, fixed_chart_type="bar")
                return

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
            if config_file is None:
                await self._start_chart_configuration(interaction, csv_file, config_file, fixed_chart_type="line")
                return

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
            if config_file is None:
                await self._start_chart_configuration(interaction, csv_file, config_file, fixed_chart_type="pie")
                return

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
