# Fingerprint by Design

**Predicting, tracing and stabilising the RF fingerprint of an open-source SKY130 transmitter, before any silicon exists**

Submission to the IEEE SSCS "Code-a-Chip" Travel Grant Awards at ISSCC 2027 · License: Apache-2.0

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/byungkim113/sscs-ose-code-a-chip.github.io/blob/isscc27-fingerprint-by-design/ISSCC27/submitted_notebooks/fingerprint_by_design/fingerprint_by_design.ipynb)

## Summary

Every radio chip is slightly imperfect, so two chips of the same design send slightly different signals: an
**RF fingerprint**. Fingerprints are normally studied after chips are built. This project asks whether a designer can
predict, explain and control a transmitter's fingerprint at design time, using only the open SkyWater SKY130 PDK.

We designed and verified a transmitter in SKY130:

* an analog core (I/Q current-steering DACs, Gilbert mixers, LO path, PA, output buffer, bias reference) and an on-chip
  LDO regulator with a bandgap reference: DRC-clean in Magic and KLayout and parasitic-extracted, with unresolved
  LVS device-dimension errors described below;
* a digital front end (SPI port, 128-sample frame memory, thermometer decoders) taken through LibreLane to a routed,
  DRC/LVS-clean layout and tested at RTL and gate level.

We then simulated hundreds of Monte Carlo "virtual chips" at transistor level. Key findings:

* Chips of one design are identified at 100% at 30 dB SNR (16 and 64 chips); same-design impostors are rejected.
* Chip-specific fingerprint energy is 7.24x greater after the PA, which also adds its own mismatch; a more
  linear PA shrinks it to 0.62x.
* It survives layout parasitics (0.99x).
* Supply drift, not temperature, breaks it (-10% supply: 100% -> 34%). Design-time drift models recover most of the
  loss; an **on-chip LDO keeps identification at 100% across +-10% supply**.
* Open problem: identifying chips from arbitrary data under temperature drift.

All tests were pre-registered; failures are reported.

**Verification correction (2026-10-24):** the notebook runs successfully, but a fresh analog LVS review found
device-property mismatches that the original check script ignored. In particular, the LDO soft-start capacitor is
30 x 30 um in the GDS versus 70 x 70 um in the schematic. Zero-volt startup tests also fail or do not start at 85 C.
Using the measured capacitor value produces 2.15-2.33 V startup peaks in the tested -40/27 C schematic benches.
A fresh capacitance-extracted LDO run confirms 2.13-2.38 V peaks over six -40/27/85 C startup cases.
See Section 1 of the notebook and `../review/REVIEW.md`; analog circuit signoff remains open.

## Contents

| Path | What it is |
|---|---|
| `fingerprint_by_design.ipynb` | The notebook (story, figures, results, limitations, reproduction guide) |
| `data/` | Result files (JSON) the figures are made from, including our run of the live demo |
| `gds/` | Layout files (gzipped GDS) of the analog core with LDO, and of the digital front end |
| `images/` | Layout renders and explanatory diagrams |
| `setup_tools.sh` | Installs the pinned SKY130 PDK and builds ngspice 47 for the live demo (Linux / Colab) |
| `sim/` | The six project scripts the live demo needs (netlist generator and helpers), copied unchanged |
| `sim/frame128_seed1.hex` | The exact main-study stimulus, avoiding a platform-dependent rounding difference |
| `LICENSE` | Apache License 2.0 |

## Running

* **Default (seconds):** every figure is regenerated from `data/` and `gds/` with `numpy`, `matplotlib` and `gdstk`,
  locally or on Colab.
* **Live transistor-level demo (Section 2b, optional):** set `RUN_LIVE = True` on Colab or Linux. It installs the PDK,
  builds ngspice 47, simulates two virtual chips and the mismatch-free design (about 5 minutes on a laptop, longer on a
  free Colab runtime) and checks the result against ours.
* **Full study (days):** not re-run in the notebook; Section 11 maps each result to its script.

## Reproducing everything

Full source (layout generators, simulation and analysis scripts, digital RTL, testbench and LibreLane configuration,
project log with every pre-registration): <https://github.com/byungkim113/Code-A-Chip>. Section 11 of the notebook
lists the tool versions and the script behind each result.
