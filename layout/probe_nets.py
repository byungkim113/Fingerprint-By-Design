# Metal-only connectivity probe (KLayout batch): which net does each point sit on, using li..met5 and vias only
# (no diffusion/substrate, so a missed tie that the substrate would hide in LVS shows up here).
# usage: klayout -b -r probe_nets.py -rd gds=tx_core.gds
import pya

ly = pya.Layout()
ly.read(gds)
top = ly.top_cell()
l2n = pya.LayoutToNetlist(pya.RecursiveShapeIterator(ly, top, []))
names = [("li", 67, 20), ("mcon", 67, 44), ("m1", 68, 20), ("via1", 68, 44), ("m2", 69, 20), ("via2", 69, 44),
         ("m3", 70, 20), ("via3", 70, 44), ("m4", 71, 20), ("via4", 71, 44), ("m5", 72, 20)]
R = {n: l2n.make_layer(ly.layer(a, b), n) for n, a, b in names}
for n in R:
    l2n.connect(R[n])
seq = ["li", "mcon", "m1", "via1", "m2", "via2", "m3", "via3", "m4", "via4", "m5"]
for a, b in zip(seq, seq[1:]):
    l2n.connect(R[a], R[b])
l2n.extract_netlist()


def net(layer, x, y):
    n = l2n.probe_net(R[layer], pya.DPoint(x, y))
    return n.expanded_name() if n else None


# tx_core points (um). LDO points: middle of its VSS/VOUT/VIN met3 tracks (ldo_blk_tracks.json), shifted by the
# LDO origin computed exactly as in tx_core._ldo_origin (top edge at y=-92, west edge at x=-75), so they follow the
# block when it changes size.
import json
from pathlib import Path
here = Path(gds).resolve().parent
lb = pya.Layout(); lb.read(str(here / "ldo_blk.gds")); bb = lb.top_cell().dbbox()
ox, oy = round(-75.0 - bb.left, 2), round(-92.0 - bb.top, 2)
trk = {(t["net"], t["ch"]): t for t in json.load(open(here / "ldo_blk_tracks.json"))}
def ldo_pt(net, ch):
    t = trk[(net, ch)]
    return ("m3", ox + (t["x0"] + t["x1"]) / 2, oy + t["y"])
spine = net("m5", 100.0, -86.0)
vdd = net("m4", 100.0, 45.0)
pts = {"LDO VSS track TOP0 (m3)": (*ldo_pt("VSS", "TOP0"), "VSS"),
       "LDO VOUT track BOT1 (m3)": (*ldo_pt("VOUT", "BOT1"), "VDD"),
       "LDO VIN track BOT0 (m3)": (*ldo_pt("VIN", "BOT0"), "VIN"),
       "I DAC VSS label (m1)": ("m1", 54.19, -74.32, "VSS"),
       "out_net VSS (m3)": ("m3", 215.5, -36.0, "VSS"),
       "bias VSS (m3)": ("m3", 85.0, -24.3, "VSS")}
print(f"LDO origin ({ox}, {oy})")
print("VSS spine net:", spine, "  core VDD run net:", vdd)
if spine is None or vdd is None or spine == vdd:
    raise RuntimeError("VSS and VDD probes must find two distinct metal nets")
failures = []
for k, (l, x, y, want) in pts.items():
    n = net(l, x, y)
    got = "VSS" if n == spine else ("VDD" if n == vdd else f"other({n})")
    ok = n is not None and (got == want or (want == 'VIN' and n not in (spine, vdd)))
    print(f"{k:<26} -> {got:<12} expected {want}  {'OK' if ok else 'MISMATCH'}")
    if not ok:
        failures.append(k)
if failures:
    raise RuntimeError("metal connectivity probes failed: " + ", ".join(failures))
