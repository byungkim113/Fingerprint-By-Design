"""Post-layout simulation: the Magic-extracted tx_core (devices + parasitic C) driven by the
same stimulus and off-chip parts as tx_full (50-ohm LO source, 10 pF + 50 ohm loads).

The extracted netlist has only the core's pins (LO_PAD, TXP, TXN, VDD, VSS, data bits), so
internal nodes are not available; identification needs only rfp/rfn. Monte Carlo draws
follow the extracted instance order, so PEX chip k is NOT schematic chip k: comparisons
with the schematic runs are population-level.

usage: python tx_pex.py nominal | sim | analyze
"""
import re
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import tx_full as tx
import tx_ident as ti
from spice import PDK_LIB, SPINIT, mc_control

PEX = Path(__file__).resolve().parents[1] / "layout" / "work" / "tx_core" / "pex" / "tx_core_pex_c.spice"
TEMPS = [-40.0, 27.0, 85.0]
VIN = 3.3                       # external supply when the extracted chip includes the LDO


def ports():
    text = PEX.read_text()
    m = re.search(r"^\.subckt tx_core (.*?)\n(?!\+)", text, flags=re.M | re.S)
    return m.group(1).replace("\n+", " ").split()


def netlist(temp, corner, codes_i, codes_q, lo_amp=0.5):
    bits = {"I": tx.thermometer(codes_i), "Q": tx.thermometer(codes_q)}
    conn = []
    for p in ports():
        m = re.fullmatch(r"D(B?)([IQ])(\d+)", p)
        if p == "LO_PAD":
            conn.append("lo_pad")
        elif p in ("TXP", "TXN"):
            conn.append({"TXP": "sfp", "TXN": "sfn"}[p])
        elif p == "VDD":
            conn.append("vdd")
        elif p == "VIN":                                   # chip with on-chip LDO: external 3.3 V supply
            conn.append("vin_ext")
        elif p == "VSS":
            conn.append("0")
        elif m:
            conn.append(f"d{'b' if m.group(1) else ''}{m.group(2).lower()}{m.group(3)}")
        else:
            raise ValueError(f"unexpected port {p}")
    srcs = []
    for ch in ("i", "q"):
        b = bits[ch.upper()]
        for k in range(tx.N_UNITS):
            srcs += [tx.pwl(f"d{ch}{k}", f"d{ch}{k}", b[k]), tx.pwl(f"db{ch}{k}", f"db{ch}{k}", 1 - b[k])]
    return "\n".join([f"* post-layout tx_core T={temp}", f'.lib "{PDK_LIB}" {corner}', f".temp {temp}",
                      f'.include "{PEX}"', (f"Vin vin_ext 0 {VIN}" if "VIN" in ports() else f"Vdd vdd 0 {tx.VDD}"),
                      *([".nodeset v(vin_ext)=3.3", ".option rshunt=1e12"] if "VIN" in ports() else []),
                      f"Vlo s 0 dc 0 ac {lo_amp} sin(0 {lo_amp} {tx.FLO})", "Rsrc s lo_pad 50",
                      "Xcore " + " ".join(conn) + " tx_core",
                      "Cxp sfp rfp 10p", "Rxp rfp 0 50", "Cxn sfn rfn 10p", "Rxn rfn 0 50", *srcs])


def body(n):
    return (f"  save v(rfp) v(rfn)\n  tran 20p {n / tx.FS:.4e} 0 20p\n"
            "  wrdata tx_out_$&seed v(rfp) v(rfn) v(rfp) v(rfn) v(rfp) v(rfn)\n  destroy all\n")


def run_dir(temp, tag="pex"):
    return tx.WORK / f"{tag}_tt_mm_T{temp:g}"


def run_one(temp):
    ci, cq = ti.frame()
    d = run_dir(temp)
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(SPINIT, d / ".spiceinit")
    (d / "c.sp").write_text(netlist(temp, "tt_mm", ci, cq) + "\n" + mc_control(16, body(len(ci)), 1) + ".end\n")
    with open(d / "ngspice.log", "w") as log:
        subprocess.run(["ngspice", "-b", "c.sp"], cwd=d, stdout=log, stderr=subprocess.STDOUT, timeout=8 * 3600)
    return temp


def nominal():
    """pre- vs post-layout at tt, 27 C: RF level and EVM (same frame)."""
    ci, cq = ti.frame()
    d = tx.WORK / "pex_nominal"
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(SPINIT, d / ".spiceinit")
    ctrl = (f"\n.control\n  save v(rfp) v(rfn)\n  tran 20p {len(ci) / tx.FS:.4e} 0 20p\n"
            "  wrdata tx_out.txt v(rfp) v(rfn) v(rfp) v(rfn) v(rfp) v(rfn)\n.endc\n.end\n")
    (d / "c.sp").write_text(netlist(27.0, "tt", ci, cq) + ctrl)
    with open(d / "ngspice.log", "w") as log:
        subprocess.run(["ngspice", "-b", "c.sp"], cwd=d, stdout=log, stderr=subprocess.STDOUT)
    ideal = (2 * ci / 31 - 1) + 1j * (2 * cq / 31 - 1)
    for name, path in (("schematic", tx.WORK / "nominal_base" / "tx_out.txt"), ("post-layout", d / "tx_out.txt")):
        t, w = tx.load_wr(path)
        n0 = 64 if name == "schematic" else 0                    # nominal_base carries the 64-sample cal segment
        y = tx.downconvert(t, w["rfp"] - w["rfn"], n0 + len(ci))[n0:]
        h = (y @ ideal.conj()) / (ideal @ ideal.conj())
        evm = np.sqrt(np.mean(np.abs(y / h - ideal) ** 2) / np.mean(np.abs(ideal) ** 2))
        print(f"{name:<12} |gain| {abs(h):.4f}  EVM {100 * evm:.2f} %")


if __name__ == "__main__":
    if sys.argv[1] == "nominal":
        nominal()
    elif sys.argv[1] == "sim":
        with ProcessPoolExecutor(2) as ex:
            print(list(ex.map(run_one, TEMPS)))
