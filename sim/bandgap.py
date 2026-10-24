"""Bandgap reference for the LDO (item 2c, full version): runs from VIN (3.3 V), 5 V devices.

  Q1 (1x), Q2 (8x) vertical PNPs (collector = substrate = VSS, base = VSS) as diodes.
  PMOS mirror (gate pb) sources equal currents into A (Q1) and B (R1 -> Q2); a PMOS-input OTA
  drives pb so that V(A) = V(B) -> I = VT ln(8) / R1 (PTAT).
  Output branch: the same current through R2 + Q3 (1x) -> VBG = VBE3 + I R2 (~1.2 V, flat in T
  for the right R2/R1). R1, R2 are the same xhigh-poly type so their ratio is temperature-stable.
  Start-up: while A is low, a long PMOS pulls node st high and MS2 pulls pb low.
usage: python bandgap.py tune | check
"""
import os
import re
import sys

import numpy as np

from spice import PDK_LIB, run_netlist

NH, PH = "sky130_fd_pr__nfet_g5v0d10v5", "sky130_fd_pr__pfet_g5v0d10v5"
XH = "sky130_fd_pr__res_xhigh_po_1p41"
PNP = "sky130_fd_pr__pnp_05v5_W3p40L3p40"
R1_L = float(os.environ.get("BG_R1_L", "8.0"))           # um, xhigh_po_1p41
SC = float(os.environ.get("BG_SCALE", "4"))               # W and L multiplier of the matched MOS devices
QM = int(os.environ.get("BG_QM", "2"))                    # PNP unit count: Q1 = QM, Q2 = 8 QM, Q3 = QM
R2_SEG = int(os.environ.get("BG_R2_SEG", "2"))
R2_L = float(os.environ.get("BG_R2_L", "39.0"))         # tuned: 0.5% over -40..85C          # um per segment


def res(name, a, b, seg, length):
    nodes = [a] + [f"{name}_{i}" for i in range(1, seg)] + [b]
    return [f"X{name}{i} {nodes[i]} {nodes[i + 1]} VSS {XH} L={length} mult=1 m=1" for i in range(seg)]


def subckt(p="bg_"):
    """ports: VIN VBG VSS PB (PB = the PTAT mirror gate, exported so other blocks can mirror the current)."""
    A, B, Bq, oa, ob, tl, st, Q3e = (p + x for x in ("a", "b", "bq", "oa", "ob", "tl", "st", "q3e"))
    pb = "PB"
    return "\n".join([
        ".subckt bandgap VIN VBG VSS PB",
        # mismatch: matched devices scaled by SC in W and L (area SC^2) and QM PNP units, because the
        # first version (minimum-ish devices) gave VOUT sd 108 mV over 16 Monte Carlo chips
        f"XQ1 VSS VSS {A} {PNP} m={QM}", f"XQ2 VSS VSS {Bq} {PNP} m={8 * QM}", f"XQ3 VSS VSS {Q3e} {PNP} m={QM}",
        *res("R1", B, Bq, 1, R1_L), *res("R2", "VBG", Q3e, R2_SEG, R2_L),
        # mirror devices weak (large |Vgs|) so pb stays well below the OTA's output ceiling at high VIN
        f"XMA {A} {pb} VIN VIN {PH} W={4.0*SC:g} L={8.0*SC:g}", f"XMB {B} {pb} VIN VIN {PH} W={4.0*SC:g} L={8.0*SC:g}",
        f"XMO VBG {pb} VIN VIN {PH} W={4.0*SC:g} L={8.0*SC:g}",
        # two-stage error amplifier. Stage 1: PMOS pair (A on M1, B on M2), NMOS mirror load; its output
        # ob sits at an NMOS gate voltage, matched to oa (removes the systematic offset that made VBG track
        # VIN when ob had to follow pb). Stage 2: M5 (gate ob) sinks the current of the diode M6 that
        # defines pb. Negative feedback: B up -> ob down -> M5 less -> pb up -> less current.
        f"XMT {tl} {pb} VIN VIN {PH} W={4.0*SC:g} L={8.0*SC:g}",
        f"XM1 {oa} {A} {tl} VIN {PH} W={2.0*SC:g} L={4.0*SC:g}", f"XM2 {ob} {B} {tl} VIN {PH} W={2.0*SC:g} L={4.0*SC:g}",
        f"XM3 {oa} {oa} VSS VSS {NH} W={4.0*SC:g} L={8.0*SC:g}", f"XM4 {ob} {oa} VSS VSS {NH} W={4.0*SC:g} L={8.0*SC:g}",
        f"XM5 {pb} {ob} VSS VSS {NH} W={4.0*SC:g} L={8.0*SC:g}", f"XM6 {pb} {pb} VIN VIN {PH} W={4.0*SC:g} L={8.0*SC:g}",
        # compensation: the laid-out 22x22 um MIM cap (~1 pF); BG_IDEAL_CC=1 reproduces the ideal 1 pF used in
        # the L1-L3 runs (2026-10-06)
        (f"Cc {pb} {ob} {os.environ.get('BG_CC', '1p')}" if os.environ.get("BG_IDEAL_CC") else
         f"XCc {pb} {ob} sky130_fd_pr__cap_mim_m3_1 W=22 L=22 MF=1 m=1"),
        # start-up: st high while VBG is low -> MS2 pulls pb (and the OTA tail) on; once VBG ~1.2 V,
        # MS3 holds st at 0 (detecting on A failed: V(A) ~0.73 V is below the 5 V NMOS threshold)
        f"XMS1 {st} VSS VIN VIN {PH} W=0.42 L=50", f"XMS3 {st} VBG VSS VSS {NH} W=4 L=0.5",
        f"XMS2 {pb} {st} VSS VSS {NH} W=0.5 L=4",
        ".ends bandgap", ""])


def bench(analysis, temp=27, corner="tt", vin=3.3):
    return "\n".join([f"* bandgap T={temp}", f'.lib "{PDK_LIB}" {corner}', f".temp {temp}", subckt(),
                      f"Vin vin 0 {vin}", "X1 vin vbg 0 pb bandgap", ".control", analysis, ".endc", ".end", ""])


def op(temp=27, vin=3.3, nodes=("vbg",)):
    out = run_netlist(bench("  op\n  print " + " ".join(f"v({n})" for n in nodes), temp, vin=vin))
    return [float(x) for x in re.findall(r"=\s*(\S+)", "\n".join(l for l in out.splitlines() if l.strip().startswith("v(")))]


if __name__ == "__main__":
    if sys.argv[1] == "check":
        for T in (-40, 27, 85):
            print(f"T={T:>4}: " + "  ".join(f"VIN {v}: VBG {op(T, v)[0]:.4f}" for v in (2.97, 3.3, 3.63)))
        print("nodes @27C 3.3V (a, b, pb, st, vbg):", [round(x, 3) for x in op(nodes=("x1.bg_a", "x1.bg_b", "pb", "x1.bg_st", "vbg"))])
