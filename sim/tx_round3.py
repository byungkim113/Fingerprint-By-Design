"""Round 3 (pre-registered in PLAN.md, 2026-10-04): (1) B v2 on chips 1-16 (post hoc),
(2) authentication, (3) temperature x supply, (4) different data frames, (5) third chip set.

usage: python tx_round3.py sim | bv2_set1 | auth | ts | frames | set3
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))      # robust2
SUPPLIES = ["180", "162", "198", "171", "189", "1764", "1836"]
GRID_V = ["162", "171", "180", "189", "198"]


def jobs():
    j = [(dict(TX_FRAME=f, TX_TAG=f"frame{f}_", TX_VARIANT="vdd180"), ("tt_mm", 1, 16, 27.0)) for f in ("2", "3")]
    j += [(dict(TX_TAG="set3_", TX_VARIANT="vdd" + v), ("tt_mm", 33, 16, 27.0)) for v in SUPPLIES]
    j += [(dict(TX_TAG="fresh_", TX_VARIANT="vdd" + v), ("tt_mm", 17, 16, T)) for T in (-40.0, 85.0) for v in ("162", "180", "198")]
    j += [(dict(TX_VARIANT="vdd" + v), (c, 101, 6, T)) for T in (-40.0, 85.0) for v in GRID_V for c in ("ss_mm", "ff_mm")]
    return j


def run(job):
    env, args = job
    code = f"import tx_ident as ti; ti.run_one({args!r})"
    subprocess.run([sys.executable, "-c", code], cwd=HERE, env=dict(os.environ, **env), check=True)
    return f"done {env} {args}"


if __name__ == "__main__" and sys.argv[1] == "sim":
    with ThreadPoolExecutor(2) as ex:                           # 2 ngspice at a time
        for out in ex.map(run, jobs()):
            print(out, flush=True)


# ---------------------------------------------------------------- analyses
def _setup():
    import tx_full as tx
    import tx_ident as ti
    sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
    ti.MASKED = True
    return tx, ti


def _frames(tx, ti, d, seeds, ci, cq):
    ideal = (2 * ci / tx.N_UNITS - 1) + 1j * (2 * cq / tx.N_UNITS - 1)
    out = []
    for s in seeds:
        t, w = tx.load_wr(d / f"tx_out_{s}")
        y = tx.downconvert(t, w["rfp"] - w["rfn"], ti.N_SAMPLES)
        out.append(y / ((y @ ideal.conj()) / (ideal @ ideal.conj())))
    return np.array(out)


def _eer(gen, imp):
    """equal error rate from genuine/impostor scores (higher = more genuine)."""
    th = np.unique(np.concatenate([gen, imp]))
    frr = np.array([(gen < t).mean() for t in th])
    far = np.array([(imp >= t).mean() for t in th])
    i = int(np.argmin(np.abs(frr - far)))
    return float((frr[i] + far[i]) / 2)


def auth():
    from robust2 import drift_model, noise_cov
    import robust2
    tx, ti = _setup()
    ci, cq = ti.frame()
    W = tx.WORK
    gen = {v: _frames(tx, ti, W / f"ident_vdd{v}_tt_mm_T27", range(1, 17), ci, cq) for v in ("180", "162", "198")}
    imp = {v: _frames(tx, ti, W / f"ident_fresh_vdd{v}_tt_mm_T27", range(17, 33), ci, cq) for v in ("180", "162", "198")}
    feats = lambda Y: np.array([ti.features(y, ci, cq) for y in Y])
    grid = SUPPLIES_SORTED = ["162", "171", "1764", "180", "1836", "189", "198"]
    Fs = [np.stack([feats(_frames(tx, ti, W / f"ident_vdd{v}_{c}_T27", range(101, 107), ci, cq)) for v in grid])
          for c in ("ss_mm", "ff_mm")]
    robust2.T_GRID = np.round(np.arange(1.62, 1.9801, 0.01), 3)
    gv = [float(v[0] + "." + v[1:]) for v in grid]
    ms, cs = drift_model(Fs, gv, grid.index("180"))
    out = {}
    for snr in (30.0, 20.0):
        rows = {}
        for seed in (0, 1, 2):
            en = np.stack([ti.bursts(gen["180"][c], np.random.default_rng(10_000 * seed + c), snr, ti.N_ENROLL) for c in range(16)])
            keep = en.reshape(-1, en.shape[-1]).std(0) > 0
            sw = noise_cov(en, keep)
            mu = en[..., keep].mean(1)
            for v in ("180", "162", "198"):
                G = np.stack([ti.bursts(gen[v][c], np.random.default_rng(10_000 * seed + 7000 + c), snr, ti.N_TEST) for c in range(16)])[..., keep]
                I = np.stack([ti.bursts(imp[v][c], np.random.default_rng(10_000 * seed + 8000 + c), snr, ti.N_TEST) for c in range(16)])[..., keep]

                def scores(X, method):
                    if method == "BASE":
                        L = np.linalg.cholesky(sw)
                        w = lambda x: np.linalg.solve(L, x.reshape(-1, x.shape[-1]).T).T.reshape(x.shape)
                        return -((w(X)[:, :, None, :] - w(mu)[None, None]) ** 2).sum(-1)     # chip, burst, claim
                    from scipy.special import logsumexp
                    ll = []
                    for m, C in zip(ms, cs):
                        S = sw + C[np.ix_(keep, keep)]
                        L = np.linalg.cholesky(S)
                        w = lambda x: np.linalg.solve(L, x.reshape(-1, x.shape[-1]).T).T.reshape(x.shape)
                        d = ((w(X)[:, :, None, :] - w(mu + m[keep])[None, None]) ** 2).sum(-1)
                        ll.append(-0.5 * (d + 2 * np.log(np.diag(L)).sum()))
                    return logsumexp(np.stack(ll), axis=0)
                for method in ("BASE", "B"):
                    sg, si = scores(G, method), scores(I, method)
                    g = np.array([sg[c, :, c] for c in range(16)]).ravel()
                    rows.setdefault((v, method), []).append(_eer(g, si.ravel()))
        out[f"{snr:g}dB"] = {f"{v}_{m}": float(np.mean(x)) for (v, m), x in rows.items()}
        print(f"SNR {snr:g} dB  EER: " + "  ".join(f"{k}: {100 * x:.1f}%" for k, x in out[f"{snr:g}dB"].items()))
    (ti.RESULTS / "tx_auth.json").write_text(json.dumps(out, indent=1))


def frames_test():
    from robust2 import mahalanobis_acc, noise_cov
    tx, ti = _setup()
    from tx_validate import level_fit
    import tx_full as txf
    codes = {}
    for f in ("1", "2", "3"):
        ci, cq, _ = txf.qpsk_codes(ti.N_SAMPLES, seed=int(f))
        codes[f] = (ci, cq)
    W = tx.WORK
    Y = {"1": _frames(tx, ti, W / "ident_vdd180_tt_mm_T27", range(1, 17), *codes["1"]),
         "2": _frames(tx, ti, W / "ident_frame2_vdd180_tt_mm_T27", range(1, 17), *codes["2"]),
         "3": _frames(tx, ti, W / "ident_frame3_vdd180_tt_mm_T27", range(1, 17), *codes["3"])}
    seen = []
    for f, (ci, cq) in codes.items():
        _, _, si, sq = level_fit(Y[f][0], ci, cq)
        seen.append((si, sq))
    msk = (np.all([s[0] for s in seen], 0), np.all([s[1] for s in seen], 0))

    def feat(z, ci, cq):
        li, lq, _, _ = level_fit(z, ci, cq)
        out = []
        for lev, m in ((li, msk[0]), (lq, msk[1])):
            k = np.arange(len(lev))[m]; lv = lev[m]
            for part in (lv.real, lv.imag):
                out.append(part - np.polyval(np.polyfit(k, part, 1), k))
        return np.concatenate(out)

    def bursts(y, ci, cq, rng, snr, n):
        CI, CQ = np.tile(ci, ti.REPS), np.tile(cq, ti.REPS)
        ideal = (2 * CI / 31 - 1) + 1j * (2 * CQ / 31 - 1)
        s = np.sqrt(np.mean(np.abs(y) ** 2) / 10 ** (snr / 10) / 2)
        res = []
        for _ in range(n):
            z = np.tile(y, ti.REPS) * np.exp(1j * rng.uniform(0, 2 * np.pi))
            z = z + s * (rng.standard_normal(z.size) + 1j * rng.standard_normal(z.size))
            z = z / ((z @ ideal.conj()) / (ideal @ ideal.conj()))
            res.append(feat(z, CI, CQ))
        return np.array(res)

    out = {"common_codes": [int(msk[0].sum()), int(msk[1].sum())]}
    for snr in (30.0, 20.0):
        acc = {f: [] for f in ("1", "2", "3")}
        for seed in (0, 1, 2):
            en = np.stack([bursts(Y["1"][c], *codes["1"], np.random.default_rng(10_000 * seed + c), snr, ti.N_ENROLL) for c in range(16)])
            te = {i: np.stack([bursts(Y[f][c], *codes[f], np.random.default_rng(10_000 * seed + 5000 + 300 * i + c), snr, ti.N_TEST)
                               for c in range(16)]) for i, f in enumerate(("1", "2", "3"))}
            keep = en.reshape(-1, en.shape[-1]).std(0) > 0
            a = mahalanobis_acc(en, te, keep, noise_cov(en, keep))
            for i, f in enumerate(("1", "2", "3")):
                acc[f].append(a[i])
        out[f"{snr:g}dB"] = {f: float(np.mean(v)) for f, v in acc.items()}
        print(f"SNR {snr:g} dB  enroll frame 1 -> test frame 1/2/3: " + "  ".join(f"{v:.3f}" for v in out[f"{snr:g}dB"].values()))
    ok = min(out["30dB"]["2"], out["30dB"]["3"]) >= 0.9
    out["verdict"] = "PASS" if ok else "FAIL"
    print("pre-registered (4):", out["verdict"], "| common codes I/Q:", out["common_codes"])
    (ti.RESULTS / "tx_frames.json").write_text(json.dumps(out, indent=1))


def set3():
    import tx_supply
    tx_supply.analyze(tag="set3_", seeds=range(33, 49), grid=tx_supply.TEST_V, exclude_interior=False, out="tx_bv2_set3.json")


def ts():
    from robust2 import mahalanobis_acc, mixture_acc, noise_cov
    tx, ti = _setup()
    ci, cq = ti.frame()
    W = tx.WORK
    feats = lambda Y: np.array([ti.features(y, ci, cq) for y in Y])
    conds = [(T, v) for T in (-40, 27, 85) for v in GRID_V]
    tdir = lambda T, v, c, tag="": W / f"ident_{tag}vdd{v}_{c}_T{T}"
    Fd = {c: {k: feats(_frames(tx, ti, tdir(T, v, c), range(101, 107), ci, cq)) for k, (T, v) in enumerate(conds)}
          for c in ("ss_mm", "ff_mm")}
    k0 = conds.index((27, "180"))
    D = {k: np.concatenate([Fd[c][k] - Fd[c][k0] for c in Fd]) for k in range(len(conds))}
    ms = np.array([D[k].mean(0) for k in range(len(conds))])
    cs = np.array([(lambda r: r.T @ r / len(r))(D[k] - D[k].mean(0)) for k in range(len(conds))])
    md = np.array([ms[k] for k in range(len(conds)) if k != k0])
    _, S, Vt = np.linalg.svd(md, full_matrices=False)
    nk = int(np.searchsorted(np.cumsum(S ** 2) / np.sum(S ** 2), 0.95) + 1)
    P = np.eye(md.shape[1]) - Vt[:nk].T @ Vt[:nk]
    tests = [(27, "180")] + [(T, v) for T in (-40, 85) for v in ("162", "180", "198")]
    Y = {c: _frames(tx, ti, tdir(c[0], c[1], "tt_mm", "fresh_"), range(17, 33), ci, cq) for c in tests}
    out = {"M2_dims": nk}
    for snr in (30.0, 20.0):
        acc = {m: {c: [] for c in tests} for m in ("BASE", "M2", "B2D")}
        for seed in (0, 1, 2):
            en = np.stack([ti.bursts(Y[(27, "180")][c], np.random.default_rng(10_000 * seed + c), snr, ti.N_ENROLL) for c in range(16)])
            te = {i: np.stack([ti.bursts(Y[t][c], np.random.default_rng(10_000 * seed + 5000 + 300 * i + c), snr, ti.N_TEST)
                               for c in range(16)]) for i, t in enumerate(tests)}
            keep = en.reshape(-1, en.shape[-1]).std(0) > 0
            sw = noise_cov(en, keep)
            base = mahalanobis_acc(en, te, keep, sw)
            Pk = P[np.ix_(keep, keep)]
            proj = lambda X: (lambda Z: (Z.__setitem__((Ellipsis, keep), X[..., keep] @ Pk.T), Z)[1])(X.copy())
            enp = proj(en)
            m2 = mahalanobis_acc(enp, {i: proj(X) for i, X in te.items()}, keep, noise_cov(enp, keep))
            for i, t in enumerate(tests):
                acc["BASE"][t].append(base[i]); acc["M2"][t].append(m2[i])
                acc["B2D"][t].append(mixture_acc(en, te[i], keep, sw, ms, cs))
        A = {m: {f"{t[0]}C_{t[1]}": float(np.mean(x)) for t, x in d.items()} for m, d in acc.items()}
        out[f"{snr:g}dB"] = A
        print(f"SNR {snr:g} dB  " + "  ".join(f"{k:>9}" for k in A["BASE"]))
        for m in A:
            print(f"  {m:<5}      " + "  ".join(f"{x:9.3f}" for x in A[m].values()))
        b = A["BASE"]; nom = "27C_180"
        for m in ("M2", "B2D"):
            gaps = {k: b[nom] - b[k] for k in b if k != nom}
            rec = np.mean([(A[m][k] - b[k]) / g for k, g in gaps.items() if g > 0.0]) if any(g > 0 for g in gaps.values()) else None
            ok = all(A[m][k] >= b[k] for k in b if k != nom) and (rec is not None and rec >= 0.5) and b[nom] - A[m][nom] <= 0.02
            out[f"{snr:g}dB_{m}_verdict"] = dict(mean_recovery=rec, verdict="PASS" if ok else "FAIL")
            print(f"  {m}: mean recovery {rec if rec is None else round(rec, 3)} -> {'PASS' if ok else 'FAIL'}")
    (ti.RESULTS / "tx_temp_supply.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__" and sys.argv[1] != "sim":
    {"auth": auth, "frames": frames_test, "set3": set3, "ts": ts}[sys.argv[1]]()
