#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
root=$PWD
export QT_QPA_PLATFORM=offscreen
export MAGIC="$HOME/rffp-review-eda/install/bin/magic"
export NETGEN="$HOME/rffp-review-eda/install/bin/netgen"
status=0
for cell in tx_core ldo_blk; do
  echo "== Magic DRC and LVS: $cell"
  bash layout/check.sh "$cell" || status=1
  echo "== KLayout DRC: $cell"
  bash layout/klayout_drc.sh "$cell" || status=1
done
echo '== Metal connectivity'
klayout -b -r layout/probe_nets.py -rd "gds=$root/layout/tx_core.gds" | tee review/metal-connectivity.log
if grep -q MISMATCH review/metal-connectivity.log; then exit 1; fi
exit "$status"
