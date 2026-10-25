#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
root=$PWD
python3 -m venv /tmp/code-a-chip-review-venv
source /tmp/code-a-chip-review-venv/bin/activate
cd notebook
bash setup_tools.sh > "$root/review/live-setup.log" 2>&1
export PATH="$HOME/rffp-tools/ngspice/bin:$PATH"
python sim/live_demo.py 2 --out "$root/review" > "$root/review/live-simulation.log" 2>&1
