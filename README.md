# PipeChart

PipeChart is a Discord bot for turning CSV data into charts. It supports an interactive setup flow, direct chart commands, and optional JSON configuration for styling and export settings.

This project is part of the IBM internship practical program at ZSEn Kraków (2025/2026).
Contributors: [Bartosz Brzezanski](https://github.com/brzerzan), [Szymon Payerhin](https://github.com/Dadzzio).

## Features

- Render bar, line, and pie charts from CSV attachments.
- Use an optional JSON file to customize labels, colors, figure size, output format, and advanced chart settings.
- Configure charts through Discord UI components with buttons, selects, and modals.
- Export charts as `png`, `svg`, or `pdf`.

## Requirements

- Python 3.14
- Dependencies from `requirements.txt`
- A Discord bot token in `.env` as `DISCORD_TOKEN`
- Optional `PREFIX` or `BOT_PREFIX` value in `.env` if you do not want the default `\`
- Optional `BETA=true` flag in `.env` to prefer the beta emoji set
- Bot permissions to send messages, embed links, and use interactive components

## Running the bot

1. Install dependencies from `requirements.txt`.
2. Set `DISCORD_TOKEN` in `.env`.
3. Run `python main.py`.

## Commands

Prefix commands use `\` by default. Slash commands are also available.

### Help

- `\help` - show a short command reference

### Interactive chart flow

- `\chart_render`
- `/chart_render`

Use this when you want the guided setup flow with a private configuration panel and an initial public building message.

### Direct chart commands

- `\bar` and `/bar`
- `\line` and `/line`
- `\pie` and `/pie`

Use these for direct rendering when you already know the chart type you want.

## Supported inputs

- A `.csv` file is required.
- A `.json` file is optional.
- CSV files must include a header row.
- If `x_column` and `y_column` are not provided, the first two CSV columns are used.
- Pie charts require non-negative values and a positive total sum.

## JSON config example

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
  "dpi": 150,
  "grid": true,
  "style": "seaborn-v0_8",
  "line_width": 2.5,
  "mean_line": true,
  "mean_color": "red",
  "mean_style": "dashed"
}
```

The JSON file can override both the basic chart fields and the newer advanced settings:

- `chart_type`: `bar`, `line`, or `pie`
- `x_column` and `y_column`: CSV columns to plot
- `title`, `x_label`, `y_label`, and `color`: chart styling for bar and line charts
- `colors` and `startangle`: pie chart styling options
- `output`: `png`, `svg`, or `pdf`
- `figsize`, `dpi`, `grid`, and `style`: figure and rendering settings
- `line_width`, `marker`, `bar_width`, and `alpha`: chart-specific styling
- `mean_line`, `mean_color`, and `mean_style`: optional mean line overlay for line and bar charts

## Supported chart types

- `bar`
- `line`
- `pie`

## Supported output formats

- `png`
- `svg`
- `pdf`

## Notes

- The interactive flow keeps track of configuration and edit panels so charts can be updated after rendering.
- The bot uses `matplotlib` for rendering and the standard library for CSV and JSON parsing.


