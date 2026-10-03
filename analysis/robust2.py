"""Pre-registered methods A (M4A) and B (M5); see PLAN.md for the rules.

M4A: M4 (Mahalanobis with S_w + lambda * Sigma_T) with lambda chosen per design by
     leave-one-wrong-corner-out on simulated design-time chips only.
M5 : temperature-marginalised likelihood. For each candidate chip, the burst is
     scored by log sum_k N(v; mu_c + m(T_k), S_w + C(T_k)) over a 5 C grid, where
     m(T) and C(T) are the shared and chip-specific drift from wrong-corner
     simulation, linearly interpolated in T. Testing at an interior temperature
     (0 or 55 C) excludes that simulated point from the interpolation.

Uses the same enrollment/test bursts (same RNG seeds) as generalize.py and
drift_cov.py, so the baseline comparison is paired.

usage: python robust2.py <design> [--seeds 0,1,2]
"""
import argparse
import json

import numpy as np
from scipy.special import logsumexp
from sklearn.covariance import LedoitWolf

from drift_test import DEPLOY, N_ENROLL, N_TEST, RESULTS, T_ENROLL, feats
from generalize import SNR, WRONG, corner_params, deployed, noise_free

LAMBDA_GRID = [0.0, 0.03, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0]
T_GRID = np.unique(np.r_[np.arange(-40, 86, 5.0), 27.0])   # 5 C grid plus the enrollment temperature
SEL_ENROLL, SEL_TEST = 20, 5


# ---------- shared helpers ----------
def mahalanobis_acc(enroll, tests, keep, S):
    """nearest enrolled mean under S; enroll (chip,burst,f), tests {ti: (chip,burst,f)}."""
    mu = enroll[..., keep].mean(1)
    L = np.linalg.cholesky(S)
    W = lambda x: np.linalg.solve(L, x.reshape(-1, x.shape[-1]).T).T.reshape(x.shape)
    tpl = W(mu)
    truth = np.arange(len(mu))[:, None]
    out = {}
    for ti, X in tests.items():
        v = W(X[..., keep])
        d = ((v[:, :, None, :] - tpl[None, None]) ** 2).sum(-1)
        out[ti] = float((d.argmin(-1) == truth).mean())
    return out


def noise_cov(enroll, keep):
    e = enroll[..., keep]
    return LedoitWolf().fit((e - e.mean(1, keepdims=True)).reshape(-1, keep.sum())).covariance_


def drift_vectors(Fs, t0):
    """Fs: list of noise-free (T, chip, f) arrays -> dict ti -> (samples, f) drift d = f(T)-f(27)."""
    out = {}
    for ti in range(Fs[0].shape[0]):
        if ti != t0:
            out[ti] = np.concatenate([F[ti] - F[t0] for F in Fs])
    return out


def sigma_t(Fs, t0):
    d = np.concatenate(list(drift_vectors(Fs, t0).values()))
    return d.T @ d / len(d)


# ---------- A: lambda selection on design-time chips ----------
def select_lambda(design, p, temps, t0, Fs):
    scores = np.zeros(len(LAMBDA_GRID))
    for k, c in enumerate(WRONG):
        pc = corner_params(design, c, p.unit_nom)
        chips = range(pc.dac_units.shape[1])
        en = np.stack([feats(pc, t0, ch, np.random.default_rng(90_000 + 1000 * k + ch), SNR, SEL_ENROLL)
                       for ch in chips])
        te = {ti: np.stack([feats(pc, ti, ch, np.random.default_rng(95_000 + 1000 * k + 100 * ti + ch),
                                  SNR, SEL_TEST) for ch in chips]) for ti in range(len(temps))}
        keep = en.reshape(-1, en.shape[-1]).std(0) > 0
        sw = noise_cov(en, keep)
        st = sigma_t([F for j, F in enumerate(Fs) if j != k], t0)[np.ix_(keep, keep)]
        for i, lam in enumerate(LAMBDA_GRID):
            scores[i] += np.mean(list(mahalanobis_acc(en, te, keep, sw + lam * st).values()))
    scores /= len(WRONG)
    return LAMBDA_GRID[int(np.argmax(scores))], scores.round(4).tolist()


