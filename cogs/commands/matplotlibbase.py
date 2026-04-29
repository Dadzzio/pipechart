import io

import matplotlib.pyplot as plt


def build_chart(cfg: dict, labels: list[str], values: list[float]) -> bytes:
    fig, ax = plt.subplots(figsize=tuple(cfg["figsize"]), dpi=int(cfg["dpi"]))
    chart_type = cfg["chart_type"]

    if chart_type == "bar":
        ax.bar(labels, values, color=cfg["color"])
    elif chart_type == "line":
        ax.plot(labels, values, marker="o", color=cfg["color"])
    elif chart_type == "pie":
        ax.pie(values, labels=labels, autopct="%.1f%%")
        ax.axis("equal")

    ax.set_title(cfg.get("title") or "PipeChart")
    if chart_type != "pie":
        ax.set_xlabel(cfg.get("x_label") or "")
        ax.set_ylabel(cfg.get("y_label") or "")
        ax.grid(axis="y", alpha=0.2)

    plt.tight_layout()
    output = io.BytesIO()
    fmt = cfg["output"]
    fig.savefig(output, format=fmt, bbox_inches="tight")
    plt.close(fig)
    output.seek(0)
    return output.read()
