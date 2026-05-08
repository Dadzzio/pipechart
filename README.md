# PipeChart

PipeChart is a Discord bot (Python) that provides an interactive chart-generation workflow.

- Render charts from a CSV dataset and optional JSON configuration.
- Configure chart options through interactive Discord UI (views/modals).
- Support bar, line and pie chart types and multiple output formats.

This project is part of the IBM internship practical program (ZSEn Kraków, 2025/2026).
Contributors: [Bartosz Brzezanski](https://github.com/brzerzan), [Szymon Payerhin](https://github.com/Dadzzio).

## Project Description

PipeChart helps users prepare chart data and generate chart outputs through an interactive Discord workflow. The bot can read an optional JSON configuration, accept a CSV attachment as data, and render charts using `matplotlib`.

The first version focuses on one chart type and one output format, with room to extend both the chart list and export options later.

## Requirements

- Discord bot token configured in `.env`
- Optional `beta=true` flag in `.env` for beta presence and startup mode
- Python 3.14
- `discord.py` and `matplotlib` installed (see `requirements.txt`)
- CSV dataset input; optional JSON config
- Bot must have permissions to send messages, use embeds, and use interactive components

## Tech stack

- Python 3.14
- `discord.py` for bot + UI components
- `matplotlib` for rendering charts
- JSON/CSV handling using the standard library

## JIRA Board

- Project board: [JIRA board](https://zse-ibm.atlassian.net/)

## Bot Commands (Current)

Command prefix: `\`

Slash commands are supported.

- `\chart_render` (alias: `\crender`)
  - Interactive chart rendering flow (public Building message + private configuration panel).
  - Attach required `*.csv` and optional `*.json` config in the same message.

- `\bar`, `\line`, `\pie` (and their slash equivalents)
  - Direct render commands (accept attachments and optional JSON config).

- `/chart_render`, `/bar`, `/line`, `/pie`
  - Slash versions of the commands. `chart_render` runs the interactive flow by default.

## Supported chart types

- `bar`
- `line`
- `pie`

## Supported output formats

- `png`
- `svg`

## JSON Config Schema (Optional)

If no config is attached, defaults are used. Example schema:

```json
{
  "chart_type": "bar",
  "x_column": "category",
  "y_column": "value",
  "title": "Sales by Category",
  "x_label": "Category",
  "y_label": "Sales",
  "color": "#4E79A7",
  "output": "png",
  "figsize": [8, 5],
  "dpi": 150
}
```

Notes

- `x_column` and `y_column` are optional; by default the first and second CSV columns are used.
- Pie charts require non-negative values and positive total sum.

Recent implementation notes

- Centralized user error reporting via `objects/context.context.app_error(...)` for consistent owner checks and ephemeral errors.
- The interactive flow tracks `config_messages` and `edit_messages` so the bot can update configuration and edit panels after rendering (success or error).
- Color inputs are validated using `matplotlib.colors.is_color_like` and configuration panels show clear validation errors.
- The public "Building..." message for preset chart types is intentionally minimalist to avoid exposing chart details while rendering.
- Message edits use a robust fallback: try `Message.edit(...)`, then `interaction.followup.edit_message(...)` if needed.
- Consolidated duplicate helpers (single `BuildingEditView`) and simplified the Edit button emoji.


