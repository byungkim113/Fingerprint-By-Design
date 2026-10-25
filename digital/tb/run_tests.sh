#!/usr/bin/env bash
# Runs the front-end tests inside the LibreLane container (Icarus Verilog + the PDK's cell models):
#   1. RTL simulation (behavioural model of the clock-gate cell)
#   2. gate-level simulation of the final routed netlist of a LibreLane run, with the SKY130 cell models
#   3. mutation test: three deliberate RTL bugs must each make the testbench fail
# usage (from digital/):  docker run --rm -v "$PWD":/d -v "$HOME/.ciel":/pdk -w /d/tb \
#                           ghcr.io/librelane/librelane:3.0.16 bash -lc "bash run_tests.sh <run-tag>"
set -euo pipefail
cd "$(dirname "$0")"
if [ -z "${CELLS:-}" ]; then
  cell_dirs=(/pdk/ciel/sky130/versions/*/sky130A/libs.ref/sky130_fd_sc_hd/verilog)
  CELLS=${cell_dirs[0]}
fi
NL=../final/tx_frontend.nl.v
if [ -n "${1:-}" ]; then NL=../runs/$1/final/nl/tx_frontend.nl.v; fi
status=0

echo "== RTL"
for half in 200 160; do
  iverilog -g2012 -DFE_BEHAVIORAL_ICG -Ptb.SPI_HALF_NS=$half -o rtl.vvp tb_tx_frontend.v ../src/tx_frontend.v
  vvp -n rtl.vvp | tee rtl.log
  grep -q '0 errors: PASS' rtl.log
done

echo "== gate level ($NL)"
for half in 200 160; do
  iverilog -g2012 -DFUNCTIONAL -DUNIT_DELAY=#1 -Ptb.SPI_HALF_NS=$half -o gl.vvp tb_tx_frontend.v "$NL" "$CELLS/primitives.v" "$CELLS/sky130_fd_sc_hd.v" > gl_compile.log 2>&1 || { cat gl_compile.log; exit 1; }
  vvp -n gl.vvp | tee gl.log
  grep -q '0 errors: PASS' gl.log
done

echo "== mutation test"
python3 - <<'PY'
src = open("../src/tx_frontend.v").read()
muts = {"m1": ("thermo[k] = (k < code)", "thermo[k] = (k <= code)"),
        "m2": ("if (count == 7'd127) begin", "if (count == 7'd126) begin"),
        "m3": ("dq <= thermo(word[4:0]); dbq <= ~thermo(word[4:0]);", "dq <= thermo(word[4:0]); dbq <= ~thermo(word[9:5]);")}
for m, (a, b) in muts.items():
    assert src.count(a) == 1, f"mutation {m} was not applied uniquely"
    open(m + ".v", "w").write(src.replace(a, b) if a in src else src)
    print(m, "applied" if a in src else "NOT APPLIED")
PY
for m in m1 m2 m3; do
  iverilog -g2012 -DFE_BEHAVIORAL_ICG -o $m.vvp tb_tx_frontend.v $m.v
  if vvp -n $m.vvp > "$m.log" 2>&1; then status=1; fi
  r=$(grep -E "checks|TIMEOUT" "$m.log")
  echo "$m: $r"
  if echo "$r" | grep -q " 0 errors"; then status=1; fi
done
rm -f m1.v m2.v m3.v *.vvp
echo "== overall: $([ $status = 0 ] && echo PASS || echo FAIL)"
exit $status
