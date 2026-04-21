# PipeChart

PipeChart is a Discord bot project built in Python that combines two related charting tasks into one workflow:

1. Chart rendering from a CSV dataset and JSON configuration.
2. Dataset compatibility validation for a selected chart type.

The bot is being developed as part of IBM internship work for class 4 practical program ZSEn Kraków for the 2025/2026. The project team includes [Bartosz Brzezanski](https://github.com/brzerzan) and [Szymon Payerhin](https://github.com/Dadzzio).

## Project Description

PipeChart is designed to help users prepare chart data and generate chart outputs through a Discord bot interface. The bot can read chart configuration from a JSON file or from a Discord UI form, loads a dataset in CSV format, validates whether the dataset fits the selected chart type, and renders the final chart in a supported output format.

The first version focuses on one chart type and one output format, with room to extend both the chart list and export options later.

## Requirements

- Discord bot token configured in `.env`
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

- The project combines chart rendering and dataset validation into a single Discord bot workflow.
- The implementation is intended to be simple, local-first, and easy to extend.
- Output targets may include HTML, PNG, or SVG depending on the chart engine used.

