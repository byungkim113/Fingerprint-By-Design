foreach {name dev params} {
  pfet5 sky130_fd_pr__pfet_g5v0d10v5 {w 10 l 0.5 nf 2}
  nfet5 sky130_fd_pr__nfet_g5v0d10v5 {w 4 l 2 nf 1}
  pnp sky130_fd_pr__pnp_05v5 {}
} {
  load $name
  box 0 0 0 0
  if {[catch {eval magic::gencell sky130::$dev X $params} err]} { puts "GENERR $name: $err" }
  select top cell
  drc style drc(full)
  drc check
  drc catchup
  set n 0
  foreach {why boxes} [drc listall why] { incr n [llength $boxes]; puts "DRC $name: [llength $boxes] x $why" }
  puts "DRCTOTAL $name: $n  bbox [box values]"
  gds write $name.gds
}
quit -noprompt
