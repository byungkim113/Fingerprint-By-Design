"""Layout of the RC-CR LO quadrature network (SKY130).

Devices are drawn by Magic's SKY130 device generator (exact PDK cells used in
sim/tx_full.py): two res_high_po_1p41 (lengths LI, LQ) and two cap_mim_m3_1 (7.8 x 7.8 um).
This script places them and routes on metal 4 so the four nets never cross:
  IN : Ri.R1 (top)    <-> Cq.C2 (bottom plate)  Cq rotated 180 deg: strap on the left, route over the top
  VQ : Rq.R1 (top)    <-> Cq.C1 (top plate)     route right, then up Rq
  VI : Ri.R2 (bottom) <-> Ci.C1 (top plate)     route under the bottom-left
  VSS: Rq.R2 (bottom) <-> Ci.C2 (bottom plate)  route on the right, lower half
Both resistor guard rings (body) are tied to VSS on metal 1.
Run layout/gen_rccr_cells.sh first (Magic) to produce the device GDS.

v2 (2026-10-03): the 0p35 resistors failed rpm.1 (RPM width) -> wide 1p41 resistors of the same
value; Cq's bottom plate (met3, its own parasitic to substrate) moved from the high-impedance VQ
node to the driven IN node; LQ may differ from LI to cancel layout-parasitic quadrature error.
"""
from pathlib import Path

import gdsfactory as gf
from glayout.backend import Component, rectangle
from glayout.pdk.sky130_mapped import sky130_mapped_pdk as pdk
from glayout.primitives.via_gen import via_stack

HERE = Path(__file__).resolve().parent
CELLS = HERE / "work" / "rccr"
WIRE = 0.8                       # metal-4 wire width (um)
# gLayout's sky130 glayer names are shifted by one: "met1" is li1, "met2" is
# metal 1 ... "met5" is metal 4
LI, M1, M4 = "met1", "met2", "met5"

# device-local terminal positions from the generated cells (um): 1p41 resistor met1 pads
# centred at x 1.27, bottom pad y 1.65, top pad y = L + 3.64; body tap (li) at y 0
R_BOT, R_BODY, R_X = 1.65, 0.0, 1.27
C_C1, C_C2, C_Y = 4.1, 9.7, 4.1
C_SIZE = (9.96, 8.2)


def r_top(cell):
    """top terminal (R1 label) of a generated resistor cell."""
    import gdstk
    c = gdstk.read_gds(str(cell)).top_level()[0].copy("flat")
    c.flatten()
    lab = [t for t in c.labels if t.text == "R1"]
    return round(lab[0].origin[1] - 0.91, 3)        # label sits 0.91 um above the pad centre
R_Q_X = 22.0                     # x offset of Rq
C_X, CQ_Y, CI_Y = 6.0, 13.0, -11.0


def wire(top, x0, y0, x1, y1, layer=M4, w=WIRE):
    """axis-aligned wire between two points (inclusive of end caps)."""
    xs, ys = sorted((x0, x1)), sorted((y0, y1))
    r = top << rectangle(layer=pdk.get_glayer(layer),
                         size=(xs[1] - xs[0] + w, ys[1] - ys[0] + w), centered=True)
    r.move((pdk.snap_to_2xgrid((xs[0] + xs[1]) / 2), pdk.snap_to_2xgrid((ys[0] + ys[1]) / 2)))


def via(top, x, y, lo=LI, hi=M4):
    """via stack lo..hi. At resistor terminals start from metal 1: the generated
    resistor already has li1-metal1 contacts there, and a second mcon array on
    top merges into an over-long contact (ct.1_b)."""
    v = top << via_stack(pdk, lo, hi)
    v.move((pdk.snap_to_2xgrid(x), pdk.snap_to_2xgrid(y)))


def label(top, x, y, text, layer=M4):
    lab = rectangle(layer=pdk.get_glayer(f"{layer}_pin"), size=(0.4, 0.4), centered=True).copy()
    lab.add_label(text=text, layer=pdk.get_glayer(f"{layer}_label"))
    r = top << lab
    r.move((x, y))


