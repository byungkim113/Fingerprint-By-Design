set cells {
  p5_g_042_20  sky130_fd_pr__pfet_g5v0d10v5 {w 0.42 l 20 nf 1}
  n5_g_2_1     sky130_fd_pr__nfet_g5v0d10v5 {w 2 l 1 nf 1}
  p5_g_2_05    sky130_fd_pr__pfet_g5v0d10v5 {w 2 l 0.5 nf 1}
  n5_g_1_05    sky130_fd_pr__nfet_g5v0d10v5 {w 1 l 0.5 nf 1}
  p5_g_sw      sky130_fd_pr__pfet_g5v0d10v5 {w 10 l 0.5 nf 4}
  mim10        sky130_fd_pr__cap_mim_m3_1 {w 10 l 10}
  mimss        sky130_fd_pr__cap_mim_m3_1 {w 28.6 l 28.6 nx 3 ny 2}
}
foreach {name dev params} $cells {
  load $name
  box 0 0 0 0
  if {[catch {eval magic::gencell sky130::$dev X $params} err]} { puts "GENERR $name: $err"; continue }
  select top cell
  drc style drc(full)
  drc check
  drc catchup
  set n 0
  foreach {why boxes} [drc listall why] { incr n [llength $boxes] }
  puts "CELL $name DRC $n"
  gds write $name.gds
}
quit -noprompt
