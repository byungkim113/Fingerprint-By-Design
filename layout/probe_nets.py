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


# tx_core points (um); LDO tracks from ldo_blk_tracks.json + LDO_O (-39.39, -317.43)
spine = net("m5", 100.0, -86.0)
vdd = net("m4", 100.0, 45.0)
pts = {"LDO VSS track TOP0 (m3)": ("m3", 61.0, -254.52, "VSS"),
       "LDO VOUT track BOT1 (m3)": ("m3", 120.0, -221.32, "VDD"),
       "LDO VIN track BOT0 (m3)": ("m3", 150.0, -303.23, "VIN"),
       "I DAC VSS label (m1)": ("m1", 54.19, -74.32, "VSS"),
       "out_net VSS (m3)": ("m3", 215.5, -36.0, "VSS"),
       "bias VSS (m3)": ("m3", 85.0, -24.3, "VSS")}
print("VSS spine net:", spine, "  core VDD run net:", vdd)
for k, (l, x, y, want) in pts.items():
    n = net(l, x, y)
    got = "VSS" if n == spine else ("VDD" if n == vdd else f"other({n})")
    print(f"{k:<26} -> {got:<12} expected {want}  {'OK' if (got == want or (want == 'VIN' and got.startswith('other'))) else 'MISMATCH'}")
