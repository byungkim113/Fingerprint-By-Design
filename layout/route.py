"""Small routing toolkit for the top-level assemblies (real SKY130 layer numbers).

All shapes are centred on a 0.01 um grid so edges land on the 0.005 um
manufacturing grid. Vias are drawn as minimum cuts with legal enclosures, or as
gLayout via stacks where there is room.
"""
import gdsfactory as gf
from glayout.pdk.sky130_mapped import sky130_mapped_pdk as pdk
from glayout.primitives.via_gen import via_stack

L = {"li": (67, 20), "mcon": (67, 44), "m1": (68, 20), "via1": (68, 44), "m2": (69, 20),
     "via2": (69, 44), "m3": (70, 20), "via3": (70, 44), "m4": (71, 20)}
PINL = {"li": ((67, 16), (67, 5)), "m1": ((68, 16), (68, 5)), "m2": ((69, 16), (69, 5)),
        "m3": ((70, 16), (70, 5)), "m4": ((71, 16), (71, 5))}
WIDTH = {"m1": 0.23, "m2": 0.26, "m3": 0.4, "m4": 0.4}
GL = {"li": "met1", "m1": "met2", "m2": "met3", "m3": "met4", "m4": "met5"}   # gLayout names
ORDER = ["li", "m1", "m2", "m3", "m4"]


def g(v):
    return round(round(v / 0.01) * 0.01, 3)


def box(top, layer, x, y, w, h):
    r = top << gf.components.rectangle(size=(w, h), layer=L[layer] if isinstance(layer, str) else layer)
    r.move((round(g(x) - w / 2, 3), round(g(y) - h / 2, 3)))


def wire(top, layer, pts, w=None):
    """Manhattan polyline on one layer through grid-snapped points."""
    w = w or WIDTH[layer]
    pts = [(g(x), g(y)) for x, y in pts]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if abs(y1 - y0) < 1e-9:
            box(top, layer, (x0 + x1) / 2, y0, round(abs(x1 - x0) + w, 3), w)
        elif abs(x1 - x0) < 1e-9:
            box(top, layer, x0, (y0 + y1) / 2, w, round(abs(y1 - y0) + w, 3))
        else:
            raise ValueError(f"non-Manhattan segment {(x0, y0)}->{(x1, y1)}")


def via1_min(top, x, y):
    """0.15 um via1 that fits inside a 0.29 um met1 device bar; met2 landing pad."""
    box(top, "via1", x, y, 0.15, 0.15)
    box(top, "m2", x, y, 0.32, 0.26)


def mcon_min(top, x, y):
    """li -> met1 on a standard-cell or resistor li terminal."""
    box(top, "mcon", x, y, 0.17, 0.17)
    box(top, "m1", x, y, 0.32, 0.29)


def stack(top, x, y, lo, hi):
    """gLayout via stack from layer lo to layer hi (real names), placed at (x, y)."""
    if ORDER.index(hi) <= ORDER.index(lo):
        return
    v = top << via_stack(pdk, GL[lo], GL[hi])
    v.move((g(x), g(y)))


def pin(top, layer, x, y, text):
    p, t = PINL[layer]
    box(top, p, x, y, 0.26, 0.26)
    top.add_label(text, position=(g(x), g(y)), layer=t)


def place(top, gds_path, dx, dy, cellname=None):
    c = gf.import_gds(gds_path, cellname=cellname) if cellname else gf.import_gds(gds_path)
    return (top << c).move((g(dx), g(dy)))


def strip_foreign_labels(path, keep):
    import gdstk
    lib = gdstk.read_gds(str(path))
    for cell in lib.cells:
        for lab in list(cell.labels):
            if lab.text not in keep:
                cell.remove(lab)
    lib.write_gds(str(path))


def via2_min(top, x, y):
    """0.2 um via2: met2 enclosure 0.04 (0.085 one direction), met3 0.065."""
    box(top, "via2", x, y, 0.2, 0.2)
    box(top, "m2", x, y, 0.37, 0.28)
    box(top, "m3", x, y, 0.33, 0.33)


def via3_min(top, x, y):
    """0.2 um via3: met3 enclosure 0.06 (0.09 one direction), met4 0.065."""
    box(top, "via3", x, y, 0.2, 0.2)
    box(top, "m3", x, y, 0.38, 0.32)
    box(top, "m4", x, y, 0.33, 0.33)
