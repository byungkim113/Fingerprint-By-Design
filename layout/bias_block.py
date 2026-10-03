"""Layout: on-chip bias reference (beta multiplier + start-up + output mirrors).

  PMOS row (bias_p) at the top: M3, M4, MS1, MOI, MOQ, MOPA, MOLO, MOOB
  NMOS row (bias_n) below it, mirrored so its gates face the PMOS gates: M1, M2, MS2, MS3
  Rs (n-diffusion, 4 x 20 um serpentine) at the bottom.
Channels: VDD track above the PMOS row (sources + well ties), output pins above that;
middle channel (pg, VSS, n1, st) between the gate rows; bottom channel under the
NMOS source/drain bars (VSS, n1, pg, st, nr). Left trunks (met2) join the middle
and bottom copies of n1, pg, st and VSS. Stubs are met2, tracks met3; different
nets only cross met2-over-met3.
Pins: VDD, VSS, BI, BQ, BPA, BLO, BOB.
"""
from pathlib import Path

import route as R
from glayout.backend import Component
from glayout.pdk.sky130_mapped import sky130_mapped_pdk as pdk

HERE = Path(__file__).resolve().parent
YN = -16.0                                  # NMOS row origin (mirrored)
RS_O = (14.0, -60.0)                        # resistor origin
TOP = {"VDD": 4.5, "OUT": 6.0, "n1": 7.5, "pg": 8.5}
MID = {"pg": -4.5, "VSS": -5.6, "n1": -6.7, "st": -7.8}
BOT = {"VSS": -24.0, "n1": -25.2, "pg": -26.4, "st": -27.6, "nr": -28.8}
TRUNK = {"n1": -3.0, "pg": -4.0, "st": -5.0, "VSS": -6.0}
PINS = ["VDD", "VSS", "BI", "BQ", "BPA", "BLO", "BOB"]

# PMOS bars (bias_p cell coords): S centre y, D centre y, G centre y
P1 = dict(S=1.43, D=1.86, G=-1.815)                  # single-finger W2/L1
PM = dict(S=1.43, D=1.86, G=-1.795)                  # 10-finger
PS1 = dict(S=0.64, D=1.07, G=-1.015)                 # MS1 W0.42/L10
TIE_Y = 2.61                                          # centre of the n-tap ring's top met1 bar (2.405..2.815)
# NMOS bars after mirroring about y=0 (bias_n cell coords): S, D, G centre y; device centre x
NM = {"M1": (1.02, -1.43, -1.86, 1.815), "M2": (4.07, -4.43, -4.86, 4.815),
      "MS2": (6.85, -0.93, -1.36, 1.315), "MS3": (9.39, -0.93, -1.36, 1.315)}


def stub(top, x, y_bar, y_to):
    R.via1_min(top, x, y_bar)
    R.wire(top, "m2", [(x, y_bar), (x, y_to)])
    R.via2_min(top, x, y_to)


