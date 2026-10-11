"""Round 2 (pre-registered in PLAN.md, 2026-10-04): method B v2 for supply drift (denser
design-time grid, fresh test chips) and the mismatch-sensitivity study (s = 0.5, 2).

usage: python tx_round2.py sim | bv2 | sens
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SUPPLIES = ["180", "162", "198", "171", "189", "1764", "1836"]
SCALES = ["0.5", "2"]


def jobs():
    j = [(dict(TX_TAG="fresh_", TX_VARIANT="vdd" + v), ("tt_mm", 17, 16, 27.0)) for v in SUPPLIES]
    j += [(dict(TX_VARIANT="vdd" + v), (c, 101, 6, 27.0)) for v in ("1764", "1836") for c in ("ss_mm", "ff_mm")]
    for s in SCALES:
        e = dict(TX_MMSCALE=s, TX_TAG=f"mm{s}_")
        j += [(dict(e, TX_VARIANT="vdd180"), ("tt_mm", 1, 16, 27.0)), (dict(e, TX_VARIANT="vdd180"), ("tt_mm", 1, 16, 85.0)),
              (dict(e, TX_VARIANT="vdd162"), ("tt_mm", 1, 16, 27.0)),
              (dict(e, TX_VARIANT="palin", TX_NDEG="3"), ("tt_mm", 1, 16, 27.0))]
    return j


def run(job):
    env, args = job
    code = f"import tx_ident as ti; ti.run_one({args!r})"
    subprocess.run([sys.executable, "-c", code], cwd=HERE, env=dict(os.environ, **env), check=True)
    return f"done {env} {args}"


def bv2():
    import tx_supply
    print("== B v2, primary (no exclusion), fresh chips 17-32")
    tx_supply.analyze(tag="fresh_", seeds=range(17, 33), grid=tx_supply.TEST_V, exclude_interior=False,
                      out="tx_bv2.json")
    print("== B v2, secondary (interior grid points excluded)")
    tx_supply.analyze(tag="fresh_", seeds=range(17, 33), grid=tx_supply.TEST_V, exclude_interior=True,
                      out="tx_bv2_excl.json")


def sens():
    import tx_full as tx
    import tx_ident as ti
    import tx_more_tests as m
    seeds = range(1, 17)
    d = lambda tag, v, T: tx.WORK / f"ident_{tag}{v}_tt_mm_T{T}"

    def mix_frames(path):
        out = []
        for s in seeds:
            t, w = tx.load_wr(path / f"tx_out_{s}")
            y = tx.downconvert(t, w["outp"] - w["outn"], ti.N_SAMPLES)
            out.append(y / ((y @ m.IDEAL.conj()) / (m.IDEAL @ m.IDEAL.conj())))
        return np.array(out)

    S = lambda Y: float(m.feats(Y).std(0).mean())
    res = {}
    ref = {"S_rf": S(m.frames(d("", "vdd180", 27), seeds)), "S_mix": S(mix_frames(d("", "vdd180", 27)))}
    ref["amp"] = ref["S_rf"] / ref["S_mix"]
    res["1"] = ref
    print(f"s=1   S_rf {ref['S_rf']:.4f}  S_mix {ref['S_mix']:.4f}  amplification {ref['amp']:.2f}")
    ok = {}
    for s in SCALES:
        tag = f"mm{s}_"
        Y27, Y85 = m.frames(d(tag, "vdd180", 27), seeds), m.frames(d(tag, "vdd180", 85), seeds)
        Y162, Ypl = m.frames(d(tag, "vdd162", 27), seeds), m.frames(d(tag, "palin", 27), seeds)
        r = {"S_rf": S(Y27), "S_mix": S(mix_frames(d(tag, "vdd180", 27))), "S_rf_palin": S(Ypl)}
        r["amp"] = r["S_rf"] / r["S_mix"]
        for snr in (30.0, 20.0):
            r[f"acc_{snr:g}dB"] = m.accuracy(Y27, {"27C_1.80": Y27, "85C": Y85, "1.62V": Y162}, snr)
        a = lambda snr, k: r[f"acc_{snr:g}dB"][k]
        s1 = abs(r["amp"] / ref["amp"] - 1) <= 0.3
        s2 = all(a(snr, "27C_1.80") - a(snr, "1.62V") > a(snr, "27C_1.80") - a(snr, "85C") for snr in (30.0, 20.0))
        s3 = r["S_rf_palin"] / r["S_rf"] < 0.8
        r["verdicts"] = dict(S1=s1, S2=s2, S3=s3)
        res[s] = r
        ok[s] = s1 and s2 and s3
        print(f"s={s:<3} S_rf {r['S_rf']:.4f} ({r['S_rf'] / ref['S_rf']:.2f}x)  S_mix {r['S_mix']:.4f}  amplification "
              f"{r['amp']:.2f}  palin/base {r['S_rf_palin'] / r['S_rf']:.2f}")
        for snr in (30.0, 20.0):
            print(f"      {snr:g} dB: " + "  ".join(f"{k}: {v:.3f}" for k, v in r[f'acc_{snr:g}dB'].items()))
        print(f"      S1 {'PASS' if s1 else 'FAIL'}  S2 {'PASS' if s2 else 'FAIL'}  S3 {'PASS' if s3 else 'FAIL'}")
    print("conclusions robust to mismatch-model error (all hold at both s):", all(ok.values()))
    (ti.RESULTS / "tx_mm_sensitivity.json").write_text(json.dumps(res, indent=1, default=bool))


if __name__ == "__main__":
    if sys.argv[1] == "sim":
        with ThreadPoolExecutor(2) as ex:                       # 2 ngspice at a time
            for out in ex.map(run, jobs()):
                print(out, flush=True)
    else:
        {"bv2": bv2, "sens": sens}[sys.argv[1]]()
