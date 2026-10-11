#!/usr/bin/env bash
# Parasitic extraction (Magic) of a flat GDS cell: <cell>_pex_c.spice (device + coupling/ground C)
# and <cell>_pex_rc.spice (plus wire resistance via extresist).
# usage: layout/pex.sh <cell>
set -euo pipefail
cell=$1
here=$(cd "$(dirname "$0")" && pwd)
export PDK_ROOT=${PDK_ROOT:-$HOME/.volare}
MAGIC=${MAGIC:-magic}
rc=$PDK_ROOT/sky130A/libs.tech/magic/sky130A.magicrc
work=$here/work/$cell/pex
mkdir -p "$work"; cd "$work"
cat > pex.tcl <<EOF
gds read $here/$cell.gds
load $cell
select top cell
extract do local
extract do capacitance
extract do coupling
extract do resistance
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice -o ${cell}_pex_c.spice
ext2sim labels on
ext2sim
extresist tolerance 10
extresist all
ext2spice lvs
ext2spice cthresh 0
ext2spice extresist on
ext2spice -o ${cell}_pex_rc.spice
quit -noprompt
EOF
"$MAGIC" -dnull -noconsole -rcfile "$rc" pex.tcl > pex.log 2>&1
for f in c rc; do
  s=${cell}_pex_$f.spice
  echo "$s: $(grep -c '^X' $s) devices, $(grep -c '^C' $s) caps, $(grep -c '^R' $s) resistors"
done
