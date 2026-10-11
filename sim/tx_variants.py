"""Step 2d: nominal check of the design variants (tt, no mismatch, 27 C, calibration
segment + QPSK frame). Reports RF level, EVM and PA compression for each variant.

usage: python tx_variants.py sim      python tx_variants.py report
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = [("base", 2), ("bigdac", 2), ("palin", 1), ("palin", 2), ("palin", 3)]
NAMES = ("rfp", "rfn", "outp", "outn", "pdp", "pdn")


def tag(v, n):
    return v if v != "palin" else f"palin{n}"


def run_case(case):
    v, n = case
    code = ("import tx_full as tx, tx_split as sp\n"
            "ci, cq = sp.stimulus()\n"
            "t = tx.netlist(ci, cq, temp=27.0, corner='tt').replace(\n"
            "  'v(lo_i) v(lo_q) v(vi) v(vq)', 'v(lo_i) v(lo_q) v(vi) v(vq) v(pdp) v(pdn)').replace(\n"
            "  'v(lo_i) v(lo_q)\\n', 'v(pdp) v(pdn)\\n')\n"
            f"tx.run(t, 'nominal_{tag(v, n)}')\n")
    env = dict(os.environ, TX_VARIANT=v, TX_NDEG=str(n))
    subprocess.run([sys.executable, "-c", code], cwd=HERE, env=env, check=True)
    return tag(v, n)


def report():
    import tx_full as tx
    import tx_ident as ti
    import tx_split as sp
    (ai, aq), (fi, fq) = sp.cal_codes(), ti.frame()
    N = sp.N_CAL
    ideal = (2 * fi / 31 - 1) + 1j * (2 * fq / 31 - 1)
    out = {}
    for v, n in CASES:
        d = tx.WORK / f"nominal_{tag(v, n)}"
        t, w = tx.load_wr(d / "tx_out.txt", NAMES)
        n_all = N + ti.N_SAMPLES
        bb = {k: tx.downconvert(t, w[a] - w[b], n_all) for k, (a, b) in
              {"mix": ("outp", "outn"), "pa": ("pdp", "pdn"), "rf": ("rfp", "rfn")}.items()}
        y = bb["rf"][N:]
        h = (y @ ideal.conj()) / (ideal @ ideal.conj())
        evm = np.sqrt(np.mean(np.abs(y / h - ideal) ** 2) / np.mean(np.abs(ideal) ** 2))
        # PA AM/AM over the calibration ramps: gain |pa|/|mix| at the largest vs the median drive
        m, p = np.abs(bb["mix"][:N]), np.abs(bb["pa"][:N])
        g = p / np.maximum(m, 1e-9)
        big, mid = m >= np.quantile(m, 0.9), (m > np.quantile(m, 0.3)) & (m < np.quantile(m, 0.5))
        comp = 20 * np.log10(np.median(g[big]) / np.median(g[mid]))
        rf_pp = np.ptp(w["rfp"] - w["rfn"])
        out[tag(v, n)] = dict(rf_pp=float(rf_pp), evm=float(evm), pa_gain=float(np.median(g[mid])),
                              pa_compression_db=float(comp))
        print(f"{tag(v, n):<8} RF {rf_pp:.3f} Vpp  EVM {100 * evm:5.2f} %  PA gain {np.median(g[mid]):.2f}  "
              f"PA compression at top drive {comp:+.2f} dB")
    (ti.RESULTS / "tx_variants_nominal.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "sim":
        with ProcessPoolExecutor(2) as ex:
            print(list(ex.map(run_case, CASES)))
    else:
        report()
