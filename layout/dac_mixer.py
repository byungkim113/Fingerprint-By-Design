"""Assembly A: one channel's current-steering DAC (with switches) + its Gilbert
switching quad. The DAC's two output buses are the quad's tail currents.

  TP  : DAC TP bus  -> Q1_S, Q2_S        TN  : DAC TN bus  -> Q3_S, Q4_S
  OUTP: Q1_D, Q4_D  (pin)                OUTN: Q2_D, Q3_D  (pin)
  LO  : Q1_G, Q3_G  (pin)                LOB : Q2_G, Q4_G  (pin)
Device bars are reached with minimum via1 cuts; vertical stubs on met2,
horizontal tracks on met3 (via2 via gLayout stacks). Quad devices are centred on
their D-label x; bar centres: S = S-label y, D = D-label y - 0.145,
G = G-label y + 0.165.
"""
from pathlib import Path

import route as R
from glayout.backend import Component
from glayout.pdk.sky130_mapped import sky130_mapped_pdk as pdk

HERE = Path(__file__).resolve().parent
QX, QY = -18.0, 3.0                       # quad placement
DEV_X = [0.68, 3.05, 5.4, 7.77]          # Q1..Q4 centres in the quad cell
S_Y, D_Y, G_Y = 2.43, 3.0 - 0.145, -2.98 + 0.165
TRK = {"LO": -3.5, "LOB": -4.6, "OUTP": 9.6, "OUTN": 10.7, "TP": 12.0, "TN": 13.2}
DAC_TP = (1.6, 4.72)                      # via positions on the DAC buses (between column straps)
DAC_TN = (-0.2, 8.33)
PINS = ["OUTP", "OUTN", "LO", "LOB", "G", "VSS"]
X_OUT = 90.0                              # east end of the OUTP/OUTN tracks


def build(name="dac_mixer"):
    pdk.activate()
    top = Component(f"{name}_hier")
    R.place(top, HERE / "dac_sw_array.gds", 0, 0)
    R.place(top, HERE / "mixer_quad.gds", QX, QY)
    x = [QX + d for d in DEV_X]
    ys, yd, yg = QY + S_Y, QY + D_Y, QY + G_Y

    def stub(xx, y_bar, net, xoff):
        """via1 on a device bar, met2 stub to the net's track, via2 up to met3."""
        xs = xx + xoff
        R.via1_min(top, xs, y_bar)
        R.wire(top, "m2", [(xs, y_bar), (xs, TRK[net])])
        R.via2_min(top, xs, TRK[net])
        return xs

    # gates (stubs at device centre, going down)
    lo = [stub(x[0], yg, "LO", 0), stub(x[2], yg, "LO", 0)]
    lob = [stub(x[1], yg, "LOB", 0), stub(x[3], yg, "LOB", 0)]
    # drains (stubs right of centre, going up)
    # (the quad's S/D bars are 0.94 um wide: +-0.25 keeps >= 0.055 um met1 around the cut)
    outp = [stub(x[0], yd, "OUTP", 0.25), stub(x[3], yd, "OUTP", 0.25)]
    outn = [stub(x[1], yd, "OUTN", 0.25), stub(x[2], yd, "OUTN", 0.25)]
    # sources (stubs left of centre, going up)
    tp = [stub(x[0], ys, "TP", -0.25), stub(x[1], ys, "TP", -0.25)]
    tn = [stub(x[2], ys, "TN", -0.25), stub(x[3], ys, "TN", -0.25)]

    x_pin = QX - 3.0
    for net, xs in (("LO", lo), ("LOB", lob)):
        R.wire(top, "m3", [(x_pin, TRK[net]), (max(xs), TRK[net])])
        R.pin(top, "m3", x_pin, TRK[net], net)
    # mixer outputs run east over the DAC array on met3 (free above it) and exit at X_OUT
    for net, xs in (("OUTP", outp), ("OUTN", outn)):
        R.wire(top, "m3", [(min(xs), TRK[net]), (X_OUT, TRK[net])])
        R.pin(top, "m3", X_OUT, TRK[net], net)
    # tails over to the DAC buses, down on met2 between the DAC's column straps
    for net, xs, (bx, by) in (("TP", tp, DAC_TP), ("TN", tn, DAC_TN)):
        R.wire(top, "m3", [(min(xs), TRK[net]), (bx, TRK[net])])
        R.via2_min(top, bx, TRK[net])
        R.wire(top, "m2", [(bx, TRK[net]), (bx, by)])
        R.via1_min(top, bx, by)
    R.pin(top, "m1", -0.5, -1.06, "G")                # DAC gate bus (reference current input)
    R.pin(top, "m1", -0.81, 0.68, "VSS")
    return top


def netlist(name="dac_mixer"):
    n = "sky130_fd_pr__nfet_01v8"
    ports = " ".join(f"D{k} DB{k}" for k in range(31))
    lines = [f".subckt {name} {ports} OUTP OUTN LO LOB G VSS",
             "XR G G VSS VSS {n} W=0.5 L=1.0 nf=1 m=1".format(n=n)]
    for k in range(31):
        lines += [f"XU{k} N{k} G VSS VSS {n} W=0.5 L=1.0 nf=1 m=1",
                  f"XSP{k} TP D{k} N{k} VSS {n} W=1.0 L=0.15 nf=1 m=1",
                  f"XSN{k} TN DB{k} N{k} VSS {n} W=1.0 L=0.15 nf=1 m=1"]
    lines += [f"XQ1 OUTP LO TP VSS {n} W=4.0 L=0.15 nf=1 m=1", f"XQ2 OUTN LOB TP VSS {n} W=4.0 L=0.15 nf=1 m=1",
              f"XQ3 OUTN LO TN VSS {n} W=4.0 L=0.15 nf=1 m=1", f"XQ4 OUTP LOB TN VSS {n} W=4.0 L=0.15 nf=1 m=1",
              f".ends {name}", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    c = build().flatten()
    c.name = "dac_mixer"
    c.write_gds(str(HERE / "dac_mixer.gds"))
    keep = set(PINS) | {f"D{k}" for k in range(31)} | {f"DB{k}" for k in range(31)}
    R.strip_foreign_labels(HERE / "dac_mixer.gds", keep)
    (HERE / "dac_mixer.spice").write_text(netlist())
    print(f"dac_mixer: size {c.xsize:.2f} x {c.ysize:.2f} um")
