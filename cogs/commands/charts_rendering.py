import io

import matplotlib.pyplot as plt

from cogs.commands.charts_specs import CHART_SPECS


def build_chart(cfg: dict, labels: list[str], values: list[float]) -> bytes:
    fig, ax = plt.subplots(figsize=tuple(cfg["figsize"]), dpi=int(cfg["dpi"]))
    chart_type = cfg.get("chart_type", "bar")
    spec = CHART_SPECS.get(chart_type, CHART_SPECS["bar"])

    style = cfg.get("style")
    if style:
        try:
            plt.style.use(style)
        except Exception:
            pass

    spec.render(ax, labels, values, cfg)

    title = cfg.get("title")
    if title is not None:
        title_text = str(title).strip()
        if title_text:
            ax.set_title(title_text)
    if spec.has_axes:
        ax.set_xlabel(cfg.get("x_label") or "")
        ax.set_ylabel(cfg.get("y_label") or "")
        if cfg.get("grid", True):
            ax.grid(axis="y", alpha=0.2)

    # Draw mean line if enabled
    if cfg.get("mean_line", False) and values:
        mean_value = sum(values) / len(values)
        mean_color = cfg.get("mean_color", "red")
        mean_style_raw = cfg.get("mean_style", "solid").lower().strip()
        
        # Convert style names to matplotlib linestyle
        style_map = {
            "solid": "-",
            "dotted": ":",
            "dashed": "--",
        }
        linestyle = style_map.get(mean_style_raw, "-")
        
        ax.axhline(y=mean_value, color=mean_color, linestyle=linestyle, linewidth=2, label=f"Mean: {mean_value:.2f}")
        ax.legend()

    plt.tight_layout()
    output = io.BytesIO()
    fmt = cfg["output"]
    fig.savefig(output, format=fmt, bbox_inches="tight")
    plt.close(fig)
    output.seek(0)
    return output.read()
