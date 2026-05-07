import io

import discord
import traceback
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
    ) -> discord.ui.View:
        cog = self
        stored_config = {}  # Store config values for edit functionality
        if session_state is None:
            session_state = {"cancelled": False, "config_messages": []}
        owner_id = session_state.get("owner_id")

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
            return output_fmt if output_fmt in ["png", "svg"] else "png"

        def _create_modal(chart_type: str):
            return PieConfigModal() if chart_type == "pie" else ConfigModal(chart_type)

        def _debug_modal(modal, label: str = "modal"):
            try:
                print(f"--- DEBUG {label} ---")
                print("modal class:", modal.__class__)
                # show some public attributes
                public_dir = [a for a in dir(modal) if not a.startswith("_")]
                print("dir (sample):", public_dir[:60])
                # try common attribute names for children
                children = None
                for attr in ("children", "_children", "components", "_state", "_items"):
                    if hasattr(modal, attr):
                        try:
                            children = getattr(modal, attr)
                            break
                        except Exception:
                            children = None
                print("children type:", type(children))
                if children:
                    for i, ch in enumerate(children):
                        try:
                            print(f" child {i}: class={ch.__class__}")
                            ch_dir = [n for n in dir(ch) if not n.startswith("_")]
                            print("   dir:", ch_dir[:40])
                            for attr in ("type", "style", "custom_id", "label", "placeholder", "default", "value", "min_length", "max_length"):
                                try:
                                    val = getattr(ch, attr)
                                except Exception:
                                    val = None
                                print(f"   {attr} = {val}")
                        except Exception:
                            print(f"  failed to inspect child {i}")
                print("--- END DEBUG ---")
            except Exception:
                print("failed to dump modal info")
                import traceback
                traceback.print_exc()

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
                label="Output Format (png/svg)",
                placeholder="png",
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
                        cfg["color"] = self.color_input.value.strip()

                    output_fmt = self.output_input.value.lower().strip() if self.output_input.value else "png"
                    if output_fmt not in ["png", "svg"]:
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

                    # If this is a bar chart and CSV has multiple columns, open iterative per-column rename modals
                    if self.chart_type == "bar" and _columns and len(_columns) > 1:
                        total = len(_columns)

                        class ColumnRenameModal(discord.ui.Modal, title="Rename column"):
                            def __init__(self, idx: int, mapping: dict, prepared_cfg, prepared_rows, prepared_columns, prepared_labels, prepared_values):
                                # create modal inputs dynamically to avoid mutating class-level TextInput
                                super().__init__()
                                self.idx = idx
                                self.mapping = mapping
                                self.prep_cfg = prepared_cfg
                                self.prep_rows = prepared_rows
                                self.prep_columns = prepared_columns
                                self.prep_labels = prepared_labels
                                self.prep_values = prepared_values
                                header = self.prep_columns[self.idx]
                                placeholder = f"New name for '{header}' ({self.idx+1}/{total})"
                                default_value = mapping.get(header, header)
                                self.rename_input = discord.ui.TextInput(
                                    label="New name",
                                    placeholder=placeholder,
                                    required=False,
                                    max_length=200,
                                    default=default_value,
                                )
                                self.add_item(self.rename_input)

                            async def on_submit(self, modal_interaction: discord.Interaction):
                                if not await _ensure_owner(modal_interaction):
                                    return
                                if session_state.get("cancelled"):
                                    await modal_interaction.response.send_message("❌ Configuration was cancelled. Start /chart_render again.", ephemeral=True)
                                    return

                                header = self.prep_columns[self.idx]
                                new_name = (self.rename_input.value or "").strip()
                                if new_name:
                                    self.mapping[header] = new_name

                                next_idx = self.idx + 1
                                if next_idx < total:
                                    # show next modal
                                    next_modal = ColumnRenameModal(next_idx, self.mapping, self.prep_cfg, self.prep_rows, self.prep_columns, self.prep_labels, self.prep_values)
                                    try:
                                        _debug_modal(next_modal, "next_modal")
                                        await modal_interaction.response.send_modal(next_modal)
                                        return
                                    except discord.errors.HTTPException as http_e:
                                        print("HTTPException while sending next_modal:", repr(http_e))
                                        try:
                                            # attempt to read response body
                                            resp = getattr(http_e, 'response', None)
                                            if resp is not None:
                                                try:
                                                    text = await resp.text()
                                                    print("response.text():", text)
                                                except Exception:
                                                    print("failed to read resp.text()")
                                        except Exception:
                                            pass
                                        tb = traceback.format_exc()
                                        print(tb)
                                        try:
                                            if modal_interaction.response.is_done():
                                                await modal_interaction.followup.send("⚠️ Modal failed to open; rendering without further renames.", ephemeral=True)
                                            else:
                                                await modal_interaction.response.send_message("⚠️ Modal failed to open; rendering without further renames.", ephemeral=True)
                                        except Exception:
                                            pass
                                    except Exception:
                                        tb = traceback.format_exc()
                                        print(tb)
                                        try:
                                            if modal_interaction.response.is_done():
                                                await modal_interaction.followup.send("⚠️ Modal failed to open; rendering without further renames.", ephemeral=True)
                                            else:
                                                await modal_interaction.response.send_message("⚠️ Modal failed to open; rendering without further renames.", ephemeral=True)
                                        except Exception:
                                            pass

                                # finished collecting names — apply mapping and render
                                mapping = self.mapping
                                labels_mapped = [mapping.get(lbl, lbl) for lbl in self.prep_labels]
                                stored_config["column_renames"] = ",".join([f"{k}:{v}" for k, v in mapping.items()])

                                try:
                                    file = cog._build_chart_file(self.prep_cfg, labels_mapped, self.prep_values)
                                    embed = context.chart_embed(
                                        chart_type=self.prep_cfg['chart_type'],
                                        rows_count=len(self.prep_rows),
                                        user_name=modal_interaction.user.display_name,
                                        user_avatar=modal_interaction.user.display_avatar,
                                        config=self.prep_cfg,
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
                                        fallback_file = cog._build_chart_file(self.prep_cfg, labels_mapped, self.prep_values)
                                        await modal_interaction.followup.send(embed=embed, file=fallback_file)

                                    for config_message in session_state.get("config_messages", []):
                                        try:
                                            await config_message.edit(embed=config_done_embed, view=None)
                                        except:
                                            pass

                                except Exception as e:
                                    await modal_interaction.followup.send(f"❌ Error rendering chart: {str(e)}", ephemeral=True)

                        # start iterative modal chain
                        initial_mapping = {}
                        if stored_config.get("column_renames"):
                            # parse previous stored mapping into dict
                            try:
                                for part in [p.strip() for p in stored_config.get("column_renames", "").split(",") if p.strip()]:
                                    if ":" in part:
                                        k, v = part.split(":", 1)
                                        initial_mapping[k.strip()] = v.strip()
                            except Exception:
                                initial_mapping = {}

                        first_modal = ColumnRenameModal(0, initial_mapping, cfg, rows, _columns, labels, values)
                        try:
                            _debug_modal(first_modal, "first_modal")
                            await interaction.response.send_modal(first_modal)
                            return
                        except discord.errors.HTTPException as http_e:
                            print("HTTPException while sending first_modal:", repr(http_e))
                            try:
                                resp = getattr(http_e, 'response', None)
                                if resp is not None:
                                    try:
                                        text = await resp.text()
                                        print("response.text():", text)
                                    except Exception:
                                        print("failed to read resp.text()")
                            except Exception:
                                pass
                            tb = traceback.format_exc()
                            print(tb)
                            # Inform the user (ephemeral) and fall back to rendering without renames
                            try:
                                if interaction.response.is_done():
                                    await interaction.followup.send("⚠️ Column rename modal failed to open; rendered without renames.", ephemeral=True)
                                else:
                                    await interaction.response.send_message("⚠️ Column rename modal failed to open; rendered without renames.", ephemeral=True)
                            except Exception:
                                pass
                            try:
                                file = cog._build_chart_file(cfg, labels, values)
                                embed = context.chart_embed(
                                    chart_type=cfg['chart_type'],
                                    rows_count=len(rows),
                                    user_name=interaction.user.display_name,
                                    user_avatar=interaction.user.display_avatar,
                                    config=cfg,
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
                                for config_message in session_state.get("config_messages", []):
                                    try:
                                        await config_message.edit(embed=discord.Embed(title="⚠️ Mapping unavailable", description="Column rename modal failed to open; rendered without renames.", color=0xFFA500), view=None)
                                    except:
                                        pass
                                return
                            except Exception as e:
                                await interaction.followup.send(f"❌ Error rendering chart: {str(e)}", ephemeral=True)
                                return
                        except Exception:
                            tb = traceback.format_exc()
                            print(tb)
                            try:
                                if interaction.response.is_done():
                                    await interaction.followup.send("⚠️ Column rename modal failed to open; rendered without renames.", ephemeral=True)
                                else:
                                    await interaction.response.send_message("⚠️ Column rename modal failed to open; rendered without renames.", ephemeral=True)
                            except Exception:
                                pass
                            try:
                                file = cog._build_chart_file(cfg, labels, values)
                                embed = context.chart_embed(
                                    chart_type=cfg['chart_type'],
                                    rows_count=len(rows),
                                    user_name=interaction.user.display_name,
                                    user_avatar=interaction.user.display_avatar,
                                    config=cfg,
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
                                for config_message in session_state.get("config_messages", []):
                                    try:
                                        await config_message.edit(embed=discord.Embed(title="⚠️ Mapping unavailable", description="Column rename modal failed to open; rendered without renames.", color=0xFFA500), view=None)
                                    except:
                                        pass
                                return
                            except Exception as e:
                                await interaction.followup.send(f"❌ Error rendering chart: {str(e)}", ephemeral=True)
                                return

                    # No renames required or not a bar chart — render immediately
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

                    for config_message in session_state.get("config_messages", []):
                        try:
                            await config_message.edit(embed=config_done_embed, view=None)
                        except:
                            pass

                except Exception as e:
                    await interaction.response.send_message(f"❌ Error rendering chart: {str(e)}", ephemeral=True)

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
                label="Output Format (png/svg)",
                placeholder="png",
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
                        _debug_modal(modal, "edit_modal")
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
                _debug_modal(modal, "charttype_modal")
                await interaction.response.send_modal(modal)

        class ChartTypeView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)  # 5 minutes
                self.add_item(ChartTypeSelect())
                self.add_item(CancelButton())
            
            async def on_timeout(self):
                """Delete the original message if timeout"""
                if original_message:
                    try:
                        await original_message.delete()
                    except:
                        pass

        return ChartTypeView()

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
