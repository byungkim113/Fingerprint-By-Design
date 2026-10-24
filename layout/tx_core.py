"""Top level: transmitter core = 2 x (DAC + mixer) + LO path + output network
+ on-chip bias reference + LO input buffer + RF output buffer.

Placement (um): lo_path at (0, 0); I channel (dac_mixer) at (55, -75);
Q channel at (82, 14.5); output network at (200, -30); bias_ref at (75, -0.3)
(the free area between the channels); lo_buf_blk at (-30, 20) west of the LO path;
out_buf_blk at (315, 25) east of the output network.
Inter-block nets:
  LO_I/LOB_I : limiter I pins (met2) -> met4 down through the LO path's met3 supply
               horizontals -> met3 into the I channel's LO/LOB tracks
  LO_Q/LOB_Q : limiter Q pins -> met2 under the supply spines (met3/met4) -> met3 into
               the Q channel's tracks
  OUTP/OUTN  : channel outputs (met3) -> met4 trunks at x=185 / 187 -> output network;
               all crossings between the two are on different layers
  VDD        : LO path VDD -> met4 over the top -> output network VDD
  VSS        : every block ties its ground to the substrate taps (one node)
  BI / BPA / BOB : bias outputs -> met4 down over the bias block; BI stacks onto the I
               DAC gate bus; BPA/BOB turn to met3 below the bias block (crossing the
               OUTP/OUTN met4 trunks) to the PA mirror and the output-buffer bias
  BQ         : straight up on met2 into the Q DAC gate bus
  BLO        : met4 up through the Q channel, met3 over the LO path, met4 down
  IN         : LO buffer output (met3) -> met4 onto the LO path input strap
  RFP / RFN  : PA drains (met3) -> output buffer follower gates (met2)
"""
from pathlib import Path

import gdstk
import route as R
from glayout.backend import Component
from glayout.pdk.sky130_mapped import sky130_mapped_pdk as pdk

HERE = Path(__file__).resolve().parent
LOP, CHI, CHQ, ONT = (0, 0), (55, -75), (82, 14.5), (200, -30)
BIA, LBF, OBF = (75, -0.3), (-30, 20), (315, 25)
def _ldo_origin(top_y=-92.0, west_x=-75.0):
    """ldo_blk origin so that its top edge sits at top_y and its west edge at west_x (from its GDS bbox)."""
    (x0, _), (_, y1) = gdstk.read_gds(str(HERE / "ldo_blk.gds")).top_level()[0].bounding_box()
    return (round(west_x - x0, 2), round(top_y - y1, 2))


LDO_O = _ldo_origin()
DATA = [f"D{c}{k}" for c in ("I", "Q") for k in range(31)] + [f"DB{c}{k}" for c in ("I", "Q") for k in range(31)]
PINS = ["LO_PAD", "TXP", "TXN", "VIN", "VSS"] + DATA      # VDD is internal: the LDO output
G_BUS_Y = -1.065                           # DAC gate (reference) bus centre, dac_mixer coords


def channel_copy(tag):
    """dac_mixer.gds with its data pins renamed D<k> -> D<tag><k>, DB<k> -> DB<tag><k>."""
    lib = gdstk.read_gds(str(HERE / "dac_mixer.gds"))
    for cell in lib.cells:
        cell.name = f"dac_mixer_{tag}"
        for lab in cell.labels:
            if lab.text.startswith("DB"):
                lab.text = f"DB{tag}{lab.text[2:]}"
            elif lab.text.startswith("D") and lab.text[1:].isdigit():
                lab.text = f"D{tag}{lab.text[1:]}"
    out = HERE / "work" / f"dac_mixer_{tag}.gds"
    lib.write_gds(str(out))
    return out


def a(o, xy):
    return (o[0] + xy[0], o[1] + xy[1])


