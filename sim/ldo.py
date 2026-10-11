"""On-chip LDO for the transmitter core (item 2c, PLAN.md): 3.3 V external supply -> 1.8 V core VDD.

All transistor-level SKY130:
  reference : beta-multiplier on VIN (5 V devices) + resistor -> VREF ~ 1.2 V
  error amp : 5-transistor OTA (5 V devices), NMOS input pair (in+ = VFB, in- = VREF)
  pass      : pfet_g5v0d10v5 (gate driven by the OTA; VOUT high -> gate high -> less current)
  divider   : xhigh-poly resistors, VOUT = VREF * (1 + R1/R2)
  output    : nfet_01v8 gate capacitors (thin oxide, VOUT <= 1.8 V) as on-chip decoupling
usage: python ldo.py dc | step | all
"""
import os
import sys

import numpy as np

from spice import PDK_LIB, run_netlist

NH, PH = "sky130_fd_pr__nfet_g5v0d10v5", "sky130_fd_pr__pfet_g5v0d10v5"
XH = "sky130_fd_pr__res_xhigh_po_1p41"
# sizes (tuned below)
RS_L = float(os.environ.get("LDO_RS_L", "14"))         # beta-multiplier resistor length (um)
RREF_SEG = int(os.environ.get("LDO_RREF_SEG", "5"))
RREF_L = float(os.environ.get("LDO_RREF_L", "38.15"))    # segment length (um): trims VREF
LP = float(os.environ.get("LDO_LP", "4"))                # reference PMOS mirror length (um)
LN = float(os.environ.get("LDO_LN", "8"))                # reference NMOS length (um)    # 50k segments in the reference resistor
W_PASS, NF_PASS = 200.0, 20
C_DEC_M = int(os.environ.get("LDO_CDEC_M", "15"))     # 20x20 um nfet gate caps (~3.4 pF each)
TAIL_X = float(os.environ.get("LDO_TAIL_X", "1"))     # OTA tail current multiplier
OTA_L = float(os.environ.get("LDO_OTA_L", "2"))         # OTA device length (um), W scaled to keep W/L
C_MILLER = os.environ.get("LDO_CC", "1p")
REF = os.environ.get("LDO_REF", "bg")       # "bg": bandgap (full version); "vin": beta-multiplier I*R (prototype)
DIV_R1_L = float(os.environ.get("LDO_DIV_R1_L", "34.1"))   # divider top resistor length: VOUT = VREF (1 + R1/R2)                  # "vin": reference on VIN; "boot": on VOUT (1.8 V devices)
RREF_BOOT = int(os.environ.get("LDO_RREF_BOOT", "2"))    # 50k segments: VREF = I(10 uA) x R


def res(name, a, b, seg, length=35.25):
    """seg x xhigh_po_1p41 segments (50.2k each at L=35.25)."""
    nodes = [a] + [f"{name}_{i}" for i in range(1, seg)] + [b]
    return [f"X{name}{i} {nodes[i]} {nodes[i + 1]} 0 {XH} L={length} mult=1 m=1" for i in range(seg)]


def boot_ref(p):
    """reference powered from the regulated VOUT: the core's beta multiplier (1.8 V devices, 10 uA
    branches), output into Rref -> VREF; a second 1x branch into an NMOS diode biases the OTA tail."""
    import bias_ref
    lines = [l.replace(" vdd vdd ", " VOUT VOUT ").replace(" vdd ", " VOUT ").replace(" 0 0 ", " VSS VSS ")
             .replace(" 0 ", " VSS ") for l in bias_ref.core(outs=((p + "vref", 1), (p + "tb", 1)), p=p + "b_")]
    return lines + res("Rref", p + "vref", "VSS", RREF_BOOT) + [f"XMTB {p}tb {p}tb VSS VSS {NH} W=4 L=2"]


def bg_ref(p):
    """bandgap reference (bandgap.py) -> VREF; the OTA tail mirrors the bandgap's PTAT current (pb gate)
    through a 5 V PMOS into an NMOS diode (tb). The bandgap subcircuit is defined beside the LDO's."""
    return [f"XBG VIN {p}vref VSS {p}pb bandgap", f"XMTP {p}tb {p}pb VIN VIN {PH} W=4 L=8",
            f"XMTB {p}tb {p}tb VSS VSS {NH} W=4 L=2"]


