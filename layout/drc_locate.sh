#!/usr/bin/env bash
# list Magic drc(full) errors of layout/<cell>.gds by rule, with unique (x,y) positions in um
cell=$1; here=$(cd "$(dirname "$0")" && pwd); mkdir -p $here/work/$cell; cd $here/work/$cell
cat > loc.tcl <<TCL
gds read $here/$cell.gds
load $cell
select top cell
drc style drc(full)
drc check
drc catchup
foreach {why boxes} [drc listall why] {
  set s {}
  foreach b \$boxes { lappend s [format "(%.2f,%.2f)" [expr ([lindex \$b 0]+[lindex \$b 2])*0.0025] [expr ([lindex \$b 1]+[lindex \$b 3])*0.0025]] }
  puts "ERR \$why : [lrange [lsort -unique \$s] 0 25]"
}
quit -noprompt
TCL
PDK_ROOT=${PDK_ROOT:-$HOME/.volare} ${MAGIC:-magic} -dnull -noconsole -rcfile ${PDK_ROOT:-$HOME/.volare}/sky130A/libs.tech/magic/sky130A.magicrc loc.tcl 2>&1 | grep "^ERR"
