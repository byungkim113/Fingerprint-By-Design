"""Layout: one 5-bit unary current-steering DAC WITH data switches (SKY130, gLayout).

Columns of three NMOS (column pitch as in dac_array.py), 31 unit columns + the
diode-connected reference column at the right:
  row 0  U_k  current source  W0.5/L1   (gate bus G, source bus VSS, as dac_array.py)
  row 1  SP_k data switch     W1/L0.15  (drains on bus TP, gate = pin D<k>)
  row 2  SN_k data switch     W1/L0.15  (drains on bus TN, gate = pin DB<k>)
Per column a vertical metal-2 strap joins the SN and SP source bars to the U
drain bar through minimum via1 cuts drawn inside the 0.29 um met1 bars (the
standard 0.43 um gLayout via stack would violate met1 spacing to the drain bar).
Unit k sits at a centre-out column position (gradient spreading).
"""
from pathlib import Path

import gdsfactory as gf
from glayout.backend import Component
from glayout.pdk.sky130_mapped import sky130_mapped_pdk as pdk
from glayout.primitives.fet import multiplier
from glayout.primitives.guardring import tapring
from glayout.routing.c_route import c_route
from glayout.routing.straight_route import straight_route
from glayout.util.comp_utils import evaluate_bbox

from dac_array import N_UNITS, RING_MARGIN, centre_out_positions, pin

W_U, L_U = 0.5, 1.0
W_S, L_S = 1.0, 0.15
OUT = Path(__file__).resolve().parent
VIA1, MET2 = (68, 44), (69, 20)
ROW_GAP = 0.6


def rect(top, layer, x0, y0, x1, y1):
    r = top << gf.components.rectangle(size=(pdk.snap_to_2xgrid(x1 - x0), pdk.snap_to_2xgrid(y1 - y0)), layer=layer)
    r.move((pdk.snap_to_2xgrid(x0), pdk.snap_to_2xgrid(y0)))


def centred(top, layer, x, y, w, h):
    """exact-size rectangle centred on (x, y); the centre is snapped to the 0.01 um
    grid so edges at +-w/2 land on the 0.005 um manufacturing grid. (Snapping each
    corner separately turned 0.15 um cuts into 0.16 um ones.)"""
    xc, yc = round(x / 0.01) * 0.01, round(y / 0.01) * 0.01
    r = top << gf.components.rectangle(size=(w, h), layer=layer)
    r.move((round(xc - w / 2, 3), round(yc - h / 2, 3)))


def via1(top, x, y):
    """0.15 um via1 cut + metal-2 landing pad (met1 is the existing bar)."""
    centred(top, VIA1, x, y, 0.15, 0.15)
    centred(top, MET2, x, y, 0.32, 0.26)


