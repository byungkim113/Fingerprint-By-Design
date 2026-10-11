"""Model-based (prediction-error) receiver for identification on arbitrary data
(pre-registered in PLAN.md, 2026-10-04, gated stages 1-3).

Each chip is enrolled as a linear-in-parameters behavioural model of data -> received signal;
a burst is attributed to the chip whose model predicts it best (after a free complex gain).

usage: python tx_modelrx.py feasibility | noisy | feasibility2 | noisy2
"""
import json
import sys

import numpy as np

import tx_full as tx
import tx_ident as ti
import tx_round3 as r3

FRAMES = ("1", "2", "3")
DIRS = {"1": "ident_vdd180_tt_mm_T27", "2": "ident_frame2_vdd180_tt_mm_T27", "3": "ident_frame3_vdd180_tt_mm_T27"}


def codes(f):
    if f == "cov":
        return ti.coverage_codes()
    ci, cq, _ = tx.qpsk_codes(ti.N_SAMPLES, seed=int(f))
    return ci, cq


ENROLL2, TEST2 = ("1", "2", "3", "cov"), ("4", "5")


def frames2():
    d = lambda f: DIRS[f] if f in DIRS else f"ident_frame{f}_vdd180_tt_mm_T27"
    return {f: r3._frames(tx, ti, tx.WORK / d(f), range(1, 17), *codes(f)) for f in ENROLL2 + TEST2}


def score_mask(f):
    """samples of test frame f whose I and Q codes both occur in the enrollment sequences."""
    eI = set(np.concatenate([codes(e)[0] for e in ENROLL2])); eQ = set(np.concatenate([codes(e)[1] for e in ENROLL2]))
    ci, cq = codes(f)
    return np.array([a in eI and b in eQ for a, b in zip(ci, cq)])


def phi(ci, cq):
    """regressors per sample: DAC code one-hots + PA compression and 1-sample memory on the ideal symbol."""
    s0 = (2 * ci / 31 - 1) + 1j * (2 * cq / 31 - 1)
    p = np.r_[s0[0], s0[:-1]]
    a = np.abs(s0)
    return np.concatenate([np.eye(32)[ci], np.eye(32)[cq][:, 1:],
                           np.stack([s0 * a ** 2, s0 * a ** 4, p, p * np.abs(p) ** 2, np.ones_like(s0)], 1)], 1).astype(complex)


def frames():
    out = {}
    for f in FRAMES:
        ci, cq = codes(f)
        out[f] = r3._frames(tx, ti, tx.WORK / DIRS[f], range(1, 17), ci, cq)     # (chip, N), gain-normalised
    return out


def fit(Phis, ys, ridge=1e-6):
    A = np.concatenate(Phis); y = np.concatenate(ys)
    return np.linalg.solve(A.conj().T @ A + ridge * np.eye(A.shape[1]), A.conj().T @ y)


def score(y, Phi, theta, mask=None):
    """residual energy after the best complex gain on the model prediction (optionally masked)."""
    if mask is not None:
        y, Phi = y[mask], Phi[mask]
    p = Phi @ theta
    g = (p.conj() @ y) / (p.conj() @ p)
    return float(np.sum(np.abs(y - g * p) ** 2))


def feasibility():
    Y = frames()
    P = {f: phi(*codes(f)) for f in FRAMES}
    accs = {}
    for test in FRAMES:
        train = [f for f in FRAMES if f != test]
        th = [fit([P[f] for f in train], [Y[f][c] for f in train]) for c in range(16)]
        hits = [int(np.argmin([score(Y[test][c], P[test], t) for t in th]) == c) for c in range(16)]
        accs[test] = float(np.mean(hits))
    m = float(np.mean(list(accs.values())))
    go = m >= 0.90
    print(f"stage 1 (noise-free) held-out frame accuracy: {accs}  mean {m:.3f} -> {'GO' if go else 'STOP'}")
    (ti.RESULTS / "tx_modelrx_stage1.json").write_text(json.dumps(dict(acc=accs, mean=m, go=go), indent=1))
    return go


def noisy_bursts(y, snr, rng, n):
    s = np.sqrt(np.mean(np.abs(y) ** 2) / 10 ** (snr / 10) / 2)
    out = []
    for _ in range(n):
        z = np.tile(y, ti.REPS) * np.exp(1j * rng.uniform(0, 2 * np.pi))
        out.append(z + s * (rng.standard_normal(z.size) + 1j * rng.standard_normal(z.size)))
    return out


