import csv
import io
import json

import discord

from cogs.commands.charts_specs import CHART_SPECS, normalize_config


def parse_config(config_raw: str | None) -> dict:
    if not config_raw:
        return normalize_config(None)

    try:
        user = json.loads(config_raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON decode error: {exc}") from None

    return normalize_config(user)


def force_chart_type(cfg: dict, chart_type: str) -> dict:
    cfg = dict(cfg)
    cfg["chart_type"] = chart_type
    return cfg


def read_csv_rows(csv_raw: str) -> tuple[list[dict], list[str]]:
    reader = csv.DictReader(io.StringIO(csv_raw))
    if not reader.fieldnames:
        raise ValueError("CSV file must include a header row.")
    rows = list(reader)
    if not rows:
        raise ValueError("CSV file has no data rows.")
    return rows, list(reader.fieldnames)


def pick_columns(cfg: dict, columns: list[str]) -> tuple[str, str]:
    x_col = cfg.get("x_column") or columns[0]
    y_col = cfg.get("y_column") or (columns[1] if len(columns) > 1 else None)

    if y_col is None:
        raise ValueError("CSV must contain at least two columns.")
    if x_col not in columns:
        raise ValueError(f"Configured x_column '{x_col}' was not found in CSV.")
    if y_col not in columns:
        raise ValueError(f"Configured y_column '{y_col}' was not found in CSV.")

    return x_col, y_col


def extract_series(rows: list[dict], x_col: str, y_col: str) -> tuple[list[str], list[float]]:
    labels = []
    values = []

    for idx, row in enumerate(rows, start=2):
        x_val = str(row.get(x_col, "")).strip()
        y_raw = str(row.get(y_col, "")).strip()

        if not x_val:
            raise ValueError(f"Row {idx}: '{x_col}' is empty.")
        if not y_raw:
            raise ValueError(f"Row {idx}: '{y_col}' is empty.")

        try:
            y_val = float(y_raw)
        except ValueError as exc:
            raise ValueError(f"Row {idx}: '{y_col}' must be numeric, got '{y_raw}'.") from exc

        labels.append(x_val)
        values.append(y_val)

    return labels, values


def validate_for_chart(chart_type: str, values: list[float]):
    spec = CHART_SPECS.get(chart_type)
    if not spec:
        raise ValueError("Unsupported chart_type. Use one of: bar, line, pie.")
    spec.validate(values)


async def read_attachment_text(attachment: discord.Attachment) -> str:
    data = await attachment.read()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Attachment '{attachment.filename}' is not valid UTF-8 text.") from exc


async def prepare_chart_data(
    csv_attachment: discord.Attachment,
    json_attachment: discord.Attachment | None,
    chart_type: str | None = None,
) -> tuple[dict, list[dict], list[str], str, str, list[str], list[float]]:
    if not csv_attachment.filename.lower().endswith(".csv"):
        raise ValueError("csv_file must be a .csv attachment.")
    if json_attachment and not json_attachment.filename.lower().endswith(".json"):
        raise ValueError("config_file must be a .json attachment.")

    csv_raw = await read_attachment_text(csv_attachment)
    config_raw = await read_attachment_text(json_attachment) if json_attachment else None

    cfg = parse_config(config_raw)
    if chart_type is not None:
        cfg = force_chart_type(cfg, chart_type)
    if cfg["output"] not in {"png", "svg", "pdf"}:
        raise ValueError("Unsupported output format. Use 'png', 'svg', or 'pdf'.")

    rows, columns = read_csv_rows(csv_raw)
    x_col, y_col = pick_columns(cfg, columns)
    labels, values = extract_series(rows, x_col, y_col)
    validate_for_chart(cfg["chart_type"], values)
    return cfg, rows, columns, x_col, y_col, labels, values
