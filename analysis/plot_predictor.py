"""Figure: design-time common-drift fraction vs measured effect of drift removal."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
NAMES = {"dac": "D1 10 µA", "dac2": "D2 cascode", "dac_ztc": "D5 ZTC 7.1 µA", "dac_hi": "D4 40 µA",
         "dac_lo": "D7 1 µA", "dac_sl": "D3 short L", "dac_casL": "D6 long-L cascode"}
HELD_OUT = {"dac2", "dac_casL"}
rows = json.loads((ROOT / "results" / "predictor.json").read_text())
fig, ax = plt.subplots(figsize=(8, 5), dpi=160)
ax.axvline(0.60, color="#8a8a86", lw=1, ls="--")
ax.axhline(0, color="#8a8a86", lw=0.8)
ax.text(0.605, 52, "rule: apply if ≥ 0.60", fontsize=8, color="#52514e")
for r in rows:
    y = 100 * (r["delta"]["-40"] + r["delta"]["85"]) / 2
    ho = r["design"] in HELD_OUT
    ax.scatter(r["frac"], y, s=70, color="#2a78d6", edgecolor="white", linewidth=2, zorder=3,
               marker="D" if ho else "o")
    ax.annotate(NAMES[r["design"]] + (" (held out)" if ho else ""), (r["frac"], y),
                xytext=(6, -12) if r["design"] == "dac_sl" else (6, 4), textcoords="offset points",
                fontsize=8, color="#0b0b0b")
ax.set_xlim(0.2, 1.05)
ax.set_xlabel("Common-drift fraction, from wrong-corner design simulation only")
ax.set_ylabel("Accuracy change from drift removal\n(mean of −40 °C and 85 °C, points)")
ax.set_title("Design-time simulation predicts whether drift removal helps (7 DAC designs)",
             loc="left", fontsize=10)
ax.grid(axis="y", color="#e4e3dd", lw=0.8)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(ROOT / "figures" / "predictor.png")
print(ROOT / "figures" / "predictor.png")
