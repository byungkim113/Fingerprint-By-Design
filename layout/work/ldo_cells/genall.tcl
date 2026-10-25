set cells {
  p5_16_32  sky130_fd_pr__pfet_g5v0d10v5 {w 16 l 32 nf 1}
  p5_8_16   sky130_fd_pr__pfet_g5v0d10v5 {w 8 l 16 nf 1}
  p5_ms1    sky130_fd_pr__pfet_g5v0d10v5 {w 0.42 l 50 nf 1}
  p5_4_8    sky130_fd_pr__pfet_g5v0d10v5 {w 4 l 8 nf 1}
  p5_20_2   sky130_fd_pr__pfet_g5v0d10v5 {w 20 l 2 nf 1}
  p5_pass   sky130_fd_pr__pfet_g5v0d10v5 {w 10 l 0.5 nf 20}
  n5_16_32  sky130_fd_pr__nfet_g5v0d10v5 {w 16 l 32 nf 1}
  n5_4_05   sky130_fd_pr__nfet_g5v0d10v5 {w 4 l 0.5 nf 1}
  n5_05_4   sky130_fd_pr__nfet_g5v0d10v5 {w 0.5 l 4 nf 1}
  n5_4_2    sky130_fd_pr__nfet_g5v0d10v5 {w 4 l 2 nf 1}
  n5_8_2    sky130_fd_pr__nfet_g5v0d10v5 {w 8 l 2 nf 1}
  n5_20_2   sky130_fd_pr__nfet_g5v0d10v5 {w 20 l 2 nf 1}
  pnp1      sky130_fd_pr__pnp_05v5_W3p40L3p40 {nx 1 ny 1}
  xh_8      sky130_fd_pr__res_xhigh_po_1p41 {w 1.41 l 8 nx 1}
  xh_39     sky130_fd_pr__res_xhigh_po_1p41 {w 1.41 l 39 nx 1}
  xh_341    sky130_fd_pr__res_xhigh_po_1p41 {w 1.41 l 34.1 nx 1}
  xh_3525   sky130_fd_pr__res_xhigh_po_1p41 {w 1.41 l 35.25 nx 1}
  mim22     sky130_fd_pr__cap_mim_m3_1 {w 22 l 22}
  n18_dec   sky130_fd_pr__nfet_01v8 {w 20 l 20 nf 1}
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
