#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export CELLS="$HOME/.volare/sky130A/libs.ref/sky130_fd_sc_hd/verilog"
bash digital/tb/run_tests.sh
