"""Step 2a: identification of transistor-level chips and method B (pre-registered in
PLAN.md, 2026-10-02).

sim mode : one ngspice session per (corner, temperature) runs every chip of that group:
           op (DAC unit currents, bias node voltages), ac (RC-CR outputs), then the
           full transmitter transient; waveforms stay on disk.
analysis : bursts of 18 noisy frames -> level-ladder residual features -> BASE
           (Mahalanobis) and B (temperature-marginalised mixture, design-time drift
           from wrong-corner chips).

usage: python tx_ident.py sim [deployed|design]     python tx_ident.py analyze [--snr 30]
"""
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import tx_full as tx
from spice import SPINIT, mc_control
from tx_validate import level_fit

N_SAMPLES = 128
TEMPS = [-40.0, 0.0, 27.0, 55.0, 85.0]
GROUPS = {"deployed": [("tt_mm", 1, 16)], "design": [("ss_mm", 101, 6), ("ff_mm", 101, 6)]}
BIAS_NODES = ["gi", "gq", "pab", "lob_bias", "ob_bias"]
REPS, N_ENROLL, N_TEST, T_ENROLL = 18, 40, 10, 27.0
RESULTS = Path(__file__).resolve().parents[1] / "results"


def frame():
    f = os.environ.get("TX_FRAME", "1")
    if f == "cov":
        return coverage_codes()
    ci, cq, _ = tx.qpsk_codes(N_SAMPLES, seed=int(f))   # data frame (round 3)
    return ci, cq


