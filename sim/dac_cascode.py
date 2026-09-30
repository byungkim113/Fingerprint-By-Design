"""Second DAC design: cascoded unary current-steering DAC.

Differences from dac.py: each unit is a current source (W=2, L=0.5) with a
cascode device (W=2, L=0.15) biased from a fixed Vcas; reference current is
20 uA. Shorter/wider sources change both the mismatch magnitude and how it
responds to temperature; the cascode raises output resistance. Output format
matches dac.py: (T, chip, iq, vout, unit) in amps.
"""
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import dac
from spice import CORNER, PDK_LIB, SEED0, mc_control, run_netlist

W_S, L_S = 2.0, 0.5
W_C, L_C = 2.0, 0.15
IREF = 20e-6
VCAS = 1.0


def netlist(temp, n_chips, seed0=None):
    seed0 = SEED0 if seed0 is None else seed0
    lines = [f"* cascode IQ DAC unit currents T={temp}",
             f'.lib "{PDK_LIB}" {CORNER}',
             f".temp {temp}",
             "Vo vo 0 0.9",
             f"Vcas vcas 0 {VCAS}"]
    for ch in "iq":
        lines += [f"Iref_{ch} 0 g{ch} {IREF}",
                  f"XR{ch} g{ch} g{ch} 0 0 sky130_fd_pr__nfet_01v8 W={W_S} L={L_S}"]
        for k in range(dac.N_UNITS):
            lines += [f"Vm{ch}{k} vo d{ch}{k} 0",
                      f"XC{ch}{k} d{ch}{k} vcas s{ch}{k} 0 sky130_fd_pr__nfet_01v8 W={W_C} L={L_C}",
                      f"XU{ch}{k} s{ch}{k} g{ch} 0 0 sky130_fd_pr__nfet_01v8 W={W_S} L={L_S}"]
    prints = "\n".join(f"  print i(Vm{ch}{k})" for ch in "iq" for k in range(dac.N_UNITS))
    body = ""
    for v in dac.VOUTS:
        body += f"  alter Vo dc = {v}\n  op\n  echo \"@@VO {v}\"\n{prints}\n"
    return "\n".join(lines) + mc_control(n_chips, body, seed0) + ".end\n"


def run(temp, n_chips):
    return temp, dac.parse(run_netlist(netlist(temp, n_chips)))


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
    rel = u / u.mean(-1, keepdims=True) - 1
    print("unit mismatch sigma per T:", rel.std(axis=(1, 2, 3)).round(4))
    if out:
        np.savez(out, data=data, temps=np.array(temps), chips=np.array(chips),
                 vouts=np.array(dac.VOUTS))
