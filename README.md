# Fingerprint by Design

Predicting, tracing and stabilising the RF fingerprint of an open-source SKY130 transmitter, before any silicon exists.
This is the full project behind the IEEE SSCS Code-a-Chip (ISSCC 2027) notebook in [`notebook/`](notebook/).

## Status (2026-10-25)

| Part | State |
|---|---|
| Analog transmitter core + on-chip LDO (`layout/tx_core.gds`, 543 x 398 um) | DRC 0 in Magic and KLayout; strict LVS match (300 devices, device sizes included); metal-only power probes 6/6; parasitic extraction (C) 477 devices, 1,947 caps |
| LDO start-up | Extracted layout peaks 1.80-1.93 V for -40/27/85 C and 1-200 us ramps (limit 1.95 V). C-only extraction, typical process, no mismatch; 17 mV margin at 85 C / 50 us. The schematic does not converge from exactly 0 V at 85 C |
| Digital front end (`digital/`, 290 x 301 um) | LibreLane: timing met at 9 corners, DRC/LVS clean; 947/947 checks at RTL and gate level; not yet integrated with the analog core; no pads |
| Studies | Transistor-level Monte Carlo identification, attribution, design variants, supply/temperature drift, LDO tests; results in `results/`, log of every pre-registration and correction in [`PLAN.md`](PLAN.md) |
| Review | Independent review and fix evidence in [`review/REVIEW.md`](review/REVIEW.md) |

Identification results use a known 128-sample frame repeated 18 times per decision (2,304 samples, 92 us); see the
notebook, Section 2 and Result 1, for the protocol and the accuracy with shorter bursts.

## Layout of the repository

| Path | Contents |
|---|---|
| `notebook/` | The submission notebook and everything it needs (data, layout files, bundled demo scripts) |
| `sim/` | Netlist generator (`tx_full.py`), LDO and bandgap (`ldo.py`, `bandgap.py`), study drivers (`tx_*.py`) |
| `analysis/` | Feature and classifier code used by the studies (`robust2.py`, ...) |
| `layout/` | Block layout generators, chip assembly (`tx_core.py`), DRC/LVS/PEX scripts; device cells in `layout/work/{ldo_cells,passives,rccr}` |
| `digital/` | Front-end RTL, testbench, LibreLane configuration, final routed artifacts in `digital/final/` |
| `results/` | Result files of every study (JSON) |
| `review/` | Review report, review scripts, LVS reports and start-up results |
| `PLAN.md` | Chronological project log: pre-registrations, results, bugs, corrections |

## Running

Tools: SKY130 PDK `c6d73a35f524070e85faff4a6a9eef49553ebc2b` (volare 0.20.6), ngspice 47, Magic 8.3.684,
Netgen 1.5.324, KLayout 0.30.12, Python 3.12. The notebook's Section 11 lists every version.

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt          # simulation, analysis, notebook
python3.12 -m venv .venv-layout && .venv-layout/bin/pip install -r requirements-layout.txt   # gLayout / gdsfactory
volare enable --pdk sky130 c6d73a35f524070e85faff4a6a9eef49553ebc2b             # PDK into ~/.volare
```

**Notebook** (replots saved results in seconds; Section 2b can run a live transistor-level demo on Linux or Colab):

```bash
cd notebook && ../.venv/bin/jupyter lab fingerprint_by_design.ipynb
```

**Live demo alone** (two Monte Carlo chips plus the mismatch-free design, about 5 minutes):

```bash
cd sim && ../.venv/bin/python live_demo.py 2 --out /tmp/fbd_demo
```

**Layout rebuild and checks.** The blocks touched by the 2026-10-25 fix rebuild in this order (verified to reproduce the
committed GDS shape-for-shape before the fix); the other blocks have their own generators in `layout/`:

```bash
cd layout && export PDK_ROOT=$HOME/.volare PDK=sky130A
for s in limiter.py lo_path.py bias_block.py out_net.py; do ../.venv-layout/bin/python $s; done
../.venv-layout/bin/python buffers.py lo && ../.venv-layout/bin/python buffers.py out
../.venv-layout/bin/python ldo_block.py && ../.venv-layout/bin/python tx_core.py
bash check.sh ldo_blk && bash check.sh tx_core          # Magic DRC + strict Netgen LVS (fails on property errors)
bash klayout_drc.sh tx_core                             # official SKY130 KLayout deck
klayout -b -r probe_nets.py -rd gds=$PWD/tx_core.gds    # metal-only power connectivity
bash pex.sh tx_core                                     # parasitic extraction
```

**LDO start-up on the extracted layout** (2 ngspice processes at a time):

```bash
LDO_PEX_FILE=$PWD/review/ldo-pex-fixed/ldo_blk_pex_c.spice LDO_OUT=/tmp/ldo_startup .venv/bin/python review/check_ldo.py --pex
```

**Digital front end** (inside the LibreLane 3.0.16 container):

```bash
cd digital
docker run --rm -v "$PWD":/d -v "$HOME/.ciel":/pdk -w /d/tb ghcr.io/librelane/librelane:3.0.16 bash -lc "bash run_tests.sh"   # tests digital/final
docker run --rm -v "$PWD":/d -v "$HOME/.ciel":/pdk -w /d -e PDK_ROOT=/pdk ghcr.io/librelane/librelane:3.0.16 \
  bash -lc "librelane --pdk-root /pdk --run-tag run7 --overwrite config.json"
```

**Studies.** Each result in the notebook maps to a script in `sim/` (notebook Section 11). The full studies take days
of ngspice time and about 55 GB of waveforms (kept outside the repository); `sim/tx_ident.py` (the main
identification driver) now refuses to analyse runs whose ngspice process failed or whose waveforms are incomplete;
the other drivers do not yet have that check.

## License

Apache-2.0 (see `notebook/LICENSE`).