def noisy():
    Y = frames()
    P = {f: phi(*codes(f)) for f in FRAMES}
    PR = {f: np.tile(P[f], (ti.REPS, 1)) for f in FRAMES}
    res = {}
    for snr in (30.0, 20.0):
        accs = []
        for seed in (0, 1, 2):
            for k, test in enumerate(FRAMES):
                train = [f for f in FRAMES if f != test]
                th = []
                for c in range(16):
                    rng = np.random.default_rng(10_000 * seed + 100 * k + c)
                    Phis, ys = [], []
                    for f in train:
                        for z in noisy_bursts(Y[f][c], snr, rng, 20):
                            g = (z @ np.tile(Y[f][c], ti.REPS).conj()) / np.sum(np.abs(Y[f][c]) ** 2) / ti.REPS
                            Phis.append(PR[f]); ys.append(z / g)                     # enrollment knows the data
                    th.append(fit(Phis, ys))
                for c in range(16):
                    rng = np.random.default_rng(10_000 * seed + 5000 + 100 * k + c)
                    for z in noisy_bursts(Y[test][c], snr, rng, ti.N_TEST):
                        accs.append(int(np.argmin([score(z, PR[test], t) for t in th]) == c))
        res[f"{snr:g}dB"] = float(np.mean(accs))
        print(f"stage 2 (noisy) held-out frame accuracy at {snr:g} dB: {res[f'{snr:g}dB']:.3f}")
    go = res["30dB"] >= 0.90
    print("stage 2 ->", "GO" if go else "STOP")
    (ti.RESULTS / "tx_modelrx_stage2.json").write_text(json.dumps(dict(acc=res, go=go), indent=1))
    return go


def feasibility2():
    Y = frames2()
    P = {f: phi(*codes(f)) for f in Y}
    th = [fit([P[f] for f in ENROLL2], [Y[f][c] for f in ENROLL2]) for c in range(16)]
    accs = {}
    for f in TEST2:
        m = score_mask(f)
        accs[f] = float(np.mean([np.argmin([score(Y[f][c], P[f], t, m) for t in th]) == c for c in range(16)]))
    mean = float(np.mean(list(accs.values())))
    go = mean >= 0.90
    print(f"v2 stage 1 (noise-free, fresh frames): {accs}  mean {mean:.3f}  (scored samples: "
          f"{[int(score_mask(f).sum()) for f in TEST2]} of {ti.N_SAMPLES}) -> {'GO' if go else 'STOP'}")
    (ti.RESULTS / "tx_modelrx_v2_stage1.json").write_text(json.dumps(dict(acc=accs, mean=mean, go=go), indent=1))
    return go


def noisy2():
    Y = frames2()
    P = {f: phi(*codes(f)) for f in Y}
    PR = {f: np.tile(P[f], (ti.REPS, 1)) for f in Y}
    MR = {f: np.tile(score_mask(f), ti.REPS) for f in TEST2}
    res = {}
    for snr in (30.0, 20.0):
        accs = []
        for seed in (0, 1, 2):
            th = []
            for c in range(16):
                rng = np.random.default_rng(10_000 * seed + c)
                Phis, ys = [], []
                for f in ENROLL2:
                    ref = np.tile(Y[f][c], ti.REPS)
                    for z in noisy_bursts(Y[f][c], snr, rng, 20):
                        g = (z @ ref.conj()) / (ref @ ref.conj())                    # enrollment knows the data
                        Phis.append(PR[f]); ys.append(z / g)
                th.append(fit(Phis, ys))
            for k, f in enumerate(TEST2):
                for c in range(16):
                    rng = np.random.default_rng(10_000 * seed + 5000 + 100 * k + c)
                    for z in noisy_bursts(Y[f][c], snr, rng, ti.N_TEST):
                        accs.append(int(np.argmin([score(z, PR[f], t, MR[f]) for t in th]) == c))
        res[f"{snr:g}dB"] = float(np.mean(accs))
        print(f"v2 stage 2 (noisy, fresh frames) accuracy at {snr:g} dB: {res[f'{snr:g}dB']:.3f}")
    go = res["30dB"] >= 0.90
    print("v2 stage 2 ->", "GO" if go else "STOP")
    (ti.RESULTS / "tx_modelrx_v2_stage2.json").write_text(json.dumps(dict(acc=res, go=go), indent=1))
    return go


COND3 = [("162", 27), ("198", 27), ("180", 85), ("162", -40)]


