"""Step 2b-split + 2c (pre-registered in PLAN.md, 2026-10-02).

Same 16 chips as tx_ident (tt_mm seeds 1-16), 27 C. Stimulus: a 64-sample calibration
segment (code ramps along both diagonals) followed by the 128-sample QPSK frame. Saves
the PA drains (pdp/pdn) so the output-stage content can be split into PA and buffer.

usage: python tx_split.py sim      python tx_split.py analyze
"""
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import tx_full as tx
import tx_ident as ti
from spice import SPINIT, mc_control
from tx_attrib import aligned_features, norm
from tx_validate import deviation, level_fit

N_CAL = 64
TEMP = 27.0
NAMES = ("rfp", "rfn", "outp", "outn", "pdp", "pdn")


def cal_codes():
    k = np.arange(32)
    return np.r_[k, k], np.r_[k, 31 - k]


def stimulus():
    (ai, aq), (fi, fq) = cal_codes(), ti.frame()
    return np.r_[ai, fi], np.r_[aq, fq]


def netlist(seed0, n):
    ci, cq = stimulus()
    base = tx.netlist(ci, cq, temp=TEMP, corner="tt_mm")
    base = re.sub(r"^XU([iq])(\d+) n([iq])(\d+) ", r"Vm\1\2 n\3\4 m\3\4 0\nXU\1\2 m\3\4 ", base, flags=re.M)
    head = base.split("\n.control")[0]
    prints = "\n".join(f"  print i(Vm{c}{k})" for c in "iq" for k in range(tx.N_UNITS))
    vs = " ".join(f"v({x})" for x in NAMES)
    body = (f"  delete all\n  op\n{prints}\n  save {vs}\n"
            f"  tran 20p {len(ci) / tx.FS:.4e} 0 20p\n  wrdata tx_out_$&seed {vs}\n  destroy all\n")
    return head + "\n" + mc_control(n, body, seed0) + ".end\n"


def run_dir():
    return tx.WORK / "split_T27"


def run_one(job):
    seed0, n = job
    d = run_dir() / f"s{seed0}"
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(SPINIT, d / ".spiceinit")
    (d / "c.sp").write_text(netlist(seed0, n))
    with open(d / "ngspice.log", "w") as log:
        subprocess.run(["ngspice", "-b", "c.sp"], cwd=d, stdout=log, stderr=subprocess.STDOUT, timeout=6 * 3600)
    return seed0


def chip(s):
    d = run_dir() / f"s{1 if s <= 8 else 9}"
    t, w = tx.load_wr(d / f"tx_out_{s}", NAMES)
    ops = ti.parse_log((d / "ngspice.log").read_text())
    n = N_CAL + ti.N_SAMPLES
    bb = {k: tx.downconvert(t, w[a] - w[b], n) for k, (a, b) in
          {"mix": ("outp", "outn"), "pa": ("pdp", "pdn"), "rf": ("rfp", "rfn")}.items()}
    return bb, ops[s]["u"]


def basis(y):
    a = np.abs(y)
    return np.stack([y, y * a ** 2, y * a ** 4, np.ones_like(y)], 1)


def model_frame(u, ci, cq):
    cum = [np.concatenate([[0.0], np.cumsum(u[k])]) for k in (0, 1)]
    return (2 * cum[0][ci] / cum[0][-1] - 1) + 1j * (2 * cum[1][cq] / cum[1][-1] - 1)


def c2_patterns(y, ci, cq):
    li, lq, si, sq = level_fit(y, ci, cq)
    return np.concatenate([(lambda d: d / np.std(d))(deviation(l, s)[0]) for l, s in ((li, si), (lq, sq))])


def c2_score(P, M):
    P = P - P.mean(0); M = M - M.mean(0)
    return float(np.median([np.corrcoef(a, b)[0, 1] for a, b in zip(P, M)])), \
        [round(float(np.corrcoef(a, b)[0, 1]), 2) for a, b in zip(P, M)]


def analyze():
    (ai, aq), (fi, fq) = cal_codes(), ti.frame()
    ideal = (2 * fi / 31 - 1) + 1j * (2 * fq / 31 - 1)
    seeds = range(1, 17)
    data = [chip(s) for s in seeds]
    # identity check against the 2a run of the same chips
    ident = []
    for s, (bb, _) in zip(seeds, data):
        t, w = tx.load_wr(ti.run_dir("tt_mm", TEMP) / f"tx_out_{s}")
        y2a = tx.downconvert(t, w["rfp"] - w["rfn"], ti.N_SAMPLES)
        y = bb["rf"][N_CAL:]
        ident.append(float(np.abs(np.vdot(y, y2a)) / np.linalg.norm(y) / np.linalg.norm(y2a)))
    print(f"identity check (frame RF vs 2a RF, |cos|): min {min(ident):.5f}")
    # ---- split: PA vs output buffer (aligned features, used codes)
    F = {k: np.array([aligned_features(norm(bb[k][N_CAL:], ideal), fi, fq) for bb, _ in data])
         for k in ("mix", "pa", "rf")}
    C = {k: v - v.mean(0) for k, v in F.items()}
    r2 = lambda P, Q: float(1 - ((P - Q) ** 2).sum() / (P ** 2).sum())
    e = lambda k: float((C[k] ** 2).sum())
    split = {"R2_mix": r2(C["rf"], C["mix"]), "R2_pa": r2(C["rf"], C["pa"]),
             "energy_pa_over_mix": e("pa") / e("mix"), "energy_rf_over_pa": e("rf") / e("pa")}
    split["PA increment"] = split["R2_pa"] - split["R2_mix"]
    split["buffer increment"] = 1 - split["R2_pa"]
    print("split:", {k: round(v, 3) for k, v in split.items()})
    # ---- 2c: extended model, everything fitted on the calibration segment only
    coefs, P_rf, M0, M1, rows = [], [], [], [], []
    for bb, u in data:
        mc = model_frame(u, ai, aq)
        g = (bb["mix"][:N_CAL] @ mc.conj()) / (mc @ mc.conj())          # model -> mixer units
        c, *_ = np.linalg.lstsq(basis(bb["mix"][:N_CAL]), bb["rf"][:N_CAL], rcond=None)
        coefs.append(c)
        mf = g * model_frame(u, fi, fq)
        rows.append(mf)
        P_rf.append(c2_patterns(bb["rf"][N_CAL:], fi, fq))
        M0.append(c2_patterns(mf, fi, fq))
        M1.append(c2_patterns(basis(mf) @ c, fi, fq))
    cpop = np.mean(coefs, 0)
    M1pop = [c2_patterns(basis(mf) @ cpop, fi, fq) for mf in rows]
    res = {"identity_min": min(ident), "split": split}
    for k, M in (("M0 DAC only", M0), ("M1pop DAC + mean output stage", M1pop), ("M1 DAC + per-chip output stage", M1)):
        med, allr = c2_score(np.array(P_rf), np.array(M))
        res[k] = {"median_r": med, "per_chip": allr}
        print(f"{k:<34} median r {med:.3f}  {allr}")
    res["verdict_2c"] = "PASS" if res["M1 DAC + per-chip output stage"]["median_r"] >= 0.8 else "FAIL"
    print("pre-registered 2c verdict:", res["verdict_2c"])
    (ti.RESULTS / "tx_split.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "sim":
        with ProcessPoolExecutor(2) as ex:
            print(list(ex.map(run_one, [(1, 8), (9, 8)])))
    else:
        analyze()
