"""Layouts: LO input buffer and RF output buffer (see sim/tx_full.py).

out_buf_blk : OFP/OFN source followers (PDP/PDN -> TXP/TXN), OSP/OSN 2 mA sinks,
              OBB bias diode (BOB).
lo_buf_blk  : 2 pF MIM coupling (LO_PAD -> LO_G), 50k/50k divider (VDD/VSS -> LO_G),
              LOF follower (LO_G -> IN), LOS 200 uA sink, LOB bias diode (BLO).
Device bars are reached with minimum via1 cuts; stubs met2, tracks met3; the NMOS
tap ring is tied to VSS where a VSS stub crosses its top bar (centre 7.22).
usage: python buffers.py out|lo
"""
import sys
from pathlib import Path

import route as R
from glayout.backend import Component
from glayout.pdk.sky130_mapped import sky130_mapped_pdk as pdk

HERE = Path(__file__).resolve().parent
P = HERE / "work" / "passives"
RING_TOP = 7.22


def stub(top, x, y_bar, y_to, via2=True):
    R.via1_min(top, x, y_bar)
    R.wire(top, "m2", [(x, y_bar), (x, y_to)])
    if via2:
        R.via2_min(top, x, y_to)


def diode_gate(top, xg, xd, y):
    """diode gate: a met2 jog onto the drain stub (a second parallel stub sat 0.07 um from it)"""
    R.via1_min(top, xg, y)
    R.wire(top, "m2", [(xg, y), (xd, y)])


def track(top, y, xs):
    R.wire(top, "m3", [(min(xs), y), (max(xs), y)])


def out_buf():
    pdk.activate()
    top = Component("out_buf_blk_hier")
    R.place(top, HERE / "out_buf.gds", 0, 0)
    T = {"VDD": 9.5, "TXP": 10.7, "TXN": 11.9, "VSS": 13.1, "BOB": -9.0}
    S_Y, D_Y = 5.43, 5.86
    # followers (4 fingers, bars x 0.215..3.105 and 4.525..7.415)
    stub(top, 0.6, S_Y, T["TXP"]); stub(top, 2.7, D_Y, T["VDD"])
    stub(top, 4.9, S_Y, T["TXN"]); stub(top, 7.0, D_Y, T["VDD"])
    # sinks (2 fingers): S -> VSS, D -> TXP / TXN
    stub(top, 11.7, S_Y, T["VSS"]); stub(top, 12.9, D_Y, T["TXP"])
    stub(top, 15.05, S_Y, T["VSS"]); stub(top, 16.25, D_Y, T["TXN"])
    # bias diode OBB (centre 9.39): S -> VSS (tied to the ring top bar on the way), D+G -> BOB
    stub(top, 9.09, 0.93, T["VSS"]); R.via1_min(top, 9.09, RING_TOP)
    stub(top, 9.69, 1.36, T["BOB"]); diode_gate(top, 9.39, 9.69, -1.315)
    stub(top, 12.1, -5.795, T["BOB"]); stub(top, 15.47, -5.795, T["BOB"])
    # follower gates -> pins below the BOB track
    stub(top, 1.16, -5.795, -10.5, via2=False); stub(top, 5.47, -5.795, -11.5, via2=False)
    track(top, T["VDD"], [2.7, 7.0]); track(top, T["TXP"], [0.6, 12.9]); track(top, T["TXN"], [4.9, 16.25])
    track(top, T["VSS"], [9.09, 11.7, 15.05]); track(top, T["BOB"], [9.69, 12.1, 15.47])
    for net, layer, xy in (("VDD", "m3", (4.0, T["VDD"])), ("TXP", "m3", (6.0, T["TXP"])),
                           ("TXN", "m3", (10.0, T["TXN"])), ("VSS", "m3", (13.0, T["VSS"])),
                           ("BOB", "m3", (11.0, T["BOB"])), ("PDP", "m2", (1.16, -10.5)),
                           ("PDN", "m2", (5.47, -11.5))):
        R.pin(top, layer, *xy, net)
    return top, ["VDD", "TXP", "TXN", "VSS", "BOB", "PDP", "PDN"]


def out_netlist(name="out_buf_blk"):
    n = "sky130_fd_pr__nfet_01v8"
    return "\n".join([f".subckt {name} VDD TXP TXN VSS BOB PDP PDN",
                      f"XOFP VDD PDP TXP VSS {n} W=40 L=0.15 nf=4 m=1",
                      f"XOFN VDD PDN TXN VSS {n} W=40 L=0.15 nf=4 m=1",
                      f"XOBB BOB BOB VSS VSS {n} W=1 L=0.5 nf=1 m=1",
                      f"XOSP TXP BOB VSS VSS {n} W=20 L=0.5 nf=2 m=1",
                      f"XOSN TXN BOB VSS VSS {n} W=20 L=0.5 nf=2 m=1", f".ends {name}", ""])