def subckt():
    p = "ldo_"
    n1, pgr, nr, st, vref, fb, a, g, tail = (p + x for x in ("n1", "pgr", "nr", "st", "vref", "fb", "a", "g", "tail"))
    return ("\n".join([
        ".subckt ldo VIN VOUT VSS",
        # beta-multiplier reference on VIN
        f"XM1 {n1} {n1} VSS VSS {NH} W={2 * LN} L={LN}", f"XM2 {pgr} {n1} {nr} VSS {NH} W={8 * LN} L={LN}",
        f"XRs {nr} VSS VSS {XH} L={RS_L} mult=1 m=1",
        f"XM3 {n1} {pgr} VIN VIN {PH} W={2 * LP} L={LP}", f"XM4 {pgr} {pgr} VIN VIN {PH} W={2 * LP} L={LP}",
        # start-up: weak long pull-up on st, strong pull-down once n1 is up, small kick device
        f"XMS1 {st} VSS VIN VIN {PH} W=0.42 L=50", f"XMS2 {st} {n1} VSS VSS {NH} W=4 L=0.5",
        f"XMS3 {pgr} {st} VSS VSS {NH} W=0.5 L=2",
        f"XM5 {vref} {pgr} VIN VIN {PH} W={2 * LP} L={LP}", *res("Rref", vref, "VSS", RREF_SEG, RREF_L),
        # error amplifier: tail mirrored from the reference (x4)
        f"XMT {tail} {n1} VSS VSS {NH} W={8 * LN * TAIL_X} L={LN}",
    ]) if REF == "vin" else "\n".join([
        ".subckt ldo VIN VOUT VSS", *boot_ref(p),
        f"XMT {tail} {p}tb VSS VSS {NH} W=8 L=2",
        # start-up: weak pull-down on the pass gate so VOUT can rise before the reference runs
        f"XMSU {g} VIN VSS VSS {NH} W=0.42 L=40",
    ]) if REF == "boot" else "\n".join([
        __import__("bandgap").subckt(), ".subckt ldo VIN VOUT VSS", *bg_ref(p),
        f"XMT {tail} {p}tb VSS VSS {NH} W=8 L=2",
    ])) + "\n" + "\n".join([
        f"XMA {a} {fb} {tail} VSS {NH} W={10 * OTA_L} L={OTA_L}", f"XMB {g} {vref} {tail} VSS {NH} W={10 * OTA_L} L={OTA_L}",
        f"XMC {a} {a} VIN VIN {PH} W={10 * OTA_L} L={OTA_L}", f"XMD {g} {a} VIN VIN {PH} W={10 * OTA_L} L={OTA_L}",
        # pass device, Miller compensation, divider (VOUT = VREF * 1.5), decoupling
        f"XMP VOUT {g} VIN VIN {PH} W={W_PASS} L=0.5 nf={NF_PASS}",
        f"Cc {g} VOUT {C_MILLER}",
        *res("R1", "VOUT", fb, 1, DIV_R1_L), *res("R2", fb, "VSS", 2),
        f"XCdec VSS VOUT VSS VSS sky130_fd_pr__nfet_01v8 W=20 L=20 m={C_DEC_M}",
        ".ends ldo", ""])


def bench(analysis, temp=27, corner="tt", vin=3.3, load="313"):
    return "\n".join([f"* ldo T={temp}", f'.lib "{PDK_LIB}" {corner}', f".temp {temp}", subckt(),
                      f"Vin vin 0 {vin}", "X1 vin vout 0 ldo", f"Rload vout 0 {load}",
                      ".control", analysis, ".endc", ".end", ""])


def dc():
    out = run_netlist(bench("  dc Vin 2.8 3.8 0.05\n  print v(vout) v(x1.ldo_vref)"))
    rows = [l.split() for l in out.splitlines() if l.strip()[:1].isdigit()]
    v = {round(float(r[1]), 3): (float(r[2]), float(r[3])) for r in rows if len(r) >= 4}
    for vin in (2.97, 3.135, 3.3, 3.465, 3.63):
        k = min(v, key=lambda x: abs(x - vin))
        print(f"VIN {k:.2f} V: VOUT {v[k][0]:.4f} V  VREF {v[k][1]:.4f} V")
    return v


if __name__ == "__main__":
    dc()
