"""Assembly C: output network = mixer loads + PA driver with its bias.

  OUTP/OUTN: mixer load resistors (to VDD) and load caps (to VSS); PA coupling caps
  PG/NG    : coupling caps -> 20 kOhm bias resistors -> VB; PA gates
  VB       : 50k/50k divider between VDD and VSS
  PA       : PA1 (RFN, PG, PTAIL), PA2 (RFP, NG, PTAIL); 311-Ohm loads to VDD
  PTAIL    : mirror PAT (x10) from IREF_PA (PAB diode)
Layers: capacitor plates on met4; cross-connections on met3; device bars via
met2 stubs. Different nets only cross on different layers, and no met3/met4
route crosses another net's capacitor plate.
"""
from pathlib import Path

import route as R
from glayout.backend import Component
from glayout.pdk.sky130_mapped import sky130_mapped_pdk as pdk

HERE = Path(__file__).resolve().parent
P = HERE / "work" / "passives"
PINS = ["OUTP", "OUTN", "RFP", "RFN", "IREF_PA", "VDD", "VSS"]


def res_pad(top, x, y, hi):
    """resistor terminal (large met1 pad) up to metal 'hi'."""
    R.box(top, "via1", x, y, 0.15, 0.15)
    R.box(top, "m2", x, y, 0.32, 0.26)
    if hi in ("m3", "m4"):
        R.via2_min(top, x, y)
    if hi == "m4":
        R.via3_min(top, x, y)
        R.box(top, "m3", x, y, 0.5, 0.5)        # met3 min area (0.24 um^2) where nothing else is on met3


def bar_stub(top, x, y, y_to, hi="m3"):
    """minimum via1 on a device bar, met2 stub to y_to, via2 up to met3."""
    R.via1_min(top, x, y)
    R.wire(top, "m2", [(x, y), (x, y_to)])
    R.via2_min(top, x, y_to)
    if hi == "m4":
        R.via3_min(top, x, y_to)


