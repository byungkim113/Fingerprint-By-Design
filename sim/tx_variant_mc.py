"""Step 2d: Monte Carlo of the design variants and the pre-registered comparison with the
base core (PLAN.md, 2026-10-03). Same chips (tt_mm seeds 1-16) and the 2a pipeline.

usage: python tx_variant_mc.py sim <palin N_DEG>    (all variant x T sessions, 2 at a time)
       python tx_variant_mc.py analyze <palin N_DEG>
"""
import os
import sys

if sys.argv[1] == "one":                       # must be set before tx_full is imported
    os.environ["TX_VARIANT"] = sys.argv[2]
    os.environ["TX_NDEG"] = sys.argv[3]

import json                                    # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402

import numpy as np                             # noqa: E402

import tx_full as tx                           # noqa: E402
import tx_ident as ti                          # noqa: E402

TEMPS = [-40.0, 27.0, 85.0]
SEEDS = range(1, 17)
SNRS = (30.0, 20.0)


def vdir(variant, temp):
    v = "" if variant == "base" else f"{variant}_"
    return tx.WORK / f"ident_{v}tt_mm_T{temp:g}"


def load(variant):
    """-> RF and mixer-output frames (T, chip, N), gain-normalised."""
    ci, cq = ti.frame()
    ideal = (2 * ci / tx.N_UNITS - 1) + 1j * (2 * cq / tx.N_UNITS - 1)
    nrm = lambda y: y / ((y @ ideal.conj()) / (ideal @ ideal.conj()))
    rf, mix = [], []
    for T in TEMPS:
        r, m = [], []
        for s in SEEDS:
            t, w = tx.load_wr(vdir(variant, T) / f"tx_out_{s}")
            r.append(nrm(tx.downconvert(t, w["rfp"] - w["rfn"], ti.N_SAMPLES)))
            m.append(nrm(tx.downconvert(t, w["outp"] - w["outn"], ti.N_SAMPLES)))
        rf.append(r); mix.append(m)
    return np.array(rf), np.array(mix)


def metrics(variant):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis"))
    from robust2 import mahalanobis_acc, noise_cov
    ti.MASKED = True
    ci, cq = ti.frame()
    Yr, Ym = load(variant)
    F = lambda Y: np.array([[ti.features(y, ci, cq) for y in Y[k]] for k in range(len(TEMPS))])
    Fr, Fm = F(Yr), F(Ym)
    t0 = TEMPS.index(27.0)
    s_rf, s_mix = float(Fr[t0].std(0).mean()), float(Fm[t0].std(0).mean())
    drift = []
    for k in range(len(TEMPS)):
        if k != t0:
            d = Fr[k] - Fr[t0]
            drift.append(np.abs(d - d.mean(0)).mean())
    out = dict(S_rf=s_rf, S_mix=s_mix, drift=float(np.mean(drift)), ratio=s_rf / float(np.mean(drift)))
    for snr in SNRS:
        accs = []
        for seed in (0, 1, 2):
            en = np.stack([ti.bursts(Yr[t0, c], np.random.default_rng(10_000 * seed + c), snr, ti.N_ENROLL)
                           for c in range(len(SEEDS))])
            te = {k: np.stack([ti.bursts(Yr[k, c], np.random.default_rng(10_000 * seed + 5000 + 300 * k + c),
                                         snr, ti.N_TEST) for c in range(len(SEEDS))]) for k in range(len(TEMPS))}
            keep = en.reshape(-1, en.shape[-1]).std(0) > 0
            accs.append(mahalanobis_acc(en, te, keep, noise_cov(en, keep)))
        out[f"acc_{snr:g}dB"] = {f"{TEMPS[k]:g}": float(np.mean([a[k] for a in accs])) for k in range(len(TEMPS))}
    return out


if __name__ == "__main__":
    if sys.argv[1] == "one":                   # one session: this variant at temperature argv[4]
        seed0, n = {"more_a": (17, 24), "more_b": (41, 24)}.get(tx.VARIANT, (1, 16))
        print("done", tx.VARIANT, ti.run_one(("tt_mm", seed0, n, float(sys.argv[4]))), flush=True)
        sys.exit()
    if sys.argv[1] == "queue":                 # extra jobs "variant:T" ..., 2 sessions at a time
        import subprocess
        from concurrent.futures import ThreadPoolExecutor
        jobs = [j.split(":") for j in sys.argv[2:]]
        run = lambda j: subprocess.run([sys.executable, __file__, "one", j[0], "2", j[1]],
                                       capture_output=True, text=True).stdout.strip()
        with ThreadPoolExecutor(2) as ex:
            for out in ex.map(run, jobs):
                print(out, flush=True)
        sys.exit()
    if sys.argv[1] == "sim":
        import subprocess
        jobs = [(v, T) for v in ("palin", "bigdac") for T in TEMPS]
        run = lambda j: subprocess.run([sys.executable, __file__, "one", j[0], sys.argv[2], str(j[1])],
                                       capture_output=True, text=True).stdout.strip()
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(2) as ex:      # 2 sessions = 2 ngspice at a time
            for out in ex.map(run, jobs):
                print(out, flush=True)
        sys.exit()
    res = {v: metrics(v) for v in ("base", "palin", "bigdac")}
    b = res["base"]
    for v, r in res.items():
        print(f"{v:<7} S_rf {r['S_rf']:.4f} ({r['S_rf'] / b['S_rf']:.2f}x)  S_mix {r['S_mix']:.4f} "
              f"({r['S_mix'] / b['S_mix']:.2f}x)  drift {r['drift']:.4f}  ratio {r['ratio']:.1f}")
        for snr in SNRS:
            a = r[f"acc_{snr:g}dB"]
            print(f"        {snr:g} dB: " + "  ".join(f"{t:>4}: {x:.3f}" for t, x in a.items()))
    p, g = res["palin"], res["bigdac"]
    v = {"P1 bigdac": 0.35 <= g["S_mix"] / b["S_mix"] <= 0.65 and 0.35 <= g["S_rf"] / b["S_rf"] <= 0.65,
         "P2 palin": 0.8 <= p["S_mix"] / b["S_mix"] <= 1.25 and p["S_rf"] / b["S_rf"] < 0.7}
    gap = lambda r, s: max(r[f"acc_{s:g}dB"]["27"] - r[f"acc_{s:g}dB"][t] for t in ("-40", "85"))
    rebuild = any(gap(r, s) >= 0.05 for r in (p, g) for s in SNRS) or any(r["ratio"] < 1.5 for r in (p, g))
    print("pre-registered:", {k: "PASS" if x else "FAIL" for k, x in v.items()},
          f"| anti-fingerprint suppression {b['S_rf'] / p['S_rf']:.2f}x, 20 dB acc @27C "
          f"{b['acc_20dB']['27']:.3f} -> {p['acc_20dB']['27']:.3f}",
          "| fast-model rebuild:", "YES" if rebuild else "no")
    res["verdicts"] = dict(v, rebuild=rebuild, palin_ndeg=int(sys.argv[2]))
    (ti.RESULTS / "tx_variants_mc.json").write_text(json.dumps(res, indent=1, default=bool))
