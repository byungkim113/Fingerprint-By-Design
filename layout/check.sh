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
# never read results from an earlier run: remove every output this script checks
rm -f magic.log "${cell}_ext.spice" reference.spice lvs.rpt netgen.log

cat > run.tcl <<EOF
gds read {$here/$cell.gds}
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
status=0
"$MAGIC" -dnull -noconsole -rcfile "$rc" run.tcl > magic.log 2>&1 || { echo "Magic failed (see $work/magic.log)"; status=1; }
grep -E "^DRC(ERR|TOTAL)" magic.log || true
grep -q '^DRCTOTAL: 0$' magic.log || status=1
[ -s "${cell}_ext.spice" ] || { echo "no extracted netlist from Magic"; exit 1; }

python3 "$here/prepare_lvs.py" "$here/$cell.spice" "$work/reference.spice" "$PDK_ROOT"
netgen_ok=1
"$NETGEN" -batch lvs "${cell}_ext.spice $cell" "reference.spice $cell" "$setup" lvs.rpt > netgen.log 2>&1 || netgen_ok=0
if [ "$netgen_ok" = 1 ] && [ -s lvs.rpt ] && grep -q "Circuits match uniquely" lvs.rpt \
   && ! grep -qiE "failed pin matching|property errors|do not match" lvs.rpt; then
  echo "LVS: MATCH ($(grep -m1 'Number of devices' lvs.rpt | sed 's/  */ /g'))"
else
  status=1
  [ "$netgen_ok" = 1 ] || echo "Netgen failed (see $work/netgen.log)"
  echo "LVS: MISMATCH (see $work/lvs.rpt)"
  grep -E "Circuit [12] contains|Final result|Mismatch" lvs.rpt 2>/dev/null | head -8 || true
fi
exit "$status"
