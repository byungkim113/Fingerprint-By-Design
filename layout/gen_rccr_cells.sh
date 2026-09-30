#!/usr/bin/env bash
# Generate the RC-CR device cells with Magic's SKY130 device generator.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
export PDK_ROOT=${PDK_ROOT:-$HOME/.volare}
mkdir -p "$here/work/rccr" && cd "$here/work/rccr"
cat > export.tcl <<'TCL'
load res_unit
box 0 0 0 0
magic::gencell sky130::sky130_fd_pr__res_high_po_0p35 R w 0.35 l 5 nx 1
select top cell
gds write res_unit.gds
load cap_unit
box 0 0 0 0
magic::gencell sky130::sky130_fd_pr__cap_mim_m3_1 C w 7.8 l 7.8
select top cell
gds write cap_unit.gds
quit -noprompt
TCL
${MAGIC:-magic} -dnull -noconsole -rcfile "$PDK_ROOT/sky130A/libs.tech/magic/sky130A.magicrc" export.tcl > export.log 2>&1
ls res_unit.gds cap_unit.gds
