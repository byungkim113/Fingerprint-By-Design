"""Layout: LO limiter (one per channel) = AC-coupling MIM cap + 200 kOhm feedback
resistor + SkyWater standard-cell inverter chain (sky130_fd_sc_hd).

Row:  tap | inv_2 | inv_4 | inv_8 (-> LOB) | inv_8 (-> LO) | tap
  g  = inv_2.A  <- Cc bottom plate, Rfb end R1
  a1 = inv_2.Y  -> inv_4.A, Rfb end R2
Pins: VIN (Cc top plate, met4), LO, LOB (met2), VPWR, VGND (met1 rails).
The feedback resistor's guard ring is a substrate tap, i.e. VGND (LVS confirms).
Device cells come from Magic's generator (work/passives) and the PDK
standard-cell GDS.
"""
from pathlib import Path

import gdsfactory as gf
from glayout.backend import Component
from glayout.pdk.sky130_mapped import sky130_mapped_pdk as pdk
from glayout.primitives.via_gen import via_stack

HERE = Path(__file__).resolve().parent
PASSIVES = HERE / "work" / "passives"
SC_GDS = Path.home() / ".volare/sky130A/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds"
SC_SPICE = Path.home() / ".volare/sky130A/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice"
L = {"li": (67, 20), "mcon": (67, 44), "m1": (68, 20), "via1": (68, 44), "m2": (69, 20),
     "m3": (70, 20), "m4": (71, 20)}
PIN = {"m1": ((68, 16), (68, 5)), "m2": ((69, 16), (69, 5)), "m4": ((71, 16), (71, 5)), "li": ((67, 16), (67, 5))}
PIN_Y = 1.20                                    # A and Y pins of inv_2/4/8 sit at this height
CELLS = [("tap", "tapvpwrvgnd_1", 0.46), ("inv2", "inv_2", 1.38), ("inv4", "inv_4", 2.30),
         ("inv8a", "inv_8", 4.14), ("inv8b", "inv_8", 4.14), ("tap2", "tapvpwrvgnd_1", 0.46)]
PIN_X = {"inv_2": {"A": 0.27, "Y": 0.73}, "inv_4": {"A": 0.30, "Y": 2.04}, "inv_8": {"A": 1.00, "Y": 3.895}}


def centred(top, layer, x, y, w, h):
    xc, yc = round(x / 0.01) * 0.01, round(y / 0.01) * 0.01
    r = top << gf.components.rectangle(size=(w, h), layer=layer)
    r.move((round(xc - w / 2, 3), round(yc - h / 2, 3)))


def span(top, layer, x0, y0, x1, y1, w):
    """straight wire of width w between two points on a 0.01 um grid."""
    x0, y0, x1, y1 = (round(v / 0.01) * 0.01 for v in (x0, y0, x1, y1))
    if abs(y1 - y0) < 1e-9:
        centred(top, layer, (x0 + x1) / 2, y0, round(abs(x1 - x0) + w, 3), w)
    else:
        centred(top, layer, x0, (y0 + y1) / 2, w, round(abs(y1 - y0) + w, 3))


def li_to_m2(top, x, y):
    """stacked mcon + via1 on a standard-cell li pin -> met2 pad."""
    centred(top, L["mcon"], x, y, 0.17, 0.17)
    centred(top, L["m1"], x, y, 0.32, 0.29)
    centred(top, L["via1"], x, y, 0.15, 0.15)
    centred(top, L["m2"], x, y, 0.32, 0.26)


def stack(top, x, y, lo, hi):
    """gLayout via stack between real metals (gLayout names are shifted by one)."""
    v = top << via_stack(pdk, lo, hi)
    v.move((round(x / 0.01) * 0.01, round(y / 0.01) * 0.01))


def label(top, layer, x, y, text):
    p, t = PIN[layer]
    centred(top, p, x, y, 0.26, 0.26)
    top.add_label(text, position=(round(x / 0.01) * 0.01, round(y / 0.01) * 0.01), layer=t)


