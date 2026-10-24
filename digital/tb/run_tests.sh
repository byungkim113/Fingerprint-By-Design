#!/usr/bin/env bash
# Runs the front-end tests inside the LibreLane container (Icarus Verilog + the PDK's cell models):
#   1. RTL simulation (behavioural model of the clock-gate cell)
#   2. gate-level simulation of the final routed netlist of a LibreLane run, with the SKY130 cell models
#   3. mutation test: three deliberate RTL bugs must each make the testbench fail
# usage (from digital/):  docker run --rm -v "$PWD":/d -v "$HOME/.ciel":/pdk -w /d/tb \
#                           ghcr.io/librelane/librelane:3.0.16 bash -lc "bash run_tests.sh <run-tag>"
set -u
RUN=${1:-run7}
CELLS=$(ls -d /pdk/ciel/sky130/versions/*/sky130A/libs.ref/sky130_fd_sc_hd/verilog | head -1)
NL=../runs/$RUN/final/nl/tx_frontend.nl.v
status=0

echo "== RTL"
iverilog -g2012 -DFE_BEHAVIORAL_ICG -o rtl.vvp tb_tx_frontend.v ../src/tx_frontend.v 2>/dev/null && vvp -n rtl.vvp | grep -E "checks|FAIL" || status=1
grep -q "0 errors" <(vvp -n rtl.vvp) || status=1

echo "== gate level ($NL)"
iverilog -g2012 -DFUNCTIONAL -DUNIT_DELAY=#1 -o gl.vvp tb_tx_frontend.v "$NL" "$CELLS/primitives.v" "$CELLS/sky130_fd_sc_hd.v" 2>&1 \
  | grep -vi "warning\|timescale" | head -5
vvp -n gl.vvp | grep -E "checks|FAIL|TIMEOUT" | head -5
grep -q "0 errors" <(vvp -n gl.vvp) || status=1

echo "== mutation test"
python3 - <<'PY'
src = open("../src/tx_frontend.v").read()
muts = {"m1": ("thermo[k] = (k < code)", "thermo[k] = (k <= code)"),
        "m2": ("if (count == 7'd127) begin", "if (count == 7'd126) begin"),
        "m3": ("dq <= thermo(word[4:0]); dbq <= ~thermo(word[4:0]);", "dq <= thermo(word[4:0]); dbq <= ~thermo(word[9:5]);")}
for m, (a, b) in muts.items():
    open(m + ".v", "w").write(src.replace(a, b) if a in src else src)
    print(m, "applied" if a in src else "NOT APPLIED")
PY
for m in m1 m2 m3; do
  iverilog -g2012 -DFE_BEHAVIORAL_ICG -o $m.vvp tb_tx_frontend.v $m.v 2>/dev/null
  r=$(vvp -n $m.vvp | grep -E "checks|TIMEOUT")
  echo "$m: $r"
  echo "$r" | grep -q " 0 errors" && status=1
done
rm -f m1.v m2.v m3.v *.vvp
echo "== overall: $([ $status = 0 ] && echo PASS || echo FAIL)"
exit $status
