"""PA stage: per-chip AM/AM and AM/PM vs temperature and supply.

Common-source NMOS driver biased from a diode-connected mirror (mismatch
between mirror and PA device sets the bias point), resistive load with a
capacitive load. Driven by a sine at FC; the fundamental's magnitude and phase
at the output (ngspice `fourier`) versus input amplitude give AM/AM and AM/PM.
"""
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from itertools import product

import numpy as np

from spice import CORNER, PDK_LIB, SEED0, mc_control, parse_blocks, run_netlist

FC = 200e6
AMPS = [0.02, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4]
W_PA, L_PA = 10.0, 0.15
W_B, L_B = 1.0, 0.15      # mirror ratio 10:1
IREF = 50e-6
RL, CL = 1000, 100e-15
N_CYC, N_SETTLE = 12, 6


def netlist(temp, vdd, n_chips, seed0=None):
    tstop = N_CYC / FC
    seed0 = SEED0 if seed0 is None else seed0
    lines = [f"* PA AM/AM AM/PM T={temp} VDD={vdd}",
             f'.lib "{PDK_LIB}" {CORNER}',
             f".temp {temp}",
             f"Vdd vdd 0 {vdd}",
             f"Iref vdd b {IREF}",
             f"XB b b 0 0 sky130_fd_pr__nfet_01v8 W={W_B} L={L_B}",
             "Rb b g 20k",
             f"Vin in 0 dc 0 sin(0 {AMPS[0]} {FC})",
             "Cc in g 10p",
             f"XP out g 0 0 sky130_fd_pr__nfet_01v8 W={W_PA} L={L_PA}",
             f"RL vdd out {RL}",
             f"CL out 0 {CL}"]
    body = ""
    for a in AMPS:
        body += (f"  alter @Vin[sin] = [ 0 {a} {FC} ]\n"
                 f"  tran {1 / FC / 64} {tstop} {N_SETTLE / FC}\n"
                 f"  echo \"@@AMP {a}\"\n"
                 f"  fourier {FC} v(out)\n")
    return "\n".join(lines) + mc_control(n_chips, body, seed0) + ".end\n"


def parse(stdout):
    """-> {chip: array[len(AMPS), 2 (mag, phase_deg)]}"""
    res = {}
    for chip, txt in parse_blocks(stdout).items():
        arr = np.full((len(AMPS), 2), np.nan)
        ai = -1
        for line in txt.splitlines():
            s = line.strip()
            if s.startswith("@@AMP"):
                ai += 1
                continue
            # harmonic-1 row: "1  2.000000e+08  mag  phase  normmag  normphase"
            m = re.match(r"1\s+\S+\s+(\S+)\s+(\S+)\s+\S+\s+\S+$", s)
            if m and ai >= 0 and np.isnan(arr[ai, 0]):
                arr[ai] = float(m.group(1)), float(m.group(2))
        res[chip] = arr
    return res


def run(args):
    temp, vdd, n, seed0 = args
    return (temp, vdd), parse(run_netlist(netlist(temp, vdd, n, seed0)))


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    temps = [float(t) for t in sys.argv[2].split(",")] if len(sys.argv) > 2 else [27]
    vdds = [float(v) for v in sys.argv[3].split(",")] if len(sys.argv) > 3 else [1.8]
    out = sys.argv[4] if len(sys.argv) > 4 else None
    jobs = [(t, v, n, SEED0) for t, v in product(temps, vdds)]
    with ProcessPoolExecutor(max_workers=8) as ex:
        results = dict(ex.map(run, jobs))
    chips = sorted(results[(temps[0], vdds[0])])
    data = np.stack([np.stack([np.stack([results[(t, v)][c] for c in chips])
                               for v in vdds]) for t in temps])
    print("shape (T, VDD, chip, amp, [mag,phase]):", data.shape,
          "nan:", np.isnan(data).sum())
    g = data[..., 0] / np.array(AMPS)
    print("small-signal gain per T (VDD[0]):", g[:, 0, :, 0].mean(-1).round(2))
    print("gain compression last/first (T0,V0):", (g[0, 0, :, -1] / g[0, 0, :, 0]).mean().round(3))
    print("phase shift last-first deg (T0,V0):", (data[0, 0, :, -1, 1] - data[0, 0, :, 0, 1]).mean().round(2))
    print("chip-to-chip gain sigma/mean (T0,V0,amp0):",
          (g[0, 0, :, 0].std() / g[0, 0, :, 0].mean()).round(4))
    if out:
        np.savez(out, data=data, temps=np.array(temps), vdds=np.array(vdds),
                 chips=np.array(chips), amps=np.array(AMPS))