# ---------- B: temperature-marginalised likelihood ----------
def drift_model(Fs, temps, t0, exclude=None):
    """m(T), C(T) on T_GRID by linear interpolation of the simulated temperatures,
    optionally excluding one simulated temperature index."""
    dv = drift_vectors(Fs, t0)
    f = Fs[0].shape[-1]
    pts = {temps[t0]: (np.zeros(f), np.zeros((f, f)))}
    for ti, d in dv.items():
        if ti == exclude:
            continue
        m = d.mean(0)
        r = d - m
        pts[temps[ti]] = (m, r.T @ r / len(r))
    ts = sorted(pts)
    ms, cs = [], []
    for T in T_GRID:
        j = np.searchsorted(ts, T)
        if j == 0 or ts[min(j, len(ts) - 1)] == T:
            t = ts[min(j, len(ts) - 1)]
            ms.append(pts[t][0]); cs.append(pts[t][1])
            continue
        if j >= len(ts):
            t = ts[-1]
            ms.append(pts[t][0]); cs.append(pts[t][1])
            continue
        a, b = ts[j - 1], ts[j]
        w = (T - a) / (b - a)
        ms.append((1 - w) * pts[a][0] + w * pts[b][0])
        cs.append((1 - w) * pts[a][1] + w * pts[b][1])
    return np.array(ms), np.array(cs)


def mixture_acc(enroll, X, keep, sw, ms, cs):
    mu = enroll[..., keep].mean(1)                                   # cand, f
    v = X[..., keep]                                                 # chip, burst, f
    ll = []
    for m, C in zip(ms, cs):
        S = sw + C[np.ix_(keep, keep)]
        L = np.linalg.cholesky(S)
        logdet = 2 * np.log(np.diag(L)).sum()
        W = lambda x: np.linalg.solve(L, x.reshape(-1, x.shape[-1]).T).T.reshape(x.shape)
        tpl = W(mu + m[keep])
        wv = W(v)
        d = ((wv[:, :, None, :] - tpl[None, None]) ** 2).sum(-1)    # chip, burst, cand
        ll.append(-0.5 * (d + logdet))
    score = logsumexp(np.stack(ll), axis=0)
    truth = np.arange(len(mu))[:, None]
    return float((score.argmax(-1) == truth).mean())


def run(design, seed, lam_sel):
    p = deployed(design)
    temps = list(p.temps)
    t0 = temps.index(T_ENROLL)
    Fs = [noise_free(corner_params(design, c, p.unit_nom),
                     range(corner_params(design, c, p.unit_nom).dac_units.shape[1]), temps) for c in WRONG]
    enroll = np.stack([feats(p, t0, c, np.random.default_rng(10_000 * seed + c), SNR, N_ENROLL)
                       for c in DEPLOY])
    tests = {ti: np.stack([feats(p, ti, c, np.random.default_rng(10_000 * seed + 5000 + 300 * ti + c),
                                 SNR, N_TEST) for c in DEPLOY]) for ti in range(len(temps))}
    keep = enroll.reshape(-1, enroll.shape[-1]).std(0) > 0
    sw = noise_cov(enroll, keep)
    st = sigma_t(Fs, t0)[np.ix_(keep, keep)]
    a = mahalanobis_acc(enroll, tests, keep, sw + lam_sel * st)
    res = {"M4A": {f"{temps[ti]:g}": v for ti, v in a.items()}}
    b = {}
    interior = {temps.index(0.0), temps.index(55.0)}
    full = drift_model(Fs, temps, t0)
    for ti in range(len(temps)):
        ms, cs = drift_model(Fs, temps, t0, exclude=ti) if ti in interior else full
        b[f"{temps[ti]:g}"] = mixture_acc(enroll, tests[ti], keep, sw, ms, cs)
    res["M5"] = b
    return dict(design=design, seed=seed, snr=SNR, lambda_selected=lam_sel, **res)


