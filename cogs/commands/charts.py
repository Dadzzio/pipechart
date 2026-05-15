import io
import hashlib

import discord
from discord import app_commands
from discord.ext import commands
import matplotlib.colors as mcolors
from datetime import datetime

from cogs.commands.charts_data import (
    extract_series,
    force_chart_type,
    parse_config,
    pick_columns,
    prepare_chart_data,
    read_attachment_text,
    read_csv_rows,
    validate_for_chart,
)
from cogs.commands.charts_rendering import build_chart
from cogs.commands.charts_specs import CHART_SPECS, normalize_config
from objects.context import context


class charts(commands.Cog):
    def __init__(self, bot):
        """Initialize the charts cog."""
        self.bot = bot

    @staticmethod
    def _build_chart_file(cfg: dict, labels: list[str], values: list[float]) -> discord.File:
        """Build a Discord file from rendered chart bytes."""
        chart_bytes = build_chart(cfg, labels, values)
        filename = f"pipechart.{cfg['output']}"
        return discord.File(io.BytesIO(chart_bytes), filename=filename)

    def _init_session_state(self, interaction: discord.Interaction, fixed_chart_type: str | None, *, completed: bool = False) -> dict:
        """Initialize session tracking for a chart run."""
        return {
            "cancelled": False,
            "completed": completed,
            "defer_render": True,
            "config_messages": [],
            "edit_messages": [],
            "advanced_messages": [],
            "config_history": [],
            "data_cache": {},
            "render_cache": {},
            "advanced_config": {},
            "pending_config": None,
            "owner_id": interaction.user.id,
            "preset_chart_type": fixed_chart_type.lower() if fixed_chart_type else None,
            "stored_config": {},
        }

    def _chart_type_options(self) -> list[discord.SelectOption]:
        """Return select options for supported chart types."""
        icon_map = {
            "bar": "📊",
            "line": "📈",
            "pie": "🥧",
        }
        options = []
        for name, spec in CHART_SPECS.items():
            icon = icon_map.get(name, "📋")
            options.append(
                discord.SelectOption(
                    label=f"{icon} {spec.label}",
                    value=name,
                    description=spec.description,
                )
            )
        return options

    async def _ensure_owner(self, interaction: discord.Interaction, session_state: dict) -> bool:
        """Ensure the interaction user matches the session owner."""
        owner_id = session_state.get("owner_id")
        if owner_id is None or interaction.user.id == owner_id:
            return True
        await context.app_error(interaction, "Only the command author can use this panel.")
        return False

    def _parse_output(self, value: str | None) -> str:
        """Normalize output format input to a supported extension."""
        output_fmt = value.lower().strip() if value else "png"
        return output_fmt if output_fmt in ["png", "svg", "pdf"] else "png"

    def _hash_text(self, text: str) -> str:
        """Create a stable hash for cached inputs."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def _get_cached_chart_data(
        self,
        session_state: dict,
        csv_attachment: discord.Attachment,
        json_attachment: discord.Attachment | None,
        chart_type: str | None,
    ) -> tuple[dict, list[dict], list[str], str, str, list[str], list[float]]:
        """Load chart data with caching to avoid re-reading attachments."""
        cache = session_state.setdefault("data_cache", {})

        csv_raw = await read_attachment_text(csv_attachment)
        csv_hash = self._hash_text(csv_raw)

        json_raw = ""
        json_hash = ""
        if json_attachment:
            json_raw = await read_attachment_text(json_attachment)
            json_hash = self._hash_text(json_raw)

        cache_miss = (
            csv_hash != cache.get("csv_hash")
            or json_hash != cache.get("json_hash")
            or not cache.get("rows")
        )

        if cache_miss:
            cfg_base = parse_config(json_raw if json_attachment else None)
            rows, columns = read_csv_rows(csv_raw)
            x_col, y_cols = pick_columns(cfg_base, columns)
            labels, values = extract_series(rows, x_col, y_cols)
            cache.update({
                "csv_hash": csv_hash,
                "json_hash": json_hash,
                "rows": rows,
                "columns": columns,
                "x_col": x_col,
                "y_cols": y_cols,
                "labels": labels,
                "values": values,
                "cfg_base": cfg_base,
            })

        cfg_base = dict(cache.get("cfg_base", {}))
        cfg = force_chart_type(cfg_base, chart_type) if chart_type else dict(cfg_base)
        validate_for_chart(cfg.get("chart_type"), cache["values"])

        return (
            cfg,
            cache["rows"],
            cache["columns"],
            cache["x_col"],
            cache["y_cols"],
            cache["labels"],
            cache["values"],
        )

    def _refresh_series_from_config(
        self,
        cfg: dict,
        rows: list[dict],
        columns: list[str],
    ) -> tuple[list[str], list[dict]]:
        """Recompute chart labels and series after config changes."""
        x_col, y_cols = pick_columns(cfg, columns)
        labels, values = extract_series(rows, x_col, y_cols)
        cfg["x_column"] = x_col
        cfg["y_columns"] = y_cols
        cfg["y_column"] = y_cols[0] if y_cols else None
        return labels, values

    def _y_columns_placeholder(self, columns: list[str], x_col: str | None = None) -> str:
        """Build a readable y_columns placeholder from CSV columns."""
        y_columns = [str(column).strip() for column in columns if str(column).strip()]
        if x_col and y_columns and y_columns[0] == x_col:
            y_columns = y_columns[1:]
        if x_col and x_col in y_columns:
            y_columns = [column for column in y_columns if column != x_col]
        return ", ".join(y_columns[:3]) if y_columns else "product_a, product_b, product_c"

    async def _y_columns_placeholder_from_csv(self, csv_file: discord.Attachment, session_state: dict) -> str:
        """Build a y_columns placeholder from the uploaded CSV."""
        cached_columns = session_state.get("data_cache", {}).get("columns", [])
        cached_x_col = session_state.get("data_cache", {}).get("x_col")
        if cached_columns:
            return self._y_columns_placeholder(cached_columns, cached_x_col)

        csv_raw = await read_attachment_text(csv_file)
        _rows, columns = read_csv_rows(csv_raw)
        x_col = columns[0] if columns else None
        return self._y_columns_placeholder(columns, x_col)

    def _get_render_cache_key(self, session_state: dict, cfg: dict) -> str:
        """Build a render cache key using data and config state."""
        data_cache = session_state.get("data_cache", {})
        csv_hash = data_cache.get("csv_hash", "")
        json_hash = data_cache.get("json_hash", "")
        normalized = self._normalize_config_for_history(cfg)
        config_key = str(sorted(normalized.items()))
        config_hash = self._hash_text(config_key)
        return f"{csv_hash}:{json_hash}:{config_hash}"

    def _build_chart_file_cached(self, session_state: dict, cfg: dict, labels: list[str], values: list[float]) -> discord.File:
        """Build a chart file using cached render bytes when possible."""
        cache = session_state.setdefault("render_cache", {})
        key = self._get_render_cache_key(session_state, cfg)
        if key not in cache:
            cache[key] = build_chart(cfg, labels, values)
        filename = f"pipechart.{cfg['output']}"
        return discord.File(io.BytesIO(cache[key]), filename=filename)

    def _sync_advanced_config(self, session_state: dict, cfg: dict) -> None:
        """Initialize advanced config defaults from the current config."""
        advanced = session_state.setdefault("advanced_config", {})
        if advanced:
            return
        advanced.update({
            "dpi": cfg.get("dpi"),
            "figsize": cfg.get("figsize"),
            "grid": cfg.get("grid", True),
            "style": cfg.get("style", ""),
            "line_width": cfg.get("line_width", 2.0),
            "mean_line": cfg.get("mean_line", False),
            "mean_color": cfg.get("mean_color", "red"),
            "mean_style": cfg.get("mean_style", "solid"),
            "output": cfg.get("output", "png"),
        })

    def _apply_advanced_config(self, cfg: dict, session_state: dict) -> dict:
        """Apply advanced options stored in session state to a config."""
        advanced = session_state.get("advanced_config", {})
        if not advanced:
            return cfg
        merged = dict(cfg)
        merged.update(advanced)
        return normalize_config(merged)

    def _create_advanced_topic_select(self, session_state: dict) -> discord.ui.Select:
        """Create a Select for choosing a single advanced topic to configure."""
        cog = self

        class AdvancedTopicSelect(discord.ui.Select):
            def __init__(self):
                """Initialize the advanced topic selector."""
                # Determine current chart type to filter options
                pending_cfg = session_state.get("pending_config", {})
                chart_type = pending_cfg.get("chart_type", "").lower() if pending_cfg else ""
                
                # Build options, excluding mean_line for pie charts
                options = []
                if chart_type != "pie":
                    options.extend([
                        discord.SelectOption(label="Mean Line", value="mean_line", emoji="📊"),
                        discord.SelectOption(label="Grid", value="grid", emoji="📐"),
                        ])
                options.extend([
                    discord.SelectOption(label="DPI", value="dpi", emoji="🖨️"),
                    discord.SelectOption(label="Style", value="style", emoji="🎨"),
                    discord.SelectOption(label="Line Width", value="line_width", emoji="📏"),
                    discord.SelectOption(label="Figure Size", value="figsize", emoji="📦"),
                    discord.SelectOption(label="Output Format", value="output", emoji="💾"),
                ])
                options.sort(key=lambda option: option.label.lower())
                
                super().__init__(
                    placeholder="Select topics to configure",
                    min_values=1,
                    max_values=1,
                    options=options,
                )

            async def callback(self, interaction: discord.Interaction):
                """Open modal for the first selected topic."""
                selected_topics = self.values
                if not selected_topics:
                    return

                first_topic = selected_topics[0]
                modal = cog._create_topic_modal(first_topic, session_state)
                await interaction.response.send_modal(modal)

        return AdvancedTopicSelect()

    def _create_topic_modal(self, topic: str, session_state: dict) -> discord.ui.Modal:
        """Create a modal for a specific advanced topic."""
        defaults = session_state.get("advanced_config", {})

        if topic == "mean_line":
            class MeanLineModal(discord.ui.Modal, title="Mean Line Config"):
                enabled_input = discord.ui.TextInput(
                    label="Enable mean line (true/false)",
                    placeholder="false",
                    required=False,
                    default=str(defaults.get("mean_line", False)).lower(),
                )
                color_input = discord.ui.TextInput(
                    label="Line color (matplotlib)",
                    placeholder="red",
                    required=False,
                    default=str(defaults.get("mean_color", "red")),
                )
                style_input = discord.ui.TextInput(
                    label="Line style (solid/dotted/dashed)",
                    placeholder="solid",
                    required=False,
                    default=str(defaults.get("mean_style", "solid")),
                )

                async def on_submit(self, modal_interaction: discord.Interaction):
                    raw_cfg = {
                        "mean_line": self.enabled_input.value,
                        "mean_color": self.color_input.value,
                        "mean_style": self.style_input.value,
                    }
                    normalized = normalize_config(raw_cfg)
                    session_state.setdefault("advanced_config", {}).update({
                        "mean_line": normalized.get("mean_line", False),
                        "mean_color": normalized.get("mean_color", "red"),
                        "mean_style": normalized.get("mean_style", "solid"),
                    })
                    await context.app_ok(modal_interaction, "Mean line saved.", ephemeral=True)

            return MeanLineModal()

        elif topic == "dpi":
            class DPIModal(discord.ui.Modal, title="DPI Settings"):
                dpi_input = discord.ui.TextInput(
                    label="DPI (resolution)",
                    placeholder="150",
                    required=False,
                    default=str(defaults.get("dpi", 150)),
                )

                async def on_submit(self, modal_interaction: discord.Interaction):
                    raw_cfg = {"dpi": self.dpi_input.value}
                    normalized = normalize_config(raw_cfg)
                    session_state.setdefault("advanced_config", {})["dpi"] = normalized.get("dpi", 150)
                    await context.app_ok(modal_interaction, "DPI saved.", ephemeral=True)

            return DPIModal()

        elif topic == "grid":
            class GridModal(discord.ui.Modal, title="Grid Settings"):
                grid_input = discord.ui.TextInput(
                    label="Enable grid (true/false)",
                    placeholder="true",
                    required=False,
                    default=str(defaults.get("grid", True)).lower(),
                )

                async def on_submit(self, modal_interaction: discord.Interaction):
                    raw_cfg = {"grid": self.grid_input.value}
                    normalized = normalize_config(raw_cfg)
                    session_state.setdefault("advanced_config", {})["grid"] = normalized.get("grid", True)
                    await context.app_ok(modal_interaction, "Grid saved.", ephemeral=True)

            return GridModal()

        elif topic == "style":
            class StyleModal(discord.ui.Modal, title="Matplotlib Style"):
                style_input = discord.ui.TextInput(
                    label="Style name (e.g., seaborn, ggplot)",
                    placeholder="",
                    required=False,
                    default=str(defaults.get("style", "")),
                )

                async def on_submit(self, modal_interaction: discord.Interaction):
                    raw_cfg = {"style": self.style_input.value}
                    normalized = normalize_config(raw_cfg)
                    session_state.setdefault("advanced_config", {})["style"] = normalized.get("style", "")
                    await context.app_ok(modal_interaction, "Style saved.", ephemeral=True)

            return StyleModal()

        elif topic == "line_width":
            class LineWidthModal(discord.ui.Modal, title="Line Width"):
                line_width_input = discord.ui.TextInput(
                    label="Line width (float)",
                    placeholder="2.0",
                    required=False,
                    default=str(defaults.get("line_width", 2.0)),
                )

                async def on_submit(self, modal_interaction: discord.Interaction):
                    raw_cfg = {"line_width": self.line_width_input.value}
                    normalized = normalize_config(raw_cfg)
                    session_state.setdefault("advanced_config", {})["line_width"] = normalized.get("line_width", 2.0)
                    await context.app_ok(modal_interaction, "Line width saved.", ephemeral=True)

            return LineWidthModal()

        elif topic == "figsize":
            def _stringify_figsize(value) -> str:
                if isinstance(value, (list, tuple)) and len(value) == 2:
                    return f"{value[0]}, {value[1]}"
                return "8, 5"

            class FigsizeModal(discord.ui.Modal, title="Figure Size"):
                figsize_input = discord.ui.TextInput(
                    label="Size (width, height)",
                    placeholder="8, 5",
                    required=False,
                    default=_stringify_figsize(defaults.get("figsize", [8, 5])),
                )

                async def on_submit(self, modal_interaction: discord.Interaction):
                    raw_cfg = {"figsize": self.figsize_input.value}
                    normalized = normalize_config(raw_cfg)
                    session_state.setdefault("advanced_config", {})["figsize"] = normalized.get("figsize", [8, 5])
                    await context.app_ok(modal_interaction, "Figure size saved.", ephemeral=True)

            return FigsizeModal()

        elif topic == "output":
            class OutputModal(discord.ui.Modal, title="Output Format"):
                output_input = discord.ui.TextInput(
                    label="Output Format (png/svg/pdf)",
                    placeholder="png, svg, or pdf",
                    max_length=3,
                    required=False,
                    default=str(defaults.get("output", "png")),
                )

                async def on_submit(self, modal_interaction: discord.Interaction):
                    raw_cfg = {"output": self.output_input.value}
                    normalized = normalize_config(raw_cfg)
                    session_state.setdefault("advanced_config", {})["output"] = normalized.get("output", "png")
                    await context.app_ok(modal_interaction, "Output format saved.", ephemeral=True)

            return OutputModal()

        return None

    def _sync_stored_config(self, session_state: dict, cfg: dict) -> None:
        """Sync stored defaults from a config dict for later editing."""
        stored_config = session_state.setdefault("stored_config", {})
        colors = cfg.get("colors")
        title_value = cfg.get("title")
        if title_value is None:
            title_value = ""
        else:
            title_value = str(title_value).strip()
        stored_config.update({
            "chart_type": cfg.get("chart_type"),
            "title": title_value,
            "x_label": cfg.get("x_label", ""),
            "y_label": cfg.get("y_label", ""),
            "color": cfg.get("color", "#4E79A7"),
            "colors": ", ".join(colors) if isinstance(colors, list) else "",
            "y_columns": ", ".join(cfg.get("y_columns", [])) if isinstance(cfg.get("y_columns"), list) else str(cfg.get("y_columns") or ""),
            "dpi": cfg.get("dpi"),
            "figsize": cfg.get("figsize"),
            "grid": cfg.get("grid"),
            "style": cfg.get("style"),
            "line_width": cfg.get("line_width"),
            "mean_line": cfg.get("mean_line", False),
            "mean_color": cfg.get("mean_color", "red"),
            "mean_style": cfg.get("mean_style", "solid"),
        })
        self._sync_advanced_config(session_state, cfg)

    def _apply_stored_defaults(self, modal, chart_type: str, stored_config: dict) -> None:
        """Apply stored defaults to modal inputs for a chart type."""
        if not stored_config or stored_config.get("chart_type") != chart_type:
            return

        modal.title_input.default = stored_config.get("title", "")
        if chart_type == "pie" and hasattr(modal, "colors_input"):
            modal.colors_input.default = stored_config.get("colors", "")
        elif chart_type != "pie":
            modal.x_label_input.default = stored_config.get("x_label", "")
            modal.y_label_input.default = stored_config.get("y_label", "")
            if hasattr(modal, "y_columns_input"):
                modal.y_columns_input.default = stored_config.get("y_columns", "")
            modal.color_input.default = stored_config.get("color", "#4E79A7")

    def _normalize_config_for_history(self, cfg: dict) -> dict:
        """Normalize config fields for history comparisons."""
        title_value = cfg.get("title")
        if title_value is None:
            title_value = ""
        else:
            title_value = str(title_value).strip()

        colors_value = cfg.get("colors")
        if colors_value is None:
            colors_value = []
        elif isinstance(colors_value, list):
            colors_value = [str(v).strip() for v in colors_value if str(v).strip()]
        else:
            colors_value = [c.strip() for c in str(colors_value).split(",") if c.strip()]

        dpi_value = cfg.get("dpi")
        dpi_text = "" if dpi_value is None else str(dpi_value).strip()

        figsize_value = cfg.get("figsize")
        if isinstance(figsize_value, (list, tuple)) and len(figsize_value) == 2:
            figsize_text = f"{figsize_value[0]}, {figsize_value[1]}"
        else:
            figsize_text = str(figsize_value or "").strip()

        grid_value = cfg.get("grid")
        grid_text = "" if grid_value is None else str(grid_value).strip()

        style_value = cfg.get("style")
        style_text = "" if style_value is None else str(style_value).strip()

        line_width_value = cfg.get("line_width")
        line_width_text = "" if line_width_value is None else str(line_width_value).strip()

        y_columns_value = cfg.get("y_columns")
        if y_columns_value is None:
            y_columns_text = ""
        elif isinstance(y_columns_value, list):
            y_columns_text = ", ".join([str(v).strip() for v in y_columns_value if str(v).strip()])
        else:
            y_columns_text = str(y_columns_value).strip()

        mean_line_value = cfg.get("mean_line")
        mean_line_text = "" if mean_line_value is None else str(mean_line_value).strip()

        mean_color_value = cfg.get("mean_color")
        mean_color_text = "" if mean_color_value is None else str(mean_color_value).strip()

        mean_style_value = cfg.get("mean_style")
        mean_style_text = "" if mean_style_value is None else str(mean_style_value).strip()

        return {
            "chart_type": str(cfg.get("chart_type") or "").strip(),
            "title": title_value,
            "x_label": str(cfg.get("x_label") or "").strip(),
            "y_label": str(cfg.get("y_label") or "").strip(),
            "color": str(cfg.get("color") or "").strip(),
            "output": str(cfg.get("output") or "").strip(),
            "colors": colors_value,
            "dpi": dpi_text,
            "figsize": figsize_text,
            "grid": grid_text,
            "style": style_text,
            "line_width": line_width_text,
            "y_columns": y_columns_text,
            "mean_line": mean_line_text,
            "mean_color": mean_color_text,
            "mean_style": mean_style_text,
        }

    def _append_config_history(self, session_state: dict, cfg: dict) -> None:
        """Append a config snapshot if it differs from the last entry."""
        history = session_state.setdefault("config_history", [])
        normalized = self._normalize_config_for_history(cfg)
        if history and self._is_same_config(normalized, history[-1]):
            return
        history.append({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            **normalized,
        })

    def _is_same_config(self, cfg: dict, stored_config: dict) -> bool:
        """Check if a config matches the last stored configuration."""
        def _norm_text(value) -> str:
            if value is None:
                return ""
            return str(value).strip()

        def _norm_colors(value) -> str:
            if value is None:
                return ""
            if isinstance(value, list):
                return ", ".join([str(v).strip() for v in value if str(v).strip()])
            return str(value).strip()

        return (
            _norm_text(cfg.get("chart_type")) == _norm_text(stored_config.get("chart_type"))
            and _norm_text(cfg.get("title")) == _norm_text(stored_config.get("title"))
            and _norm_text(cfg.get("x_label")) == _norm_text(stored_config.get("x_label"))
            and _norm_text(cfg.get("y_label")) == _norm_text(stored_config.get("y_label"))
            and _norm_text(cfg.get("color")) == _norm_text(stored_config.get("color"))
            and _norm_text(cfg.get("output")) == _norm_text(stored_config.get("output"))
            and _norm_colors(cfg.get("colors")) == _norm_colors(stored_config.get("colors"))
            and _norm_text(cfg.get("y_columns")) == _norm_text(stored_config.get("y_columns"))
            and _norm_text(cfg.get("dpi")) == _norm_text(stored_config.get("dpi"))
            and _norm_text(cfg.get("figsize")) == _norm_text(stored_config.get("figsize"))
            and _norm_text(cfg.get("grid")) == _norm_text(stored_config.get("grid"))
            and _norm_text(cfg.get("style")) == _norm_text(stored_config.get("style"))
            and _norm_text(cfg.get("line_width")) == _norm_text(stored_config.get("line_width"))
            and _norm_text(cfg.get("mean_line")) == _norm_text(stored_config.get("mean_line"))
            and _norm_text(cfg.get("mean_color")) == _norm_text(stored_config.get("mean_color"))
            and _norm_text(cfg.get("mean_style")) == _norm_text(stored_config.get("mean_style"))
        )

    async def _update_tracked_panel_messages(
        self,
        interaction: discord.Interaction,
        session_state: dict,
        embed: discord.Embed,
        *,
        clear_view: bool = True,
        view: discord.ui.View | None = None,
    ) -> bool:
        """Update tracked config/edit panel messages with an embed."""
        updated_any = False
        kwargs = {"embed": embed}
        if view is not None:
            kwargs["view"] = view
        elif clear_view:
            kwargs["view"] = None
            
        combined = session_state.get("config_messages", []) + session_state.get("edit_messages", [])
        for tracked_message in combined:
            try:
                await tracked_message.edit(**kwargs)
                updated_any = True
            except Exception:
                try:
                    await interaction.followup.edit_message(tracked_message.id, **kwargs)
                    updated_any = True
                except Exception:
                    pass

        return updated_any

    async def _update_chart_message(
        self,
        interaction: discord.Interaction,
        message: discord.Message | None,
        session_state: dict | None,
        cfg: dict,
        labels: list[str],
        values: list[float],
        embed: discord.Embed,
        view: discord.ui.View | None,
    ) -> bool:
        """Update a chart message with a fresh file attachment."""
        if not message:
            return False

        try:
            if session_state is not None:
                fresh_file = self._build_chart_file_cached(session_state, cfg, labels, values)
            else:
                fresh_file = self._build_chart_file(cfg, labels, values)
            await message.edit(embed=embed, attachments=[fresh_file], view=view)
            if view is not None:
                view.message = message
            return True
        except Exception:
            try:
                if session_state is not None:
                    fresh_file = self._build_chart_file_cached(session_state, cfg, labels, values)
                else:
                    fresh_file = self._build_chart_file(cfg, labels, values)
                await interaction.followup.edit_message(message.id, embed=embed, attachments=[fresh_file], view=view)
                if view is not None:
                    view.message = message
                return True
            except Exception:
                return False

    def _build_config_panel_embed(self, preset_name: str, fixed_chart_type: str | None) -> discord.Embed:
        """Build the configuration panel embed for chart setup."""
        description = (
            f"Configure the {preset_name} chart below."
            if fixed_chart_type
            else "Select chart type and configure it in the next step"
        )
        embed = discord.Embed(
            title="📊 Chart Wizard",
            description=description,
            color=0x4E79A7,
        )
        embed.add_field(
            name="⏱️ Timeout",
            value="Configuration window closes in 5 minutes. If no selection is made, the build message will be deleted.",
            inline=False,
        )
        return embed

    async def _send_panel_message(
        self,
        interaction: discord.Interaction,
        embed: discord.Embed,
        view: discord.ui.View,
        session_state: dict,
        store_key: str,
    ) -> None:
        """Send an ephemeral panel message and track it in session state."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        panel_message = await interaction.followup.send(embed=embed, view=view, ephemeral=True, wait=True)
        if panel_message:
            session_state.setdefault(store_key, []).append(panel_message)

    async def _handle_modal_submit(
        self,
        interaction: discord.Interaction,
        *,
        csv_file: discord.Attachment,
        config_file: discord.Attachment | None,
        chart_type: str,
        session_state: dict,
        original_message: discord.Message | None,
        fixed_chart_type: str | None,
        mode: str,
        title: str | None,
        x_label: str | None,
        y_label: str | None,
        color: str | None,
        output: str | None,
        colors: str | None,
        y_columns: str | None,
    ) -> None:
        """Handle modal submission and render/update charts."""
        if not await self._ensure_owner(interaction, session_state):
            return
        if session_state.get("cancelled"):
            await context.app_error(interaction, "Configuration was cancelled. Start /chart_render again.")
            return

        await interaction.response.defer()

        async def _handle_error(err_text: str) -> None:
            """Send a user-visible error for config/edit flows."""
            if mode == "config":
                error_embed = discord.Embed(
                    color=0xF54336,
                    description=f"{interaction.client.emotes['main']['no']} {err_text}",
                )
                if not await self._update_tracked_panel_messages(interaction, session_state, error_embed):
                    await context.app_error(interaction, err_text)
            else:
                await context.app_error(interaction, err_text)

        try:
            cfg, rows, _columns, _x_col, _y_col, labels, values = await self._get_cached_chart_data(
                session_state,
                csv_file,
                config_file,
                chart_type,
            )

            if mode == "edit":
                if title is not None:
                    cfg["title"] = title.strip()
            else:
                if title:
                    cfg["title"] = title

            if chart_type == "pie":
                parsed_colors = []
                invalid_colors = []
                if colors:
                    parsed_colors = [c.strip() for c in colors.split(",") if c.strip()]
                    for c in parsed_colors:
                        if not mcolors.is_color_like(c):
                            invalid_colors.append(c)
                    if invalid_colors:
                        err_text = f"Invalid color(s): {', '.join(invalid_colors)}. Use color names or hex like '#4E79A7'."
                        await _handle_error(err_text)
                        return
                    if parsed_colors:
                        cfg["colors"] = parsed_colors
            else:
                if y_columns:
                    parsed_y_columns = [col.strip() for col in y_columns.split(",") if col.strip()]
                    if parsed_y_columns:
                        cfg["y_columns"] = parsed_y_columns
                        cfg["y_column"] = parsed_y_columns[0]
                if mode == "edit":
                    if x_label is not None:
                        cfg["x_label"] = x_label.strip()
                    if y_label is not None:
                        cfg["y_label"] = y_label.strip()
                else:
                    if x_label:
                        cfg["x_label"] = x_label
                    if y_label:
                        cfg["y_label"] = y_label
                if mode == "edit":
                    if color is not None:
                        val = color.strip()
                        if not val:
                            cfg["color"] = "#4E79A7"
                        else:
                            if not mcolors.is_color_like(val):
                                await _handle_error(f"Invalid color value: {val}. Use a color name or hex like '#4E79A7'.")
                                return
                            cfg["color"] = val
                else:
                    if color:
                        val = color.strip()
                        if not mcolors.is_color_like(val):
                            await _handle_error(f"Invalid color value: {val}. Use a color name or hex like '#4E79A7'.")
                            return
                        cfg["color"] = val

                labels, values = self._refresh_series_from_config(cfg, rows, _columns)
            cfg = self._apply_advanced_config(cfg, session_state)

            if mode == "edit":
                stored_config = session_state.get("stored_config", {})
                if self._is_same_config(cfg, stored_config):
                    await context.app_ok(interaction, "No changes detected. Chart was not re-rendered.", ephemeral=True)
                    return
            self._sync_stored_config(session_state, cfg)

            if session_state.get("defer_render"):
                session_state["pending_config"] = dict(cfg)
                
                await context.app_ok(interaction, "Main settings saved.", ephemeral=True)
                return

            embed = context.chart_embed(
                chart_type=cfg['chart_type'],
                rows_count=len(rows),
                user_name=interaction.user.display_name,
                user_avatar=interaction.user.display_avatar,
                config=cfg,
            )

            edit_view = self._create_edit_view(
                session_state,
                csv_file=csv_file,
                config_file=config_file,
                fixed_chart_type=fixed_chart_type,
            )

            if mode == "config":
                success_embed = discord.Embed(
                    title="✅ Chart rendered!",
                    description="Configuration submitted successfully.",
                    color=0x37EC2A,
                )

                public_updated = False
                if original_message:
                    public_updated = await self._update_chart_message(
                        interaction,
                        original_message,
                        session_state,
                        cfg,
                        labels,
                        values,
                        embed,
                        edit_view,
                    )

                if not public_updated:
                    fallback_file = self._build_chart_file_cached(session_state, cfg, labels, values)
                    sent = await interaction.followup.send(embed=embed, file=fallback_file, view=edit_view, wait=True)
                    if sent:
                        if edit_view:
                            edit_view.message = sent
                        session_state.setdefault("config_messages", []).append(sent)

                session_state["completed"] = True
                await self._update_tracked_panel_messages(interaction, session_state, success_embed)
                self._append_config_history(session_state, cfg)
            else:
                success_embed = discord.Embed(
                    title="✅ Chart updated!",
                    description="Chart has been re-rendered with your new settings.",
                    color=0x37EC2A,
                )

                target_message = interaction.message or original_message
                updated = await self._update_chart_message(
                    interaction,
                    target_message,
                    session_state,
                    cfg,
                    labels,
                    values,
                    embed,
                    edit_view,
                )
                if not updated:
                    await context.app_error(interaction, "Could not update the original chart message.")
                    return

                await self._update_tracked_panel_messages(interaction, session_state, success_embed)
                if fixed_chart_type:
                    await context.app_ok(interaction, "Chart rendered successfully.", ephemeral=True)
                self._append_config_history(session_state, cfg)
        except Exception as error:
            await _handle_error(f"Error rendering chart: {str(error)}")

    def _create_chart_modal(
        self,
        *,
        chart_type: str,
        csv_file: discord.Attachment,
        config_file: discord.Attachment | None,
        session_state: dict,
        original_message: discord.Message | None,
        fixed_chart_type: str | None,
        mode: str,
        y_columns_placeholder: str = "product_a, product_b",
    ) -> discord.ui.Modal:
        """Create a configuration or edit modal for a chart type."""
        cog = self
        chart_type = chart_type.lower()
        stored_config = session_state.setdefault("stored_config", {})
        is_edit = mode == "edit"

        if chart_type == "pie":
            modal_title = "Re-configure Pie Chart" if is_edit else "Configure Pie Chart"

            class PieConfigModal(discord.ui.Modal, title=modal_title):
                title_input = discord.ui.TextInput(
                    label="Chart Title",
                    placeholder="Enter chart title",
                    max_length=100,
                    required=False,
                    default="",
                )
                colors_input = discord.ui.TextInput(
                    label="Slice colors (comma-separated)",
                    placeholder="red, #4E79A7, 0.6, C2",
                    max_length=250,
                    required=False,
                )

                async def on_submit(self, interaction: discord.Interaction):
                    """Handle pie modal submission."""
                    await cog._handle_modal_submit(
                        interaction,
                        csv_file=csv_file,
                        config_file=config_file,
                        chart_type=chart_type,
                        session_state=session_state,
                        original_message=original_message,
                        fixed_chart_type=fixed_chart_type,
                        mode=mode,
                        title=self.title_input.value,
                        x_label=None,
                        y_label=None,
                        color=None,
                        output=None,
                        colors=self.colors_input.value,
                        y_columns=None,
                    )

            modal = PieConfigModal()
        else:
            modal_title = "Re-configure Chart" if is_edit else "Configure Your Chart"

            class ConfigModal(discord.ui.Modal, title=modal_title):
                title_input = discord.ui.TextInput(
                    label="Chart Title",
                    placeholder="Enter chart title",
                    max_length=100,
                    required=False,
                    default="",
                )
                x_label_input = discord.ui.TextInput(
                    label="X Axis Label",
                    placeholder="Leave empty for default",
                    max_length=100,
                    required=False,
                )
                y_label_input = discord.ui.TextInput(
                    label="Y Axis Label",
                    placeholder="Leave empty for default",
                    max_length=100,
                    required=False,
                )
                y_columns_input = discord.ui.TextInput(
                    label="Y Columns (comma-separated)",
                    placeholder=y_columns_placeholder,
                    max_length=250,
                    required=False,
                )
                color_input = discord.ui.TextInput(
                    label="Color (any matplotlib value)",
                    placeholder="#4E79A7, red, 0.5",
                    max_length=50,
                    required=False,
                    default="#4E79A7",
                )

                async def on_submit(self, interaction: discord.Interaction):
                    """Handle non-pie modal submission."""
                    await cog._handle_modal_submit(
                        interaction,
                        csv_file=csv_file,
                        config_file=config_file,
                        chart_type=chart_type,
                        session_state=session_state,
                        original_message=original_message,
                        fixed_chart_type=fixed_chart_type,
                        mode=mode,
                        title=self.title_input.value,
                        x_label=self.x_label_input.value,
                        y_label=self.y_label_input.value,
                        color=self.color_input.value,
                        output=None,
                        colors=None,
                        y_columns=self.y_columns_input.value,
                    )

            modal = ConfigModal()

        cog._apply_stored_defaults(modal, chart_type, stored_config)
        return modal

    def _create_edit_panel_view(
        self,
        csv_file: discord.Attachment,
        config_file: discord.Attachment | None,
        original_message: discord.Message | None,
        session_state: dict,
        fixed_chart_type: str | None,
    ) -> discord.ui.View:
        """Create the ephemeral panel view for editing a chart."""
        cog = self

        class MainSettingsButton(discord.ui.Button):
            def __init__(self):
                """Initialize the Main settings button for fixed chart types."""
                super().__init__(style=discord.ButtonStyle.primary, label="Main settings", emoji="🛠️")

            async def callback(self, interaction: discord.Interaction):
                """Open a modal for the fixed chart type."""
                if not await cog._ensure_owner(interaction, session_state):
                    return
                if session_state.get("cancelled"):
                    await context.app_error(interaction, "Configuration was cancelled.")
                    return

                modal = cog._create_chart_modal(
                    chart_type=fixed_chart_type,
                    csv_file=csv_file,
                    config_file=config_file,
                    session_state=session_state,
                    original_message=original_message,
                    fixed_chart_type=fixed_chart_type,
                    mode="edit",
                    y_columns_placeholder=await cog._y_columns_placeholder_from_csv(csv_file, session_state),
                )
                await interaction.response.send_modal(modal)

        class EditChartTypeSelect(discord.ui.Select):
            def __init__(self):
                """Initialize chart type selector for edit panel."""
                pending_cfg = session_state.get("pending_config", {})
                current_chart_type = pending_cfg.get("chart_type", "").lower() if pending_cfg else ""
                super().__init__(
                    placeholder="Select chart type",
                    min_values=1,
                    max_values=1,
                    options=cog._chart_type_options(),
                )

            async def callback(self, select_interaction: discord.Interaction):
                """Open a modal for the selected chart type."""
                if not await cog._ensure_owner(select_interaction, session_state):
                    return
                if session_state.get("cancelled"):
                    await context.app_error(select_interaction, "Configuration was cancelled.")
                    return

                chart_type = self.values[0]
                modal = cog._create_chart_modal(
                    chart_type=chart_type,
                    csv_file=csv_file,
                    config_file=config_file,
                    session_state=session_state,
                    original_message=original_message,
                    fixed_chart_type=None,
                    mode="edit",
                    y_columns_placeholder=await cog._y_columns_placeholder_from_csv(csv_file, session_state),
                )
                await select_interaction.response.send_modal(modal)

        class AdvancedButton(discord.ui.Button):
            def __init__(self):
                """Initialize the Advanced options button."""
                super().__init__(style=discord.ButtonStyle.secondary, label="Advanced", emoji="⚙️")

            async def callback(self, interaction: discord.Interaction):
                """Open advanced options panel."""
                if not await cog._ensure_owner(interaction, session_state):
                    return
                if session_state.get("cancelled"):
                    await context.app_error(interaction, "Configuration was cancelled.")
                    return
                advanced_select = next(
                    (
                        item for item in self.view.children
                        if isinstance(item, discord.ui.Select)
                        and getattr(item, "placeholder", "") == "Select topics to configure"
                    ),
                    None,
                )
                if advanced_select:
                    self.view.remove_item(advanced_select)
                    self.label = "Advanced"
                else:
                    self.view.add_item(cog._create_advanced_topic_select(session_state))
                    self.label = "Hide Advanced"
                await interaction.response.edit_message(view=self.view)

        class MeanLineButton(discord.ui.Button):
            def __init__(self):
                """Initialize the Mean Line config button."""
                super().__init__(style=discord.ButtonStyle.secondary, label="Mean Line", emoji="📊")

            async def callback(self, interaction: discord.Interaction):
                """Open mean line configuration modal."""
                if not await cog._ensure_owner(interaction, session_state):
                    return
                if session_state.get("cancelled"):
                    await context.app_error(interaction, "Configuration was cancelled.")
                    return
                modal = cog._create_mean_line_modal(session_state)
                await interaction.response.send_modal(modal)

        class RenderButton(discord.ui.Button):
            def __init__(self):
                """Initialize the Render chart button."""
                super().__init__(style=discord.ButtonStyle.success, label="Render chart", emoji="✅")

            async def callback(self, interaction: discord.Interaction):
                """Render chart with pending changes."""
                if not await cog._ensure_owner(interaction, session_state):
                    return
                if session_state.get("cancelled"):
                    await context.app_error(interaction, "Configuration was cancelled.")
                    return

                pending_cfg = session_state.get("pending_config")
                if not pending_cfg:
                    stored = session_state.get("stored_config", {})
                    if not stored:
                        await context.app_error(interaction, "No saved settings yet. Click Main settings first.")
                        return
                    pending_cfg = stored

                await interaction.response.defer()

                cfg, rows, _columns, _x_col, _y_col, labels, values = await cog._get_cached_chart_data(
                    session_state,
                    csv_file,
                    config_file,
                    pending_cfg.get("chart_type"),
                )
                cfg.update(pending_cfg)
                labels, values = cog._refresh_series_from_config(cfg, rows, _columns)
                cfg = cog._apply_advanced_config(cfg, session_state)
                cog._sync_stored_config(session_state, cfg)

                embed = context.chart_embed(
                    chart_type=cfg['chart_type'],
                    rows_count=len(rows),
                    user_name=interaction.user.display_name,
                    user_avatar=interaction.user.display_avatar,
                    config=cfg,
                )
                
                updated = await cog._update_chart_message(
                    interaction,
                    original_message,
                    session_state,
                    cfg,
                    labels,
                    values,
                    embed,
                    cog._create_edit_view(session_state, csv_file, config_file, fixed_chart_type),
                )
                if updated:
                    success_embed = discord.Embed(
                        title="✅ Chart updated!",
                        description="Chart has been re-rendered with your new settings.",
                        color=0x37EC2A,
                    )
                    await cog._update_tracked_panel_messages(interaction, session_state, success_embed)
                    cog._append_config_history(session_state, cfg)

        class DeleteButton(discord.ui.Button):
            def __init__(self):
                """Initialize the Delete button for the rendered chart."""
                super().__init__(style=discord.ButtonStyle.danger, label="Delete", emoji="🗑️")

            async def callback(self, interaction: discord.Interaction):
                """Prompt for confirmation before deleting the rendered chart."""
                if not await cog._ensure_owner(interaction, session_state):
                    return

                chart_message = interaction.message

                class ConfirmDeleteView(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=60)
                        self.message = None

                    @discord.ui.button(label="Yes, delete", style=discord.ButtonStyle.danger, emoji="🗑️")
                    async def confirm(self, confirm_interaction: discord.Interaction, button: discord.ui.Button):
                        session_state["cancelled"] = True
                        try:
                            if original_message:
                                await original_message.delete()
                        except Exception:
                            pass

                        combined_panels = session_state.get("config_messages", []) + session_state.get("edit_messages", [])
                        for panel_msg in combined_panels:
                            try:
                                await panel_msg.delete()
                            except Exception:
                                pass

                        if chart_message:
                            try:
                                await chart_message.delete()
                            except Exception:
                                pass

                    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
                    async def cancel(self, cancel_interaction: discord.Interaction, button: discord.ui.Button):
                        await cancel_interaction.response.edit_message(
                            content="Deletion cancelled.",
                            embed=None,
                            view=None,
                        )

                    async def on_timeout(self):
                        for item in self.children:
                            item.disabled = True
                        if self.message:
                            try:
                                timeout_embed = discord.Embed(
                                    title="⏱️ Confirmation Timed Out",
                                    description="The confirmation prompt has expired. The chart and panels remain unchanged.",
                                    color=0xF59E0B,
                                )
                                await self.message.edit(embed=timeout_embed, view=self, content=None)
                            except Exception:
                                pass

                confirm_embed = discord.Embed(
                    title="🗑️ Are you sure?",
                    description="This will permanently delete the chart message and close all configuration panels.",
                    color=0xF54336,
                )

                view = ConfirmDeleteView()
                await interaction.response.send_message(embed=confirm_embed, view=view, ephemeral=True)
                try:
                    view.message = await interaction.original_response()
                except Exception:
                    pass

        class EditPanelContainerView(discord.ui.View):
            def __init__(self):
                """Initialize the edit panel view container."""
                super().__init__(timeout=300)
                if fixed_chart_type:
                    self.add_item(MainSettingsButton())
                else:
                    self.add_item(EditChartTypeSelect())
                self.add_item(RenderButton())
                self.add_item(AdvancedButton())

            async def on_timeout(self):
                """Disable the edit panel when timeout occurs."""
                for item in self.children:
                    item.disabled = True
                
                timeout_embed = discord.Embed(
                    title="⏱️ Timeout Expired",
                    description="The edit panel has timed out. Please run the command again to start a new session.",
                    color=0xF59E0B,
                )
                await cog._update_tracked_panel_messages(
                    interaction=None, # Cannot rely on original interaction during timeout
                    session_state=session_state,
                    embed=timeout_embed,
                    clear_view=False,
                    view=self
                )

        return EditPanelContainerView()

    def _create_edit_view(
        self,
        session_state: dict,
        csv_file: discord.Attachment | None = None,
        config_file: discord.Attachment | None = None,
        fixed_chart_type: str | None = None,
    ) -> discord.ui.View:
        """Create a view with just an Edit button to attach to rendered chart messages."""
        cog = self
        fixed_chart_type = fixed_chart_type.lower() if fixed_chart_type else None

        class EditButton(discord.ui.Button):
            def __init__(self):
                """Initialize the Edit button."""
                super().__init__(style=discord.ButtonStyle.secondary, label="Edit", emoji="📝")

            async def callback(self, interaction: discord.Interaction):
                """Open the ephemeral edit panel for the chart."""
                if not await cog._ensure_owner(interaction, session_state):
                    return
                if session_state.get("cancelled"):
                    await context.app_error(interaction, "Configuration was cancelled. Start /chart_render again.")
                    return
                if not csv_file:
                    await context.app_error(interaction, "Configuration data missing. Start /chart_render again.")
                    return

                panel_view = cog._create_edit_panel_view(
                    csv_file=csv_file,
                    config_file=config_file,
                    original_message=interaction.message,
                    session_state=session_state,
                    fixed_chart_type=fixed_chart_type
                )

                edit_embed = discord.Embed(
                    title="📊 Edit Chart",
                    description="Configure your chart settings below, then click **Render chart**.",
                    color=0x4E79A7,
                )
                await cog._send_panel_message(
                    interaction,
                    edit_embed,
                    panel_view,
                    session_state,
                    "edit_messages",
                )

        class EditChartView(discord.ui.View):
            def __init__(self):
                """Initialize the chart message view container."""
                super().__init__(timeout=3600)

                class DeleteButton(discord.ui.Button):
                    def __init__(self):
                        """Initialize the Delete button for the rendered chart."""
                        super().__init__(style=discord.ButtonStyle.danger, label="Delete", emoji="🗑️")

                    async def callback(self, interaction: discord.Interaction):
                        """Prompt for confirmation before deleting the rendered chart."""
                        if not await cog._ensure_owner(interaction, session_state):
                            return

                        chart_message = interaction.message

                        class ConfirmDeleteView(discord.ui.View):
                            def __init__(self):
                                super().__init__(timeout=60)
                                self.message = None

                            @discord.ui.button(label="Yes, delete", style=discord.ButtonStyle.danger, emoji="🗑️")
                            async def confirm(self, confirm_interaction: discord.Interaction, button: discord.ui.Button):
                                session_state["cancelled"] = True
                                combined_panels = session_state.get("config_messages", []) + session_state.get("edit_messages", [])
                                for panel_msg in combined_panels:
                                    try:
                                        await panel_msg.delete()
                                    except Exception:
                                        pass

                                if chart_message:
                                    try:
                                        await chart_message.delete()
                                    except Exception:
                                        pass
                                if self.message: 
                                    try:
                                        await self.message.delete()
                                    except Exception:
                                        try:
                                            await confirm_interaction.delete()
                                        except Exception:
                                            try:
                                                await confirm_interaction.response.edit_message(content="Deleted.", embed=None, view=None)
                                            except Exception:
                                                pass

                            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
                            async def cancel(self, cancel_interaction: discord.Interaction, button: discord.ui.Button):
                                await cancel_interaction.response.edit_message(
                                    content="Deletion cancelled.",
                                    embed=None,
                                    view=None,
                                )

                            async def on_timeout(self):
                                for item in self.children:
                                    item.disabled = True
                                if self.message:
                                    try:
                                        timeout_embed = discord.Embed(
                                            title="⏱️ Confirmation Timed Out",
                                            description="The confirmation prompt has expired. The chart and panels remain unchanged.",
                                            color=0xF59E0B,
                                        )
                                        await self.message.edit(embed=timeout_embed, view=self, content=None)
                                    except Exception:
                                        pass

                        confirm_embed = discord.Embed(
                            title="🗑️ Are you sure?",
                            description="This will permanently delete the chart message and close all configuration panels.",
                            color=0xF54336,
                        )

                        view = ConfirmDeleteView()
                        await interaction.response.send_message(embed=confirm_embed, view=view, ephemeral=True)
                        try:
                            view.message = await interaction.original_response()
                        except Exception:
                            pass

                class DownloadButton(discord.ui.Button):
                    def __init__(self):
                        """Initialize the Download button for the rendered chart."""
                        super().__init__(style=discord.ButtonStyle.success, label="Download", emoji="⬇️")

                    async def callback(self, interaction: discord.Interaction):
                        """Send download link for the chart."""
                        chart_message = interaction.message
                        if not chart_message or not chart_message.attachments:
                            await context.app_error(interaction, "Chart file not found.")
                            return

                        attachment = chart_message.attachments[0]
                        download_embed = discord.Embed(
                            title="📥 Download Chart",
                            description=f"[Click here to download your chart]({attachment.url})",
                            color=0x10B981,
                        )
                        download_embed.add_field(
                            name="📄 Filename",
                            value=attachment.filename,
                            inline=True,
                        )
                        download_embed.add_field(
                            name="📊 Size",
                            value=f"{attachment.size:,} bytes",
                            inline=True,
                        )
                        await interaction.response.send_message(embed=download_embed, ephemeral=True)

                self.add_item(DownloadButton())
                self.add_item(EditButton())
                self.add_item(DeleteButton())

            async def on_timeout(self):
                """Disable the Edit button when timeout occurs."""
                for item in self.children:
                    item.disabled = True
                if getattr(self, "message", None):
                    try:
                        await self.message.edit(view=self)
                    except Exception:
                        pass

        return EditChartView()

    def _chart_type_select_view(
        self,
        csv_file: discord.Attachment,
        config_file: discord.Attachment | None = None,
        original_message: discord.Message | None = None,
        session_state: dict | None = None,
        fixed_chart_type: str | None = None,
    ) -> discord.ui.View:
        """Create the configuration view for chart setup panels."""
        cog = self
        if session_state is None:
            session_state = {
                "cancelled": False,
                "completed": False,
                "defer_render": True,
                "config_messages": [],
                "edit_messages": [],
                "config_history": [],
                "data_cache": {},
                "render_cache": {},
                "advanced_config": {},
                "pending_config": None,
                "stored_config": {},
            }
        session_state.setdefault("defer_render", True)
        session_state.setdefault("pending_config", None)
        session_state.setdefault("stored_config", {})
        fixed_chart_type = fixed_chart_type.lower() if fixed_chart_type else None

        class CancelButton(discord.ui.Button):
            def __init__(self):
                """Initialize the Cancel button."""
                super().__init__(style=discord.ButtonStyle.danger, label="✕ Cancel")

            async def callback(self, interaction: discord.Interaction):
                """Cancel the configuration session and lock the panel."""
                if not await cog._ensure_owner(interaction, session_state):
                    return
                session_state["cancelled"] = True

                if self.view:
                    for item in self.view.children:
                        item.disabled = True

                cancelled_embed = discord.Embed(
                    title="❌ Configuration cancelled",
                    description="This configuration panel is locked. Run `/chart_render` again to start a new one.",
                    color=0xF54336,
                )
                await interaction.response.edit_message(embed=cancelled_embed, view=self.view)

                for config_message in session_state.get("config_messages", []):
                    try:
                        if interaction.message and config_message.id == interaction.message.id:
                            continue
                        try:
                            await config_message.edit(embed=cancelled_embed, view=None)
                        except Exception:
                            try:
                                await interaction.followup.edit_message(config_message.id, embed=cancelled_embed, view=None)
                            except Exception:
                                pass
                    except Exception:
                        pass

                if original_message:
                    try:
                        await original_message.delete()
                    except Exception:
                        pass

        class ConfigureButton(discord.ui.Button):
            def __init__(self):
                """Initialize the main settings button for fixed chart types."""
                super().__init__(style=discord.ButtonStyle.primary, label="Main settings", emoji="🛠️")

            async def callback(self, interaction: discord.Interaction):
                """Open a modal for the fixed chart type."""
                if not await cog._ensure_owner(interaction, session_state):
                    return
                if session_state.get("cancelled"):
                    await context.app_error(interaction, "Configuration was cancelled. Run the command again.")
                    return
                if not fixed_chart_type:
                    await context.app_error(interaction, "Missing chart preset.")
                    return

                modal = cog._create_chart_modal(
                    chart_type=fixed_chart_type,
                    csv_file=csv_file,
                    config_file=config_file,
                    session_state=session_state,
                    original_message=original_message,
                    fixed_chart_type=fixed_chart_type,
                    mode="config",
                    y_columns_placeholder=await cog._y_columns_placeholder_from_csv(csv_file, session_state),
                )
                await interaction.response.send_modal(modal)

        class AdvancedButton(discord.ui.Button):
            def __init__(self):
                """Initialize the Advanced options button."""
                super().__init__(style=discord.ButtonStyle.secondary, label="Advanced", emoji="⚙️")

            async def callback(self, interaction: discord.Interaction):
                """Open advanced options panel."""
                if not await cog._ensure_owner(interaction, session_state):
                    return
                advanced_select = next(
                    (
                        item for item in self.view.children
                        if isinstance(item, discord.ui.Select)
                        and getattr(item, "placeholder", "") == "Select topics to configure"
                    ),
                    None,
                )
                if advanced_select:
                    self.view.remove_item(advanced_select)
                    self.label = "Advanced"
                else:
                    self.view.add_item(cog._create_advanced_topic_select(session_state))
                    self.label = "Hide Advanced"
                await interaction.response.edit_message(view=self.view)

        class RenderButton(discord.ui.Button):
            def __init__(self):
                """Initialize the Render chart button."""
                super().__init__(style=discord.ButtonStyle.success, label="Render chart", emoji="✅")

            async def callback(self, interaction: discord.Interaction):
                """Render a chart using the last saved settings."""
                if not await cog._ensure_owner(interaction, session_state):
                    return
                if session_state.get("cancelled"):
                    await context.app_error(interaction, "Configuration was cancelled. Run the command again.")
                    return

                pending_cfg = session_state.get("pending_config")
                if not pending_cfg:
                    await context.app_error(interaction, "No saved settings yet. Click Main settings first.")
                    return

                await interaction.response.defer()

                cfg, rows, _columns, _x_col, _y_col, labels, values = await cog._get_cached_chart_data(
                    session_state,
                    csv_file,
                    config_file,
                    pending_cfg.get("chart_type"),
                )
                cfg.update(pending_cfg)
                labels, values = cog._refresh_series_from_config(cfg, rows, _columns)
                cfg = cog._apply_advanced_config(cfg, session_state)
                cog._sync_stored_config(session_state, cfg)

                embed = context.chart_embed(
                    chart_type=cfg['chart_type'],
                    rows_count=len(rows),
                    user_name=interaction.user.display_name,
                    user_avatar=interaction.user.display_avatar,
                    config=cfg,
                )
                edit_view = cog._create_edit_view(
                    session_state,
                    csv_file=csv_file,
                    config_file=config_file,
                    fixed_chart_type=fixed_chart_type,
                )

                public_updated = False
                if original_message:
                    public_updated = await cog._update_chart_message(
                        interaction,
                        original_message,
                        session_state,
                        cfg,
                        labels,
                        values,
                        embed,
                        edit_view,
                    )
                if not public_updated:
                    fallback_file = cog._build_chart_file_cached(session_state, cfg, labels, values)
                    sent = await interaction.followup.send(embed=embed, file=fallback_file, view=edit_view, wait=True)
                    if sent and edit_view:
                        edit_view.message = sent
                        session_state.setdefault("config_messages", []).append(sent)

                success_embed = discord.Embed(
                    title="✅ Chart rendered!",
                    description="Chart has been rendered with your settings.",
                    color=0x37EC2A,
                )
                session_state["completed"] = True
                await cog._update_tracked_panel_messages(interaction, session_state, success_embed)
                cog._append_config_history(session_state, cfg)

        class ChartTypeSelect(discord.ui.Select):
            def __init__(self):
                """Initialize the chart type selector for configuration."""
                super().__init__(placeholder="Select chart type", min_values=1, max_values=1, options=cog._chart_type_options())

            async def callback(self, interaction: discord.Interaction):
                """Open a modal for the selected chart type."""
                if not await cog._ensure_owner(interaction, session_state):
                    return
                if session_state.get("cancelled"):
                    await context.app_error(interaction, "Configuration was cancelled. Start /chart_render again.")
                    return

                chart_type = self.values[0]
                modal = cog._create_chart_modal(
                    chart_type=chart_type,
                    csv_file=csv_file,
                    config_file=config_file,
                    session_state=session_state,
                    original_message=original_message,
                    fixed_chart_type=fixed_chart_type,
                    mode="config",
                    y_columns_placeholder=await cog._y_columns_placeholder_from_csv(csv_file, session_state),
                )
                await interaction.response.send_modal(modal)

        class ChartTypeView(discord.ui.View):
            def __init__(self):
                """Initialize the configuration view container."""
                super().__init__(timeout=300)
                if fixed_chart_type:
                    self.add_item(ConfigureButton())
                else:
                    self.add_item(ChartTypeSelect())
                self.add_item(RenderButton())
                self.add_item(AdvancedButton())
                self.add_item(CancelButton())

            async def on_timeout(self):
                """Disable the wizard panel when the session expires."""
                if session_state.get("completed") or session_state.get("cancelled"):
                    return

                timeout_embed = discord.Embed(
                    title="⏱️ Session Expired",
                    description="The chart wizard has expired. Run `/chart_render` again to start a new session.",
                    color=0xF59E0B,
                )
                for item in self.children:
                    item.disabled = True

                for config_message in session_state.get("config_messages", []):
                    try:
                        await config_message.edit(embed=timeout_embed, view=self)
                    except Exception:
                        pass
                if original_message:
                    try:
                        await original_message.delete()
                    except Exception:
                        pass

        return ChartTypeView()

    async def _start_chart_configuration(
        self,
        interaction: discord.Interaction,
        csv_file: discord.Attachment,
        config_file: discord.Attachment | None = None,
        fixed_chart_type: str | None = None,
    ) -> None:
        """Start the interactive configuration flow for chart commands."""
        session_state = self._init_session_state(interaction, fixed_chart_type, completed=False)

        cog = self

        class BuildingEditView(discord.ui.View):
            def __init__(self, csv_attachment, cfg_file, state: dict):
                """Initialize the public build message view."""
                super().__init__(timeout=300)
                self.csv_file = csv_attachment
                self.config_file = cfg_file
                self.state = state
                self.original_msg = None

            @discord.ui.button(style=discord.ButtonStyle.secondary, label="Configuration", emoji="⚙️")
            async def edit_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                """Open the configuration panel from the public build message."""
                if button_interaction.user.id != self.state.get("owner_id"):
                    await context.app_error(button_interaction, "Only the command author can use this panel.")
                    return
                if self.state.get("cancelled"):
                    await context.app_error(button_interaction, "Configuration was cancelled. Run the command again.")
                    return

                preset_name = (self.state.get("preset_chart_type") or "chart").title()
                config_embed = cog._build_config_panel_embed(preset_name, self.state.get("preset_chart_type"))
                view = cog._chart_type_select_view(
                    self.csv_file,
                    self.config_file,
                    self.original_msg,
                    session_state=self.state,
                    fixed_chart_type=self.state.get("preset_chart_type"),
                )
                await cog._send_panel_message(
                    button_interaction,
                    config_embed,
                    view,
                    self.state,
                    "config_messages",
                )

        preset_name = (fixed_chart_type or "chart").title()
        building_embed = discord.Embed(
                title=f"🔨 Building {preset_name}...",
                description="Chart is being prepared. Click Configure to set chart options, or check your private message.",
                color=0xFFA500,
            )
        building_embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        
        if fixed_chart_type:
            # Minimal embed for building when a preset is used — avoid chart details here
            building_embed.title = f"🔨 Building {(fixed_chart_type or "chart").title()}..."
            building_embed.color = 0x4E79A7
            
        view = BuildingEditView(csv_file, config_file, session_state)
        await interaction.response.send_message(embed=building_embed, view=view)
        original_message = await interaction.original_response()
        view.original_msg = original_message

        config_embed = self._build_config_panel_embed(preset_name, fixed_chart_type)
        view = self._chart_type_select_view(
            csv_file,
            config_file,
            original_message,
            session_state=session_state,
            fixed_chart_type=fixed_chart_type,
        )
        await self._send_panel_message(
            interaction,
            config_embed,
            view,
            session_state,
            "config_messages",
        )

    async def _render_chart_response(
        self,
        ctx,
        csv_attachment: discord.Attachment,
        json_attachment: discord.Attachment | None,
        chart_type: str | None = None,
        title: str | None = None,
    ):
        """Render a chart for legacy text commands."""
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
        include_edit_view: bool = False,
        session_state: dict | None = None,
    ):
        """Render a chart for slash commands and optionally attach edit view."""
        if session_state is None:
            cfg, rows, _columns, _x_col, _y_col, labels, values = await prepare_chart_data(
                csv_file,
                config_file,
                chart_type=chart_type,
            )
        else:
            cfg, rows, _columns, _x_col, _y_col, labels, values = await self._get_cached_chart_data(
                session_state,
                csv_file,
                config_file,
                chart_type,
            )

        if session_state is not None:
            cfg = self._apply_advanced_config(cfg, session_state)
            self._sync_stored_config(session_state, cfg)

        if session_state is not None:
            file = self._build_chart_file_cached(session_state, cfg, labels, values)
        else:
            file = self._build_chart_file(cfg, labels, values)
        embed = context.chart_embed(
            chart_type=cfg['chart_type'],
            rows_count=len(rows),
            user_name=interaction.user.display_name,
            user_avatar=interaction.user.display_avatar,
            config=cfg,
        )
        
        view = None
        if include_edit_view and session_state:
            view = self._create_edit_view(
                session_state,
                csv_file=csv_file,
                config_file=config_file,
                fixed_chart_type=chart_type,
            )
        
        await interaction.response.send_message(embed=embed, file=file, view=view)
        if view is not None:
            try:
                sent = await interaction.original_response()
                view.message = sent
            except Exception:
                pass
        if session_state is not None:
            self._append_config_history(session_state, cfg)

    @app_commands.command(name="chart_render", description="Render a chart from CSV and optional JSON config")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def chart_render_slash(
        self,
        interaction: discord.Interaction,
        csv_file: discord.Attachment,
        config_file: discord.Attachment | None = None,
    ):
        """Handle /chart_render slash command."""
        try:
            if config_file is None:
                # No JSON config — open interactive panel
                await self._start_chart_configuration(interaction, csv_file, config_file)
                return

            # JSON config provided — render directly with Edit button
            session_state = self._init_session_state(interaction, None, completed=True)
            await self._render_chart_slash_response(
                interaction,
                csv_file,
                config_file,
                title="Chart rendered",
                include_edit_view=True,
                session_state=session_state,
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
        """Handle /bar slash command."""
        try:
            if config_file is None:
                await self._start_chart_configuration(interaction, csv_file, config_file, fixed_chart_type="bar")
                return

            # JSON config provided — render directly with Edit button
            session_state = self._init_session_state(interaction, "bar", completed=True)
            await self._render_chart_slash_response(
                interaction,
                csv_file,
                config_file,
                chart_type="bar",
                title="Bar chart rendered",
                include_edit_view=True,
                session_state=session_state,
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
        """Handle /line slash command."""
        try:
            if config_file is None:
                await self._start_chart_configuration(interaction, csv_file, config_file, fixed_chart_type="line")
                return

            # JSON config provided — render directly with Edit button
            session_state = self._init_session_state(interaction, "line", completed=True)
            await self._render_chart_slash_response(
                interaction,
                csv_file,
                config_file,
                chart_type="line",
                title="Line chart rendered",
                include_edit_view=True,
                session_state=session_state,
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
        """Handle /pie slash command."""
        try:
            if config_file is None:
                await self._start_chart_configuration(interaction, csv_file, config_file, fixed_chart_type="pie")
                return

            # JSON config provided — render directly with Edit button
            session_state = self._init_session_state(interaction, "pie", completed=True)
            await self._render_chart_slash_response(
                interaction,
                csv_file,
                config_file,
                chart_type="pie",
                title="Pie chart rendered",
                include_edit_view=True,
                session_state=session_state,
            )
        except Exception as error:
            await context.app_error(interaction, str(error))
    
    
    
    
    @commands.command(name="chart_render", aliases=["render"])
    async def chart_render(self, ctx):
        """Render a chart from CSV + optional JSON config."""
        message = f"Please use the slash command `/chart_render` to run this action."
        try:
            await ctx.warning(message)
        except Exception:
            try:
                await ctx.send(message)
            except Exception:
                pass
            
    @commands.command(name="bar", aliases=["cbar"])
    async def bar(self, ctx):
        """Render a bar chart from CSV + optional JSON config."""
        message = f"Please use the slash command `/bar` or `/chart_render` to run this action."
        try:
            await ctx.warning(message)
        except Exception:
            try:
                await ctx.send(message)
            except Exception:
                pass

    @commands.command(name="line", aliases=["cline"])
    async def line(self, ctx):
        """Render a line chart from CSV + optional JSON config."""
        message = f"Please use the slash command `/line` or `/chart_render` to run this action."
        try:
            await ctx.warning(message)
        except Exception:
            try:
                await ctx.send(message)
            except Exception:
                pass

    @commands.command(name="pie", aliases=["cpie"])
    async def pie(self, ctx):
        """Render a pie chart from CSV + optional JSON config."""
        message = f"Please use the slash command `/pie` or `/chart_render` to run this action."
        try:
            await ctx.warning(message)
        except Exception:
            try:
                await ctx.send(message)
            except Exception:
                pass


async def setup(bot):
    """Register the charts cog."""
    await bot.add_cog(charts(bot))