def build():
    pdk.activate()
    u = multiplier(pdk, "n+s/d", width=W_U, length=L_U, fingers=1, dummy=False)
    s = multiplier(pdk, "n+s/d", width=W_S, length=L_S, fingers=1, dummy=False)
    dx = pdk.snap_to_2xgrid(evaluate_bbox(u)[0] + 2 * pdk.get_grule("met1")["min_separation"] + 0.3)
    hu, hs = evaluate_bbox(u)[1], evaluate_bbox(s)[1]
    y1 = pdk.snap_to_2xgrid(hu / 2 + ROW_GAP + hs / 2)        # row centre offsets
    y2 = pdk.snap_to_2xgrid(y1 + hs + ROW_GAP)
    top = Component("dac_sw_array_hier")
    rows = {"U": [], "SP": [], "SN": []}
    for i in range(N_UNITS + 1):
        rows["U"].append((top << u).movex(i * dx))
        if i < N_UNITS:
            rows["SP"].append((top << s).move((i * dx, y1)))
            rows["SN"].append((top << s).move((i * dx, y2)))
    U, SP, SN = rows["U"], rows["SP"], rows["SN"]
    ref = U[-1]

    # current-source row: buses as in dac_array.py
    top << straight_route(pdk, U[0].ports["source_W"], U[-1].ports["source_E"])
    top << straight_route(pdk, U[0].ports["gate_W"], U[-1].ports["gate_E"])
    top << straight_route(pdk, U[0].ports["plusdoped_W"], U[-1].ports["plusdoped_E"])
    top << c_route(pdk, ref.ports["drain_E"], ref.ports["gate_E"], extension=3 * pdk.util_max_metal_seperation())
    # switch rows: drain buses TP / TN, merged implants; gates stay separate
    for R in (SP, SN):
        top << straight_route(pdk, R[0].ports["drain_W"], R[-1].ports["drain_E"])
        top << straight_route(pdk, R[0].ports["plusdoped_W"], R[-1].ports["plusdoped_E"])

    # per-column vertical metal-2 strap: SN source -> SP source -> U drain
    for i in range(N_UNITS):
        x = U[i].ports["drain_N"].center[0] + 0.3
        ys = [SN[i].ports["source_N"].center[1] - 0.145, SP[i].ports["source_N"].center[1] - 0.145,
              U[i].ports["drain_N"].center[1] - 0.145]
        for y in ys:
            via1(top, x, y)
        centred(top, MET2, x, (ys[0] + ys[-1]) / 2, 0.32, round(round(ys[0] / 0.01) * 0.01 - round(ys[-1] / 0.01) * 0.01 + 0.26, 3))

    w, h = evaluate_bbox(top)
    bb = top.bbox
    ew, eh = (pdk.snap_to_2xgrid(d + RING_MARGIN) for d in (w, h))
    ring = top << tapring(pdk, enclosed_rectangle=(ew, eh), sdlayer="p+s/d",
                          horizontal_glayer="met2", vertical_glayer="met1")
    ring.move((pdk.snap_to_2xgrid((bb[0][0] + bb[1][0]) / 2 - ring.center[0]),
               pdk.snap_to_2xgrid((bb[0][1] + bb[1][1]) / 2 - ring.center[1])))
    top << straight_route(pdk, U[0].ports["source_W"], ring.ports["W_top_met_E"], glayer2="met1")

    pos = centre_out_positions(N_UNITS)
    for k in range(N_UNITS):
        pin(top, SP[pos[k]].ports["gate_S"], f"D{k}")
        pin(top, SN[pos[k]].ports["gate_S"], f"DB{k}")
    pin(top, SP[0].ports["drain_W"], "TP")
    pin(top, SN[0].ports["drain_W"], "TN")
    pin(top, U[0].ports["gate_W"], "G")
    pin(top, U[0].ports["source_W"], "VSS")
    return top


def netlist():
    ports = " ".join(f"D{k} DB{k}" for k in range(N_UNITS)) + " TP TN G VSS"
    n = "sky130_fd_pr__nfet_01v8"
    lines = [f".subckt dac_sw_array {ports}", f"XR G G VSS VSS {n} W={W_U} L={L_U} nf=1 m=1"]
    for k in range(N_UNITS):
        lines += [f"XU{k} N{k} G VSS VSS {n} W={W_U} L={L_U} nf=1 m=1",
                  f"XSP{k} TP D{k} N{k} VSS {n} W={W_S} L={L_S} nf=1 m=1",
                  f"XSN{k} TN DB{k} N{k} VSS {n} W={W_S} L={L_S} nf=1 m=1"]
    return "\n".join(lines + [".ends dac_sw_array", ""])


if __name__ == "__main__":
    c = build().flatten()
    c.name = "dac_sw_array"
    c.write_gds(str(OUT / "dac_sw_array.gds"))
    (OUT / "dac_sw_array.spice").write_text(netlist())
    print(f"size {c.xsize:.2f} x {c.ysize:.2f} um -> {OUT / 'dac_sw_array.gds'}")
