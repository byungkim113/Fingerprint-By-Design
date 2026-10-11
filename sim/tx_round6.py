"""LDO tests L1-L3 (pre-registered in PLAN.md 2026-10-06): simulations."""
import os
import subprocess

import numpy as np
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
VINS = ["330", "297", "363", "3135", "3465", "3234", "3366"]


def jobs():
    j = [(dict(TX_TAG="ldo_", TX_VARIANT="ldo" + v), 27.0) for v in VINS]                                   # L1
    j += [(dict(TX_TAG=f"ldof{f}_", TX_FRAME=f, TX_VARIANT="ldo330"), 27.0) for f in ("2", "3", "cov")]     # L3 enroll
    j += [(dict(TX_TAG=f"ldof{f}_", TX_FRAME=f, TX_VARIANT=v), T)                                           # L3 tests
          for v, T in (("ldo330", 27.0), ("ldo297", 27.0), ("ldo363", 27.0), ("ldo330", 85.0), ("ldo297", -40.0))
          for f in ("4", "5")]
    j += [(dict(TX_TAG="ldo_", TX_VARIANT="ldo" + v), T) for T in (-40.0, 85.0) for v in ("297", "330", "363")]  # L2
    return j


def run(job):
    env, T = job
    subprocess.run([sys.executable, "-c", f"import tx_ident as ti; ti.run_one(('tt_mm', 1, 16, {T}))"],
                   cwd=HERE, env=dict(os.environ, **env), check=True)
    return f"done {env} T={T}"


if __name__ == "__main__" and len(sys.argv) == 1:
    with ThreadPoolExecutor(2) as ex:
        for out in ex.map(run, jobs()):
            print(out, flush=True)


# ------------------------------------------------------------------ analyses (pre-registered L1-L3)
def _d(tag, v, T):
    import tx_full as tx
    return tx.WORK / f"ident_{tag}ldo{v}_tt_mm_T{T}"


def l1():
    import json
    import tx_ident as ti
    import tx_more_tests as m
    Y = {v: m.frames(_d("ldo_", v, 27), range(1, 17)) for v in VINS}
    order = ["297", "3135", "3234", "330", "3366", "3465", "363"]
    out = {}
    for snr in (30.0, 20.0):
        a = m.accuracy(Y["330"], {v: Y[v] for v in order}, snr)
        out[f"{snr:g}dB"] = a
        print(f"L1 {snr:g} dB  " + "  ".join(f"{float(v[0] + '.' + v[1:]):.3f}V: {a[v]:.3f}" for v in order))
    ok = min(out["30dB"].values()) >= 0.90
    out["verdict"] = "PASS" if ok else "FAIL"
    print("pre-registered L1:", out["verdict"])
    (ti.RESULTS / "tx_ldo_L1.json").write_text(json.dumps(out, indent=1))


def l2():
    import json
    import tx_ident as ti
    import tx_more_tests as m
    conds = [(T, v) for T in (-40, 85) for v in ("297", "330", "363")]
    Y0 = m.frames(_d("ldo_", "330", 27), range(1, 17))
    Y = {f"{T}C_{v}": m.frames(_d("ldo_", v, T), range(1, 17)) for T, v in conds}
    out = {}
    for snr in (30.0, 20.0):
        a = m.accuracy(Y0, dict({"27C_330": Y0}, **Y), snr)
        out[f"{snr:g}dB"] = a
        print(f"L2 {snr:g} dB  " + "  ".join(f"{k}: {x:.3f}" for k, x in a.items()))
    mean = float(np.mean([out["30dB"][k] for k in Y]))
    out["verdict"] = dict(mean_30dB=mean, PASS=mean >= 0.80)
    print(f"pre-registered L2: mean over 6 conditions {mean:.3f} ->", "PASS" if mean >= 0.80 else "FAIL")
    (ti.RESULTS / "tx_ldo_L2.json").write_text(json.dumps(out, indent=1, default=bool))


def l3():
    import json
    import tx_full as tx
    import tx_ident as ti
    import tx_modelrx as mr
    import tx_round3 as r3
    fr = lambda f, v, T: r3._frames(tx, ti, (_d("ldo_", v, T) if f == "1" else _d(f"ldof{f}_", v, T)), range(1, 17), *mr.codes(f))
    Y = {f: fr(f, "330", 27) for f in ("1", "2", "3", "cov")}
    P = {f: mr.phi(*mr.codes(f)) for f in ("1", "2", "3", "cov", "4", "5")}
    PR = {f: np.tile(P[f], (ti.REPS, 1)) for f in P}
    conds = [("330", 27), ("297", 27), ("363", 27), ("330", 85), ("297", -40)]
    tests = {c: {f: fr(f, *c) for f in ("4", "5")} for c in conds}
    out = {}
    for snr in (30.0, 20.0):
        acc = {c: [] for c in conds}
        for seed in (0, 1, 2):
            th = []
            for c in range(16):
                rng = np.random.default_rng(10_000 * seed + c)
                Phis, ys = [], []
                for f in ("1", "2", "3", "cov"):
                    ref = np.tile(Y[f][c], ti.REPS)
                    for z in mr.noisy_bursts(Y[f][c], snr, rng, 20):
                        g = (z @ ref.conj()) / (ref @ ref.conj())
                        Phis.append(PR[f]); ys.append(z / g)
                th.append(mr.fit(Phis, ys))
            for i, cnd in enumerate(conds):
                for j, f in enumerate(("4", "5")):
                    for c in range(16):
                        rng = np.random.default_rng(10_000 * seed + 5000 + 300 * i + 100 * j + c)
                        for z in mr.noisy_bursts(tests[cnd][f][c], snr, rng, ti.N_TEST):
                            acc[cnd].append(int(np.argmin([mr.score(z, PR[f], t) for t in th]) == c))
        A = {f"{T}C_{v}": float(np.mean(x)) for (v, T), x in acc.items()}
        out[f"{snr:g}dB"] = A
        print(f"L3 {snr:g} dB  " + "  ".join(f"{k}: {x:.3f}" for k, x in A.items()))
    a = out["30dB"]
    mean = float(np.mean([a[k] for k in ("27C_297", "27C_363", "85C_330", "-40C_297")]))
    ok = mean >= 0.80 and a["27C_330"] >= 0.90
    out["verdict"] = dict(mean_drift=mean, PASS=ok)
    print(f"pre-registered L3: nominal {a['27C_330']:.3f}, mean over drift {mean:.3f} ->", "PASS" if ok else "FAIL")
    (ti.RESULTS / "tx_ldo_L3.json").write_text(json.dumps(out, indent=1, default=bool))


if __name__ == "__main__" and len(sys.argv) > 1:
    import numpy as np  # noqa: F811
    {"l1": l1, "l2": l2, "l3": l3}[sys.argv[1]]()