def build(name="tx_core"):
    pdk.activate()
    top = Component(f"{name}_hier")
    R.place(top, HERE / "lo_path.gds", *LOP)
    R.place(top, channel_copy("I"), *CHI)
    R.place(top, channel_copy("Q"), *CHQ)
    R.place(top, HERE / "out_net.gds", *ONT)
    R.place(top, HERE / "bias_ref.gds", *BIA)
    R.place(top, HERE / "lo_buf_blk.gds", *LBF)
    R.place(top, HERE / "out_buf_blk.gds", *OBF)

    # ---- LO into the I channel (met4 down, met3 across)
    lo_i, lob_i = (22.17, -58.8), (18.54, -58.8)
    ch_lo_i, ch_lob_i = a(CHI, (-21, -3.5)), a(CHI, (-21, -4.6))
    for p, q in ((lo_i, ch_lo_i), (lob_i, ch_lob_i)):
        R.via2_min(top, *p); R.via3_min(top, *p)
        R.box(top, "m3", *p, 0.5, 0.5)          # met3 min area in the met2->met4 stack
        R.wire(top, "m4", [p, (p[0], q[1])])
        R.via3_min(top, p[0], q[1])
        R.wire(top, "m3", [(p[0], q[1]), q])
    # ---- LO into the Q channel (met2 under the spines, met3 into the tracks)
    lo_q, lob_q = (47.47, 17.0), (43.84, 17.0)
    ch_lo_q, ch_lob_q = a(CHQ, (-21, -3.5)), a(CHQ, (-21, -4.6))
    R.wire(top, "m2", [lo_q, (58, 17.0)])
    R.via2_min(top, 58, 17.0)
    R.wire(top, "m3", [(58, 17.0), (58, ch_lo_q[1]), ch_lo_q])
    R.via2_min(top, *lob_q)
    R.wire(top, "m3", [lob_q, (lob_q[0], 13.5)])
    R.via2_min(top, lob_q[0], 13.5)
    R.wire(top, "m2", [(lob_q[0], 13.5), (57, 13.5)])
    R.via2_min(top, 57, 13.5)
    R.wire(top, "m3", [(57, 13.5), (57, ch_lob_q[1]), ch_lob_q])

    # ---- OUTP / OUTN trunks
    xp, xn = 185.0, 187.0
    for ch in (CHI, CHQ):
        op, on = a(ch, (90, 9.6)), a(ch, (90, 10.7))
        R.wire(top, "m3", [op, (xp, op[1])]); R.via3_min(top, xp, op[1])
        R.wire(top, "m3", [on, (xn, on[1])]); R.via3_min(top, xn, on[1])
    yp = [a(CHI, (90, 9.6))[1], a(CHQ, (90, 9.6))[1]]
    yn = [a(CHI, (90, 10.7))[1], a(CHQ, (90, 10.7))[1]]
    on_outp, on_outn = a(ONT, (-3, -3)), a(ONT, (-3, 33))
    R.wire(top, "m4", [(xp, min(yp)), (xp, max(yp))])
    R.wire(top, "m4", [(xn, min(yn)), (xn, max(yn))])
    R.via3_min(top, xp, on_outp[1])
    R.wire(top, "m3", [(xp, on_outp[1]), on_outp])     # crosses the OUTN trunk on met3
    R.via3_min(top, *on_outp)
    R.wire(top, "m4", [(xn, on_outn[1]), on_outn])

    # ---- VDD over the top on met4
    vdd_lo, vdd_on = (54.0, 18.52), a(ONT, (-11, 70))
    R.via3_min(top, *vdd_lo)
    R.wire(top, "m4", [vdd_lo, (54.0, 45.0), (vdd_on[0], 45.0), vdd_on])
    R.via3_min(top, *vdd_on)

    route_new_blocks(top)
    vss_grid(top)
    ldo_supply(top)
    for net, layer, xy in (("LO_PAD", "m4", a(LBF, (-29.8, 0.2))), ("TXP", "m3", a(OBF, (6.0, 10.7))),
                           ("TXN", "m3", a(OBF, (10.0, 11.9))),
                           ("VSS", "m5", (100.0, -86.0))):
        R.pin(top, layer, *xy, net)
    return top


def up34(top, x, y):
    """met2 end -> via2 + via3 to met4 (met3 min-area pad in between)."""
    R.via2_min(top, x, y); R.via3_min(top, x, y)
    R.box(top, "m3", x, y, 0.5, 0.5)