def run_m5_only(design, seed):
    """Noise-sweep mode: BASE (Mahalanobis, no drift model) and M5 at the module SNR."""
    p = deployed(design)
    temps = list(p.temps)
    t0 = temps.index(T_ENROLL)
    Fs = [noise_free(corner_params(design, c, p.unit_nom),
                     range(corner_params(design, c, p.unit_nom).dac_units.shape[1]), temps) for c in WRONG]
    enroll = np.stack([feats(p, t0, c, np.random.default_rng(10_000 * seed + c), SNR, N_ENROLL)
                       for c in DEPLOY])
    tests = {ti: np.stack([feats(p, ti, c, np.random.default_rng(10_000 * seed + 5000 + 300 * ti + c),
                                 SNR, N_TEST) for c in DEPLOY]) for ti in range(len(temps))}
    keep = enroll.reshape(-1, enroll.shape[-1]).std(0) > 0
    sw = noise_cov(enroll, keep)
    base = mahalanobis_acc(enroll, tests, keep, sw)
    res = {"BASE": {f"{temps[ti]:g}": v for ti, v in base.items()}}
    interior = {temps.index(0.0), temps.index(55.0)}
    full = drift_model(Fs, temps, t0)
    res["M5"] = {}
    for ti in range(len(temps)):
        ms, cs = drift_model(Fs, temps, t0, exclude=ti) if ti in interior else full
        res["M5"][f"{temps[ti]:g}"] = mixture_acc(enroll, tests[ti], keep, sw, ms, cs)
    return dict(design=design, seed=seed, snr=SNR, **res)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--snr", type=float, default=None, help="noise-sweep mode: only BASE (lambda=0) and M5")
    a = ap.parse_args()
    if a.snr is not None:
        import generalize, sys as _s
        SNR = a.snr
        _s.modules[__name__].SNR = a.snr
        out = [run_m5_only(a.design, int(s)) for s in a.seeds.split(",")]
        tag = f"_snr{a.snr:g}" + ("" if a.seeds == "0,1,2" else "_seeds" + a.seeds.replace(",", "-"))
        (RESULTS / f"robust2_{a.design}{tag}.json").write_text(json.dumps(out, indent=1))
        m = lambda k, t: np.mean([r[k][t] for r in out])
        print(f"{a.design} SNR {a.snr:g}")
        for k in ("BASE", "M5"):
            print(f"  {k:<5}" + "  ".join(f"{t:>4}:{m(k, t):.3f}" for t in ("-40", "0", "27", "55", "85")))
        gap = {t: m("BASE", "27") - m("BASE", t) for t in ("-40", "85")}
        rec = {t: (m("M5", t) - m("BASE", t)) / gap[t] for t in gap}
        harm = all(m("M5", t) >= m("BASE", t) for t in gap)
        print(f"  M5: gap rec -40 {rec['-40']:.1%}  85 {rec['85']:.1%} -> {'PASS' if min(rec.values()) >= .5 else 'FAIL'}"
              f" | 27C cost {100 * (m('BASE', '27') - m('M5', '27')):+.1f} pts | no-harm {'yes' if harm else 'NO'}")
        raise SystemExit
    p = deployed(a.design)
    temps = list(p.temps)
    t0 = temps.index(T_ENROLL)
    Fs = [noise_free(corner_params(a.design, c, p.unit_nom),
                     range(corner_params(a.design, c, p.unit_nom).dac_units.shape[1]), temps) for c in WRONG]
    lam, sel_scores = select_lambda(a.design, p, temps, t0, Fs)
    out = [run(a.design, int(s), lam) for s in a.seeds.split(",")]
    for r in out:
        r["lambda_scores"] = dict(zip(map(str, LAMBDA_GRID), sel_scores))
    tag = "" if a.seeds == "0,1,2" else "_seeds" + a.seeds.replace(",", "-")
    (RESULTS / f"robust2_{a.design}{tag}.json").write_text(json.dumps(out, indent=1))

    base = json.loads((RESULTS / f"generalize_{a.design}.json").read_text())
    m4 = json.loads((RESULTS / f"drift_cov_{a.design}.json").read_text())
    m = lambda rs, k, t: np.mean([r[k][t] for r in rs])
    print(f"{a.design}: lambda selected {lam}  (design-time scores {dict(zip(LAMBDA_GRID, sel_scores))})")
    rows = [("baseline", base, "baseline"), ("M4", m4, "M4"), ("M4A", out, "M4A"), ("M5", out, "M5")]
    for name, rs, k in rows:
        print(f"  {name:<9}" + "  ".join(f"{t:>4}:{m(rs, k, t):.3f}" for t in ("-40", "0", "27", "55", "85")))
    for k in ("M4A", "M5"):
        gap = {t: m(base, "baseline", "27") - m(base, "baseline", t) for t in ("-40", "85")}
        rec = {t: (m(out, k, t) - m(base, "baseline", t)) / gap[t] for t in gap}
        cost = m(base, "baseline", "27") - m(out, k, "27")
        harm = all(m(out, k, t) >= m(base, "baseline", t) for t in gap)
        print(f"  {k}: gap rec -40 {rec['-40']:.1%}  85 {rec['85']:.1%} -> {'PASS' if min(rec.values()) >= .5 else 'FAIL'}"
              f" | 27C cost {cost * 100:+.1f} pts ({'ok' if cost <= .02 else 'over 2'}) | no-harm {'yes' if harm else 'NO'}")
