"""Layout: on-chip LDO (bandgap + error amplifier + 5 V pass device + divider + decoupling), sim/ldo.py.

Devices are Magic-generated SKY130 cells (layout/work/ldo_cells, genall.tcl) with labelled ports.
One device row; a TOP channel (gates, resistor R1 ends, PNP bases, MIM top plates) and a BOTTOM channel
(sources/drains, emitters, R2 ends, MIM bottom straps, PMOS bulk). Stubs are met2 from a via on each
terminal (mcon added where the terminal is li only), tracks are met3 (one per net per channel), and nets
used in both channels are joined by met2 trunks west of the row. MIM terminals use met4 stubs + via3.
NMOS / PNP-collector / resistor bodies are the p-substrate (VSS, tied by the decap's ring contact).
Pins: VIN, VOUT, VSS.
"""
import re
from pathlib import Path

import gdstk
import route as R
from glayout.backend import Component
from glayout.pdk.sky130_mapped import sky130_mapped_pdk as pdk

HERE = Path(__file__).resolve().parent
CELLS = HERE / "work" / "ldo_cells"
GAP = 4.0                     # between device bounding boxes (HV n-well spacing margin)
PITCH = 1.2                   # track pitch
TOPROLE = {"G", "R1", "C1", "Base"}
BOTROLE = {"S", "D", "Emitter", "R2", "C2", "B"}

P5, N5 = "pfet_g5v0d10v5", "nfet_g5v0d10v5"
# (instance, cell, {role: net}); MOS roles S/D/G/B, PNP Emitter/Base, resistor R1/R2, MIM C1/C2
DEVICES = (
    [(f"Q1_{i}", "pnp1", {"Emitter": "bg_a", "Base": "VSS"}) for i in range(2)]
    + [(f"Q2_{i}", "pnp1", {"Emitter": "bg_bq", "Base": "VSS"}) for i in range(16)]
    + [(f"Q3_{i}", "pnp1", {"Emitter": "bg_q3e", "Base": "VSS"}) for i in range(2)]
    + [("R10", "xh_8", {"R1": "bg_b", "R2": "bg_bq"}),
       ("R20", "xh_39", {"R1": "ldo_vref", "R2": "bg_r2m"}), ("R21", "xh_39", {"R1": "bg_r2m", "R2": "bg_q3e"}),
       ("MA", "p5_16_32", {"D": "bg_a", "G": "ldo_pb", "S": "VIN", "B": "VIN"}),
       ("MB", "p5_16_32", {"D": "bg_b", "G": "ldo_pb", "S": "VIN", "B": "VIN"}),
       ("MO", "p5_16_32", {"D": "ldo_vref", "G": "ldo_pb", "S": "VIN", "B": "VIN"}),
       ("MTB", "p5_16_32", {"D": "bg_tl", "G": "ldo_pb", "S": "VIN", "B": "VIN"}),
       ("M6", "p5_16_32", {"D": "ldo_pb", "G": "ldo_pb", "S": "VIN", "B": "VIN"}),
       ("M1", "p5_8_16", {"D": "bg_oa", "G": "bg_a", "S": "bg_tl", "B": "VIN"}),
       ("M2", "p5_8_16", {"D": "bg_ob", "G": "bg_b", "S": "bg_tl", "B": "VIN"}),
       ("MS1", "p5_ms1", {"D": "bg_st", "G": "VSS", "S": "VIN", "B": "VIN"}),
       ("M3", "n5_16_32", {"D": "bg_oa", "G": "bg_oa", "S": "VSS"}),
       ("M4", "n5_16_32", {"D": "bg_ob", "G": "bg_oa", "S": "VSS"}),
       ("M5", "n5_16_32", {"D": "ldo_pb", "G": "bg_ob", "S": "VSS"}),
       ("MS3", "n5_4_05", {"D": "bg_st", "G": "ldo_vref", "S": "VSS"}),
       ("MS2", "n5_05_4", {"D": "ldo_pb", "G": "bg_st", "S": "VSS"}),
       ("CCB", "mim22", {"C1": "ldo_pb", "C2": "bg_ob"}),
       ("MTP", "p5_4_8", {"D": "ldo_tb", "G": "ldo_pb", "S": "VIN", "B": "VIN"}),
       ("MC", "p5_20_2", {"D": "ldo_a", "G": "ldo_a", "S": "VIN", "B": "VIN"}),
       ("MD", "p5_20_2", {"D": "ldo_g", "G": "ldo_a", "S": "VIN", "B": "VIN"}),
       ("MP", "p5_pass", {"D": "VOUT", "G": "ldo_g", "S": "VIN", "B": "VIN"}),
       ("MTN", "n5_4_2", {"D": "ldo_tb", "G": "ldo_tb", "S": "VSS"}),
       ("MT", "n5_8_2", {"D": "ldo_tail", "G": "ldo_tb", "S": "VSS"}),
       ("MAO", "n5_20_2", {"D": "ldo_a", "G": "ldo_fb", "S": "ldo_tail"}),
       ("MBO", "n5_20_2", {"D": "ldo_g", "G": "ldo_vss_ref", "S": "ldo_tail"}),   # OTA sees the soft-started ref
       ("CCL", "mim22", {"C1": "ldo_g", "C2": "VOUT"}),
       # start-up guard (2026-10-12): holds the pass gate at VIN until VREF is up
       ("GRP", "p5_g_042_20", {"D": "ldo_x", "G": "VSS", "S": "VIN", "B": "VIN"}),
       ("GRN", "n5_g_2_1", {"D": "ldo_x", "G": "ldo_vref", "S": "VSS"}),
       ("GIP", "p5_g_2_05", {"D": "ldo_y", "G": "ldo_x", "S": "VIN", "B": "VIN"}),
       ("GIN", "n5_g_1_05", {"D": "ldo_y", "G": "ldo_x", "S": "VSS"}),
       ("GSW", "p5_g_sw", {"D": "ldo_g", "G": "ldo_y", "S": "VIN", "B": "VIN"}),
       ("GCX", "mim10", {"C1": "ldo_x", "C2": "VIN"}), ("GCY", "mim10", {"C1": "ldo_y", "C2": "VSS"}),
       # soft-start: 10 x 50k between VREF and the OTA input, 70x70 um MIM to VSS
       *[(f"RSS{i}", "xh_3525", {"R1": "ldo_vref" if i == 0 else f"ldo_ss{i}", "R2": "ldo_vss_ref" if i == 9 else f"ldo_ss{i + 1}"})
         for i in range(10)],
       ("CSS", "mim70", {"C1": "ldo_vss_ref", "C2": "VSS"}),
       ("RD1", "xh_341", {"R1": "VOUT", "R2": "ldo_fb"}),
       ("RD2", "xh_3525", {"R1": "ldo_fb", "R2": "ldo_r2m"}), ("RD3", "xh_3525", {"R1": "ldo_r2m", "R2": "VSS"})]
    + [(f"CD{i}", "n18_dec", {"G": "VOUT", "S": "VSS", "D": "VSS", **({"B": "VSS"} if i == 0 else {})})
       for i in range(15)])