def stage3():
    """combined drift + arbitrary data (pre-registered 2026-10-04): MRX vs MRX-B (model-space design-time
    drift offsets from ss/ff design chips on the coverage sequence)."""
    Y = frames2()
    P = {f: phi(*codes(f)) for f in Y}
    PR = {f: np.tile(P[f], (ti.REPS, 1)) for f in Y}
    cov = codes("cov")
    d = lambda tag, v, c, T: tx.WORK / f"ident_{tag}vdd{v}_{c}_T{T}"
    # design-time drift offsets in model space
    th_d = {}
    for v, T in [("180", 27)] + COND3:
        th_d[(v, T)] = [fit([P["cov"]], [y]) for c in ("ss_mm", "ff_mm")
                        for y in r3._frames(tx, ti, d("framecov_", v, c, T), range(101, 107), *cov)]
    dth = {k: np.mean(np.array(th_d[k]) - np.array(th_d[("180", 27)]), 0) for k in COND3}
    offsets = [np.zeros_like(dth[COND3[0]])] + [dth[k] for k in COND3]
    # test frames at each condition (nominal = the stage-2 fresh frames)
    tests = {("180", 27): {f: Y[f] for f in TEST2}}
    for v, T in COND3:
        tests[(v, T)] = {f: r3._frames(tx, ti, d(f"frame{f}_", v, "tt_mm", T), range(1, 17), *codes(f)) for f in TEST2}
    res = {}
    for snr in (30.0, 20.0):
        acc = {m: {k: [] for k in tests} for m in ("MRX", "MRX-B")}
        for seed in (0, 1, 2):
            th = []
            for c in range(16):
                rng = np.random.default_rng(10_000 * seed + c)
                Phis, ys = [], []
                for f in ENROLL2:
                    ref = np.tile(Y[f][c], ti.REPS)
                    for z in noisy_bursts(Y[f][c], snr, rng, 20):
                        g = (z @ ref.conj()) / (ref @ ref.conj())
                        Phis.append(PR[f]); ys.append(z / g)
                th.append(fit(Phis, ys))
            for i, (k, fr) in enumerate(tests.items()):
                for j, f in enumerate(TEST2):
                    for c in range(16):
                        rng = np.random.default_rng(10_000 * seed + 5000 + 300 * i + 100 * j + c)
                        for z in noisy_bursts(fr[f][c], snr, rng, ti.N_TEST):
                            acc["MRX"][k].append(int(np.argmin([score(z, PR[f], t) for t in th]) == c))
                            acc["MRX-B"][k].append(int(np.argmin([min(score(z, PR[f], t + o) for o in offsets)
                                                                    for t in th]) == c))
        A = {m: {f"{k[1]}C_{k[0]}": float(np.mean(x)) for k, x in dd.items()} for m, dd in acc.items()}
        res[f"{snr:g}dB"] = A
        print(f"SNR {snr:g} dB  " + "  ".join(f"{k:>9}" for k in A["MRX"]))
        for m in A:
            print(f"  {m:<6}     " + "  ".join(f"{x:9.3f}" for x in A[m].values()))
    a = res["30dB"]; dk = [f"{k[1]}C_{k[0]}" for k in COND3]
    mean_b = float(np.mean([a["MRX-B"][k] for k in dk]))
    ok = mean_b >= 0.80 and all(a["MRX-B"][k] >= a["MRX"][k] for k in dk)
    res["verdict"] = dict(mean_MRXB_drift=mean_b, PASS=ok)
    print(f"pre-registered stage 3: MRX-B mean over drift conditions {mean_b:.3f}, never below MRX: "
          f"{all(a['MRX-B'][k] >= a['MRX'][k] for k in dk)} -> {'PASS' if ok else 'FAIL'}")
    (ti.RESULTS / "tx_modelrx_stage3.json").write_text(json.dumps(res, indent=1, default=bool))


def score_sub(y, Phi, theta, B):
    """residual after fitting y ~ g * Phi theta + B beta (B = drift-direction waveforms)."""
    A = np.concatenate([(Phi @ theta)[:, None], B], 1)
    w, *_ = np.linalg.lstsq(A, y, rcond=None)
    return float(np.sum(np.abs(y - A @ w) ** 2))


