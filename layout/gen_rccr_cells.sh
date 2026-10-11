#!/usr/bin/env bash
# Generate the RC-CR device cells with Magic's SKY130 device generator.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
export PDK_ROOT=${PDK_ROOT:-$HOME/.volare}
mkdir -p "$here/work/rccr" && cd "$here/work/rccr"
# wide (1p41) resistors: the 0p35 cells failed the RPM/URPM width rule (rpm.1); lengths LI/LQ
# (um) set the RC-CR I/Q branches (Q may be trimmed vs I to cancel layout parasitics)
LI=${LI:-25.6}; LQ=${LQ:-20.3}
cat > export.tcl <<TCL
load res_i
box 0 0 0 0
magic::gencell sky130::sky130_fd_pr__res_high_po_1p41 R w 1.41 l $LI nx 1
select top cell
gds write res_i.gds
load res_q
box 0 0 0 0
magic::gencell sky130::sky130_fd_pr__res_high_po_1p41 R w 1.41 l $LQ nx 1
select top cell
gds write res_q.gds
load cap_unit
box 0 0 0 0
magic::gencell sky130::sky130_fd_pr__cap_mim_m3_1 C w 7.8 l 7.8
select top cell
gds write cap_unit.gds
quit -noprompt
TCL
${MAGIC:-magic} -dnull -noconsole -rcfile "$PDK_ROOT/sky130A/libs.tech/magic/sky130A.magicrc" export.tcl > export.log 2>&1
ls res_i.gds res_q.gds cap_unit.gds
