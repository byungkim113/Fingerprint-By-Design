"""LO quadrature check of the lo_path block: schematic vs Magic-extracted (C), same stimulus.
Phase of LO_Q relative to LO_I (fundamental) and of the RC-CR outputs (schematic only).

usage: python lo_quad.py [pex_netlist ...]
"""
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

import tx_full as tx
from spice import PDK_LIB, SPINIT

HERE = Path(__file__).resolve().parent
LAY = HERE.parent / "layout"
W = HERE / "work" / "lo_quad"


def bench(sub_text, corner="tt", temp=27.0, r_src=150.0):
    return "\n".join([f"* lo_path quadrature", f'.lib "{PDK_LIB}" {corner}', f".temp {temp}",
                      f'.include "{tx.STDCELLS}"', sub_text, f"Vdd vdd 0 {tx.VDD}",
                      f"Vlo s 0 dc 0.9 sin(0.9 0.4 {tx.FLO})", f"Rs s in {r_src}",
                      "X1 in loi lobi loq lobq vdd 0 lo_path",
                      ".control\n  save v(loi) v(loq)\n  tran 10p 60n 0 10p\n  wrdata out.txt v(loi) v(loq)\n.endc\n.end\n"])


def phase(tag, sub_text, **kw):
    d = W / tag
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(SPINIT, d / ".spiceinit")
    (d / "c.sp").write_text(bench(sub_text, **kw))
    subprocess.run(["ngspice", "-b", "c.sp"], cwd=d, capture_output=True)
    a = np.loadtxt(d / "out.txt")
    t, i, q = a[:, 0], a[:, 1], a[:, 3]
    m = t > 20e-9
    e = np.exp(-2j * np.pi * tx.FLO * t[m])
    fi, fq = np.trapezoid(i[m] * e, t[m]), np.trapezoid(q[m] * e, t[m])
    return float(np.degrees(np.angle(fq / fi)))


if __name__ == "__main__":
    sch = phase("schematic", (LAY / "lo_path.spice").read_text())   # the LVS netlist
    print(f"schematic   : LO_Q - LO_I phase {sch:+.1f} deg (ideal +-90)")
    for p in sys.argv[1:] or [str(LAY / "work/lo_path/pex/lo_path_pex_c.spice")]:
        print(f"{Path(p).name:<24}: LO_Q - LO_I phase {phase(Path(p).stem, Path(p).read_text()):+.1f} deg")
