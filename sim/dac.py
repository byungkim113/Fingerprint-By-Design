"""I/Q current-steering DAC: per-chip unit-cell currents vs temperature.

Each DAC = 31 unary NMOS unit current sources mirrored from a diode-connected
reference fed by an ideal Iref. Unit drains are held at Vout through 0 V
ammeters, so one op point gives all 31 unit currents. Swept at three Vout
values to capture finite output resistance (code-dependent nonlinearity once a
resistive load is applied in Python).
"""
import re
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from spice import CORNER, PDK_LIB, SEED0, mc_control, parse_blocks, run_netlist

N_UNITS = 31
W, L = 0.5, 1.0          # unit cell (um); small area -> visible mismatch
IREF = 10e-6
VOUTS = [0.6, 0.9, 1.2]


def netlist(temp, n_chips, seed0=None):
    seed0 = SEED0 if seed0 is None else seed0
    lines = [f"* IQ DAC unit currents T={temp}",
             f'.lib "{PDK_LIB}" {CORNER}',
             f".temp {temp}",
             "Vo vo 0 0.9"]
    for ch in "iq":
        lines += [f"Iref_{ch} 0 g{ch} {IREF}",
                  f"XR{ch} g{ch} g{ch} 0 0 sky130_fd_pr__nfet_01v8 W={W} L={L}"]
        for k in range(N_UNITS):
            lines += [f"Vm{ch}{k} vo d{ch}{k} 0",
                      f"XU{ch}{k} d{ch}{k} g{ch} 0 0 sky130_fd_pr__nfet_01v8 W={W} L={L}"]
    prints = "\n".join(f"  print i(Vm{ch}{k})" for ch in "iq" for k in range(N_UNITS))
    body = ""
    for v in VOUTS:
        body += f"  alter Vo dc = {v}\n  op\n  echo \"@@VO {v}\"\n{prints}\n"
    return "\n".join(lines) + mc_control(n_chips, body, seed0) + ".end\n"


def parse(stdout):
    """-> {chip: array[2 (i/q), len(VOUTS), N_UNITS]} in amps."""
    res = {}
    for chip, txt in parse_blocks(stdout).items():
        arr = np.full((2, len(VOUTS), N_UNITS), np.nan)
        vi = -1
        for line in txt.splitlines():
            if line.startswith("@@VO"):
                vi += 1
                continue
            m = re.match(r"i\(vm([iq])(\d+)\)\s*=\s*(\S+)", line.strip())
            if m:
                arr["iq".index(m.group(1)), vi, int(m.group(2))] = float(m.group(3))
        res[chip] = arr
    return res


def run(temp, n_chips, seed0=None):
    return temp, parse(run_netlist(netlist(temp, n_chips, seed0)))


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    temps = [float(t) for t in sys.argv[2].split(",")] if len(sys.argv) > 2 else [27]
    out = sys.argv[3] if len(sys.argv) > 3 else None
    with ProcessPoolExecutor(max_workers=min(len(temps), 8)) as ex:
        results = dict(ex.map(run, temps, [n] * len(temps)))
    chips = sorted(results[temps[0]])
    data = np.stack([np.stack([results[t][c] for c in chips]) for t in temps])
    print("shape (T, chip, iq, vout, unit):", data.shape, "nan:", np.isnan(data).sum())
    u = data[:, :, :, 1, :]
    print("unit I @Vo=0.9 mean per T (uA):", (u.mean(axis=(1, 2, 3)) * 1e6).round(3))
    print("unit sigma/mean @T0:", (u[0].std() / u[0].mean()).round(4))
    if out:
        np.savez(out, data=data, temps=np.array(temps), chips=np.array(chips),
                 vouts=np.array(VOUTS))