def lo_buf():
    pdk.activate()
    top = Component("lo_buf_blk_hier")
    R.place(top, HERE / "lo_buf.gds", 0, 0)
    R.place(top, P / "c_31.gds", -45, -15)                 # Clo: C1 top plate (-29.8, 0.2), C2 strap (-13.1, 0.2)
    R.place(top, P / "r_x50k.gds", 12, -50)                # Rlo1: top pad (13.27, -11.1) -> LO_G, bottom -> VDD
    R.place(top, P / "r_x50k.gds", 16, -50)                # Rlo2: top pad (17.27, -11.1) -> LO_G, bottom -> VSS
    T = {"VDD": 9.5, "VSS": 10.7, "IN": 11.9, "LO_G": -9.5, "BLO": -12.5}
    # follower LOF (2 fingers, centre 1.01): S -> IN, D -> VDD, G -> LO_G
    stub(top, 0.5, 5.43, T["IN"]); stub(top, 1.5, 5.86, T["VDD"]); stub(top, 1.01, -5.815, T["LO_G"])
    # LOB diode (centre 3.78): S -> VSS (ring tie), D+G -> BLO;  LOS sink (centre 6.32)
    stub(top, 3.48, 0.93, T["VSS"]); R.via1_min(top, 3.48, RING_TOP)
    stub(top, 4.08, 1.36, T["BLO"]); diode_gate(top, 3.78, 4.08, -1.315)
    stub(top, 6.02, 1.43, T["VSS"]); stub(top, 6.62, 1.86, T["IN"]); stub(top, 6.32, -1.815, T["BLO"])
    track(top, T["IN"], [0.5, 6.62]); track(top, T["BLO"], [4.08, 6.32])
    # LO_G: the met3 track runs onto the cap's met3 bottom plate (C2; the cell's own via3 column
    # already straps it to met4 - an extra via3 there merged with those cuts); divider tops up to it
    for x in (13.27, 17.27):
        R.box(top, "via1", x, -11.1, 0.15, 0.15); R.box(top, "m2", x, -11.1, 0.32, 0.26)
        R.via2_min(top, x, -11.1); R.wire(top, "m3", [(x, -11.1), (x, T["LO_G"])])
    track(top, T["LO_G"], [-13.1, 1.01, 13.27, 17.27])
    # divider bottoms: Rlo1 -> VDD (trunk x=22), Rlo2 -> VSS (trunk x=24)
    for x, net, y_run, xt in ((13.27, "VDD", -51.0, 22.0), (17.27, "VSS", -52.5, 24.0)):
        R.box(top, "via1", x, -48.35, 0.15, 0.15); R.box(top, "m2", x, -48.35, 0.32, 0.26)
        R.wire(top, "m2", [(x, -48.35), (x, y_run)]); R.via2_min(top, x, y_run)
        R.wire(top, "m3", [(x, y_run), (xt, y_run)]); R.via2_min(top, xt, y_run)
        R.wire(top, "m2", [(xt, y_run), (xt, T[net])]); R.via2_min(top, xt, T[net])
    track(top, T["VDD"], [1.5, 22.0]); track(top, T["VSS"], [3.48, 6.02, 24.0])
    for net, layer, xy in (("LO_PAD", "m4", (-29.8, 0.2)), ("IN", "m3", (3.0, T["IN"])),
                           ("VDD", "m3", (10.0, T["VDD"])), ("VSS", "m3", (12.0, T["VSS"])),
                           ("BLO", "m3", (5.0, T["BLO"]))):
        R.pin(top, layer, *xy, net)
    return top, ["LO_PAD", "IN", "VDD", "VSS", "BLO"]


def lo_netlist(name="lo_buf_blk"):
    n = "sky130_fd_pr__nfet_01v8"
    return "\n".join([f".subckt {name} LO_PAD IN VDD VSS BLO",
                      "XClo LO_PAD LO_G sky130_fd_pr__cap_mim_m3_1 W=31 L=31 MF=1 m=1",
                      "XRlo1 LO_G VDD VSS sky130_fd_pr__res_xhigh_po_1p41 L=35.25 mult=1 m=1",
                      "XRlo2 LO_G VSS VSS sky130_fd_pr__res_xhigh_po_1p41 L=35.25 mult=1 m=1",
                      f"XLOF VDD LO_G IN VSS {n} W=20 L=0.15 nf=2 m=1",
                      f"XLOB BLO BLO VSS VSS {n} W=1 L=0.5 nf=1 m=1",
                      f"XLOS IN BLO VSS VSS {n} W=2 L=0.5 nf=1 m=1", f".ends {name}", ""])


if __name__ == "__main__":
    which = sys.argv[1]
    top, pins = (out_buf() if which == "out" else lo_buf())
    name = "out_buf_blk" if which == "out" else "lo_buf_blk"
    c = top.flatten()
    c.name = name
    c.write_gds(str(HERE / f"{name}.gds"))
    R.strip_foreign_labels(HERE / f"{name}.gds", set(pins))
    (HERE / f"{name}.spice").write_text(out_netlist() if which == "out" else lo_netlist())
    print(f"{name}: size {c.xsize:.2f} x {c.ysize:.2f} um")