def build():
    pdk.activate()
    res_i = gf.import_gds(CELLS / "res_i.gds")
    res_q = gf.import_gds(CELLS / "res_q.gds")
    ri_top, rq_top = r_top(CELLS / "res_i.gds"), r_top(CELLS / "res_q.gds")
    cap = gf.import_gds(CELLS / "cap_unit.gds")
    top = Component("rccr_hier")
    top << res_i                                  # Ri at origin
    (top << res_q).movex(R_Q_X)                   # Rq
    cq = top << cap                               # Cq rotated 180 deg into the same box
    cq.rotate(180)
    cq.move((C_X + C_SIZE[0], CQ_Y + C_SIZE[1]))
    (top << cap).move((C_X, CI_Y))                # Ci
    ri, rq = R_X, R_Q_X + R_X
    cq1, cq2, cqy = C_X + C_SIZE[0] - C_C1, C_X + C_SIZE[0] - C_C2, CQ_Y + C_SIZE[1] - C_Y
    ci1, ci2, ciy = C_X + C_C1, C_X + C_C2, CI_Y + C_Y
    y_top, y_bot = max(ri_top, rq_top) + 3.3, CI_Y - 2.0

    # IN: Cq.C2 strap (left) up, left, down to Ri.R1
    wire(top, cq2, cqy, cq2, y_top); wire(top, ri, y_top, cq2, y_top); wire(top, ri, y_top, ri, ri_top)
    via(top, ri, ri_top, M1)
    # VQ: Cq.C1 top plate right, up Rq to Rq.R1
    wire(top, cq1, cqy, rq, cqy); wire(top, rq, cqy, rq, rq_top)
    via(top, rq, rq_top, M1)
    # VI: Ci.C1 down, left, up to Ri.R2
    wire(top, ci1, ciy, ci1, y_bot); wire(top, ri, y_bot, ci1, y_bot); wire(top, ri, y_bot, ri, R_BOT)
    via(top, ri, R_BOT, M1)
    # VSS: Ci.C2 right, up to Rq.R2; Rq body on the same metal-4 wire
    wire(top, ci2, ciy, rq, ciy); wire(top, rq, ciy, rq, R_BOT)
    via(top, rq, R_BOT, M1)
    via(top, rq, R_BODY)
    # the body-tap and R2 stacks are both VSS; their 1.5 um met3 pads sat 0.15 um apart (m3.2): bridge
    wire(top, rq, R_BODY, rq, R_BOT, layer="met4", w=1.5)
    # Ri body to Rq body on metal 1 (passes under the VI metal-4 wire)
    via(top, ri, R_BODY, LI, M1)
    wire(top, ri, R_BODY, rq, R_BODY, layer=M1, w=0.3)

    label(top, ri, y_top, "IN"); label(top, rq, cqy, "VQ")
    label(top, ri, y_bot, "VI"); label(top, rq, ciy, "VSS")
    return top


def lengths():
    import os
    return float(os.environ.get("LI", "25.6")), float(os.environ.get("LQ", "20.3"))


def netlist():
    li, lq = lengths()
    return "\n".join([
        ".subckt rccr IN VI VQ VSS",
        f"XRi IN VI VSS sky130_fd_pr__res_high_po_1p41 L={li} mult=1 m=1",
        "XCi VI VSS sky130_fd_pr__cap_mim_m3_1 W=7.8 L=7.8 MF=1 m=1",
        "XCq VQ IN sky130_fd_pr__cap_mim_m3_1 W=7.8 L=7.8 MF=1 m=1",     # top plate on VQ
        f"XRq VQ VSS VSS sky130_fd_pr__res_high_po_1p41 L={lq} mult=1 m=1",
        ".ends rccr", ""])


if __name__ == "__main__":
    c = build().flatten()
    c.name = "rccr"
    c.write_gds(str(HERE / "rccr.gds"))
    (HERE / "rccr.spice").write_text(netlist())
    print(f"size {c.xsize:.2f} x {c.ysize:.2f} um -> {HERE / 'rccr.gds'}")
    # DRC and LVS: layout/check.sh rccr
