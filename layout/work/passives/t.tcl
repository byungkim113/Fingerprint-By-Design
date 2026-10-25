proc mk {cell dev args} {
  load $cell
  box 0 0 0 0
  if {[catch {magic::gencell sky130::$dev R {*}$args} e]} { puts "GENERR $cell: $e" }
  select top cell
  drc style drc(full)
  drc check
  drc catchup
  set n 0
  foreach {why boxes} [drc listall why] { puts "DRC $cell: [llength $boxes] x $why"; incr n [llength $boxes] }
  puts "TOTAL $cell $n"
  gds write $cell.gds
}
mk r_load   sky130_fd_pr__res_high_po_1p41  w 1.41 l 5.6 nx 1
mk r_pa     sky130_fd_pr__res_high_po_5p73  w 5.73 l 4.3 nx 1
mk r_x20k   sky130_fd_pr__res_xhigh_po_1p41 w 1.41 l 14.1 nx 1
mk r_x200k  sky130_fd_pr__res_xhigh_po_1p41 w 1.41 l 35.6475 nx 4 snake 1   ;# snake bends: 35.6475 extracts to 141.0
quit -noprompt
