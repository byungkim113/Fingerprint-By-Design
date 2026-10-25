#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
root=$PWD
mkdir -p review/digital-output
cp digital/tb/frame.hex review/digital-output/
cd review/digital-output
iverilog -g2012 -DFE_BEHAVIORAL_ICG -o baseline.vvp "$root/digital/tb/tb_tx_frontend.v" "$root/digital/src/tx_frontend.v"
vvp baseline.vvp | tee baseline.log
iverilog -g2012 -DFE_BEHAVIORAL_ICG -Ptb.SPI_HALF_NS=160 -o supported.vvp "$root/digital/tb/tb_tx_frontend.v" "$root/digital/src/tx_frontend.v"
vvp supported.vvp | tee supported.log
# Preserve the clock period and change only SPI half-period to reach the documented 4x ratio.
iverilog -g2012 -DFE_BEHAVIORAL_ICG -Ptb.SPI_HALF_NS=80 -o fast.vvp "$root/digital/tb/tb_tx_frontend.v" "$root/digital/src/tx_frontend.v"
if vvp fast.vvp > fast.log; then
    echo 'ERROR: the unsupported 4x rate unexpectedly passed'; exit 1
fi
cat fast.log
grep -q 'errors: FAIL' fast.log
echo 'PASS: supported SPI rates pass and unsupported 4x is caught'
