"""Figure: identification accuracy vs SNR at the temperature extremes, with and
without shared-drift removal (drift_test results, 3 seeds, mean ± std)."""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SNRS = [10, 15, 20, 25, 30]
SERIES = [("baseline", "No drift handling", "#2a78d6"),
          ("subspace", "Remove simulated drift (no sensor)", "#eb6834"),
          ("known_temp", "Subtract drift at known temperature", "#1baf7a")]


def load(snr):
    f = ROOT / "results" / ("drift_test.json" if snr == 20 else f"drift_test_snr{snr}.json")
    return json.loads(f.read_text())


def main():
    runs = {s: load(s) for s in SNRS}
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), dpi=160, sharey=True)
    for ax, temp in zip(axes, ["-40", "27", "85"]):
        for key, name, col in SERIES:
            m = np.array([np.mean([r[key][temp] for r in runs[s]]) for s in SNRS])
            sd = np.array([np.std([r[key][temp] for r in runs[s]]) for s in SNRS])
            ax.plot(SNRS, m * 100, color=col, lw=2, marker="o", ms=5, label=name)
            ax.fill_between(SNRS, (m - sd) * 100, (m + sd) * 100, color=col, alpha=0.15, lw=0)
        ax.set_title(f"{temp} °C", loc="left", fontsize=11)
        ax.set_xticks(SNRS)
        ax.set_xlabel("SNR (dB)")
        ax.grid(axis="y", color="#e4e3dd", lw=0.8)
        ax.set_ylim(0, 100)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].set_ylabel("Chip identification accuracy (%)")
    axes[0].legend(loc="lower right", frameon=False, fontsize=8)
    fig.suptitle("Drift removal needs ≥20 dB SNR  (150 chips, enrolled at 27 °C, 1 burst per decision, "
                 "3 seeds; band = ±1 std)", x=0.01, ha="left", fontsize=10)
    fig.tight_layout()
    out = ROOT / "figures" / "noise_sweep.png"
    fig.savefig(out)
    print(out)


if __name__ == "__main__":
    main()