def cell_info(name):
    """bbox and labelled terminals (role, x, y, has_m1, layer) of a generated cell."""
    c = gdstk.read_gds(str(CELLS / f"{name}.gds")).top_level()[0].copy("flat")
    c.flatten()
    (x0, y0), (x1, y1) = c.bounding_box()
    m1 = [p for p in c.polygons if (p.layer, p.datatype) == (68, 20)]
    terms = []
    for t in c.labels:
        # finger-numbered MOS labels (D0, S1, G2 ...) -> role; resistor/MIM terminal names keep their digit
        role = t.text if t.text in ("R1", "R2", "C1", "C2") else re.sub(r"\d+$", "", t.text)
        x, y = t.origin
        terms.append((role, x, y, any(p.contain((x, y)) for p in m1), t.layer))
    # multi-finger MOS: the generator labels only some S/D strips; take every tall m1 strip and give the
    # unlabelled ones the role that alternates with their labelled neighbours (S D S D ...)
    sd = [t for t in terms if t[0] in ("S", "D")]
    if sd:
        strips = sorted([p for p in m1 if (p.bounding_box()[1][1] - p.bounding_box()[0][1]) > 0.5 * (y1 - y0)
                         and (p.bounding_box()[1][0] - p.bounding_box()[0][0]) < 0.5], key=lambda p: p.bounding_box()[0][0])
        role_of = {}
        for i, p in enumerate(strips):
            for t in sd:
                if p.contain((t[1], t[2])):
                    role_of[i] = t[0]
        if role_of and len(role_of) < len(strips):
            i0, r0 = next(iter(role_of.items()))
            ymid = sd[0][2]
            for i, p in enumerate(strips):
                if i not in role_of:
                    role = r0 if (i - i0) % 2 == 0 else ("D" if r0 == "S" else "S")
                    (sx0, _), (sx1, _) = p.bounding_box()
                    terms.append((role, (sx0 + sx1) / 2, ymid, True, 67))
    return (x0, y0, x1, y1), terms


