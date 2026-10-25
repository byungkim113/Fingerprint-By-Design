proc mk {cell dev args} {
  load $cell
  box 0 0 0 0
  if {[catch {magic::gencell sky130::$dev C {*}$args} e]} { puts "GENERR $cell: $e" }
  select top cell
  drc style drc(full)
  drc check
  drc catchup
  set n 0
  foreach {why boxes} [drc listall why] { puts "DRC $cell: [llength $boxes] x $why"; incr n [llength $boxes] }
  puts "TOTAL $cell $n"
  gds write $cell.gds
}
mk c_3   sky130_fd_pr__cap_mim_m3_1 w 3 l 3
mk c_11  sky130_fd_pr__cap_mim_m3_1 w 11 l 11
mk c_30  sky130_fd_pr__cap_mim_m3_1 w 30 l 30
mk r_x50k sky130_fd_pr__res_xhigh_po_1p41 w 1.41 l 35.25 nx 1
quit -noprompt
