#!/usr/bin/env bash
# Full simulation set for the generalization study (see PLAN.md).
cd "$(dirname "$0")"
PY=../.venv/bin/python
T=-40,0,27,55,85
one() {  # design
  local d=$1
  if [ "$d" = dac2 ]; then
    for c in ss_mm ff_mm ff_ll_mm; do [ -f ../data/design_${c}_dac2.npz ] || SKY130_CORNER=$c CHIP_SEED0=151 $PY dac_cascode.py 50 $T ../data/design_${c}_dac2.npz; done
    return
  fi
  [ -f ../data/${d}_200.npz ] || $PY dac_variants.py $d 200 $T ../data/${d}_200.npz
  for c in ss_mm ff_mm ss_hh_mm ff_ll_mm; do
    [ -f ../data/design_${c}_${d}.npz ] || SKY130_CORNER=$c CHIP_SEED0=151 $PY dac_variants.py $d 50 $T ../data/design_${c}_${d}.npz
  done
}
export -f one; export PY T
printf "%s\n" ${DESIGNS:-dac_ztc dac_hi dac_lo dac_sl dac_casL dac2} | xargs -P 3 -I{} bash -c 'one {}'
echo ALL DONE
