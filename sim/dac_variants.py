"""DAC design variants for the generalization study.

Each variant is a 31-unit unary NMOS current-source DAC (I and Q) with the
same measurement setup as dac.py; only the unit cell and bias change:

  dac_sl   : simple mirror, short channel  W0.5/L0.3, Iref 10 uA
  dac_hi   : simple mirror, W0.5/L1, Iref 40 uA   (far above ZTC)
  dac_ztc  : simple mirror, W0.5/L1, Iref 7.1 uA  (gate at the ZTC point, ~0.95 V)
  dac_lo   : simple mirror, W0.5/L1, Iref 1 uA    (far below ZTC)
  dac_casL : cascoded, source W0.5/L1 + cascode W0.5/L0.5, Iref 10 uA, Vcas 1.3 V

usage: python dac_variants.py <name> <n_chips> <temps> <out.npz>
(corner and first chip seed from SKY130_CORNER / CHIP_SEED0, as in spice.py)
"""
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import dac
from spice import CORNER, PDK_LIB, SEED0, mc_control, run_netlist

CONFIGS = {
    "dac_sl": dict(w=0.5, l=0.3, iref=10e-6),
    "dac_hi": dict(w=0.5, l=1.0, iref=40e-6),
    "dac_ztc": dict(w=0.5, l=1.0, iref=7.1e-6),
    "dac_lo": dict(w=0.5, l=1.0, iref=1e-6),
    "dac_casL": dict(w=0.5, l=1.0, iref=10e-6, cas=(0.5, 0.5, 1.3)),
}


def netlist(cfg, temp, n_chips):
    w, l, iref = cfg["w"], cfg["l"], cfg["iref"]
    cas = cfg.get("cas")
    lines = [f"* DAC variant T={temp}", f'.lib "{PDK_LIB}" {CORNER}', f".temp {temp}", "Vo vo 0 0.9"]
    if cas:
        lines.append(f"Vcas vcas 0 {cas[2]}")
    for ch in "iq":
        lines += [f"Iref_{ch} 0 g{ch} {iref}",
                  f"XR{ch} g{ch} g{ch} 0 0 sky130_fd_pr__nfet_01v8 W={w} L={l}"]
        for k in range(dac.N_UNITS):
            lines.append(f"Vm{ch}{k} vo d{ch}{k} 0")
            if cas:
                lines += [f"XC{ch}{k} d{ch}{k} vcas s{ch}{k} 0 sky130_fd_pr__nfet_01v8 W={cas[0]} L={cas[1]}",
                          f"XU{ch}{k} s{ch}{k} g{ch} 0 0 sky130_fd_pr__nfet_01v8 W={w} L={l}"]
            else:
                lines.append(f"XU{ch}{k} d{ch}{k} g{ch} 0 0 sky130_fd_pr__nfet_01v8 W={w} L={l}")
    prints = "\n".join(f"  print i(Vm{ch}{k})" for ch in "iq" for k in range(dac.N_UNITS))
    body = "".join(f"  alter Vo dc = {v}\n  op\n  echo \"@@VO {v}\"\n{prints}\n" for v in dac.VOUTS)
    return "\n".join(lines) + mc_control(n_chips, body, SEED0) + ".end\n"


def run(args):
    name, temp, n = args
    return temp, dac.parse(run_netlist(netlist(CONFIGS[name], temp, n)))


if __name__ == "__main__":
    name, n = sys.argv[1], int(sys.argv[2])
    temps = [float(t) for t in sys.argv[3].split(",")]
    out = sys.argv[4] if len(sys.argv) > 4 else None
    with ProcessPoolExecutor(max_workers=min(len(temps), 5)) as ex:
        results = dict(ex.map(run, [(name, t, n) for t in temps]))
    chips = sorted(results[temps[0]])
    data = np.stack([np.stack([results[t][c] for c in chips]) for t in temps])
    u = data[:, :, :, 1, :]
    rel = u / u.mean(-1, keepdims=True) - 1
    print(f"{name} {CORNER}: shape {data.shape} nan {np.isnan(data).sum()}  "
          f"unit uA per T {(u.mean(axis=(1, 2, 3)) * 1e6).round(3)}  mismatch {rel.std(axis=(1, 2, 3)).round(4)}")
    if out:
        np.savez(out, data=data, temps=np.array(temps), chips=np.array(chips), vouts=np.array(dac.VOUTS))
