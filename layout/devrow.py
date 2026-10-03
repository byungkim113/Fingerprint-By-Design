"""Generic layout: a row of independent NMOS transistors with one pin per terminal.

Used for blocks whose interconnect is done at the top level (mixer switching
quads, PA differential pair, PA tail mirror). Each device gets pins
<name>_D, <name>_G, <name>_S; bodies tie to a p+ substrate tap ring (VSS pin).
Devices are spaced so no met1 bars merge; all cross-connections are left to the
top-level router on metal 3/4.

usage: python devrow.py <cell>   (cells defined in CELLS)
"""
import sys
from pathlib import Path

from glayout.backend import Component
from glayout.pdk.sky130_mapped import sky130_mapped_pdk as pdk
from glayout.primitives.fet import multiplier, pmos
from glayout.primitives.guardring import tapring
from glayout.util.comp_utils import evaluate_bbox

from dac_array import RING_MARGIN, pin

OUT = Path(__file__).resolve().parent
NF = "sky130_fd_pr__nfet_01v8"
PF = "sky130_fd_pr__pfet_01v8"

# cell name -> list of (device name, W per finger, L[, fingers[, "p"]])
CELLS = {
    "mixer_quad": [("Q1", 4.0, 0.15), ("Q2", 4.0, 0.15), ("Q3", 4.0, 0.15), ("Q4", 4.0, 0.15)],
    "pa_pair": [("PA1", 10.0, 0.15), ("PA2", 10.0, 0.15)],
    "pa_mirror": [("PAB", 1.0, 0.5), ("PAT", 10.0, 0.5)],
    # bias reference (sim/bias_ref.py)
    "bias_n": [("M1", 2.0, 1.0), ("M2", 8.0, 1.0), ("MS2", 1.0, 0.5), ("MS3", 1.0, 0.5)],
    "bias_p": [("M3", 2.0, 1.0, 1, "p"), ("M4", 2.0, 1.0, 1, "p"), ("MS1", 0.42, 10.0, 1, "p"),
               ("MOI", 2.0, 1.0, 1, "p"), ("MOQ", 2.0, 1.0, 1, "p"), ("MOPA", 2.0, 1.0, 10, "p"),
               ("MOLO", 2.0, 1.0, 10, "p"), ("MOOB", 2.0, 1.0, 10, "p")],
    # LO input buffer and output buffer (sim/tx_full.py)
    "lo_buf": [("LOF", 10.0, 0.15, 2), ("LOB", 1.0, 0.5), ("LOS", 2.0, 0.5)],
    "out_buf": [("OFP", 10.0, 0.15, 4), ("OFN", 10.0, 0.15, 4), ("OBB", 1.0, 0.5),
                ("OSP", 10.0, 0.5, 2), ("OSN", 10.0, 0.5, 2)],
}


def spec(d):
    name, w, l = d[:3]
    nf = d[3] if len(d) > 3 else 1
    kind = d[4] if len(d) > 4 else "n"
    return name, w, l, nf, kind


def build(cell):
    pdk.activate()
    top = Component(f"{cell}_hier")
    refs, x = [], 0.0
    devs = [spec(d) for d in CELLS[cell]]
    for name, w, l, nf, kind in devs:
        if kind == "p":                                 # own n-well with n-tap tie ring
            m = pmos(pdk, width=w, length=l, fingers=nf, with_tie=True, with_dummy=False,
                     with_substrate_tap=False)
        else:
            m = multiplier(pdk, "n+s/d", width=w, length=l, fingers=nf, dummy=False)
        bw = evaluate_bbox(m)[0]
        r = top << m
        r.movex(pdk.snap_to_2xgrid(x + bw / 2))
        refs.append((name, kind, r))
        x += bw + (2.0 if kind == "p" else 1.0)         # >= spacing between devices / wells
    if any(k == "n" for _, k, _ in refs):
        w, h = evaluate_bbox(top)
        bb = top.bbox
        ring = top << tapring(pdk, enclosed_rectangle=(pdk.snap_to_2xgrid(w + RING_MARGIN),
                                                       pdk.snap_to_2xgrid(h + RING_MARGIN)),
                              sdlayer="p+s/d", horizontal_glayer="met2", vertical_glayer="met1")
        ring.move((pdk.snap_to_2xgrid((bb[0][0] + bb[1][0]) / 2 - ring.center[0]),
                   pdk.snap_to_2xgrid((bb[0][1] + bb[1][1]) / 2 - ring.center[1])))
        pin(top, ring.ports["S_top_met_S"], "VSS")
    for name, kind, r in refs:
        pin(top, r.ports["drain_N"], f"{name}_D")
        pin(top, r.ports["source_W"], f"{name}_S")
        pin(top, r.ports["gate_S"], f"{name}_G")
        if kind == "p":
            pin(top, r.ports["tie_N_top_met_N"], f"{name}_B")
    return top


def netlist(cell):
    devs = [spec(d) for d in CELLS[cell]]
    has_n = any(k == "n" for *_, k in devs)
    ports = " ".join(f"{n}_D {n}_G {n}_S" + (f" {n}_B" if k == "p" else "") for n, _, _, _, k in devs)
    lines = [f".subckt {cell} {ports}" + (" VSS" if has_n else "")]
    for n, w, l, nf, k in devs:
        model, body = (PF, f"{n}_B") if k == "p" else (NF, "VSS")
        lines.append(f"X{n} {n}_D {n}_G {n}_S {body} {model} W={round(w * nf, 3)} L={l} nf={nf} m=1")
    return "\n".join(lines + [f".ends {cell}", ""])


if __name__ == "__main__":
    cell = sys.argv[1]
    c = build(cell).flatten()
    c.name = cell
    c.write_gds(str(OUT / f"{cell}.gds"))
    (OUT / f"{cell}.spice").write_text(netlist(cell))
    print(f"{cell}: size {c.xsize:.2f} x {c.ysize:.2f} um")
