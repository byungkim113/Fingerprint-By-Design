#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
root=$PWD
export PDK_ROOT="$HOME/.volare"
mkdir -p review/ldo-pex
cd review/ldo-pex
cat > extract.tcl <<EOF
gds read {$root/layout/ldo_blk.gds}
load ldo_blk
select top cell
extract do local
extract do capacitance
extract do coupling
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice -o ldo_blk_pex_c.spice
quit -noprompt
EOF
"$HOME/rffp-review-eda/install/bin/magic" -dnull -noconsole -rcfile "$HOME/.volare/sky130A/libs.tech/magic/sky130A.magicrc" extract.tcl > extract.log 2>&1
test -s ldo_blk_pex_c.spice
echo 'LDO capacitance-extracted netlist generated'
