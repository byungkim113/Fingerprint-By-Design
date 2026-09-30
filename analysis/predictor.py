"""Design-time predictor of whether shared-drift removal helps (pre-registered in
PLAN.md): common-drift fraction from the four WRONG-corner populations only,
compared with the measured effect of M2 in results/generalize_<design>.json."""
import json

import numpy as np

from drift_test import T_ENROLL, drift_split
from generalize import RESULTS, WRONG, corner_params, deployed, noise_free

DESIGNS = ["dac", "dac2", "dac_ztc", "dac_hi", "dac_lo", "dac_sl", "dac_casL"]
THRESHOLD = 0.60


def design_time_fraction(design):
    p = deployed(design)                     # only for temps and the nominal unit current
    temps = list(p.temps)
    t0 = temps.index(T_ENROLL)
    fr = []
    for c in WRONG:
        pc = corner_params(design, c, p.unit_nom)
        F = noise_free(pc, range(pc.dac_units.shape[1]), temps)
        fr += list(drift_split(F, t0).values())
    return float(np.mean(fr))


if __name__ == "__main__":
    rows = []
    for d in DESIGNS:
        f = RESULTS / f"generalize_{d}.json"
        if not f.exists():
            print(f"{d}: no generalize result yet")
            continue
        out = json.loads(f.read_text())
        m = lambda k, t: np.mean([r[k][t] for r in out])
        delta = {t: m("M2", t) - m("baseline", t) for t in ("-40", "85")}
        frac = design_time_fraction(d)
        apply = frac >= THRESHOLD
        helps = all(v > 0 for v in delta.values())
        rows.append(dict(design=d, frac=frac, apply=apply, helps=helps, delta=delta,
                         correct=(apply == helps)))
        print(f"{d:9s} design-time common fraction {frac:.3f}  rule: {'apply' if apply else 'skip '}  "
              f"M2 effect -40 {delta['-40']:+.3f}  85 {delta['85']:+.3f}  -> {'correct' if apply == helps else 'WRONG'}")
    (RESULTS / "predictor.json").write_text(json.dumps(rows, indent=1))
