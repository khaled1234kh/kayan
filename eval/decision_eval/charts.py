"""Dependency-free publication-quality SVG charts for confusion matrices."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _heat_color(fraction: float) -> str:
    # Soft blue ramp; darker = more mass in the cell.
    stop = max(0.0, min(1.0, fraction))
    red = int(245 - 165 * stop)
    green = int(249 - 130 * stop)
    blue = int(255 - 60 * stop)
    return f"rgb({red},{green},{blue})"


def confusion_svg(matrix: list[list[int]], labels: list[str], title: str) -> str:
    """Render a full confusion matrix with row-normalized percentages."""
    cell, pad, label_w, label_h = 110, 6, 118, 118
    n = len(labels)
    width = label_w + n * (cell + pad) + pad
    height = label_h + n * (cell + pad) + pad + 70
    rows = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="Segoe UI, Arial, sans-serif">',
        f'<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{pad}" y="26" font-size="16" font-weight="600" fill="#12263a">{_esc(title)}</text>',
        f'<text x="{label_w + 6}" y="{label_h - 12}" font-size="11" fill="#476">PREDICTED →</text>',
        f'<text x="10" y="{label_h + 6}" font-size="11" fill="#476">TRUE ↓</text>',
    ]
    for j, col in enumerate(labels):
        x = label_w + j * (cell + pad) + cell / 2 + pad
        rows.append(f'<text x="{x:.0f}" y="{label_h + cell - 8}" text-anchor="middle" font-size="12" fill="#12263a">{_esc(col)}</text>')
    for i, row_label in enumerate(labels):
        y = label_h + i * (cell + pad) + pad
        rows.append(f'<text x="{label_w - 10}" y="{y + cell / 2 + 4:.0f}" text-anchor="end" font-size="12" fill="#12263a">{_esc(row_label)}</text>')
        total = sum(matrix[i]) or 1
        for j, value in enumerate(matrix[i]):
            x = label_w + j * (cell + pad) + pad
            fraction = value / total
            rows.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="6" fill="{_heat_color(fraction)}" stroke="#c7d6e5"/>')
            rows.append(f'<text x="{x + cell / 2:.0f}" y="{y + cell / 2 - 2:.0f}" text-anchor="middle" font-size="19" font-weight="700" fill="#12263a">{value}</text>')
            rows.append(f'<text x="{x + cell / 2:.0f}" y="{y + cell / 2 + 18:.0f}" text-anchor="middle" font-size="11" fill="#36536e">{100 * fraction:.1f}%</text>')
    rows.append(f'<text x="{pad}" y="{height - 16}" font-size="10" fill="#678">Rows = true class, columns = predicted class. Percentages are row-normalized. Exact case-level accuracy is reported separately.</text>')
    rows.append("</svg>")
    return "\n".join(rows)


def write_charts(reanalysis: dict[str, Any], outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    written = []
    for arm in reanalysis["arms"]:
        cm = arm["classification_overall"]["confusion"]
        safe = arm["arm"].replace("/", "_").replace(":", "-")
        target = outdir / f"confusion_{safe}.svg"
        target.write_text(
            confusion_svg(cm["matrix"], cm["labels"], f"{arm['arm']} — canonical decision confusion"),
            encoding="utf-8",
        )
        written.append(target)
    return written
