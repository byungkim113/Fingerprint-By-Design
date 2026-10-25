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
mk r_nd80 sky130_fd_pr__res_generic_nd w 1 l 20.41 nx 4 snake 1   ;# snake bends: 20.41 extracts to 79.98
quit -noprompt
