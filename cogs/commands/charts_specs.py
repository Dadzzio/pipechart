from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ChartSpec:
    name: str
    label: str
    description: str
    render: Callable
    validate: Callable
    has_axes: bool = True


def _validate_common(values: list[float]) -> None:
    if len(values) < 2:
        raise ValueError("At least two rows are required.")


def _validate_pie(values: list[float]) -> None:
    _validate_common(values)
    if any(v < 0 for v in values):
        raise ValueError("Pie chart does not support negative values.")
    if sum(values) <= 0:
        raise ValueError("Pie chart requires values with positive total sum.")


def _render_bar(ax, labels: list[str], values: list[float], cfg: dict) -> None:
    ax.bar(
        labels,
        values,
        color=cfg.get("color"),
        width=cfg.get("bar_width", 0.8),
        alpha=cfg.get("alpha", 1.0),
    )


def _render_line(ax, labels: list[str], values: list[float], cfg: dict) -> None:
    ax.plot(
        labels,
        values,
        marker=cfg.get("marker", "o"),
        color=cfg.get("color"),
        linewidth=cfg.get("line_width", 2.0),
    )


def _render_pie(ax, labels: list[str], values: list[float], cfg: dict) -> None:
    pie_colors = cfg.get("colors")
    autopct = cfg.get("autopct", "%.1f%%")
    startangle = cfg.get("startangle", 0)
    if pie_colors:
        ax.pie(values, labels=labels, autopct=autopct, colors=pie_colors, startangle=startangle)
    else:
        ax.pie(values, labels=labels, autopct=autopct, startangle=startangle)
    ax.axis("equal")


CHART_SPECS = {
    "bar": ChartSpec(
        name="bar",
        label="Bar",
        description="Bar chart visualization",
        render=_render_bar,
        validate=_validate_common,
        has_axes=True,
    ),
    "line": ChartSpec(
        name="line",
        label="Line",
        description="Line chart visualization",
        render=_render_line,
        validate=_validate_common,
        has_axes=True,
    ),
    "pie": ChartSpec(
        name="pie",
        label="Pie",
        description="Pie chart visualization",
        render=_render_pie,
        validate=_validate_pie,
        has_axes=False,
    ),
}

DEFAULT_CONFIG = {
    "chart_type": "bar",
    "x_column": None,
    "y_column": None,
    "title": None,
    "x_label": "",
    "y_label": "",
    "color": "#4E79A7",
    "output": "png",
    "figsize": [8, 5],
    "dpi": 150,
    "grid": True,
    "style": "seaborn-v0_8",
    "line_width": 2.0,
    "marker": "o",
    "bar_width": 0.8,
    "alpha": 1.0,
    "autopct": "%.1f%%",
    "startangle": 0,
    "mean_line": False,
    "mean_color": "red",
    "mean_style": "solid",
}


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


def _parse_figsize(value) -> list[float]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return [float(value[0]), float(value[1])]
        except (TypeError, ValueError):
            return DEFAULT_CONFIG["figsize"]
    if value is None:
        return DEFAULT_CONFIG["figsize"]
    text = str(value).strip()
    if not text:
        return DEFAULT_CONFIG["figsize"]
    parts = [p.strip() for p in text.replace("x", ",").split(",") if p.strip()]
    if len(parts) != 2:
        return DEFAULT_CONFIG["figsize"]
    try:
        return [float(parts[0]), float(parts[1])]
    except ValueError:
        return DEFAULT_CONFIG["figsize"]


def normalize_config(raw_cfg: dict | None) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if raw_cfg:
        cfg.update(raw_cfg)

    cfg["chart_type"] = str(cfg.get("chart_type", "bar")).lower()
    cfg["output"] = str(cfg.get("output", "png")).lower()

    try:
        cfg["dpi"] = int(cfg.get("dpi", DEFAULT_CONFIG["dpi"]))
    except (TypeError, ValueError):
        cfg["dpi"] = DEFAULT_CONFIG["dpi"]

    cfg["figsize"] = _parse_figsize(cfg.get("figsize"))
    cfg["grid"] = _parse_bool(cfg.get("grid", True))

    style_value = cfg.get("style")
    cfg["style"] = str(style_value).strip() if style_value is not None else ""

    line_width = cfg.get("line_width")
    try:
        cfg["line_width"] = float(line_width) if line_width is not None else DEFAULT_CONFIG["line_width"]
    except (TypeError, ValueError):
        cfg["line_width"] = DEFAULT_CONFIG["line_width"]

    startangle = cfg.get("startangle")
    try:
        cfg["startangle"] = float(startangle) if startangle is not None else DEFAULT_CONFIG["startangle"]
    except (TypeError, ValueError):
        cfg["startangle"] = DEFAULT_CONFIG["startangle"]

    cfg["mean_line"] = _parse_bool(cfg.get("mean_line", False))
    
    mean_color = cfg.get("mean_color")
    cfg["mean_color"] = str(mean_color).strip() if mean_color is not None else DEFAULT_CONFIG["mean_color"]
    
    mean_style = cfg.get("mean_style")
    cfg["mean_style"] = str(mean_style).strip().lower() if mean_style is not None else DEFAULT_CONFIG["mean_style"]
    valid_styles = {"solid", "dotted", "dashed"}
    if cfg["mean_style"] not in valid_styles:
        cfg["mean_style"] = DEFAULT_CONFIG["mean_style"]

    return cfg
