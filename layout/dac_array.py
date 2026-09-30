"""Layout of one 5-bit unary DAC current-source array (SKY130, gLayout).

Row of 32 NMOS (W=0.5 um, L=1 um): 31 unit current sources + 1 diode-connected
reference at the right end. Unit k sits at a centre-out position so adjacent
thermometer codes are not clustered (1-D gradient spreading). Shared nets:
  G   : gate bus (met1) across the row; reference drain tied to it by a C-route
  VSS : source bus (met1) across the row, tied to a p+ substrate tap ring
  D<k>: one pin per unit drain (no bus)
Outputs dac_array.gds and dac_array.spice (LVS reference), then runs Magic DRC
and Netgen LVS through gLayout.
"""
from pathlib import Path

from glayout.backend import Component, rectangle
from glayout.pdk.sky130_mapped import sky130_mapped_pdk as pdk
from glayout.primitives.fet import multiplier
from glayout.primitives.guardring import tapring
from glayout.routing.c_route import c_route
from glayout.routing.straight_route import straight_route
from glayout.util.comp_utils import align_comp_to_port, evaluate_bbox

N_UNITS = 31
RING_MARGIN = 2.0         # um of clearance between the array and the tap ring
W, L = 0.5, 1.0
OUT = Path(__file__).resolve().parent


def centre_out_positions(n):
    """unit k -> row position; k=0 at centre, then alternating outward."""
    c = (n - 1) // 2
    order = [c]
    for d in range(1, n):
        for p in (c - d, c + d):
            if 0 <= p < n and len(order) < n:
                order.append(p)
    return order


def pin(comp, port, name):
    # gLayout's sky130 glayer names are shifted (its "met1" is li1, "met2" is
    # metal 1), so take the pin layer from the port being labelled
    layer = pdk.layer_to_glayer(port.layer)
    lab = rectangle(layer=pdk.get_glayer(f"{layer}_pin"), size=(0.27, 0.27), centered=True).copy()
    lab.add_label(text=name, layer=pdk.get_glayer(f"{layer}_label"))
    comp.add(align_comp_to_port(lab, port, alignment=("c", "c")))


def build():
    pdk.activate()
    dev = multiplier(pdk, "n+s/d", width=W, length=L, fingers=1, dummy=False)
    dx = pdk.snap_to_2xgrid(evaluate_bbox(dev)[0] + 2 * pdk.get_grule("met1")["min_separation"] + 0.3)
    top = Component("dac_array_hier")
    pos = centre_out_positions(N_UNITS)
    refs = []
    for i in range(N_UNITS + 1):                       # position 31 = reference
        r = top << dev
        r.movex(i * dx)
        refs.append(r)
    ref = refs[-1]

    # shared buses: straight met1 lines through every device's source / gate bar
    src = top << straight_route(pdk, refs[0].ports["source_W"], refs[-1].ports["source_E"])
    gate = top << straight_route(pdk, refs[0].ports["gate_W"], refs[-1].ports["gate_E"])
    # merge the n+ implant of the row
    top << straight_route(pdk, refs[0].ports["plusdoped_W"], refs[-1].ports["plusdoped_E"])
    # diode connection of the reference: drain -> gate on its east side
    top << c_route(pdk, ref.ports["drain_E"], ref.ports["gate_E"],
                   extension=3 * pdk.util_max_metal_seperation())

    # substrate tap ring around everything, source bus tied to its west side
    w, h = evaluate_bbox(top)
    bb = top.bbox                                   # before the ring is added
    ew, eh = (pdk.snap_to_2xgrid(d + RING_MARGIN) for d in (w, h))
    ring = top << tapring(pdk, enclosed_rectangle=(ew, eh), sdlayer="p+s/d",
                          horizontal_glayer="met2", vertical_glayer="met1")
    # centre on the array, snapped to the manufacturing grid (off-grid moves
    # split tap contacts and trip licon.1/licon.2)
    ring.move((pdk.snap_to_2xgrid((bb[0][0] + bb[1][0]) / 2 - ring.center[0]),
               pdk.snap_to_2xgrid((bb[0][1] + bb[1][1]) / 2 - ring.center[1])))
    top << straight_route(pdk, refs[0].ports["source_W"], ring.ports["W_top_met_E"], glayer2="met1")

    # pins
    for k in range(N_UNITS):
        pin(top, refs[pos[k]].ports["drain_N"], f"D{k}")
    pin(top, refs[0].ports["gate_W"], "G")
    pin(top, refs[0].ports["source_W"], "VSS")
    return top


def netlist():
    ports = " ".join(f"D{k}" for k in range(N_UNITS)) + " G VSS"
    lines = [f".subckt dac_array {ports}",
             f"XR G G VSS VSS sky130_fd_pr__nfet_01v8 W={W} L={L} nf=1 m=1"]
    lines += [f"XU{k} D{k} G VSS VSS sky130_fd_pr__nfet_01v8 W={W} L={L} nf=1 m=1"
              for k in range(N_UNITS)]
    return "\n".join(lines + [".ends dac_array", ""])


if __name__ == "__main__":
    c = build().flatten()
    c.name = "dac_array"                 # flatten() renames the cell
    gds = OUT / "dac_array.gds"
    c.write_gds(str(gds))
    (OUT / "dac_array.spice").write_text(netlist())
    print(f"size {c.xsize:.2f} x {c.ysize:.2f} um  -> {gds}")
    # DRC and LVS: layout/check.sh dac_array