def coverage_codes(seed=2026):
    """code-coverage enrollment sequence: every I and Q code 4 times, with varied partner codes."""
    rng = np.random.default_rng(seed)
    ci = np.concatenate([rng.permutation(32) for _ in range(N_SAMPLES // 32)])
    cq = np.concatenate([rng.permutation(32) for _ in range(N_SAMPLES // 32)])
    return ci, cq


def netlist(corner, seed0, n_chips, temp):
    ci, cq = frame()
    base = tx.netlist(ci, cq, temp=temp, corner=corner)
    base = re.sub(r"^XU([iq])(\d+) n([iq])(\d+) ", r"Vm\1\2 n\3\4 m\3\4 0\nXU\1\2 m\3\4 ", base, flags=re.M)
    head = base.split("\n.control")[0]
    prints = "\n".join(f"  print i(Vm{c}{k})" for c in "iq" for k in range(tx.N_UNITS))
    # memory: keep only the six waveforms during the transient, free everything per chip
    body = (f"  delete all\n  op\n{prints}\n  print " + " ".join(f"v({n})" for n in BIAS_NODES) + "\n"
            f"  ac lin 1 {tx.FLO} {tx.FLO}\n  print vm(vi) vp(vi) vm(vq) vp(vq)\n"
            f"  save v(rfp) v(rfn) v(outp) v(outn) v(lo_i) v(lo_q)\n"
            f"  tran 20p {N_SAMPLES / tx.FS:.4e} 0 20p\n"
            f"  wrdata tx_out_$&seed v(rfp) v(rfn) v(outp) v(outn) v(lo_i) v(lo_q)\n"
            f"  destroy all\n")
    return head + "\n" + mc_control(n_chips, body, seed0) + ".end\n"


def run_dir(corner, temp):
    v = "" if tx.VARIANT == "base" else f"{tx.VARIANT}_"
    tag = os.environ.get("TX_TAG", "")                 # separate directories (fresh chips, scaled mismatch)
    return tx.WORK / f"ident_{tag}{v}{corner}_T{temp:g}"


def run_one(job):
    corner, seed0, n, temp = job
    d = run_dir(corner, temp)
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(SPINIT, d / ".spiceinit")
    (d / "c.sp").write_text(netlist(corner, seed0, n, temp))
    with open(d / "ngspice.log", "w") as log:                 # streamed: finished chips survive
        subprocess.run(["ngspice", "-b", "c.sp"], cwd=d, stdout=log, stderr=subprocess.STDOUT,
                       timeout=6 * 3600)
    return corner, temp


def parse_log(text):
    chips, cur = {}, None
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"@@CHIP (\d+)", s)
        if m:
            cur = int(m.group(1)); chips[cur] = {"u": np.full((2, tx.N_UNITS), np.nan)}
            continue
        if cur is None:
            continue
        m = re.match(r"i\(vm([iq])(\d+)\)\s*=\s*(\S+)", s)
        if m:
            chips[cur]["u"]["iq".index(m.group(1)), int(m.group(2))] = float(m.group(3))
            continue
        m = re.match(r"(v\(\w+\)|v[mp]\(v[iq]\))\s*=\s*(\S+)", s)
        if m:
            chips[cur][m.group(1)] = float(m.group(2))
    return chips


def frames(corner, seeds):
    """-> (T, chip, N_SAMPLES) noise-free, gain-normalised baseband frames, and op data."""
    ci, cq = frame()
    ideal = (2 * ci / tx.N_UNITS - 1) + 1j * (2 * cq / tx.N_UNITS - 1)
    Y, ops = [], []
    for temp in TEMPS:
        d = run_dir(corner, temp)
        op = parse_log((d / "ngspice.log").read_text())
        ys = []
        for s in seeds:
            t, w = tx.load_wr(d / f"tx_out_{s}")
            y = tx.downconvert(t, w["rfp"] - w["rfn"], N_SAMPLES)
            ys.append(y / ((y @ ideal.conj()) / (ideal @ ideal.conj())))
        Y.append(ys); ops.append([op[s] for s in seeds])
    return np.array(Y), ops


MASKED = "--masked" in sys.argv     # sensitivity rerun: drop levels of codes the frame never uses


def features(z, ci, cq):
    li, lq, si, sq = level_fit(z, ci, cq)
    out = []
    for lev, seen in ((li, si), (lq, sq)):
        if not MASKED:
            seen = np.ones(len(lev), bool)
        k = np.arange(len(lev))[seen]
        lev = lev[seen]
        for part in (lev.real, lev.imag):
            out.append(part - np.polyval(np.polyfit(k, part, 1), k))
    return np.concatenate(out)


def bursts(y, rng, snr, n):
    """n bursts of REPS noisy copies of frame y: random carrier phase, AWGN, LS gain."""
    ci, cq = frame()
    CI, CQ = np.tile(ci, REPS), np.tile(cq, REPS)
    ideal = (2 * CI / tx.N_UNITS - 1) + 1j * (2 * CQ / tx.N_UNITS - 1)
    s = np.sqrt(np.mean(np.abs(y) ** 2) / 10 ** (snr / 10) / 2)
    out = []
    for _ in range(n):
        z = np.tile(y, REPS) * np.exp(1j * rng.uniform(0, 2 * np.pi))
        z = z + s * (rng.standard_normal(z.size) + 1j * rng.standard_normal(z.size))
        z = z / ((z @ ideal.conj()) / (ideal @ ideal.conj()))
        out.append(features(z, CI, CQ))
    return np.array(out)


def analyze(snr):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    from robust2 import drift_model, mahalanobis_acc, mixture_acc, noise_cov
    ci, cq = frame()
    Yd, ops = frames("tt_mm", range(1, 17))
    t0 = TEMPS.index(T_ENROLL)
    # design-time drift: noise-free features of the wrong-corner chips
    Fs = []
    for corner, s0, n in GROUPS["design"]:
        Yw, _ = frames(corner, range(s0, s0 + n))
        Fs.append(np.array([[features(y, ci, cq) for y in Yw[ti]] for ti in range(len(TEMPS))]))
    interior = {TEMPS.index(0.0), TEMPS.index(55.0)}
    full = drift_model(Fs, TEMPS, t0)
    res = []
    for seed in (0, 1, 2):
        n_chips = Yd.shape[1]
        enroll = np.stack([bursts(Yd[t0, c], np.random.default_rng(10_000 * seed + c), snr, N_ENROLL)
                           for c in range(n_chips)])
        tests = {ti: np.stack([bursts(Yd[ti, c], np.random.default_rng(10_000 * seed + 5000 + 300 * ti + c),
                                      snr, N_TEST) for c in range(n_chips)]) for ti in range(len(TEMPS))}
        keep = enroll.reshape(-1, enroll.shape[-1]).std(0) > 0
        sw = noise_cov(enroll, keep)
        base = mahalanobis_acc(enroll, tests, keep, sw)
        b = {}
        for ti in range(len(TEMPS)):
            ms, cs = drift_model(Fs, TEMPS, t0, exclude=ti) if ti in interior else full
            b[f"{TEMPS[ti]:g}"] = mixture_acc(enroll, tests[ti], keep, sw, ms, cs)
        res.append({"seed": seed, "BASE": {f"{TEMPS[ti]:g}": v for ti, v in base.items()}, "B": b})
    m = lambda k, t: float(np.mean([r[k][t] for r in res]))
    ts = [f"{t:g}" for t in TEMPS]
    print(f"transistor-level identification, 16 chips, SNR {snr:g} dB{' (masked features)' if MASKED else ''}")
    for k in ("BASE", "B"):
        print(f"  {k:<5}" + "  ".join(f"{t:>4}:{m(k, t):.3f}" for t in ts))
    verdict = {"identifiable": m("BASE", "27") >= 0.90}
    gap = {t: m("BASE", "27") - m("BASE", t) for t in ("-40", "85")}
    rec = {t: ((m("B", t) - m("BASE", t)) / gap[t]) if gap[t] >= 0.05 else None for t in gap}
    cost = m("BASE", "27") - m("B", "27")
    harm = all(m("B", t) >= m("BASE", t) for t in ts)
    testable = all(v is not None for v in rec.values())
    verdict["B"] = ("not testable" if not testable else
                    "PASS" if min(rec.values()) >= 0.5 and cost <= 0.02 and harm else "FAIL")
    print(f"  gaps {gap}  recovery {rec}  27C cost {100 * cost:+.1f} pts  no-harm {harm}")
    print(f"  pre-registered: identifiable {'PASS' if verdict['identifiable'] else 'FAIL'} | B {verdict['B']}")
    (RESULTS / f"tx_ident_snr{snr:g}{'_masked' if MASKED else ''}.json").write_text(json.dumps(
        dict(snr=snr, runs=res, gap=gap, recovery=rec, cost_27=cost, no_harm=harm, verdict=verdict), indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "sim":
        groups = sys.argv[2:] or ["deployed", "design"]
        jobs = [(c, s0, n, T) for g in groups for c, s0, n in GROUPS[g] for T in TEMPS]
        with ProcessPoolExecutor(2) as ex:                     # at most 2 ngspice at once
            for done in ex.map(run_one, jobs):
                print("done", done, flush=True)
    else:
        analyze(float(sys.argv[sys.argv.index("--snr") + 1]) if "--snr" in sys.argv else 30.0)