def mrx_s(test_frames=TEST2, out="tx_modelrx_S_stepA.json", label="step A (exploratory)"):
    d = lambda tag, v, c, T: tx.WORK / f"ident_{tag}vdd{v}_{c}_T{T}"
    Y = frames2()
    for f in test_frames:
        if f not in Y:
            Y[f] = r3._frames(tx, ti, d(f"frame{f}_", "180", "tt_mm", 27), range(1, 17), *codes(f))
    P = {f: phi(*codes(f)) for f in Y}
    PR = {f: np.tile(P[f], (ti.REPS, 1)) for f in Y}
    cov = codes("cov")
    th_d = {k: [fit([P["cov"]], [y]) for c in ("ss_mm", "ff_mm")
                for y in r3._frames(tx, ti, d("framecov_", *k[:1], c, k[1]), range(101, 107), *cov)]
            for k in [("180", 27)] + COND3}
    D = np.concatenate([np.array(th_d[k]) - np.array(th_d[("180", 27)]) for k in COND3])      # 48 x params
    _, S, Vh = np.linalg.svd(D, full_matrices=False)
    r = int(np.searchsorted(np.cumsum(S ** 2) / np.sum(S ** 2), 0.95) + 1)
    Vr = Vh[:r].T                                                                               # params x r
    print(f"drift subspace: r = {r} directions (95% energy)")
    BR = {f: PR[f] @ Vr for f in test_frames}
    tests = {("180", 27): {f: Y[f] for f in test_frames}}
    for v, T in COND3:
        tests[(v, T)] = {f: r3._frames(tx, ti, d(f"frame{f}_", v, "tt_mm", T), range(1, 17), *codes(f)) for f in test_frames}
    res = {"r": r}
    for snr in (30.0, 20.0):
        acc = {m: {k: [] for k in tests} for m in ("MRX", "MRX-S")}
        for seed in (0, 1, 2):
            th = []
            for c in range(16):
                rng = np.random.default_rng(10_000 * seed + c)
                Phis, ys = [], []
                for f in ENROLL2:
                    ref = np.tile(Y[f][c], ti.REPS)
                    for z in noisy_bursts(Y[f][c], snr, rng, 20):
                        g = (z @ ref.conj()) / (ref @ ref.conj())
                        Phis.append(PR[f]); ys.append(z / g)
                th.append(fit(Phis, ys))
            for i, (k, fr) in enumerate(tests.items()):
                for j, f in enumerate(test_frames):
                    for c in range(16):
                        rng = np.random.default_rng(10_000 * seed + 5000 + 300 * i + 100 * j + c)
                        for z in noisy_bursts(fr[f][c], snr, rng, ti.N_TEST):
                            acc["MRX"][k].append(int(np.argmin([score(z, PR[f], t) for t in th]) == c))
                            acc["MRX-S"][k].append(int(np.argmin([score_sub(z, PR[f], t, BR[f]) for t in th]) == c))
        A = {m: {f"{k[1]}C_{k[0]}": float(np.mean(x)) for k, x in dd.items()} for m, dd in acc.items()}
        res[f"{snr:g}dB"] = A
        print(f"SNR {snr:g} dB  " + "  ".join(f"{k:>9}" for k in A["MRX"]))
        for m in A:
            print(f"  {m:<6}     " + "  ".join(f"{x:9.3f}" for x in A[m].values()))
    a = res["30dB"]; dk = [f"{k[1]}C_{k[0]}" for k in COND3]
    mean_s = float(np.mean([a["MRX-S"][k] for k in dk]))
    ok = mean_s >= 0.80 and all(a["MRX-S"][k] >= a["MRX"][k] for k in dk) and a["MRX"]["27C_180"] - a["MRX-S"]["27C_180"] <= 0.02
    res["verdict"] = dict(mean_drift=mean_s, ok=ok)
    print(f"{label}: MRX-S mean over drift {mean_s:.3f} -> {'PROMISING/PASS' if ok else 'NOT PROMISING/FAIL'}")
    (ti.RESULTS / out).write_text(json.dumps(res, indent=1, default=bool))
    return ok


def amp_cutoff():
    """design-time amplitude cutoff A* from the ss/ff design chips on the coverage sequence."""
    d = lambda v, c, T: tx.WORK / f"ident_framecov_vdd{v}_{c}_T{T}"
    ci, cq = codes("cov")
    a = np.abs((2 * ci / 31 - 1) + 1j * (2 * cq / 31 - 1))
    sp, dr = [], []
    for c in ("ss_mm", "ff_mm"):
        nom = r3._frames(tx, ti, d("180", c, 27), range(101, 107), ci, cq)
        sp.append(np.abs(nom - nom.mean(0)).mean(0))
        for v, T in COND3:
            k = r3._frames(tx, ti, d(v, c, T), range(101, 107), ci, cq)
            D = k - nom
            dr.append(np.abs(D - D.mean(0)).mean(0))
    sp, dr = np.mean(sp, 0), np.mean(dr, 0)
    best = None
    for q in np.arange(0.3, 1.01, 0.1):
        A = np.quantile(a, min(q, 1.0))
        m = a <= A + 1e-12
        ratio = sp[m].mean() / dr[m].mean()
        print(f"  quantile {q:.1f}: |s0| <= {A:.3f}  ({m.mean():.0%} of samples)  spread/drift {ratio:.2f}")
        if best is None or ratio > best[1]:
            best = (A, ratio, q)
    print(f"A* = {best[0]:.3f} (quantile {best[2]:.1f}, ratio {best[1]:.2f})")
    return best[0]


