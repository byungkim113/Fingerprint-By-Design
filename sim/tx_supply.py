"""Item 2: supply drift on the v2 core (pre-registered in PLAN.md, 2026-10-03).

2a tolerance: tt_mm seeds 1-16 at seven supplies; 2b design-time compensation for supply:
M2 (projection of the shared-drift subspace) and B (robust2 M5 mixture over a 0.01 V grid),
both learned only from ss_mm/ff_mm chips (seeds 101-106) at five supplies.

usage: python tx_supply.py sim      python tx_supply.py analyze
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TEST_V = ["162", "171", "1764", "180", "1836", "189", "198"]
GRID_V = ["162", "171", "180", "189", "198"]
DEPLOY = ("tt_mm", 1, 16)
DESIGN = [("ss_mm", 101, 6), ("ff_mm", 101, 6)]
volt = lambda v: float(v[0] + "." + v[1:])


def jobs():
    j = [("vdd" + v, *DEPLOY) for v in ("180", "162", "198", "171", "189", "1764", "1836")]
    return j + [("vdd" + v, c, s0, n) for v in GRID_V for c, s0, n in DESIGN]


def run(job):
    variant, corner, s0, n = job
    code = f"import tx_ident as ti; ti.run_one(({corner!r}, {s0}, {n}, 27.0))"
    subprocess.run([sys.executable, "-c", code], cwd=HERE, env=dict(os.environ, TX_VARIANT=variant), check=True)
    return f"done {variant} {corner}"


def analyze(tag="", seeds=range(1, 17), grid=GRID_V, exclude_interior=True, out="tx_supply.json"):
    """tag/seeds select the test chips; grid = design-time supplies; exclude_interior drops a test
    supply from the interpolation when it is an interior grid point (v1 rule)."""
    import tx_full as tx
    import tx_ident as ti
    sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
    from robust2 import drift_model, mahalanobis_acc, mixture_acc, noise_cov
    import robust2
    ti.MASKED = True
    ci, cq = ti.frame()
    ideal = (2 * ci / tx.N_UNITS - 1) + 1j * (2 * cq / tx.N_UNITS - 1)

    def frames(v, corner, seeds, tag=""):
        d = tx.WORK / f"ident_{tag}vdd{v}_{corner}_T27"
        out = []
        for s in seeds:
            t, w = tx.load_wr(d / f"tx_out_{s}")
            y = tx.downconvert(t, w["rfp"] - w["rfn"], ti.N_SAMPLES)
            out.append(y / ((y @ ideal.conj()) / (ideal @ ideal.conj())))
        return np.array(out)

    feats = lambda Y: np.array([ti.features(y, ci, cq) for y in Y])
    GRID_V = list(grid)
    Yd = {v: frames(v, "tt_mm", seeds, tag) for v in TEST_V}
    # design-time features: list (per corner) of (V, chip, f), grid order
    Fs = [np.stack([feats(frames(v, c, range(s0, s0 + n))) for v in GRID_V]) for c, s0, n in DESIGN]
    gv = [volt(v) for v in GRID_V]
    g0 = GRID_V.index("180")
    # M2: shared-drift subspace from the per-V mean drift of the design-time chips
    D = np.concatenate([F[k] - F[g0] for F in Fs for k in range(len(GRID_V)) if k != g0])
    mean_drifts = np.array([np.concatenate([F[k] - F[g0] for F in Fs]).mean(0)
                            for k in range(len(GRID_V)) if k != g0])
    U, S, Vt = np.linalg.svd(mean_drifts, full_matrices=False)
    k = int(np.searchsorted(np.cumsum(S ** 2) / np.sum(S ** 2), 0.95) + 1)
    P = np.eye(D.shape[1]) - Vt[:k].T @ Vt[:k]
    # B: mixture over a 0.01 V grid
    robust2.T_GRID = np.round(np.arange(1.62, 1.9801, 0.01), 3)
    full = drift_model(Fs, gv, g0)
    res = {"M2_dims": k}
    for snr in (30.0, 20.0):
        acc = {m: {v: [] for v in TEST_V} for m in ("BASE", "M2", "B")}
        for seed in (0, 1, 2):
            n = 16
            en = np.stack([ti.bursts(Yd["180"][c], np.random.default_rng(10_000 * seed + c), snr, ti.N_ENROLL)
                           for c in range(n)])
            te = {i: np.stack([ti.bursts(Yd[v][c], np.random.default_rng(10_000 * seed + 5000 + 300 * i + c),
                                         snr, ti.N_TEST) for c in range(n)]) for i, v in enumerate(TEST_V)}
            keep = en.reshape(-1, en.shape[-1]).std(0) > 0
            sw = noise_cov(en, keep)
            base = mahalanobis_acc(en, te, keep, sw)
            Pk = P[np.ix_(keep, keep)]
            enp = en.copy(); enp[..., keep] = en[..., keep] @ Pk.T
            tep = {}
            for i, X in te.items():
                Xp = X.copy(); Xp[..., keep] = X[..., keep] @ Pk.T; tep[i] = Xp
            swp = noise_cov(enp, keep)                   # Ledoit-Wolf on the projected enrollment
            m2 = mahalanobis_acc(enp, tep, keep, swp)
            for i, v in enumerate(TEST_V):
                acc["BASE"][v].append(base[i]); acc["M2"][v].append(m2[i])
                interior = v in GRID_V and v not in ("162", "180", "198")
                excl = GRID_V.index(v) if (exclude_interior and interior) else None
                ms, cs = drift_model(Fs, gv, g0, exclude=excl) if excl is not None else full
                acc["B"][v].append(mixture_acc(en, te[i], keep, sw, ms, cs))
        A = {m: {v: float(np.mean(x)) for v, x in d.items()} for m, d in acc.items()}
        res[f"{snr:g}dB"] = A
        print(f"SNR {snr:g} dB   " + "  ".join(f"{volt(v):>6.3f}" for v in TEST_V))
        for m in A:
            print(f"  {m:<5}        " + "  ".join(f"{A[m][v]:6.3f}" for v in TEST_V))
        b = A["BASE"]
        tol = max([0.0] + [x for x, (lo, hi) in ((2, ("1764", "1836")), (5, ("171", "189")), (10, ("162", "198")))
                           if b[lo] >= 0.9 and b[hi] >= 0.9])
        print(f"  tolerance (BASE >= 0.90): +-{tol:g}%")
        for m in ("M2", "B"):
            gap = {v: b["180"] - b[v] for v in ("162", "198")}
            rec = {v: ((A[m][v] - b[v]) / g) if g >= 0.05 else None for v, g in gap.items()}
            cost = b["180"] - A[m]["180"]
            harm = all(A[m][v] >= b[v] for v in TEST_V)
            ok = None if any(r is None for r in rec.values()) else (min(rec.values()) >= 0.5 and cost <= 0.02 and harm)
            verdict = "not testable" if ok is None else ("PASS" if ok else "FAIL")
            print(f"  {m}: recovery {rec}  cost@1.80 {100 * cost:+.1f} pts  no-harm {harm} -> {verdict}")
            res[f"{snr:g}dB_{m}_verdict"] = dict(recovery=rec, cost=cost, no_harm=harm, verdict=verdict)
        res[f"{snr:g}dB_tolerance_pct"] = tol
    (ti.RESULTS / out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "sim":
        with ThreadPoolExecutor(2) as ex:                     # 2 ngspice at a time
            for out in ex.map(run, jobs()):
                print(out, flush=True)
    else:
        analyze()
