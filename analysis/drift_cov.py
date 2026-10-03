"""M4: simulation-informed drift covariance receiver (pre-registered in PLAN.md).

Temperature drift is learned from design-time circuit simulation of the four
WRONG process corners (never the deployed tt chips, never any measurement at
another temperature). Every design-time chip contributes its drift vectors
d = f(T) - f(27 C), which carry both the shift shared by all chips and the
chip-specific part. Sigma_T = mean(d d^T).

The receiver treats that drift as extra within-chip variation: nearest enrolled
chip mean under the Mahalanobis distance of S = S_w + lambda * Sigma_T, where
S_w is the 27 C enrollment noise covariance (Ledoit-Wolf). lambda = 1 is the
pre-registered value; other lambdas are printed as diagnostics only.

  M4_0 : lambda = 0 (enrollment noise only; control, should track the LDA baseline)
  M4   : lambda = 1 (pre-registered)

usage: python drift_cov.py <design> [--seeds 0,1,2]
"""
import argparse
import json

import numpy as np
from sklearn.covariance import LedoitWolf

from drift_test import DEPLOY, N_ENROLL, N_TEST, RESULTS, T_ENROLL, feats
from generalize import SNR, WRONG, corner_params, deployed, noise_free

LAMBDAS = {"M4_0": 0.0, "M4": 1.0, "diag_lam0.25": 0.25, "diag_lam4": 4.0}


def drift_covariance(design, p, temps, t0):
    ds = []
    for c in WRONG:
        pc = corner_params(design, c, p.unit_nom)
        F = noise_free(pc, range(pc.dac_units.shape[1]), temps)          # T, chip, f
        for ti in range(len(temps)):
            if ti != t0:
                ds.append(F[ti] - F[t0])
    d = np.concatenate(ds)                                                # samples, f
    return d.T @ d / len(d)


def run(design, seed):
    p = deployed(design)
    temps = list(p.temps)
    t0 = temps.index(T_ENROLL)
    sig_t = drift_covariance(design, p, temps, t0)

    enroll = np.stack([feats(p, t0, c, np.random.default_rng(10_000 * seed + c), SNR, N_ENROLL)
                       for c in DEPLOY])                                  # chip, burst, f
    tests = {ti: np.stack([feats(p, ti, c, np.random.default_rng(10_000 * seed + 5000 + 300 * ti + c),
                                 SNR, N_TEST) for c in DEPLOY]) for ti in range(len(temps))}
    keep = enroll.reshape(-1, enroll.shape[-1]).std(0) > 0
    e = enroll[..., keep]
    mu = e.mean(1)                                                        # chip, f
    s_w = LedoitWolf().fit((e - mu[:, None]).reshape(-1, keep.sum())).covariance_
    sig_t = sig_t[np.ix_(keep, keep)]
    truth = np.arange(len(DEPLOY))[:, None]

    res = {}
    for name, lam in LAMBDAS.items():
        L = np.linalg.cholesky(s_w + lam * sig_t)
        W = lambda x: np.linalg.solve(L, x.reshape(-1, x.shape[-1]).T).T.reshape(x.shape)
        tpl = W(mu)
        acc = {}
        for ti, t in enumerate(temps):
            v = W(tests[ti][..., keep])
            d = ((v[:, :, None, :] - tpl[None, None]) ** 2).sum(-1)
            acc[f"{t:g}"] = float((d.argmin(-1) == truth).mean())
        res[name] = acc
    return dict(design=design, seed=seed, snr=SNR, **res)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("--seeds", default="0,1,2")
    a = ap.parse_args()
    out = [run(a.design, int(s)) for s in a.seeds.split(",")]
    tag = "" if a.seeds == "0,1,2" else "_seeds" + a.seeds.replace(",", "-")
    (RESULTS / f"drift_cov_{a.design}{tag}.json").write_text(json.dumps(out, indent=1))
    base = json.loads((RESULTS / f"generalize_{a.design}.json").read_text())   # LDA baseline, same seeds/data
    m = lambda rs, k, t: np.mean([r[k][t] for r in rs])
    print(f"{a.design}")
    print(f"  {'baseline':<13}" + "  ".join(f"{t:>4}:{m(base, 'baseline', t):.3f}" for t in base[0]["baseline"]))
    for k in LAMBDAS:
        print(f"  {k:<13}" + "  ".join(f"{t:>4}:{m(out, k, t):.3f}±{np.std([r[k][t] for r in out]):.3f}"
                                      for t in out[0][k]))
    gap = {t: m(base, "baseline", "27") - m(base, "baseline", t) for t in ("-40", "85")}
    rec = {t: (m(out, "M4", t) - m(base, "baseline", t)) / gap[t] for t in gap}
    harm = all(m(out, "M4", t) >= m(base, "baseline", t) for t in gap)
    print(f"  gap recovered M4: -40 {rec['-40']:.1%}  85 {rec['85']:.1%}  -> "
          f"{'PASS' if min(rec.values()) >= 0.5 else 'FAIL'}   no-harm: {'yes' if harm else 'NO'}")
