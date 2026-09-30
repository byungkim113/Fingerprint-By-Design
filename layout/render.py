"""Render a flat GDS layout to PNG with a per-layer legend (SKY130 layers)."""
import sys
from pathlib import Path

import gdstk
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Polygon

# (layer, datatype): (name, face colour, alpha) — drawing layers only, bottom to top
LAYERS = {
    (65, 20): ("diffusion", "#1baf7a", 0.55),
    (65, 44): ("tap", "#008300", 0.55),
    (66, 20): ("poly", "#e34948", 0.55),
    (86, 20): ("poly-resistor marker", "#e87ba4", 0.25),
    (67, 20): ("li1", "#b5b3a8", 0.55),
    (68, 20): ("metal 1", "#2a78d6", 0.45),
    (69, 20): ("metal 2", "#eb6834", 0.40),
    (70, 20): ("metal 3", "#eda100", 0.35),
    (89, 44): ("MIM top plate", "#8b5e3c", 0.35),
    (71, 20): ("metal 4", "#4a3aa7", 0.55),
}


def render(gds, png, title):
    lib = gdstk.read_gds(str(gds))
    top = lib.top_level()[0]
    polys = top.get_polygons()
    (x0, y0), (x1, y1) = top.bounding_box()
    aspect = (y1 - y0 + 2) / (x1 - x0 + 2)
    w = 14
    fig, ax = plt.subplots(figsize=(w, max(2.6, min(9, w * aspect * 0.8 + 1.2))), dpi=160)
    used = []
    for spec, (name, col, a) in LAYERS.items():
        ps = [p for p in polys if (p.layer, p.datatype) == spec]
        if not ps:
            continue
        used.append(Patch(facecolor=col, alpha=min(1, a + 0.2), label=name))
        for p in ps:
            ax.add_patch(Polygon(p.points, closed=True, facecolor=col, edgecolor=col, lw=0.3, alpha=a))
    for lab in top.get_labels():
        if lab.texttype == 5:
            ax.annotate(lab.text, lab.origin, fontsize=6, ha="center", va="center", color="#0b0b0b")
    ax.set_xlim(x0 - 1, x1 + 1)
    ax.set_ylim(y0 - 1, y1 + 1)
    ax.set_aspect("equal")
    ax.set_xlabel("x (µm)")
    ax.set_ylabel("y (µm)")
    ax.set_title(title, loc="left", fontsize=11)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(handles=used, loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(png)
    print(png)


if __name__ == "__main__":
    gds, png, title = sys.argv[1], sys.argv[2], sys.argv[3]
    render(Path(gds), Path(png), title)
