"""Analyses of the pre-registered tests V (supply drift), N (more chips) and P (post-layout);
see PLAN.md, 2026-10-03. Masked features and the BASE classifier, as in step 2d.

usage: python tx_more_tests.py vdd | more | pex
"""
import json
import os
import sys

import numpy as np

import tx_full as tx
import tx_ident as ti

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis"))
from robust2 import mahalanobis_acc, noise_cov  # noqa: E402

ti.MASKED = True
CI, CQ = ti.frame()
IDEAL = (2 * CI / tx.N_UNITS - 1) + 1j * (2 * CQ / tx.N_UNITS - 1)


def frames(d, seeds):
    out = []
    for s in seeds:
        t, w = tx.load_wr(d / f"tx_out_{s}")
        y = tx.downconvert(t, w["rfp"] - w["rfn"], ti.N_SAMPLES)
        out.append(y / ((y @ IDEAL.conj()) / (IDEAL @ IDEAL.conj())))
    return np.array(out)


def accuracy(Y_enroll, Y_tests, snr, seeds=(0, 1, 2)):
    """BASE classifier; Y_enroll (chip, N), Y_tests {name: (chip, N)} -> {name: acc}."""
    res = {k: [] for k in Y_tests}
    names = list(Y_tests)
    for seed in seeds:
        n = len(Y_enroll)
        en = np.stack([ti.bursts(Y_enroll[c], np.random.default_rng(10_000 * seed + c), snr, ti.N_ENROLL)
                       for c in range(n)])
        te = {i: np.stack([ti.bursts(Y_tests[k][c], np.random.default_rng(10_000 * seed + 5000 + 300 * i + c),
                                     snr, ti.N_TEST) for c in range(n)]) for i, k in enumerate(names)}
        keep = en.reshape(-1, en.shape[-1]).std(0) > 0
        a = mahalanobis_acc(en, te, keep, noise_cov(en, keep))
        for i, k in enumerate(names):
            res[k].append(a[i])
    return {k: float(np.mean(v)) for k, v in res.items()}


def feats(Y):
    return np.array([ti.features(y, CI, CQ) for y in Y])


def drift_ratio(F_ref, F_other):
    d = F_other - F_ref
    return float(F_ref.std(0).mean() / np.abs(d - d.mean(0)).mean())


def vdd():
    seeds = range(1, 17)
    Y = {"1.80": frames(ti.run_dir("tt_mm", 27.0), seeds),
         "1.62": frames(tx.WORK / "ident_vdd162_tt_mm_T27", seeds),
         "1.98": frames(tx.WORK / "ident_vdd198_tt_mm_T27", seeds)}
    F = {k: feats(v) for k, v in Y.items()}
    out = {"ratio": {k: drift_ratio(F["1.80"], F[k]) for k in ("1.62", "1.98")}}
    for snr in (30.0, 20.0):
        out[f"acc_{snr:g}dB"] = accuracy(Y["1.80"], Y, snr)
    gaps = {s: max(out[f"acc_{s:g}dB"]["1.80"] - out[f"acc_{s:g}dB"][k] for k in ("1.62", "1.98")) for s in (30.0, 20.0)}
    out["verdict"] = "VDD drift matters" if max(gaps.values()) >= 0.05 else "VDD drift does not matter"
    print(json.dumps(out, indent=1))
    (ti.RESULTS / "tx_vdd.json").write_text(json.dumps(out, indent=1))


def more():
    Y = np.concatenate([frames(ti.run_dir("tt_mm", 27.0), range(1, 17)),
                        frames(tx.WORK / "ident_more_a_tt_mm_T27", range(17, 41)),
                        frames(tx.WORK / "ident_more_b_tt_mm_T27", range(41, 65))])
    out = {}
    for n in (16, 32, 64):
        out[n] = {f"{snr:g}dB": accuracy(Y[:n], {"27": Y[:n]}, snr)["27"] for snr in (30.0, 20.0, 15.0, 10.0)}
        print(f"N={n:>2}: " + "  ".join(f"{k}: {v:.3f}" for k, v in out[n].items()))
    (ti.RESULTS / "tx_more_chips.json").write_text(json.dumps(out, indent=1))


def pex():
    temps = [-40.0, 27.0, 85.0]
    seeds = range(1, 17)
    Yp = {T: frames(tx.WORK / f"pex_tt_mm_T{T:g}", seeds) for T in temps}
    Ys = {T: frames(ti.run_dir("tt_mm", T), seeds) for T in temps}
    out = {}
    for name, Y in (("schematic", Ys), ("post-layout", Yp)):
        F = {T: feats(Y[T]) for T in temps}
        r = {"S_rf": float(F[27.0].std(0).mean()),
             "ratio": float(np.mean([drift_ratio(F[27.0], F[T]) for T in (-40.0, 85.0)]))}
        for snr in (30.0, 20.0):
            r[f"acc_{snr:g}dB"] = accuracy(Y[27.0], {f"{T:g}": Y[T] for T in temps}, snr)
        out[name] = r
        print(name, json.dumps(r))
    rel = out["post-layout"]["S_rf"] / out["schematic"]["S_rf"]
    ok = out["post-layout"]["acc_30dB"]["27"] >= 0.9 and 0.67 <= rel <= 1.5
    out["verdict"] = {"S_rf post/schematic": rel, "PASS": ok}
    print("pre-registered P:", "PASS" if ok else "FAIL", f"(S_rf ratio {rel:.2f})")
    (ti.RESULTS / "tx_pex.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    {"vdd": vdd, "more": more, "pex": pex}[sys.argv[1]]()