def build(name="bias_ref"):
    pdk.activate()
    top = Component(f"{name}_hier")
    R.place(top, HERE / "bias_p.gds", 0, 0)
    n = R.place(top, HERE / "bias_n.gds", 0, 0)
    n.mirror_y()                                  # gates up, source/drain bars down
    n.movey(YN)
    R.place(top, HERE / "work" / "passives" / "r_nd80.gds", *RS_O)
    tracks = {}

    def t(group, net, x):
        tracks.setdefault((group, net), []).append(x)

    # ---- PMOS row: sources + well ties -> VDD (up); gates -> middle channel (down)
    pmos_single = {"M3": 2.19, "M4": 8.57, "MOI": 30.34, "MOQ": 36.71}
    for dev, xc in pmos_single.items():
        xs = xc - 0.4
        stub(top, xs, P1["S"], TOP["VDD"]); R.via1_min(top, xs, TIE_Y); t("TOP", "VDD", xs)
        stub(top, xc, P1["G"], MID["pg"]); t("MID", "pg", xc)
    for dev, (xs_lab, xd, xg) in {"MOPA": (42.285, 49.08, 43.08), "MOLO": (60.635, 67.43, 61.43),
                                 "MOOB": (78.985, 85.78, 79.78)}.items():
        xs = xs_lab + 0.4
        stub(top, xs, PM["S"], TOP["VDD"]); R.via1_min(top, xs, TIE_Y); t("TOP", "VDD", xs)
        stub(top, xg, PM["G"], MID["pg"]); t("MID", "pg", xg)
    # MS1: source + tie -> VDD, gate -> VSS (middle), drain -> st (middle)
    # MS1 is smaller, its n-tap ring's top bar sits lower (label 2.03 -> bar centre 1.825); a via at
    # the other devices' TIE_Y missed it and left MS1's n-well floating (LVS caught it)
    stub(top, 14.54, PS1["S"], TOP["VDD"]); R.via1_min(top, 14.54, 2.03 - 0.205); t("TOP", "VDD", 14.54)
    stub(top, 14.95, PS1["G"], MID["VSS"]); t("MID", "VSS", 14.95)
    stub(top, 19.95, PS1["D"], MID["st"]); t("MID", "st", 19.95)
    # drains: outputs up to pins; M3 -> n1, M4 -> pg via the top runs
    outs = {"MOI": (30.74, "BI"), "MOQ": (37.11, "BQ"), "MOPA": (49.08, "BPA"),
            "MOLO": (67.43, "BLO"), "MOOB": (85.78, "BOB")}
    for dev, (xd, pin) in outs.items():
        R.via1_min(top, xd, P1["D"])
        R.wire(top, "m2", [(xd, P1["D"]), (xd, TOP["OUT"])])
        R.pin(top, "m2", xd, TOP["OUT"], pin)
    stub(top, 2.59, P1["D"], TOP["n1"]); t("TOP", "n1", 2.59)
    stub(top, 8.97, P1["D"], TOP["pg"]); t("TOP", "pg", 8.97)

    # ---- NMOS row (mirrored): gates up to the middle channel, S/D down to the bottom channel
    gate_net = {"M1": "n1", "M2": "n1", "MS2": "n1", "MS3": "st"}
    sd = {"M1": ("VSS", "n1"), "M2": ("nr", "pg"), "MS2": ("VSS", "st"), "MS3": ("VSS", "pg")}
    for dev, (xc, ys, yd, yg) in NM.items():
        off = 0.4 if dev in ("M1", "M2") else 0.3       # bar half-width 0.81 (L=1) / 0.56 (L=0.5)
        stub(top, xc, YN + yg, MID[gate_net[dev]]); t("MID", gate_net[dev], xc)
        s_net, d_net = sd[dev]
        stub(top, xc - off, YN + ys, BOT[s_net]); t("BOT", s_net, xc - off)
        stub(top, xc + off, YN + yd, BOT[d_net]); t("BOT", d_net, xc + off)

    # ---- resistor: R1 -> nr, R2 -> VSS; guard-ring tap B -> VSS (ties metal VSS to the substrate)
    # terminals already have met1 pads (y 0.56..0.99): via1 straight onto them (a second mcon
    # there violated mcon spacing); the guard-ring tap B is li only and needs the mcon
    r1 = (RS_O[0] + 1.025, RS_O[1] + 0.775)
    r2 = (RS_O[0] + 4.925, RS_O[1] + 0.775)
    rb = (RS_O[0] + 2.975, RS_O[1] + 0.0)
    for (x, y), net in ((r1, "nr"), (r2, "VSS"), (rb, "VSS")):
        if (x, y) == rb:
            R.mcon_min(top, x, y)
        R.box(top, "via1", x, y, 0.15, 0.15); R.box(top, "m2", x, y, 0.32, 0.26)
        R.wire(top, "m2", [(x, y), (x, BOT[net])])
        R.via2_min(top, x, BOT[net])
        t("BOT", net, x)

    # ---- trunks join middle and bottom copies; n1/pg also take the top runs from M3/M4
    for net, xt in TRUNK.items():
        ys = [MID[net], BOT[net]] + ([TOP[net]] if net in TOP else [])
        R.wire(top, "m2", [(xt, min(ys)), (xt, max(ys))])
        for g, yy in (("MID", MID), ("BOT", BOT), ("TOP", TOP)):
            if net in yy and (g, net) in tracks:
                R.via2_min(top, xt, yy[net]); t(g, net, xt)
    # ---- draw every track as one met3 run across its points
    for (g, net), xs in tracks.items():
        y = {"TOP": TOP, "MID": MID, "BOT": BOT}[g][net]
        R.wire(top, "m3", [(min(xs), y), (max(xs), y)])

    R.pin(top, "m3", 40.0, TOP["VDD"], "VDD")
    R.pin(top, "m3", 0.0, BOT["VSS"], "VSS")
    return top


def netlist(name="bias_ref"):
    n, p = "sky130_fd_pr__nfet_01v8", "sky130_fd_pr__pfet_01v8"
    return "\n".join([
        f".subckt {name} VDD VSS BI BQ BPA BLO BOB",
        f"XM1 N1 N1 VSS VSS {n} W=2 L=1 nf=1 m=1", f"XM2 PG N1 NR VSS {n} W=8 L=1 nf=1 m=1",
        f"XMS2 ST N1 VSS VSS {n} W=1 L=0.5 nf=1 m=1", f"XMS3 PG ST VSS VSS {n} W=1 L=0.5 nf=1 m=1",
        "XRs NR VSS VSS sky130_fd_pr__res_generic_nd W=1 L=80",
        f"XM3 N1 PG VDD VDD {p} W=2 L=1 nf=1 m=1", f"XM4 PG PG VDD VDD {p} W=2 L=1 nf=1 m=1",
        f"XMS1 ST VSS VDD VDD {p} W=0.42 L=10 nf=1 m=1",
        f"XMOI BI PG VDD VDD {p} W=2 L=1 nf=1 m=1", f"XMOQ BQ PG VDD VDD {p} W=2 L=1 nf=1 m=1",
        f"XMOPA BPA PG VDD VDD {p} W=20 L=1 nf=10 m=1", f"XMOLO BLO PG VDD VDD {p} W=20 L=1 nf=10 m=1",
        f"XMOOB BOB PG VDD VDD {p} W=20 L=1 nf=10 m=1",
        f".ends {name}", ""])


if __name__ == "__main__":
    c = build().flatten()
    c.name = "bias_ref"
    c.write_gds(str(HERE / "bias_ref.gds"))
    R.strip_foreign_labels(HERE / "bias_ref.gds", set(PINS))
    (HERE / "bias_ref.spice").write_text(netlist())
    print(f"bias_ref: size {c.xsize:.2f} x {c.ysize:.2f} um")
