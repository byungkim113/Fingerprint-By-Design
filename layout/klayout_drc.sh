#!/usr/bin/env bash
# Independent DRC with the official SKY130 KLayout deck (FEOL + BEOL + off-grid).
# usage: layout/klayout_drc.sh <cell>   (expects layout/<cell>.gds)
set -euo pipefail
cell=$1
here=$(cd "$(dirname "$0")" && pwd)
PDK_ROOT=${PDK_ROOT:-$HOME/.volare}
KLAYOUT=${KLAYOUT:-/Applications/KLayout/klayout.app/Contents/MacOS/klayout}
mkdir -p "$here/work/$cell"
rpt=$here/work/$cell/klayout_drc.lyrdb
"$KLAYOUT" -b -r "$PDK_ROOT/sky130A/libs.tech/klayout/drc/sky130A_mr.drc" \
  -rd input="$here/$cell.gds" -rd top_cell="$cell" -rd report="$rpt" \
  -rd feol=true -rd beol=true -rd offgrid=true > "$here/work/$cell/klayout_drc.log" 2>&1
python3 - "$rpt" <<'PY'
import sys, xml.etree.ElementTree as ET
root = ET.parse(sys.argv[1]).getroot()
from collections import Counter
cnt = Counter(it.findtext("category").strip("'") for it in root.iter("item"))
print("KLAYOUT DRC total:", sum(cnt.values()))
for k, v in cnt.most_common():
    print(f"  {v} x {k}")
PY
