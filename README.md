# PipeChart

PipeChart is a Discord bot project built in Python that combines chart rendering and chart-type selection into one workflow:

1. Chart rendering from a CSV dataset and JSON configuration.
2. Dedicated commands for bar, line, and pie charts.

The bot is being developed as part of IBM internship work for class 4 practical program ZSEn Kraków for the 2025/2026. The project team includes [Bartosz Brzezanski](https://github.com/brzerzan) and [Szymon Payerhin](https://github.com/Dadzzio).

## Project Description

PipeChart is designed to help users prepare chart data and generate chart outputs through a Discord bot interface. The bot can read chart configuration from a JSON file or from a Discord UI form, loads a dataset in CSV format, and renders the final chart in a supported output format. It can also support user integration search workflows inside Discord.

The first version focuses on one chart type and one output format, with room to extend both the chart list and export options later.

## Requirements

- Discord bot token configured in `.env`
- Optional `beta=true` flag in `.env` for beta presence and startup mode
- Python 3.14
- CSV dataset input
- JSON chart configuration input or Discord UI configuration input
- Discord bot permissions to read messages, respond in channels, and use interactive UI components

## Technical Stack

- Programming language: Python 3.14
- Frameworks and libraries: `discord.py`, `matplotlib`
- Runtime interface: Discord bot
- Supporting tools: JSON, CSV handling, and standard Python libraries

## JIRA Board

- Project board: [JIRA board](https://zse-ibm.atlassian.net/)

## Development Notes

- The project combines chart rendering and chart-type selection into a single Discord bot workflow.
- The implementation is intended to be simple, local-first, and easy to extend.
- Output targets may include HTML, PNG, or SVG depending on the chart engine used.

## Bot Commands (Current)

Command prefix: `\`

Slash commands are also supported (`/`) and synced automatically on startup.

- `\chart_render` (alias: `\crender`)
	- Renders chart image from attached CSV and optional JSON config.
	- Attach required `*.csv` and optional `*.json` config in the same message.

- `\bar` (alias: `\cbar`)
	- Renders a bar chart from attached CSV and optional JSON config.

- `\line` (alias: `\cline`)
	- Renders a line chart from attached CSV and optional JSON config.

- `\pie` (alias: `\cpie`)
	- Renders a pie chart from attached CSV and optional JSON config.

- `/chart_render`
	- Slash version of chart rendering.
	- Parameters: `csv_file` (required), `config_file` (optional JSON).

- `/bar`
	- Slash version of bar chart rendering.
	- Parameters: `csv_file` (required), `config_file` (optional JSON).

- `/line`
	- Slash version of line chart rendering.
	- Parameters: `csv_file` (required), `config_file` (optional JSON).

- `/pie`
	- Slash version of pie chart rendering.
	- Parameters: `csv_file` (required), `config_file` (optional JSON).

- `/ping`
	- Slash latency check.

Slash commands are enabled for:

- Guild installs
- User installs (User Integration)
- Guild channels, DMs, and private channels

Supported chart types:

- `bar`
- `line`
- `pie`

Supported output formats:

- `png`
- `svg`

## JSON Config Schema (Optional)

If no config is attached, defaults are used.

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

Notes:

- `x_column` and `y_column` are optional; if omitted, first and second CSV column are used.
- Pie charts require non-negative values and positive total sum.