def route_new_blocks(top):
    bpin = lambda xl: a(BIA, (xl, 6.0))                   # bias output pins (met2 stub ends)
    # BI -> I DAC gate bus: met4 down over the bias block, stack to met1 between gate contacts
    bi, gi = bpin(30.74), (a(BIA, (30.74, 0))[0], a(CHI, (0, G_BUS_Y))[1])
    up34(top, *bi)
    R.wire(top, "m4", [bi, gi])
    R.via1_min(top, *gi); R.via2_min(top, *gi); R.via3_min(top, *gi)
    R.box(top, "m3", *gi, 0.5, 0.5)
    # BQ -> Q DAC gate bus: met2 straight up (crosses only the bias met3 tracks and the ring's met1)
    bq = bpin(37.11)
    gq = (bq[0], a(CHQ, (0, G_BUS_Y))[1])
    R.wire(top, "m2", [bq, gq]); R.via1_min(top, *gq)
    # BPA -> PA mirror (out_net IREF_PA track, met3 at local y -4): met4 down, met3 east at y=-56,
    # met2 up across the out_net VSS met3 track
    bpa = bpin(49.08); y_pa = -56.0; x_pa = a(ONT, (80.3, 0))[0]; iref = (x_pa, a(ONT, (0, -4))[1])
    up34(top, *bpa)
    R.wire(top, "m4", [bpa, (bpa[0], y_pa)]); R.via3_min(top, bpa[0], y_pa)
    R.wire(top, "m3", [(bpa[0], y_pa), (x_pa, y_pa)]); R.via2_min(top, x_pa, y_pa)
    R.wire(top, "m2", [(x_pa, y_pa), iref]); R.via2_min(top, *iref)
    # BOB -> output-buffer bias track (local y -9): met4 down, met3 east at y=-58, met4 up east of out_net
    bob = bpin(85.78); y_ob = -58.0; ob = a(OBF, (12.0, -9.0))
    up34(top, *bob)
    R.wire(top, "m4", [bob, (bob[0], y_ob)]); R.via3_min(top, bob[0], y_ob)
    R.wire(top, "m3", [(bob[0], y_ob), (ob[0], y_ob)]); R.via3_min(top, ob[0], y_ob)
    R.wire(top, "m4", [(ob[0], y_ob), ob]); R.via3_min(top, *ob)
    # BLO -> LO buffer bias track (local y -12.5): met4 up through the Q channel, met3 west above
    # the LO path (y=62, clear of the met4 VDD run at y=45), met4 down into the LO buffer
    blo = bpin(67.43); y_lo = 62.0; lb = a(LBF, (6.0, -12.5))
    up34(top, *blo)
    R.wire(top, "m4", [blo, (blo[0], 40.0)]); R.via3_min(top, blo[0], 40.0)
    R.wire(top, "m3", [(blo[0], 40.0), (blo[0], y_lo), (lb[0], y_lo)]); R.via3_min(top, lb[0], y_lo)
    R.wire(top, "m4", [(lb[0], y_lo), lb]); R.via3_min(top, *lb)
    # IN: LO buffer output track (met3, local y 11.9) east, met4 down onto the LO path input strap
    # (RC-CR v2: the IN route enters the RC-CR from the top, met4 at x 1.27 spanning this y)
    y_in = a(LBF, (0, 11.9))[1]
    R.wire(top, "m3", [a(LBF, (6.62, 11.9)), (1.27, y_in)]); R.via3_min(top, 1.27, y_in)
    # RFP / RFN (out_net met3 verticals at local x 95.43 / 103.43, bottoms at local y 41.45) -> down,
    # east on met3 below the RFN vertical, met2 up to the follower gate stubs (PDP / PDN)
    for xl, y_run, pd in ((95.43, 8.0, (1.16, -10.5)), (103.43, 9.5, (5.47, -11.5))):
        x0 = a(ONT, (xl, 0))[0]; p = a(OBF, pd)
        R.wire(top, "m3", [(x0, a(ONT, (0, 41.65))[1]), (x0, y_run), (p[0], y_run)])
        R.via2_min(top, p[0], y_run); R.wire(top, "m2", [(p[0], y_run), p])
    # VDD: extend the met4 run at y=45 west to the LO buffer and east to the output buffer; drop
    # met4 onto the bias VDD track
    lv, ov, bv = a(LBF, (18.0, 9.5)), a(OBF, (5.0, 9.5)), a(BIA, (75.0, 4.5))
    for v in (lv, ov, bv):
        R.via3_min(top, *v)
        R.wire(top, "m4", [v, (v[0], 45.0)])
    R.wire(top, "m4", [(lv[0], 45.0), (ov[0], 45.0)])