N_ROWS = 3


def build(name="ldo_blk"):
    """devices in N_ROWS rows (split by cumulative width); per row a TOP and a BOT channel; nets used in
    more than one channel are joined by met4 trunks west of the rows (met4 only crosses met3 tracks)."""
    pdk.activate()
    top = Component(f"{name}_hier")
    info = [(inst, cell, nets, *cell_info(cell)) for inst, cell, nets in DEVICES]
    widths = [bb[2] - bb[0] + GAP for *_, bb, _ in info]
    target = sum(widths) / N_ROWS
    rows, cur, acc = [], [], 0.0
    for it, w in zip(info, widths):
        if acc + w > target * 1.02 and cur and len(rows) < N_ROWS - 1:
            rows.append(cur); cur, acc = [], 0.0
        cur.append(it); acc += w
    rows.append(cur)
    ytrk, xs, y_base, trunk_pts = {}, {}, 0.0, {}
    for r, row in enumerate(rows):
        # terminal points of this row (device-local), nets per channel
        local, x = [], 0.0
        for inst, cell, nets, (x0, y0, x1, y1), terms in row:
            local.append((inst, cell, nets, x - x0, -y0, (x, 0.0, x + x1 - x0, y1 - y0), terms))
            x += x1 - x0 + GAP
        h = max(b[3] for *_, b, _ in local)
        chans = {"TOP": set(), "BOT": set()}
        for inst, cell, nets, dx, dy, bb, terms in local:
            for role, *_ in terms:
                if role in nets:
                    chans["TOP" if role in TOPROLE else "BOT"].add(nets[role])
        nb, nt = sorted(chans["BOT"]), sorted(chans["TOP"])
        y_dev = y_base + 2.0 + len(nb) * PITCH + 1.0               # device row origin
        for i, n in enumerate(nb):
            ytrk[(n, f"BOT{r}")] = y_dev - 2.0 - i * PITCH
        for i, n in enumerate(nt):
            ytrk[(n, f"TOP{r}")] = y_dev + h + 2.0 + i * PITCH
        for inst, cell, nets, dx, dy, bb, terms in local:
            R.place(top, CELLS / f"{cell}.gds", dx, dy + y_dev)
            for role, tx, ty, has_m1, layer in terms:
                if role not in nets:
                    continue
                net = nets[role]
                key = (net, ("TOP" if role in TOPROLE else "BOT") + str(r))
                yt = ytrk[key]
                px, py = tx + dx, ty + dy + y_dev
                if role == "B":                              # ring contact at the ring's east end, away from fingers
                    px = bb[2] - 0.6
                if layer == 71:                              # MIM terminal on met4
                    R.wire(top, "m4", [(px, py), (px, yt)]); R.via3_min(top, px, yt)
                else:
                    if not has_m1:
                        R.mcon_min(top, px, py)
                    R.box(top, "m1", px, py, 0.32, 0.32)    # generated S/D strips are 0.23 wide: via1 needs 0.085 one way
                    R.via1_min(top, px, py)
                    R.wire(top, "m2", [(px, py), (px, yt)])
                    # a same-net via2 within 0.45 um would merge into one oversized cut (via2.1a): share it
                    if all(abs(px - q) > 0.45 for q in xs.get(key, [])):
                        R.via2_min(top, px, yt)
                xs.setdefault(key, []).append(px)
        y_base = y_dev + h + 2.0 + len(nt) * PITCH + 1.0
    # met4 trunks west of the rows for nets that appear in more than one channel
    by_net = {}
    for (net, ch) in ytrk:
        by_net.setdefault(net, []).append(ch)
    multi = sorted(n for n, chs in by_net.items() if len(chs) > 1)
    for k, net in enumerate(multi):
        xt = -3.0 - k * 1.2
        ys = [ytrk[(net, ch)] for ch in by_net[net]]
        R.wire(top, "m4", [(xt, min(ys)), (xt, max(ys))])
        for ch in by_net[net]:
            R.via3_min(top, xt, ytrk[(net, ch)])
            xs[(net, ch)].append(xt)
    for key, xl in xs.items():
        R.wire(top, "m3", [(min(xl), ytrk[key]), (max(xl), ytrk[key])])
        if max(xl) - min(xl) < 0.6:                         # met3 min area only where the track is short
            R.box(top, "m3", (min(xl) + max(xl)) / 2, ytrk[key], 0.6, 0.4)
    for net in ("VIN", "VOUT", "VSS"):
        key = min((k for k in xs if k[0] == net), key=lambda k: ytrk[k])
        R.pin(top, "m3", min(xs[key]), ytrk[key], net)
    # track geometry for the top-level integration (tx_core.py)
    import json
    (HERE / "ldo_blk_tracks.json").write_text(json.dumps(
        [dict(net=n, ch=c, y=ytrk[(n, c)], x0=min(xs[(n, c)]), x1=max(xs[(n, c)])) for (n, c) in xs], indent=1))
    return top


