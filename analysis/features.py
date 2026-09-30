"""Per-chip fingerprint features from the three block datasets, and a
uniqueness-vs-stability score for each feature.

Score per feature: between-chip std (uniqueness) divided by within-chip std
across temperature (drift). Computed raw, and after subtracting the population
mean at each temperature ("common-mode drift removed", what an on-chip
temperature sensor plus a population model could correct).
"""
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parents[1] / "data"
RL_DAC = 20e3             # DAC resistive load for code-dependent nonlinearity


def load():
    dac = np.load(DATA / "dac_200.npz")
    pa = np.load(DATA / "pa_200.npz")
    lo = np.load(DATA / "lo_200.npz")
    assert (dac["temps"] == pa["temps"]).all() and (dac["temps"] == lo["temps"]).all()
    assert (dac["chips"] == pa["chips"]).all() and (dac["chips"] == lo["chips"]).all()
    return dac, pa, lo


def block_features(dac, pa, lo, vdd_idx=1):
    """-> dict block -> array (T, chip, n_feat), plus feature names."""
    temps = dac["temps"]
    # DAC: relative unit-current pattern at Vo=0.9 (I and Q), plus I/Q DAC gain ratio
    u = dac["data"][:, :, :, 1, :]                        # T, chip, iq, unit
    rel = u / u.mean(-1, keepdims=True) - 1
    dac_gain_ratio = u[:, :, 1].sum(-1) / u[:, :, 0].sum(-1) - 1
    dac_f = np.concatenate([rel.reshape(*rel.shape[:2], -1),
                            dac_gain_ratio[..., None]], -1)
    dac_names = [f"dac_{c}_u{k}" for c in "iq" for k in range(u.shape[-1])] + ["dac_iq_gain"]
    # PA: small-signal gain, compression at max drive, AM/PM at max drive
    p = pa["data"][:, vdd_idx]                             # T, chip, amp, [mag, ph]
    g = p[..., 0] / pa["amps"]
    pa_f = np.stack([g[..., 0], g[..., -1] / g[..., 0], p[..., -1, 1] - p[..., 0, 1]], -1)
    pa_names = ["pa_gain", "pa_compression", "pa_ampm_deg"]
    # LO: I/Q gain imbalance (dB) and phase error (deg)
    d = lo["data"]
    lo_f = np.stack([20 * np.log10(d[..., 2] / d[..., 0]),
                     np.degrees(d[..., 3] - d[..., 1]) - 90], -1)
    lo_names = ["lo_iq_gain_db", "lo_iq_phase_deg"]
    return temps, {"dac": (dac_f, dac_names), "pa": (pa_f, pa_names),
                   "lo": (lo_f, lo_names)}


def stability_scores(f):
    """f: (T, chip, n_feat) -> (raw_score, cm_removed_score), each (n_feat,)."""
    between = f.std(1).mean(0)                             # across chips, avg over T
    within_raw = f.std(0).mean(0)                          # across T, avg over chips
    f_cm = f - f.mean(1, keepdims=True)
    within_cm = f_cm.std(0).mean(0)
    return between / within_raw, between / within_cm


if __name__ == "__main__":
    dac, pa, lo = load()
    temps, blocks = block_features(dac, pa, lo)
    print("temps:", temps)
    print(f"{'feature':<18}{'between σ':>12}{'raw score':>12}{'CM-removed':>12}")
    for b, (f, names) in blocks.items():
        raw, cm = stability_scores(f)
        between = f.std(1).mean(0)
        idx = range(len(names)) if b != "dac" else [0, 1, 31, 62]
        for i in idx:
            print(f"{names[i]:<18}{between[i]:>12.4g}{raw[i]:>12.2f}{cm[i]:>12.2f}")
        if b == "dac":
            print(f"{'  (dac units median)':<18}{'':>12}{np.median(raw[:62]):>12.2f}{np.median(cm[:62]):>12.2f}")