def build(name="lo_limiter"):
    pdk.activate()
    top = Component(f"{name}_hier")
    x = 0.0
    pos = {}
    for tag, cell, w in CELLS:
        sc = gf.import_gds(SC_GDS, cellname=f"sky130_fd_sc_hd__{cell}")
        (top << sc).movex(round(x, 3))
        pos[tag] = (x, cell)
        x += w
    px = lambda tag, pin: pos[tag][0] + PIN_X[pos[tag][1]][pin]

    # inverter chain on met2 at the pin height
    for a, b in (("inv2", "inv4"), ("inv4", "inv8a"), ("inv8a", "inv8b")):
        xs, xd = px(a, "Y"), px(b, "A")
        li_to_m2(top, xs, PIN_Y)
        li_to_m2(top, xd, PIN_Y)
        span(top, L["m2"], xs, PIN_Y, xd, PIN_Y, 0.26)
    xg, xa1 = px("inv2", "A"), px("inv4", "A")
    li_to_m2(top, xg, PIN_Y)
    li_to_m2(top, px("inv8b", "Y"), PIN_Y)

    # feedback resistor above the row: R1 over g, R2 reached from a1 via a met3 jog
    rfb = gf.import_gds(PASSIVES / "r_x200k.gds")
    y_r = 4.5
    x_r = xg - 1.27                               # R1 at (1.27, 0.74) in the cell
    (top << rfb).move((round(x_r / 0.01) * 0.01, y_r))
    r1 = (x_r + 1.27, y_r + 0.74)
    r2 = (x_r + 6.94, y_r + 0.74)
    # g leaves the crowded inv_2 pins on met2 to the left (a1's pad is only
    # 0.46 um away), then rises on met3 at x_gv
    x_gv = -0.6
    span(top, L["m2"], xg, PIN_Y, x_gv, PIN_Y, 0.26)
    stack(top, x_gv, PIN_Y, "met3", "met4")       # met2 -> met3
    stack(top, *r1, "met2", "met4")               # met1 -> met3 at R1
    span(top, L["m3"], x_gv, PIN_Y, x_gv, r1[1], 0.4)
    span(top, L["m3"], x_gv, r1[1], r1[0], r1[1], 0.4)
    y_jog = 3.6
    stack(top, xa1, PIN_Y, "met3", "met4")
    stack(top, *r2, "met2", "met4")
    span(top, L["m3"], xa1, PIN_Y, xa1, y_jog, 0.4)
    span(top, L["m3"], xa1, y_jog, r2[0], y_jog, 0.4)
    span(top, L["m3"], r2[0], y_jog, r2[0], r2[1], 0.4)

    # coupling cap to the left; its bottom-plate strap C2 (met4) -> g
    cc = gf.import_gds(PASSIVES / "c_3.gds")
    x_c, y_c = -7.0, -0.4
    (top << cc).move((x_c, y_c))
    c1 = (x_c + 1.7, y_c + 1.7)
    c2 = (x_c + 4.9, y_c + 1.7)
    y_g4 = -1.6                                     # met3 run below the row, up to met4 at C2
    stack(top, x_gv, y_g4, "met4", "met5")        # met3 -> met4 (same met3 riser as g)
    span(top, L["m3"], x_gv, PIN_Y, x_gv, y_g4, 0.4)
    span(top, L["m4"], x_gv, y_g4, c2[0], y_g4, 0.4)
    span(top, L["m4"], c2[0], y_g4, c2[0], c2[1], 0.4)

    # pins
    label(top, "m4", *c1, "VIN")
    label(top, "m2", px("inv8b", "Y"), PIN_Y, "LO")
    label(top, "m2", px("inv8a", "Y") + 0.5, PIN_Y, "LOB")
    label(top, "m1", 0.6, 2.72, "VPWR")
    label(top, "m1", 0.6, 0.0, "VGND")
    return top


def netlist(name="lo_limiter"):
    return "\n".join([
        f".subckt {name} VIN LO LOB VPWR VGND",
        "XCc VIN G sky130_fd_pr__cap_mim_m3_1 W=3 L=3 MF=1 m=1",
        "XRfb1 G S1 VGND sky130_fd_pr__res_xhigh_po_1p41 L=35.25 mult=1 m=1",
        "XRfb2 S1 S2 VGND sky130_fd_pr__res_xhigh_po_1p41 L=35.25 mult=1 m=1",
        "XRfb3 S2 S3 VGND sky130_fd_pr__res_xhigh_po_1p41 L=35.25 mult=1 m=1",
        "XRfb4 S3 A1 VGND sky130_fd_pr__res_xhigh_po_1p41 L=35.25 mult=1 m=1",
        "XL1 G VGND VGND VPWR VPWR A1 sky130_fd_sc_hd__inv_2",
        "XL2 A1 VGND VGND VPWR VPWR A2 sky130_fd_sc_hd__inv_4",
        "XL3 A2 VGND VGND VPWR VPWR LOB sky130_fd_sc_hd__inv_8",
        "XL4 LOB VGND VGND VPWR VPWR LO sky130_fd_sc_hd__inv_8",
        f".ends {name}", ""])


OUR_LABELS = {"VIN", "LO", "LOB", "VPWR", "VGND"}


def strip_foreign_labels(path, keep):
    """drop labels other than ours (standard cells carry A/Y/VPB/... labels that
    would otherwise become top-level ports after flattening)."""
    import gdstk
    lib = gdstk.read_gds(str(path))
    for cell in lib.cells:
        for lab in list(cell.labels):
            if lab.text not in keep:
                cell.remove(lab)
    lib.write_gds(str(path))


if __name__ == "__main__":
    c = build().flatten()
    c.name = "lo_limiter"
    c.write_gds(str(HERE / "lo_limiter.gds"))
    strip_foreign_labels(HERE / "lo_limiter.gds", OUR_LABELS)
    (HERE / "lo_limiter.spice").write_text(f'.include "{SC_SPICE}"\n' + netlist())
    print(f"lo_limiter: size {c.xsize:.2f} x {c.ysize:.2f} um")
