"""Generalization study across DAC designs (pre-registered in PLAN.md).

For one DAC design, compares receivers (DAC level-deviation features -> LDA on
27 C enrollment -> nearest enrolled template), 150 deployed tt_mm chips,
SNR 20 dB, one burst per decision:

  baseline : no drift handling
  M1       : remove drift subspace learned from the tt design population
             (same process as the deployed chips; optimistic)
  M2       : remove drift subspace learned from the union of the four WRONG
             corners {ss, ff, ss_hh, ff_ll}; tt excluded (process unknown)
  M3       : M2 + per-chip scale fit: for each enrolled template t, fit
             k = clip(v.t / t.t, 0.7, 1.4) and score |v - k t|^2
  M1s      : M1 + the same scale fit (diagnostic)

Pass (per design): M2 (and separately M3) recovers >= 50% of the baseline's
27 C-to-extreme accuracy gap at both -40 C and 85 C, mean of 3 seeds.

usage: python generalize.py <design> [--seeds 0,1,2]
"""
import argparse
import json

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

from drift_test import DATA, DEPLOY, DESIGN, ENERGY, N_ENROLL, N_TEST, RESULTS, T_ENROLL, drift_split, feats
from txmodel import params_from

SNR = 20.0
WRONG = ["ss_mm", "ff_mm", "ss_hh_mm", "ff_ll_mm"]
K_BOUNDS = (0.7, 1.4)


def _npz(name):
    return np.load(DATA / f"{name}.npz")


def deployed(design):
    d = _npz("dac_200" if design == "dac" else f"{design}_200")
    unit_nom = 10e-6 if design == "dac" else \
        float(d["data"][list(d["temps"]).index(T_ENROLL), :, :, 1].mean())
    return params_from(d, _npz("pa_200"), _npz("lo_200"), unit_nom=unit_nom)


def corner_params(design, corner, unit_nom):
    f = lambda b: _npz(f"design_{corner}_{b}")
    return params_from(f(design), f("pa"), f("lo"), unit_nom=unit_nom)


def noise_free(p, chips, temps):
    return np.stack([np.stack([feats(p, ti, c, np.random.default_rng(777), 200, 1)[0]
                               for c in chips]) for ti in range(len(temps))])       # T, chip, f


def subspace(drifts):
    """rows = drift vectors -> orthonormal basis capturing ENERGY of their energy."""
    _, s, vt = np.linalg.svd(np.asarray(drifts), full_matrices=False)
    e = np.cumsum(s ** 2) / np.sum(s ** 2)
    r = int(np.searchsorted(e, ENERGY) + 1)
    return vt[:r].T, r, e.round(4).tolist()


def run(design, seed):
    p = deployed(design)
    temps = list(p.temps)
    t0 = temps.index(T_ENROLL)

    # design-time drift models
    F_tt = noise_free(p, DESIGN, temps)
    m_tt = F_tt.mean(1)
    U1, r1, e1 = subspace(np.delete(m_tt - m_tt[t0], t0, 0))
    wrong_drifts = []
    for c in WRONG:
        pc = corner_params(design, c, p.unit_nom)
        m = noise_free(pc, range(pc.dac_units.shape[1]), temps).mean(1)
        wrong_drifts += list(np.delete(m - m[t0], t0, 0))
    U2, r2, e2 = subspace(wrong_drifts)
    cos12 = float(np.linalg.svd(U1.T @ U2, compute_uv=False).max())   # best-aligned direction

    enroll = np.stack([feats(p, t0, c, np.random.default_rng(10_000 * seed + c), SNR, N_ENROLL)
                       for c in DEPLOY])
    tests = {ti: np.stack([feats(p, ti, c, np.random.default_rng(10_000 * seed + 5000 + 300 * ti + c),
                                 SNR, N_TEST) for c in DEPLOY]) for ti in range(len(temps))}
    keep = enroll.reshape(-1, enroll.shape[-1]).std(0) > 0
    y = np.repeat(np.arange(len(DEPLOY)), N_ENROLL)
    truth = np.arange(len(DEPLOY))[:, None]

    def evaluate(P, scale):
        e = (enroll @ P)[..., keep]
        lda = LinearDiscriminantAnalysis(solver="eigen", shrinkage="auto")
        lda.fit(e.reshape(-1, keep.sum()), y)
        pr = lambda f: lda.transform(f.reshape(-1, keep.sum())).reshape(*f.shape[:-1], -1)
        pe = pr(e)
        mu = pe.reshape(-1, pe.shape[-1]).mean(0)
        tpl = pe.mean(1) - mu                                          # chip, d
        acc = {}
        for ti, t in enumerate(temps):
            v = pr((tests[ti] @ P)[..., keep]) - mu                     # chip, burst, d
            if scale:
                k = np.clip((v @ tpl.T) / (tpl ** 2).sum(-1), *K_BOUNDS)   # chip, burst, cand
                d = ((v[:, :, None, :] - k[..., None] * tpl[None, None]) ** 2).sum(-1)
            else:
                d = ((v[:, :, None, :] - tpl[None, None]) ** 2).sum(-1)
            acc[f"{t:g}"] = float((d.argmin(-1) == truth).mean())
        return acc

    I = np.eye(enroll.shape[-1])
    P1, P2 = I - U1 @ U1.T, I - U2 @ U2.T
    res = {"baseline": evaluate(I, False), "M1": evaluate(P1, False), "M2": evaluate(P2, False),
           "M3": evaluate(P2, True), "M1s": evaluate(P1, True)}
    split = {f"{temps[k]:g}": v for k, v in drift_split(F_tt, t0).items()}
    return dict(design=design, seed=seed, snr=SNR, rank_tt=r1, rank_wrong=r2, energy_tt=e1,
                energy_wrong=e2, cos_tt_vs_wrong=cos12, common_drift_fraction=split, **res)


def gap_recovered(out, method, t):
    mean = lambda k, tt: np.mean([r[k][tt] for r in out])
    gap = mean("baseline", "27") - mean("baseline", t)
    return (mean(method, t) - mean("baseline", t)) / gap


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("--seeds", default="0,1,2")
    a = ap.parse_args()
    out = [run(a.design, int(s)) for s in a.seeds.split(",")]
    tag = "" if a.seeds == "0,1,2" else "_seeds" + a.seeds.replace(",", "-")
    (RESULTS / f"generalize_{a.design}{tag}.json").write_text(json.dumps(out, indent=1))
    r = out[0]
    print(f"{a.design}: rank tt {r['rank_tt']}  rank wrong {r['rank_wrong']}  "
          f"align tt-vs-wrong {r['cos_tt_vs_wrong']:.3f}  common drift "
          f"{ {k: round(v, 3) for k, v in r['common_drift_fraction'].items()} }")
    for k in ("baseline", "M1", "M2", "M3", "M1s"):
        print(f"  {k:<9}" + "  ".join(f"{t:>4}:{np.mean([x[k][t] for x in out]):.3f}±"
                                      f"{np.std([x[k][t] for x in out]):.3f}" for t in r[k]))
    for m in ("M1", "M2", "M3"):
        g = [gap_recovered(out, m, t) for t in ("-40", "85")]
        print(f"  gap recovered {m}: -40 {g[0]:.1%}  85 {g[1]:.1%}  -> "
              f"{'PASS' if min(g) >= 0.5 else 'FAIL'}")
