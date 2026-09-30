"""Shared-drift removal test.

Question: can the temperature drift that all chips share be learned from a
separate design-time population and removed, restoring cross-temperature
identification without a per-device temperature sensor?

Split: chips 150-199 = design-time population (noise-free simulation, all
temperatures); chips 0-149 = deployed devices (enrolled at 27 C only, tested
at every temperature, SNR 20 dB, one burst per decision).

Variants (all: DAC level-deviation features -> LDA fitted on 27 C enrollment
-> nearest enrolled mean):
  baseline   : no drift handling
  subspace   : project out the design-time drift subspace (smallest rank r
               capturing >= 95% of design drift energy); no temperature needed
  known_temp : subtract the design-time mean drift at the true test
               temperature (reference: requires a temperature sensor)

Success criterion (fixed before running): subspace recovers >= 50% of the
baseline's accuracy loss at -40 C and at 85 C, averaged over 3 seeds.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

from feature_match import estimate_levels, flat
from txmodel import params_from, transmit

RESULTS = Path(__file__).resolve().parents[1] / "results"
DATA = Path(__file__).resolve().parents[1] / "data"
DESIGN = range(150, 200)
DEPLOY = range(0, 150)
N_ENROLL, N_TEST, T_ENROLL = 40, 10, 27.0
SNR = 20.0
ENERGY = 0.95


def feats(p, ti, c, rng, snr, n):
    return flat(estimate_levels(transmit(p, ti, c, rng, snr, n), pa_terms=False))


def _npz(name):
    return np.load(DATA / f"{name}.npz")


def deployed_params(dac, differential):
    """Deployed chips: tt_mm, DAC design 'dac' (dac_200) or 'dac2' (cascode)."""
    d = _npz("dac_200" if dac == "dac" else "dac2_200")
    unit_nom = 10e-6 if dac == "dac" else float(d["data"][list(d["temps"]).index(T_ENROLL), :, :, 1].mean())
    return params_from(d, _npz("pa_200"), _npz("lo_200"), unit_nom=unit_nom,
                       differential=differential)


def design_params(corner, dac, differential, p):
    """Design-time population: the deployed-model chips 150-199, or the same
    chip seeds re-simulated at a different (mis-specified) process corner."""
    if corner is None:
        return p, DESIGN
    f = lambda b: _npz(f"design_{corner}_{b}")
    pd = params_from(f(dac), f("pa"), f("lo"), unit_nom=p.unit_nom, differential=differential)
    return pd, range(pd.dac_units.shape[1])


def drift_split(F, t0):
    """F (T, chip, f) noise-free features -> fraction of drift energy that is a
    shift shared by all chips, per non-reference temperature."""
    out = {}
    for ti in range(F.shape[0]):
        if ti == t0:
            continue
        drift = F[ti] - F[t0]
        common = drift.mean(0)
        out[ti] = float(np.sum(common ** 2) * len(drift) / np.sum(drift ** 2))
    return out


def run(seed, corner=None, dac="dac", differential=False):
    p = deployed_params(dac, differential)
    temps = list(p.temps)
    t0 = temps.index(T_ENROLL)

    # design-time population: noise-free, one burst each (deterministic chip behaviour)
    pd, dchips = design_params(corner, dac, differential, p)
    assert list(pd.temps) == temps
    des = np.stack([np.stack([feats(pd, ti, c, np.random.default_rng(777), 200, 1)[0]
                              for c in dchips]) for ti in range(len(temps))])    # T, chip, f
    m = des.mean(1)                                                             # T, f
    drift = np.delete(m - m[t0], t0, 0)
    u, s, vt = np.linalg.svd(drift, full_matrices=False)
    r = int(np.searchsorted(np.cumsum(s ** 2) / np.sum(s ** 2), ENERGY) + 1)
    U = vt[:r].T
    energy = (np.cumsum(s ** 2) / np.sum(s ** 2)).round(4).tolist()

    enroll = np.stack([feats(p, t0, c, np.random.default_rng(10_000 * seed + c), SNR, N_ENROLL)
                       for c in DEPLOY])                                        # chip, burst, f
    tests = {ti: np.stack([feats(p, ti, c, np.random.default_rng(10_000 * seed + 5000 + 300 * ti + c),
                                 SNR, N_TEST) for c in DEPLOY]) for ti in range(len(temps))}
    keep = enroll.reshape(-1, enroll.shape[-1]).std(0) > 0
    y = np.repeat(np.arange(len(DEPLOY)), N_ENROLL)
    truth = np.arange(len(DEPLOY))[:, None]

    def evaluate(tf_enroll, tf_test):
        e = tf_enroll(enroll)[..., keep]
        lda = LinearDiscriminantAnalysis(solver="eigen", shrinkage="auto")
        lda.fit(e.reshape(-1, keep.sum()), y)
        pr = lambda f: lda.transform(f.reshape(-1, keep.sum())).reshape(*f.shape[:-1], -1)
        tpl = pr(e).mean(1)
        acc = {}
        for ti, t in enumerate(temps):
            v = pr(tf_test(tests[ti], ti)[..., keep])
            d = ((v[:, :, None, :] - tpl[None, None]) ** 2).sum(-1)
            acc[f"{t:g}"] = float((d.argmin(-1) == truth).mean())
        return acc

    P = np.eye(U.shape[0]) - U @ U.T
    res = {
        "baseline": evaluate(lambda f: f, lambda f, ti: f),
        "subspace": evaluate(lambda f: f @ P, lambda f, ti: f @ P),
        "known_temp": evaluate(lambda f: f, lambda f, ti: f - (m[ti] - m[t0])),
    }
    # true drift (deployed model, noise-free, design-range chips): direction and split
    true_F = np.stack([np.stack([feats(p, ti, c, np.random.default_rng(777), 200, 1)[0]
                                 for c in DESIGN]) for ti in range(len(temps))])
    true_m = true_F.mean(1)
    tv = np.linalg.svd(np.delete(true_m - true_m[t0], t0, 0), full_matrices=False)[2][0]
    split = {f"{temps[k]:g}": v for k, v in drift_split(true_F, t0).items()}
    return dict(seed=seed, snr=SNR, corner=corner or "tt_mm", dac=dac, differential=differential,
                rank=r, cos_to_true_drift=float(abs(tv @ vt[0])), common_drift_fraction=split,
                drift_energy_cumulative=energy, **res)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--corner", default="tt_mm", help="design-time model corner")
    ap.add_argument("--snr", type=float, default=20.0)
    ap.add_argument("--dac", default="dac", choices=["dac", "dac2"])
    ap.add_argument("--differential", action="store_true")
    a = ap.parse_args()
    SNR = a.snr
    corner = None if a.corner == "tt_mm" else a.corner
    out = []
    for sd in [int(x) for x in a.seeds.split(",")]:
        r = run(sd, corner, a.dac, a.differential)
        out.append(r)
        print(f"seed {sd}  design corner {r['corner']}  dac {a.dac}  diff {a.differential}  rank {r['rank']}  "
              f"drift energy {r['drift_energy_cumulative']}  cos to true drift {r['cos_to_true_drift']:.4f}",
              flush=True)
        print("  common-drift fraction:", {k: round(v, 3) for k, v in r["common_drift_fraction"].items()})
        for k in ("baseline", "subspace", "known_temp"):
            print(f"  {k:<11}" + "  ".join(f"{t:>4}:{acc:.3f}" for t, acc in r[k].items()), flush=True)
    RESULTS.mkdir(exist_ok=True)
    tag = ('' if corner is None else '_' + corner) + ('' if SNR == 20 else f'_snr{SNR:g}') \
        + ('' if a.dac == "dac" else '_' + a.dac) + ('_diff' if a.differential else '') \
        + ('' if a.seeds == "0,1,2" else '_seeds' + a.seeds.replace(',', '-'))
    (RESULTS / f"drift_test{tag}.json").write_text(json.dumps(out, indent=1))

    def mean(k, t):
        return np.mean([r[k][t] for r in out])
    print("\nmean over seeds")
    for k in ("baseline", "subspace", "known_temp"):
        print(f"  {k:<11}" + "  ".join(f"{t:>4}:{mean(k, t):.3f}±{np.std([r[k][t] for r in out]):.3f}"
                                      for t in out[0][k]))
    for t in ("-40", "85"):
        gap = mean("baseline", "27") - mean("baseline", t)
        rec = (mean("subspace", t) - mean("baseline", t)) / gap
        print(f"  gap recovered by subspace at {t} C: {rec:.1%}  "
              f"(criterion >= 50%: {'MET' if rec >= 0.5 else 'NOT MET'})")
