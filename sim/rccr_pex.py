"""Post-layout check of the RC-CR quadrature network (pre-registered in PLAN.md).

Compares the schematic (as in lo.py) with the Magic C-only extraction of
layout/rccr.gds (devices + parasitic capacitors), both driven from a 50-ohm
source and loaded by the same 5 fF per output. Reports I/Q gain imbalance and
phase error at FC: nominal (tt, no mismatch) and the chip-to-chip spread from a
50-chip mismatch Monte Carlo (tt_mm), at -40, 27 and 85 C.
"""
import re
import sys
from pathlib import Path

import numpy as np

import lo
from spice import PDK_LIB, mc_control, run_netlist

PEX = Path(__file__).resolve().parents[1] / "layout" / "work" / "rccr_pex" / "rccr_pexc.spice"
TEMPS = [-40.0, 27.0, 85.0]
N_MC = 50


def schematic_body():
    return [f"XRi in vi 0 sky130_fd_pr__res_high_po_0p35 L={lo.R_L} mult=1 m=1",
            f"XCi vi 0 sky130_fd_pr__cap_mim_m3_1 W={lo.C_W} L={lo.C_L} MF=1 m=1",
            f"XCq in vq sky130_fd_pr__cap_mim_m3_1 W={lo.C_W} L={lo.C_L} MF=1 m=1",
            f"XRq vq 0 0 sky130_fd_pr__res_high_po_0p35 L={lo.R_L} mult=1 m=1"]


def pex_body():
    """Extracted device and parasitic lines, nets renamed to the testbench's."""
    ren = {"IN": "in", "VI": "vi", "VQ": "vq", "VSS": "0"}
    out = []
    for line in PEX.read_text().splitlines():
        if not re.match(r"^[XC]\w*\s", line):
            continue
        f = line.split()
        nodes, rest = [], []
        for tok in f[1:]:
            (rest if (rest or tok.startswith("sky130") or re.match(r"^[\d.]+[fpn]?$", tok)) else nodes).append(tok)
        out.append(" ".join([f[0] + "_pex"] + [ren.get(n, n) for n in nodes] + rest))
    return out


def netlist(body, temp, corner, n_chips):
    lines = [f"* RC-CR {('PEX' if 'pex' in body[0] else 'schematic')} T={temp}",
             f'.lib "{PDK_LIB}" {corner}', f".temp {temp}",
             "Vs s 0 dc 0 ac 1", "Rs s in 50", *body, "Cli vi 0 5f", "Clq vq 0 5f"]
    meas = f"  ac lin 1 {lo.FC} {lo.FC}\n  print vm(vi) vp(vi) vm(vq) vp(vq)\n"
    if n_chips:
        return "\n".join(lines) + mc_control(n_chips, meas) + ".end\n"
    return "\n".join(lines) + "\n.control\n" + meas + ".endc\n.end\n"


def imbalance(v):
    """-> (gain imbalance dB, phase error deg) from |vi|, ang vi, |vq|, ang vq."""
    return 20 * np.log10(v[..., 2] / v[..., 0]), np.degrees(v[..., 3] - v[..., 1]) - 90


def nominal(body, temp):
    out = run_netlist(netlist(body, temp, "tt", 0))
    v = dict(re.findall(r"(v[mp]\(v[iq]\))\s*=\s*(\S+)", out))
    return np.array([float(v[k]) for k in ("vm(vi)", "vp(vi)", "vm(vq)", "vp(vq)")])


def monte_carlo(body, temp):
    res = lo.parse(run_netlist(netlist(body, temp, "tt_mm", N_MC)))
    return np.stack([res[k] for k in sorted(res)])


if __name__ == "__main__":
    bodies = {"schematic": schematic_body(), "post-layout": pex_body()}
    print("PEX body:\n  " + "\n  ".join(bodies["post-layout"]))
    rows = {}
    for name, body in bodies.items():
        for t in TEMPS:
            g, ph = imbalance(nominal(body, t))
            gm, pm = imbalance(monte_carlo(body, t))
            rows[(name, t)] = (g, ph, gm.std(), pm.std())
    print(f"\n{'':12}{'T':>6}{'gain dB':>10}{'phase deg':>11}{'chip sd dB':>12}{'chip sd deg':>13}")
    for (name, t), (g, ph, gs, ps) in rows.items():
        print(f"{name:12}{t:>6g}{g:>10.3f}{ph:>11.3f}{gs:>12.3f}{ps:>13.3f}")
    print("\nshift (post-layout - schematic):")
    ok = True
    for t in TEMPS:
        s, p = rows[("schematic", t)], rows[("post-layout", t)]
        dph, rel = p[1] - s[1], p[3] / s[3] - 1
        ok &= abs(dph) < 1 and abs(rel) < 0.2 and abs(p[2] / s[2] - 1) < 0.2
        print(f"  T={t:5g}: gain {p[0] - s[0]:+.3f} dB, phase {dph:+.3f} deg, "
              f"spread gain {100 * (p[2] / s[2] - 1):+.1f}%, phase {100 * rel:+.1f}%")
    print("pre-registered verdict:", "LAYOUT-SAFE" if ok else "NOT layout-safe")
    sys.exit(0)