def build(name="out_net"):
    pdk.activate()
    top = Component(f"{name}_hier")
    for f, o in (("c_11", (0, 0)), ("c_11", (0, 16)), ("c_31", (20, 0)), ("c_31", (20, 36)),
                 ("r_load", (-8, 0)), ("r_load", (-8, 16)), ("r_x20k", (56, 4)), ("r_x20k", (56, 40)),
                 ("r_x50k", (62, 4)), ("r_x50k", (68, 4)), ("r_pa", (92, 40)), ("r_pa", (100, 40))):
        R.place(top, P / f"{f}.gds", *o)
    R.place(top, HERE / "pa_pair.gds", 82, 30)
    R.place(top, HERE / "pa_mirror.gds", 82, 5)

    # resistor pad centres (cell pad centres + placement)
    rl_p, rl_n = {"b": (-6.73, 1.65), "t": (-6.73, 9.24)}, {"b": (-6.73, 17.65), "t": (-6.73, 25.24)}
    r20_p, r20_n = {"b": (57.27, 5.65), "t": (57.27, 21.74)}, {"b": (57.27, 41.65), "t": (57.27, 57.74)}
    r50_a, r50_b = {"b": (63.27, 5.65), "t": (63.27, 42.9)}, {"b": (69.27, 5.65), "t": (69.27, 42.9)}
    rpa_p, rpa_n = {"b": (95.43, 41.65), "t": (95.43, 47.94)}, {"b": (103.43, 41.65), "t": (103.43, 47.94)}
    # PA pair (cell at 82,30): PA1 centre x 82.68, PA2 85.05; bars S 35.43, D 35.855, G 24.185
    # mirror (cell at 82,5): PAB centre 82.77 (G 3.685, S 5.93, D 6.365); PAT 85.31 (G -0.815, S 10.43, D 10.855)

    # OUTP / OUTN on met4
    R.wire(top, "m4", [(5.7, 5.7), (-3, 5.7), (-3, 9.24), rl_p["t"]]); res_pad(top, *rl_p["t"], "m4")
    R.wire(top, "m4", [(-3, 5.7), (-3, -3), (35.2, -3), (35.2, 15.2)])
    R.wire(top, "m4", [(5.7, 21.7), (-3, 21.7), (-3, 25.24), rl_n["t"]]); res_pad(top, *rl_n["t"], "m4")
    R.wire(top, "m4", [(-3, 21.7), (-3, 33), (35.2, 33), (35.2, 51.2)])

    # VDD on met3: west spine x=-11, north bus y=70, drops to divider top and PA loads
    for pad in (rl_p["b"], rl_n["b"]):
        res_pad(top, *pad, "m3"); R.wire(top, "m3", [pad, (-11, pad[1])])
    R.wire(top, "m3", [(-11, 1.65), (-11, 70), (103.43, 70)])
    for pad in (r50_a["t"], rpa_p["t"], rpa_n["t"]):
        res_pad(top, *pad, "m3"); R.wire(top, "m3", [(pad[0], 70), pad])

    # VSS: load-cap bottom plates on met4 (x=15.5), then met3 south bus y=-6 east to the
    # divider bottom and the mirror (track y=14 over it)
    R.wire(top, "m4", [(12.9, 5.7), (15.5, 5.7), (15.5, 21.7), (12.9, 21.7)])
    R.via3_min(top, 15.5, 5.7)
    R.wire(top, "m3", [(15.5, 5.7), (15.5, -6), (90, -6), (90, 14), (82.52, 14)])
    res_pad(top, *r50_b["b"], "m3"); R.wire(top, "m3", [(69.27, -6), r50_b["b"]])
    # tie the metal VSS to the substrate: r50k_b guard-ring tap (li, y = 4.0) under the VSS run
    R.mcon_min(top, 69.27, 4.0)
    R.box(top, "via1", 69.27, 4.0, 0.15, 0.15)
    R.box(top, "m2", 69.27, 4.0, 0.32, 0.26)
    R.via2_min(top, 69.27, 4.0)
    bar_stub(top, 82.52, 5.93, 14)              # PAB source
    bar_stub(top, 85.06, 10.43, 14)             # PAT source

    # PG: cap C2 (met4) -> r20k_p bottom; -> PA1 gate (met4 y=18, met3 into the stub)
    R.wire(top, "m4", [(51.9, 15.2), (54.5, 15.2), (54.5, 5.65), r20_p["b"]]); res_pad(top, *r20_p["b"], "m4")
    R.wire(top, "m4", [(54.5, 15.2), (54.5, 18), (78, 18)]); R.via3_min(top, 78, 18)
    R.wire(top, "m3", [(78, 18), (82.68, 18)])
    bar_stub(top, 82.68, 24.185, 18)            # PA1 gate
    # NG: cap C2 (met4) -> r20k_n top; -> PA2 gate (met4 x=76, met3 y=20)
    R.wire(top, "m4", [(51.9, 51.2), (54.5, 51.2), (54.5, 57.74), r20_n["t"]]); res_pad(top, *r20_n["t"], "m4")
    R.wire(top, "m4", [(54.5, 51.2), (76, 51.2), (76, 20)]); R.via3_min(top, 76, 20)
    R.wire(top, "m3", [(76, 20), (85.05, 20)])
    bar_stub(top, 85.05, 24.185, 20)            # PA2 gate

    # VB on met3: spine x=59.5
    for pad in (r20_p["t"], r20_n["b"], r50_a["b"]):
        res_pad(top, *pad, "m3")
    R.wire(top, "m3", [r20_p["t"], (59.5, 21.74)])
    R.wire(top, "m3", [r20_n["b"], (59.5, 41.65), (69.27, 41.65), r50_b["t"]]); res_pad(top, *r50_b["t"], "m3")
    R.wire(top, "m3", [(59.5, 41.65), (59.5, 5.65), r50_a["b"]])

    # PTAIL (met3 y=40): PA1/PA2 sources, PAT drain (jogged east of PA2 on met2)
    bar_stub(top, 82.43, 35.43, 40)
    bar_stub(top, 84.80, 35.43, 40)
    R.via1_min(top, 85.56, 10.855)
    R.wire(top, "m2", [(85.56, 10.855), (86.6, 10.855), (86.6, 40)])
    R.via2_min(top, 86.6, 40)
    R.wire(top, "m3", [(82.43, 40), (86.6, 40)])
    # RFN (met3 y=44) PA1 drain -> r_pa_n bottom; RFP (met3 y=43) PA2 drain -> r_pa_p bottom
    bar_stub(top, 82.93, 35.855, 44)
    R.wire(top, "m3", [(82.93, 44), (103.43, 44), rpa_n["b"]]); res_pad(top, *rpa_n["b"], "m3")
    bar_stub(top, 85.30, 35.855, 43)
    R.wire(top, "m3", [(85.30, 43), (95.43, 43), rpa_p["b"]]); res_pad(top, *rpa_p["b"], "m3")

    # IREF_PA (met3 y=-4): PAB drain+gate, PAT gate
    # PAB drain joins its own gate stub on met2 (same net; two via2 cuts 0.25 um apart
    # would violate via2 spacing)
    R.via1_min(top, 83.02, 6.365)
    R.wire(top, "m2", [(83.02, 6.365), (83.02, 3.685), (82.77, 3.685)])
    bar_stub(top, 82.77, 3.685, -4)
    bar_stub(top, 85.31, -0.815, -4)
    R.wire(top, "m3", [(80, -4), (85.31, -4)])

    for net, layer, xy in (("OUTP", "m4", (-3, -3)), ("OUTN", "m4", (-3, 33)), ("RFP", "m3", (95.43, 43)),
                           ("RFN", "m3", (103.43, 44)), ("IREF_PA", "m3", (80, -4)), ("VDD", "m3", (-11, 70)),
                           ("VSS", "m3", (15.5, -6))):
        R.pin(top, layer, *xy, net)
    return top


