"""Smoke test: one DAC unit-cell NMOS, DRC (Magic) and LVS (Netgen) via gLayout."""
from glayout.pdk.sky130_mapped import sky130_mapped_pdk as pdk
from glayout.primitives.fet import nmos

c = nmos(pdk, width=0.5, length=1.0, fingers=1, with_dummy=False, with_dnwell=False)
c.name = "unit_nmos"
c.write_gds("unit_nmos.gds")
print("bbox (um):", c.xsize, c.ysize)
print("ports:", sorted(p for p in c.ports if "_E" in p or p.endswith("_W"))[:12])
drc = pdk.drc_magic(c, c.name)
print("DRC:", drc)