def vss_grid(top):
    """metal VSS: until now every block tied its ground only to the substrate taps. A met5
    spine below the core (met5 is otherwise unused, so it cannot short anything) with
    met5 drops to one tie point per block, stacked down to that block's VSS metal."""
    y_spine = -86.0
    ties = [(a(LBF, (14.0, 10.7)), "m3"),                  # LO buffer VSS track
            ((22.74, -6.9), "m4"),                         # LO path VSS rail
            (a(BIA, (10.0, -24.0)), "m3"),                 # bias reference bottom VSS track
            (a(CHI, (60.0, -2.55)), "m1"),                 # I channel tap ring (bottom bar)
            (a(CHQ, (53.0, -2.55)), "m1"),                 # Q channel tap ring (bottom bar)
            (a(ONT, (15.5, -6.0)), "m3"),                  # output network VSS track
            (a(OBF, (13.0, 13.1)), "m3")]                  # output buffer VSS track
    for (x, y), layer in ties:
        if layer == "m1":
            R.via1_min(top, x, y); R.via2_min(top, x, y)
            R.box(top, "m3", x, y, 0.5, 0.5)
        if layer in ("m1", "m3"):
            R.via3_min(top, x, y)
        R.via4_min(top, x, y)
        R.wire(top, "m5", [(x, y), (x, y_spine)])
    xs = [x for (x, _), _ in ties]
    R.wire(top, "m5", [(min(xs), y_spine), (max(xs), y_spine)])


def ldo_supply(top):
    """on-chip LDO (ldo_blk) below the core: VOUT -> core VDD (met4 up the east side to the VDD run at
    y=45, crossing only met3), VSS -> the met5 spine (extended east), VIN = the chip's supply pin."""
    import json
    R.place(top, HERE / "ldo_blk.gds", *LDO_O)
    trk = {(t["net"], t["ch"]): t for t in json.loads((HERE / "ldo_blk_tracks.json").read_text())}
    vout = trk[("VOUT", "TOP2")]                         # topmost LDO track, spans to the east end
    xv, yv = LDO_O[0] + vout["x1"] - 0.9, LDO_O[1] + vout["y"]
    R.via3_min(top, xv, yv)
    R.wire(top, "m4", [(xv, yv), (xv, 45.0), (a(OBF, (5.0, 9.5))[0], 45.0)])
    vss = trk[("VSS", "BOT2")]
    xs, ys = LDO_O[0] + vss["x1"] - 4.4, LDO_O[1] + vss["y"]
    R.via3_min(top, xs, ys); R.via4_min(top, xs, ys)
    R.wire(top, "m5", [(xs, ys), (xs, -86.0), (a(OBF, (13.0, 13.1))[0], -86.0)])


def netlist(name="tx_core"):
    import dac_mixer
    import lo_path
    import out_net
    import bias_block
    import buffers
    dport = lambda t: " ".join(f"D{t}{k} DB{t}{k}" for k in range(31))
    return "\n".join([
        dac_mixer.netlist(), lo_path.netlist(), out_net.netlist(), bias_block.netlist(),
        buffers.lo_netlist(), buffers.out_netlist(),
        __import__("ldo_block").netlist(),
        f".subckt {name} LO_PAD TXP TXN VIN VSS {dport('I')} {dport('Q')}",
        "XLDO VIN VDD VSS ldo_blk",
        f"XI {dport('I')} OUTP OUTN LO_I LOB_I IREF_I VSS dac_mixer",
        f"XQ {dport('Q')} OUTP OUTN LO_Q LOB_Q IREF_Q VSS dac_mixer",
        "XLO IN LO_I LOB_I LO_Q LOB_Q VDD VSS lo_path",
        "XON OUTP OUTN RFP RFN IREF_PA VDD VSS out_net",
        "XB VDD VSS IREF_I IREF_Q IREF_PA BLO BOB bias_ref",
        "XLB LO_PAD IN VDD VSS BLO lo_buf_blk",
        "XOB VDD TXP TXN VSS BOB RFP RFN out_buf_blk",
        f".ends {name}", ""])


if __name__ == "__main__":
    import limiter
    c = build().flatten()
    c.name = "tx_core"
    c.write_gds(str(HERE / "tx_core.gds"))
    R.strip_foreign_labels(HERE / "tx_core.gds", set(PINS))
    (HERE / "tx_core.spice").write_text(f'.include "{limiter.SC_SPICE}"\n' + netlist())
    print(f"tx_core: size {c.xsize:.2f} x {c.ysize:.2f} um")
