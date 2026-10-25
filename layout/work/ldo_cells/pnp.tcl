load pnp
box 0 0 0 0
if {[catch {magic::gencell sky130::sky130_fd_pr__pnp_05v5_W3p40L3p40 Q nx 1 ny 1} err]} { puts "GENERR $err" }
select top cell
drc style drc(full)
drc check
drc catchup
set n 0
foreach {why boxes} [drc listall why] { incr n [llength $boxes]; puts "DRC pnp: [llength $boxes] x $why" }
puts "DRCTOTAL pnp: $n bbox [box values]"
gds write pnp.gds
quit -noprompt
