"""Assembly B: LO path = RC-CR quadrature network + two LO limiters.

  IN (external LO) -> RC-CR -> VI -> limiter I (VIN) -> LO_I, LOB_I
                            -> VQ -> limiter Q (VIN) -> LO_Q, LOB_Q
VI/VQ run on metal 4 into each limiter's coupling-cap top plate. The two
limiters' VPWR rails (separate n-wells) are tied by a metal-3 route around the
outside of the blocks; grounds meet through the substrate taps and are also
tied on metal 3.
"""
from pathlib import Path

import route as R
from glayout.backend import Component
from glayout.pdk.sky130_mapped import sky130_mapped_pdk as pdk

HERE = Path(__file__).resolve().parent
LIM_I = (10.0, -60.0)                     # limiter I origin
LIM_Q = (35.3, 15.8)                      # limiter Q origin (VIN lands at y = 17.1)
VIN = (-5.3, 1.3)                         # in the limiter cell
LO_P, LOB_P = (12.17, 1.2), (8.54, 1.2)
PINS = ["IN", "LO_I", "LOB_I", "LO_Q", "LOB_Q", "VDD", "VSS"]


def build(name="lo_path"):
    pdk.activate()
    top = Component(f"{name}_hier")
    R.place(top, HERE / "rccr.gds", 0, 0)
    for o in (LIM_I, LIM_Q):
        R.place(top, HERE / "lo_limiter.gds", *o)

    # VI (rccr bottom-left, met4) down and right into limiter I's cap top plate
    vin_i = (LIM_I[0] + VIN[0], LIM_I[1] + VIN[1])
    R.wire(top, "m4", [(0.74, -13.0), (0.74, vin_i[1]), vin_i])
    # VQ (rccr right, met4) straight across into limiter Q's cap top plate
    vin_q = (LIM_Q[0] + VIN[0], LIM_Q[1] + VIN[1])
    R.wire(top, "m4", [(22.74, 17.1), vin_q])

    # VDD: limiter VPWR rails (met1, y = origin + 2.72) tied on met3 east of everything
    x_e = 54.0
    rails = [(o[0] + 12.4, o[1] + 2.72) for o in (LIM_I, LIM_Q)]
    for x, y in rails:
        R.box(top, "via1", x, y, 0.15, 0.15)
        R.box(top, "m2", x, y, 0.32, 0.26)
        R.via2_min(top, x, y)
        R.wire(top, "m3", [(x, y), (x_e, y)])
    R.wire(top, "m3", [(x_e, rails[0][1]), (x_e, rails[1][1])])
    # VSS: limiter VGND rails (met1, y = origin) on met3 to x_s, vertical on met4;
    # VSS horizontals stop west of the VDD vertical, VDD horizontals cross VSS on another layer
    x_s = 52.0                                    # west of the VDD vertical (x_e = 54)
    gnds = [(o[0] + 12.4, o[1]) for o in (LIM_I, LIM_Q)]
    for x, y in gnds:
        R.box(top, "via1", x, y, 0.15, 0.15)
        R.box(top, "m2", x, y, 0.32, 0.26)
        R.via2_min(top, x, y)
        R.wire(top, "m3", [(x, y), (x_s, y)])
        R.via3_min(top, x_s, y)
    # vertical on met4: on met3 it would cross the VDD route (met3) and short them
    R.wire(top, "m4", [(x_s, gnds[0][1]), (x_s, gnds[1][1])])

    R.pin(top, "m4", 0.74, 23.2, "IN")
    for tag, o in (("I", LIM_I), ("Q", LIM_Q)):
        R.pin(top, "m2", o[0] + LO_P[0], o[1] + LO_P[1], f"LO_{tag}")
        R.pin(top, "m2", o[0] + LOB_P[0], o[1] + LOB_P[1], f"LOB_{tag}")
    R.pin(top, "m3", x_e, rails[1][1], "VDD")
    R.pin(top, "m4", x_s, gnds[1][1], "VSS")
    return top


def netlist(name="lo_path"):
    import limiter
    lim = limiter.netlist().replace(".subckt lo_limiter", ".subckt lo_limiter_sub").replace(
        ".ends lo_limiter", ".ends lo_limiter_sub")
    return "\n".join([
        lim,
        f".subckt {name} IN LO_I LOB_I LO_Q LOB_Q VDD VSS",
        "XRi IN VI VSS sky130_fd_pr__res_high_po_0p35 L=5 mult=1 m=1",
        "XCi VI VSS sky130_fd_pr__cap_mim_m3_1 W=7.8 L=7.8 MF=1 m=1",
        "XCq IN VQ sky130_fd_pr__cap_mim_m3_1 W=7.8 L=7.8 MF=1 m=1",
        "XRq VQ VSS VSS sky130_fd_pr__res_high_po_0p35 L=5 mult=1 m=1",
        "XLI VI LO_I LOB_I VDD VSS lo_limiter_sub",
        "XLQ VQ LO_Q LOB_Q VDD VSS lo_limiter_sub",
        f".ends {name}", ""])


if __name__ == "__main__":
    c = build().flatten()
    c.name = "lo_path"
    c.write_gds(str(HERE / "lo_path.gds"))
    R.strip_foreign_labels(HERE / "lo_path.gds", set(PINS))
    import limiter
    (HERE / "lo_path.spice").write_text(f'.include "{limiter.SC_SPICE}"\n' + netlist())
    print(f"lo_path: size {c.xsize:.2f} x {c.ysize:.2f} um")