def netlist(name="out_net"):
    n = "sky130_fd_pr__nfet_01v8"
    return "\n".join([
        f".subckt {name} OUTP OUTN RFP RFN IREF_PA VDD VSS",
        "XRLp VDD OUTP VSS sky130_fd_pr__res_high_po_1p41 L=5.6 mult=1 m=1",
        "XRLn VDD OUTN VSS sky130_fd_pr__res_high_po_1p41 L=5.6 mult=1 m=1",
        "XCLp OUTP VSS sky130_fd_pr__cap_mim_m3_1 W=11 L=11 MF=1 m=1",
        "XCLn OUTN VSS sky130_fd_pr__cap_mim_m3_1 W=11 L=11 MF=1 m=1",
        "XCcp OUTP PG sky130_fd_pr__cap_mim_m3_1 W=31 L=31 MF=1 m=1",
        "XCcn OUTN NG sky130_fd_pr__cap_mim_m3_1 W=31 L=31 MF=1 m=1",
        "XRbp PG VB VSS sky130_fd_pr__res_xhigh_po_1p41 L=14.1 mult=1 m=1",
        "XRbn NG VB VSS sky130_fd_pr__res_xhigh_po_1p41 L=14.1 mult=1 m=1",
        "XRv1 VDD VB VSS sky130_fd_pr__res_xhigh_po_1p41 L=35.25 mult=1 m=1",
        "XRv2 VB VSS VSS sky130_fd_pr__res_xhigh_po_1p41 L=35.25 mult=1 m=1",
        f"XPA1 RFN PG PTAIL VSS {n} W=10 L=0.15 nf=1 m=1",
        f"XPA2 RFP NG PTAIL VSS {n} W=10 L=0.15 nf=1 m=1",
        "XRPAp VDD RFP VSS sky130_fd_pr__res_high_po_5p73 L=4.3 mult=1 m=1",
        "XRPAn VDD RFN VSS sky130_fd_pr__res_high_po_5p73 L=4.3 mult=1 m=1",
        f"XPAB IREF_PA IREF_PA VSS VSS {n} W=1 L=0.5 nf=1 m=1",
        f"XPAT PTAIL IREF_PA VSS VSS {n} W=10 L=0.5 nf=1 m=1",
        f".ends {name}", ""])


if __name__ == "__main__":
    c = build().flatten()
    c.name = "out_net"
    c.write_gds(str(HERE / "out_net.gds"))
    R.strip_foreign_labels(HERE / "out_net.gds", set(PINS))
    (HERE / "out_net.spice").write_text(netlist())
    print(f"out_net: size {c.xsize:.2f} x {c.ysize:.2f} um")