def netlist(name="ldo_blk"):
    """flat LVS netlist of the laid-out LDO (sim/ldo.py with MIM compensation caps)."""
    p5, n5, pnp = "sky130_fd_pr__pfet_g5v0d10v5", "sky130_fd_pr__nfet_g5v0d10v5", "sky130_fd_pr__pnp_05v5_W3p40L3p40"
    xh = "sky130_fd_pr__res_xhigh_po_1p41"
    size = {"p5_16_32": (16, 32, 1), "p5_8_16": (8, 16, 1), "p5_ms1": (0.42, 50, 1), "p5_4_8": (4, 8, 1),
            "p5_20_2": (20, 2, 1), "p5_pass": (200, 0.5, 20), "n5_16_32": (16, 32, 1), "n5_4_05": (4, 0.5, 1),
            "p5_g_042_20": (0.42, 20, 1), "n5_g_2_1": (2, 1, 1), "p5_g_2_05": (2, 0.5, 1), "n5_g_1_05": (1, 0.5, 1),
            "p5_g_sw": (40, 0.5, 4),
            "n5_05_4": (0.5, 4, 1), "n5_4_2": (4, 2, 1), "n5_8_2": (8, 2, 1), "n5_20_2": (20, 2, 1)}
    rl = {"xh_8": 8, "xh_39": 39, "xh_341": 34.1, "xh_3525": 35.25}
    lines = [f".subckt {name} VIN VOUT VSS"]
    for inst, cell, nets in DEVICES:
        if cell in size:
            w, l, nf = size[cell]
            model = p5 if cell.startswith("p5") else n5
            lines.append(f"X{inst} {nets['D']} {nets['G']} {nets['S']} {nets.get('B', 'VSS') if cell.startswith('p5') else 'VSS'} "
                         f"{model} W={w} L={l} nf={nf} m=1")
        elif cell == "pnp1":
            lines.append(f"X{inst} VSS VSS {nets['Emitter']} {pnp} m=1")
        elif cell in rl:
            lines.append(f"X{inst} {nets['R1']} {nets['R2']} VSS {xh} L={rl[cell]} mult=1 m=1")
        elif cell.startswith("mim"):
            sz = int(cell[3:])
            lines.append(f"X{inst} {nets['C1']} {nets['C2']} sky130_fd_pr__cap_mim_m3_1 W={sz} L={sz} MF=1 m=1")
        elif cell == "n18_dec":
            lines.append(f"X{inst} VSS VOUT VSS VSS sky130_fd_pr__nfet_01v8 W=20 L=20 nf=1 m=1")
    return "\n".join(lines + [f".ends {name}", ""])


if __name__ == "__main__":
    c = build().flatten()
    c.name = "ldo_blk"
    c.write_gds(str(HERE / "ldo_blk.gds"))
    R.strip_foreign_labels(HERE / "ldo_blk.gds", {"VIN", "VOUT", "VSS"})
    (HERE / "ldo_blk.spice").write_text(netlist())
    print(f"ldo_blk: size {c.xsize:.2f} x {c.ysize:.2f} um, {len(DEVICES)} devices")
