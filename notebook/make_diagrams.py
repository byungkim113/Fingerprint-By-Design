"""Static explanatory figures for the notebook: signal chain, research workflow, annotated layout."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

def box(ax, x, y, w, h, text, fc, fs=9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec="#333", lw=1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs)

def arrow(ax, x0, y0, x1, y1):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="->", lw=1.2, color="#333"))

# 1. signal chain
fig, ax = plt.subplots(figsize=(11, 4.2))
ax.set_xlim(0, 11); ax.set_ylim(0, 4.2); ax.axis("off")
C_DAC, C_LO, C_PA, C_SUP = "#cfe2ff", "#d7f5d0", "#ffd9c7", "#eee3ff"
box(ax, 0.1, 2.6, 1.4, 0.8, "data bits\n(124 lines)", "#f2f2f2")
box(ax, 1.9, 3.1, 1.6, 0.7, "I DAC\n31 current cells", C_DAC); box(ax, 1.9, 2.1, 1.6, 0.7, "Q DAC\n31 current cells", C_DAC)
box(ax, 3.9, 3.1, 1.5, 0.7, "I mixer\n(switching quad)", C_DAC); box(ax, 3.9, 2.1, 1.5, 0.7, "Q mixer\n(switching quad)", C_DAC)
box(ax, 5.8, 2.6, 1.3, 0.8, "shared load\n+ coupling", C_PA); box(ax, 7.4, 2.6, 1.3, 0.8, "PA\n(diff. pair)", C_PA)
box(ax, 9.0, 2.6, 1.4, 0.8, "output buffer\n-> 50 ohm", C_PA)
box(ax, 0.1, 0.9, 1.4, 0.8, "external LO\n200 MHz", "#f2f2f2"); box(ax, 1.9, 0.9, 1.4, 0.8, "LO input\nbuffer", C_LO)
box(ax, 3.6, 0.9, 1.3, 0.8, "RC-CR\n(I/Q split)", C_LO); box(ax, 5.2, 0.9, 1.4, 0.8, "limiters\n(inverters)", C_LO)
box(ax, 7.2, 0.15, 1.5, 0.75, "bandgap +\nbias reference", C_SUP); box(ax, 9.0, 0.15, 1.4, 0.75, "LDO\n3.3 V -> 1.8 V", C_SUP)
for (a, b) in (((1.5, 3.0), (1.9, 3.45)), ((1.5, 3.0), (1.9, 2.45)), ((3.5, 3.45), (3.9, 3.45)), ((3.5, 2.45), (3.9, 2.45)),
               ((5.4, 3.45), (5.8, 3.1)), ((5.4, 2.45), (5.8, 2.9)), ((7.1, 3.0), (7.4, 3.0)), ((8.7, 3.0), (9.0, 3.0)),
               ((1.5, 1.3), (1.9, 1.3)), ((3.3, 1.3), (3.6, 1.3)), ((4.9, 1.3), (5.2, 1.3))):
    arrow(ax, *a, *b)
arrow(ax, 5.9, 1.7, 4.65, 2.1); arrow(ax, 6.1, 1.7, 4.65, 3.1)
ax.text(5.5, 4.0, "transistor-level SKY130 transmitter core (everything except the LO source and data bits is on chip)",
        ha="center", fontsize=9, style="italic")
ax.text(9.7, 1.05, "supplies every block", ha="center", fontsize=8, color="#555")
fig.savefig("images/signal_chain.png", dpi=150, bbox_inches="tight"); plt.close(fig)

# 2. research workflow
fig, ax = plt.subplots(figsize=(11, 2.6))
ax.set_xlim(0, 11); ax.set_ylim(0, 2.6); ax.axis("off")
steps = [("1. Design + layout", "SKY130 transmitter,\nDRC / LVS / PEX", "#cfe2ff"),
         ("2. Virtual chips", "Monte Carlo mismatch:\nmany chips of one design", "#d7f5d0"),
         ("3. Fingerprint", "receiver measures each\nchip's DAC level pattern", "#ffd9c7"),
         ("4. Pre-registered tests", "prediction + pass rule\nwritten before each run", "#fff1b8"),
         ("5. Design change", "PA, DAC, LDO ...\nthen test again", "#eee3ff")]
for i, (t, s, c) in enumerate(steps):
    x = 0.1 + i * 2.18
    box(ax, x, 0.55, 1.95, 1.5, "", c)
    ax.text(x + 0.975, 1.7, t, ha="center", fontsize=9.5, weight="bold"); ax.text(x + 0.975, 1.05, s, ha="center", fontsize=8.5)
    if i < 4:
        arrow(ax, x + 1.95, 1.3, x + 2.18, 1.3)
ax.annotate("", xy=(1.0, 0.5), xytext=(9.8, 0.5), arrowprops=dict(arrowstyle="->", lw=1, color="#888", connectionstyle="arc3,rad=0.25"))
ax.text(5.4, 0.02, "design changes go back into the loop - all before any silicon exists", ha="center", fontsize=8.5, color="#555")
fig.savefig("images/workflow.png", dpi=150, bbox_inches="tight"); plt.close(fig)

# 3. annotated layout (pixel boxes on the 1800 x 1340 render)
img = plt.imread("images/chip_layout.png")
fig, ax = plt.subplots(figsize=(12, 9))
ax.imshow(img); ax.axis("off")
labels = [((30, 25, 1660, 520), "transmitter core", "#1f6fd1"),
          ((30, 545, 1760, 1315), "on-chip LDO: bandgap reference, error amplifier, 5 V pass device, soft-start, decoupling", "#8a2be2")]
for (x0, y0, x1, y1), t, c in labels:
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec=c, lw=2.2, ls="--"))
    if y0 < 100:
        ax.text(x0 + 8, y0 - 8, t, color=c, fontsize=11, weight="bold", va="bottom")
    else:
        ax.text(x0 + 8, y1 + 10, t, color=c, fontsize=11, weight="bold", va="top")
blocks = [((40, 120), "LO in"), ((230, 360), "LO path\n(RC-CR + limiters)"), ((560, 140), "Q DAC + mixer"),
          ((790, 470), "I DAC + mixer"), ((640, 300), "bias ref."), ((1080, 380), "output network + PA"),
          ((1360, 100), "output\nbuffer")]
for (x, y), t in blocks:
    ax.text(x, y, t, fontsize=9.5, color="black", bbox=dict(fc="white", ec="#999", alpha=0.85, pad=2))
fig.savefig("images/chip_layout_annotated.png", dpi=110, bbox_inches="tight"); plt.close(fig)
print("diagrams written")