def mrx_a(test_frames=TEST2, out="tx_modelrx_A_stepA.json", label="step A (exploratory)"):
    A_star = amp_cutoff()
    d = lambda tag, v, c, T: tx.WORK / f"ident_{tag}vdd{v}_{c}_T{T}"
    Y = frames2()
    for f in test_frames:
        if f not in Y:
            Y[f] = r3._frames(tx, ti, d(f"frame{f}_", "180", "tt_mm", 27), range(1, 17), *codes(f))
    P = {f: phi(*codes(f)) for f in Y}
    PR = {f: np.tile(P[f], (ti.REPS, 1)) for f in Y}
    MR = {}
    for f in test_frames:
        ci, cq = codes(f)
        MR[f] = np.tile(np.abs((2 * ci / 31 - 1) + 1j * (2 * cq / 31 - 1)) <= A_star + 1e-12, ti.REPS)
    print("scored fraction:", {f: round(float(MR[f].mean()), 2) for f in test_frames})
    tests = {("180", 27): {f: Y[f] for f in test_frames}}
    for v, T in COND3:
        tests[(v, T)] = {f: r3._frames(tx, ti, d(f"frame{f}_", v, "tt_mm", T), range(1, 17), *codes(f)) for f in test_frames}
    res = {"A_star": float(A_star)}
    for snr in (30.0, 20.0):
        acc = {m_: {k: [] for k in tests} for m_ in ("MRX", "MRX-A")}
        for seed in (0, 1, 2):
            th = []
            for c in range(16):
                rng = np.random.default_rng(10_000 * seed + c)
                Phis, ys = [], []
                for f in ENROLL2:
                    ref = np.tile(Y[f][c], ti.REPS)
                    for z in noisy_bursts(Y[f][c], snr, rng, 20):
                        g = (z @ ref.conj()) / (ref @ ref.conj())
                        Phis.append(PR[f]); ys.append(z / g)
                th.append(fit(Phis, ys))
            for i, (k, fr) in enumerate(tests.items()):
                for j, f in enumerate(test_frames):
                    for c in range(16):
                        rng = np.random.default_rng(10_000 * seed + 5000 + 300 * i + 100 * j + c)
                        for z in noisy_bursts(fr[f][c], snr, rng, ti.N_TEST):
                            acc["MRX"][k].append(int(np.argmin([score(z, PR[f], t) for t in th]) == c))
                            acc["MRX-A"][k].append(int(np.argmin([score(z, PR[f], t, MR[f]) for t in th]) == c))
        A = {m_: {f"{k[1]}C_{k[0]}": float(np.mean(x)) for k, x in dd.items()} for m_, dd in acc.items()}
        res[f"{snr:g}dB"] = A
        print(f"SNR {snr:g} dB  " + "  ".join(f"{k:>9}" for k in A["MRX"]))
        for m_ in A:
            print(f"  {m_:<6}     " + "  ".join(f"{x:9.3f}" for x in A[m_].values()))
    a = res["30dB"]; dk = [f"{k[1]}C_{k[0]}" for k in COND3]
    mean_a = float(np.mean([a["MRX-A"][k] for k in dk]))
    ok = mean_a >= 0.80 and all(a["MRX-A"][k] >= a["MRX"][k] for k in dk) and a["MRX"]["27C_180"] - a["MRX-A"]["27C_180"] <= 0.02
    res["verdict"] = dict(mean_drift=mean_a, ok=ok)
    print(f"{label}: MRX-A mean over drift {mean_a:.3f} -> {'PROMISING/PASS' if ok else 'NOT PROMISING/FAIL'}")
    (ti.RESULTS / out).write_text(json.dumps(res, indent=1, default=bool))
    return ok


if __name__ == "__main__":
    {"mrx_a": mrx_a, "feasibility": feasibility, "noisy": noisy, "feasibility2": feasibility2, "noisy2": noisy2,
     "stage3": stage3, "mrx_s": mrx_s,
     "mrx_s_confirm": lambda: mrx_s(("6", "7"), "tx_modelrx_S_stepB.json", "step B (confirmatory)")}[sys.argv[1]]()
