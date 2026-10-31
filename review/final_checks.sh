#!/usr/bin/env bash
# Run targeted submission checks in the prepared Linux review environment.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/rffp-tools/ngspice/bin:$HOME/rffp-review-eda/install/bin:$PATH"
export PDK_ROOT="$HOME/.volare"
export QT_QPA_PLATFORM=offscreen
if [ "${1:-tools}" = tools ]; then
  python3 -m venv "$HOME/rffp-final-venv"
  "$HOME/rffp-final-venv/bin/pip" install -q numpy scipy scikit-learn matplotlib volare==0.20.6
fi
if [ -d "$HOME/rffp-final-venv/bin" ]; then
  export PATH="$HOME/rffp-final-venv/bin:$PATH"
fi
case "${1:-tools}" in
  all)
    if [ ! -x "$HOME/rffp-final-venv/bin/python3" ]; then bash "$0" tools; fi
    export PATH="$HOME/rffp-final-venv/bin:$PATH"
    bash notebook/setup_tools.sh > review/final-setup.log 2>&1
    echo "PASS: live-demo installer and pinned PDK check"
    bash "$0" digital > review/final-digital.log 2>&1
    echo 'PASS: digital RTL, gate-level and mutation tests'
    bash "$0" layout > review/final-layout.log 2>&1 &
    layout_pid=$!
    bash "$0" live > review/final-live.log 2>&1
    echo 'PASS: fresh live transistor-level demo'
    wait "$layout_pid"
    echo 'PASS: physical verification'
    bash "$0" ldo > review/final-ldo.log 2>&1
    echo 'PASS: extracted-LDO startup'
    ;;
  tools)
    python3 -c 'import numpy, scipy, sklearn, matplotlib; print("Python dependencies available")'
    ngspice -v | head -8
    magic --version
    klayout -v
    cat "$PDK_ROOT/sky130A/SOURCES"
    ;;
  digital)
    export CELLS="$PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/verilog"
    bash digital/tb/run_tests.sh
    ;;
  layout)
    bash review/run_layout.sh
    ;;
  live)
    python3 notebook/sim/live_demo.py 2 --out review/final-live-output
    python3 - <<'PY'
import json
import numpy as np
from pathlib import Path
live = json.loads(Path('review/final-live-output/live_fingerprints.json').read_text())
ref = json.loads(Path('notebook/data/live_reference.json').read_text())
def bb(d, chip):
    a = np.array(d['chips'][chip]['baseband'])
    return a[0] + 1j * a[1]
error = np.max(np.abs(bb(live, 'nominal') - bb(ref, 'nominal')))
delta = np.concatenate([np.array(live['chips']['1']['fingerprint'][key]) -
                        np.array(live['chips']['2']['fingerprint'][key])
                        for key in ('I_real', 'I_imag', 'Q_real', 'Q_imag')])
assert np.isfinite(error) and error < 1e-5, error
assert np.isfinite(delta).all() and np.sqrt(np.mean(delta**2)) > 1e-6
print('PASS: nominal reference agreement', error, '; distinct finite chip fingerprints')
PY
    ;;
  ldo)
    export LDO_PEX_FILE="$PWD/review/ldo-pex-fixed/ldo_blk_pex_c.spice"
    export LDO_OUT="$PWD/review/final-ldo-output"
    export LDO_RAMPS=1,10,50,200
    python3 review/check_ldo.py --pex
    python3 - <<'PY'
import json
from pathlib import Path
rows = json.loads(Path('review/final-ldo-output/startup.json').read_text())
assert len(rows) == 12
assert all(r['returncode'] == 0 and r.get('complete') and r['peak_V'] <= 1.95
           and abs(r['final_V'] - 1.8) < .05 for r in rows), rows
print('PASS: all 12 extracted-LDO startup cases; maximum peak', max(r['peak_V'] for r in rows))
PY
    ;;
  *) echo "Usage: $0 tools|all|digital|layout|live|ldo" >&2; exit 2 ;;
esac
