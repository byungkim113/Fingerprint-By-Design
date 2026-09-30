#!/usr/bin/env bash
# DRC (Magic) + LVS (Magic extraction -> Netgen) for a flat GDS cell.
# usage: layout/check.sh <cell>   (expects layout/<cell>.gds and layout/<cell>.spice)
set -euo pipefail
cell=$1
here=$(cd "$(dirname "$0")" && pwd)
export PDK_ROOT=${PDK_ROOT:-$HOME/.volare}
MAGIC=${MAGIC:-magic}
NETGEN=${NETGEN:-netgen}
rc=$PDK_ROOT/sky130A/libs.tech/magic/sky130A.magicrc
setup=$PDK_ROOT/sky130A/libs.tech/netgen/sky130A_setup.tcl
work=$here/work/$cell
mkdir -p "$work"
cd "$work"

cat > run.tcl <<EOF
gds read $here/$cell.gds
load $cell
select top cell
drc style drc(full)
drc check
drc catchup
set n 0
foreach {why boxes} [drc listall why] { puts "DRCERR: [llength \$boxes] x \$why"; incr n [llength \$boxes] }
puts "DRCTOTAL: \$n"
extract do local
extract all
ext2spice lvs
ext2spice -o ${cell}_ext.spice
quit -noprompt
EOF
"$MAGIC" -dnull -noconsole -rcfile "$rc" run.tcl > magic.log 2>&1
grep -E "^DRC(ERR|TOTAL)" magic.log

"$NETGEN" -batch lvs "${cell}_ext.spice $cell" "$here/$cell.spice $cell" "$setup" lvs.rpt > netgen.log 2>&1 || true
if grep -q "Circuits match uniquely" lvs.rpt && ! grep -q "failed pin matching" lvs.rpt; then
  echo "LVS: MATCH ($(grep -m1 'Number of devices' lvs.rpt | sed 's/  */ /g'))"
else
  echo "LVS: MISMATCH (see $work/lvs.rpt)"
  grep -E "Circuit [12] contains|Final result|Mismatch" lvs.rpt | head -8
fi
