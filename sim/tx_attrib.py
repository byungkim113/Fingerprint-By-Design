"""Step 2b: which block carries the chip-specific fingerprint the Python model misses
(pre-registered in PLAN.md, 2026-10-02). Uses only the step-2a runs (tx_ident.py).

Stages, each turned into the same masked level-ladder residual features:
  S_dac   : model frame from the chip's op DAC unit currents, ideal LO
  S_lo_rc : S_dac with the RC-CR ac outputs as I/Q gains (what the Python model uses)
  S_lo_lim: S_dac with the limiter-output fundamentals as I/Q gains
  S_mix   : transistor-level mixer output outp - outn
  RF      : rfp - rfn (target)
No parameters are fitted; R2 compares chip-specific parts (mean over chips removed).
"""
import json

import numpy as np

import tx_full as tx
from tx_ident import N_SAMPLES, RESULTS, TEMPS, features, frame, parse_log, run_dir

SEEDS = range(1, 17)


def aligned_features(z, ci, cq):
    """rotation-invariant variant (deviation from the pre-registration, see PLAN.md): each
    ladder is rotated onto its own fitted direction before taking along-ladder (INL) and
    cross-ladder residuals, so a systematic ladder angle (common quadrature error) cannot
    move a chip's DAC nonlinearity between features."""
    from tx_validate import level_fit
    li, lq, si, sq = level_fit(z, ci, cq)
    out = []
    # only codes the frame actually uses (unused levels come out of the fit as 0 and
    # corrupted every residual in the first run; C2 masked them the same way)
    for lev, seen in ((li, si), (lq, sq)):
        k = np.arange(len(lev))[seen]
        lev = lev[seen]
        v = lev * np.exp(-1j * np.angle(np.polyfit(k, lev, 1)[0]))
        for part in (v.real, v.imag):
            out.append(part - np.polyval(np.polyfit(k, part, 1), k))
    return np.concatenate(out)


def norm(y, ideal):
    return y / ((y @ ideal.conj()) / (ideal @ ideal.conj()))


def fundamental(t, v):
    return np.trapezoid(v * np.exp(-2j * np.pi * tx.FLO * t), t)


def stage_features(temp, feat=features):
    ci, cq = frame()
    ideal = (2 * ci / tx.N_UNITS - 1) + 1j * (2 * cq / tx.N_UNITS - 1)
    d = run_dir("tt_mm", temp)
    ops = parse_log((d / "ngspice.log").read_text())
    out = {k: [] for k in ("S_dac", "S_lo_rc", "S_lo_lim", "S_mix", "RF")}
    lim = []
    for s in SEEDS:
        t, w = tx.load_wr(d / f"tx_out_{s}")
        lim.append(fundamental(t, w["lo_q"]) / fundamental(t, w["lo_i"]))
    u = 1j * np.sign(np.mean(lim).imag)                      # nominal quadrature direction
    for s, r_lim in zip(SEEDS, lim):
        t, w = tx.load_wr(d / f"tx_out_{s}")
        op = ops[s]
        cum = [np.concatenate([[0.0], np.cumsum(op["u"][k])]) for k in (0, 1)]
        bi = 2 * cum[0][ci] / cum[0][-1] - 1
        bq = 2 * cum[1][cq] / cum[1][-1] - 1
        gi = op["vm(vi)"] * np.exp(1j * (op["vp(vi)"] + np.pi / 4))
        gq = op["vm(vq)"] * np.exp(1j * (op["vp(vq)"] - np.pi / 4))
        frames = {"S_dac": bi + 1j * bq,
                  "S_lo_rc": gi / abs(gi) * bi + 1j * gq / abs(gi) * bq,
                  "S_lo_lim": bi + 1j * (r_lim / u) * bq,
                  "S_mix": tx.downconvert(t, w["outp"] - w["outn"], N_SAMPLES),
                  "RF": tx.downconvert(t, w["rfp"] - w["rfn"], N_SAMPLES)}
        for k, y in frames.items():
            out[k].append(feat(norm(y, ideal), ci, cq))
    return {k: np.array(v) for k, v in out.items()}


def r2(P, Q):
    return 1 - ((P - Q) ** 2).sum() / (P ** 2).sum()


if __name__ == "__main__":
    import sys
    aligned = "--aligned" in sys.argv
    print("features:", "ladder-aligned (deviation)" if aligned else "as pre-registered (fixed axes)")
    res = {}
    for temp in TEMPS:
        F = stage_features(temp, aligned_features if aligned else features)
        C = {k: v - v.mean(0) for k, v in F.items()}             # chip-specific parts
        row = {k: dict(R2=float(r2(C["RF"], C[k])),
                       corr=float(np.median([np.corrcoef(a, b)[0, 1] for a, b in zip(C["RF"], C[k])])))
               for k in ("S_dac", "S_lo_rc", "S_lo_lim", "S_mix")}
        lo = max(row["S_lo_rc"]["R2"], row["S_lo_lim"]["R2"])
        row["increments"] = {"DAC unit currents": row["S_dac"]["R2"],
                             "LO imbalance": lo - row["S_dac"]["R2"],
                             "switches/quads/load": row["S_mix"]["R2"] - lo,
                             "PA + output buffer": 1 - row["S_mix"]["R2"]}
        res[f"{temp:g}"] = row
        print(f"T={temp:5g}  " + "  ".join(f"{k} R2 {row[k]['R2']:+.3f} (r {row[k]['corr']:.2f})"
                                           for k in ("S_dac", "S_lo_rc", "S_lo_lim", "S_mix")))
        print("         increments: " + "  ".join(f"{k} {v:+.3f}" for k, v in row["increments"].items()))
    inc = res["27"]["increments"]
    beyond = {k: v for k, v in inc.items() if k != "DAC unit currents"}
    top = max(beyond, key=beyond.get)
    print(f"pre-registered rule @27C: largest increment beyond DAC = {top} {beyond[top]:+.3f} -> "
          + ("dominant missing block: do 2c" if beyond[top] >= 0.25 else "spread out: skip 2c"))
    (RESULTS / f"tx_attrib{'_aligned' if aligned else ''}.json").write_text(json.dumps(res, indent=1))
