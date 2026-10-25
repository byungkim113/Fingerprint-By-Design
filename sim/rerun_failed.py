"""Rerun Monte Carlo chips whose transient aborted (convergence) in the LDO test runs, one at a time,
with Gear integration; same seed, condition and data frame, so the chip is identical. The rerun's
waveform replaces the incomplete tx_out_<seed>; the session's own log is left untouched.
usage: python rerun_failed.py"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
WORK = HERE / "work" / "tx"
END_TIME = 128 / 25e6  # all LDO study frames are 128 samples at 25 MS/s


def incomplete():
    out = []
    for d in sorted(WORK.glob("ident_ldo*_tt_mm_T*")):
        for s in range(1, 17):
            f = d / f"tx_out_{s}"
            try:
                a = np.loadtxt(f)
                ok = a.ndim == 2 and a[-1, 0] >= END_TIME * (1 - 1e-6)
            except Exception:
                ok = False
            if not ok:
                out.append((d, s))
    return out


def env_for(d):
    m = re.match(r"ident_(ldo_|ldof(\w+?)_)(ldo\d+)_tt_mm_T(-?\d+)", d.name)
    tag, frame, variant, temp = m.group(1), m.group(2) or "1", m.group(3), float(m.group(4))
    return dict(TX_TAG=tag, TX_FRAME=frame, TX_VARIANT=variant), temp


def rerun(d, seed):
    env, temp = env_for(d)
    tmp = d / (f"rerun_{seed}" + ("_rdd" if os.environ.get("RERUN_RDD") else ""))
    tmp.mkdir(exist_ok=True)
    code = ("import tx_ident as ti, shutil\n"
            "from spice import SPINIT\n"
            f"t = ti.netlist('tt_mm', {seed}, 1, {temp})\n"
            "t = t.replace('\\n.control', '\\n.option method=gear\\n.control', 1)\n"
            # second attempt for chips that still failed: the 0 V ammeter between the LDO output and the core
            # (stiff 'vdd#branch') becomes a 1 milliohm resistor (6 uV at the core's 6 mA)
            "import os\n"
            "t = t.replace('Vdd vdd_ldo vdd 0', 'Rdd vdd_ldo vdd 1m') if os.environ.get('RERUN_RDD') else t\n"
            f"open(r'{tmp}/c.sp', 'w').write(t)\n"
            f"shutil.copy(SPINIT, r'{tmp}/.spiceinit')\n")
    subprocess.run([sys.executable, "-c", code], cwd=HERE, env=dict(os.environ, **env), check=True)
    with open(tmp / "ngspice.log", "w") as log:
        subprocess.run(["ngspice", "-b", "c.sp"], cwd=tmp, stdout=log, stderr=subprocess.STDOUT, timeout=4 * 3600)
    f = tmp / f"tx_out_{seed}"
    a = np.loadtxt(f) if f.exists() else None
    if a is not None and a.ndim == 2 and a[-1, 0] >= END_TIME * (1 - 1e-6):
        shutil.copy(f, d / f"tx_out_{seed}")
        return "fixed"
    return "still failing"


if __name__ == "__main__":
    if "--rdd" in sys.argv:
        os.environ["RERUN_RDD"] = "1"
    todo = incomplete()
    print("incomplete chip-runs:", [(d.name, s) for d, s in todo], flush=True)
    for d, s in todo:
        print(d.name, s, rerun(d, s), flush=True)
