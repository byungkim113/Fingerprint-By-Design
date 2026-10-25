#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -f "$HOME/rffp-review-venv/bin/activate" ]; then
  python3 -m venv "$HOME/rffp-review-venv"
  "$HOME/rffp-review-venv/bin/python" -m pip install -q numpy
fi
source "$HOME/rffp-review-venv/bin/activate"
export PATH="$HOME/rffp-tools/ngspice/bin:$PATH"
python review/check_ldo.py "$@" | tee "review/ldo-startup${1:-}.log"
