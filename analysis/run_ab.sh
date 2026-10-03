#!/usr/bin/env bash
# A/B on the 7 development designs + full pipeline on the 3 fresh held-out designs.
cd "$(dirname "$0")"
PY=${PY:-$HOME/venvs/rffp/bin/python}
dev() { $PY robust2.py "$1" > ../results/robust2_$1.log 2>&1; echo "DONE dev $1"; }
fresh() {
  $PY generalize.py "$1" > ../results/generalize_$1.log 2>&1 &&
  $PY drift_cov.py  "$1" > ../results/drift_cov_$1.log  2>&1 &&
  $PY robust2.py    "$1" > ../results/robust2_$1.log    2>&1
  echo "DONE fresh $1"
}
export -f dev fresh; export PY
{ printf "fresh %s\n" dac_big dac_mid dac_cas2; printf "dev %s\n" dac dac2 dac_ztc dac_hi dac_lo dac_sl dac_casL; } \
  | xargs -P 4 -L 1 bash -c '$0 $1'
echo ALL DONE
