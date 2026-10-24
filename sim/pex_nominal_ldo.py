"""Nominal post-layout check of the full chip with the on-chip LDO (item 4b): schematic (tx_full variant ldo330)
vs the Magic-extracted chip (devices + parasitic C), tt, 27C, 3.3 V external supply, same 128-sample frame.
usage: python pex_nominal_ldo.py"""
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def run(which):
    env = dict(os.environ, TX_VARIANT="ldo330")
    code = ("import shutil, tx_full as tx, tx_ident as ti, tx_pex as tp\n"
            "from spice import SPINIT\n"
            "ci, cq = ti.frame()\n"
            f"d = tx.WORK / 'nominal_{which}_ldo330'; d.mkdir(parents=True, exist_ok=True)\n"
            "shutil.copy(SPINIT, d / '.spiceinit')\n"
            "ctrl = (f'\\n.control\\n  save v(rfp) v(rfn)\\n  tran 20p {len(ci)/tx.FS:.4e} 0 20p\\n'\n"
            "        '  wrdata tx_out.txt v(rfp) v(rfn) v(rfp) v(rfn) v(rfp) v(rfn)\\n.endc\\n.end\\n')\n"
            + ("t = tx.netlist(ci, cq, temp=27.0, corner='tt').split('\\n.control')[0] + ctrl\n" if which == "sch" else
               "t = tp.netlist(27.0, 'tt', ci, cq) + ctrl\n")
            + "(d / 'c.sp').write_text(t)\n"
            "import subprocess\n"
            "with open(d / 'ngspice.log', 'w') as log:\n"
            "    subprocess.run(['ngspice', '-b', 'c.sp'], cwd=d, stdout=log, stderr=subprocess.STDOUT)\n"
            "print(d)\n")
    return subprocess.run([sys.executable, "-c", code], cwd=HERE, env=env, capture_output=True, text=True).stdout.strip()


if __name__ == "__main__":
    with ThreadPoolExecutor(2) as ex:
        dirs = list(ex.map(run, ("sch", "pex")))
    sys.path.insert(0, HERE)
    import tx_full as tx
    import tx_ident as ti
    ci, cq = ti.frame()
    I, Q = 2 * ci / 31 - 1, 2 * cq / 31 - 1
    ideal = I + 1j * Q
    for name, d in zip(("schematic+LDO", "post-layout+LDO"), dirs):
        t, w = tx.load_wr(os.path.join(d, "tx_out.txt"))
        y = tx.downconvert(t, w["rfp"] - w["rfn"], ti.N_SAMPLES)
        h = (y @ ideal.conj()) / (ideal @ ideal.conj())
        c, *_ = np.linalg.lstsq(np.stack([I, 1j * Q], 1).astype(complex), y, rcond=None)
        print(f"{name:<16} |gain| {abs(h):.4f}  EVM {100 * np.linalg.norm(y / h - ideal) / np.linalg.norm(ideal):.2f} %  "
              f"Q/I phase {np.degrees(np.angle(c[1] / c[0])):+.1f} deg")
