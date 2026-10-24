# Fingerprint by Design

**Predicting, tracing and stabilising the RF fingerprint of an open-source SKY130 transmitter, before any silicon exists**

Submission to the IEEE SSCS "Code-a-Chip" Travel Grant Awards at ISSCC 2027 · License: Apache-2.0

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/byungkim113/Code-A-Chip/blob/main/notebook/fingerprint_by_design.ipynb)

## Summary

Every radio chip is slightly imperfect, so two chips of the same design send slightly different signals: an
**RF fingerprint**. Fingerprints are normally studied after chips are built. This project asks whether a designer can
predict, explain and control a transmitter's fingerprint at design time, using only the open SkyWater SKY130 PDK.

We designed and verified a transmitter in SKY130:

* an analog core (I/Q current-steering DACs, Gilbert mixers, LO path, PA, output buffer, bias reference) and an on-chip
  LDO regulator with a bandgap reference: DRC-clean in Magic and KLayout, LVS-matched, parasitic-extracted;
* a digital front end (SPI port, 128-sample frame memory, thermometer decoders) taken through LibreLane to a routed,
  DRC/LVS-clean layout and tested at RTL and gate level.

We then simulated hundreds of Monte Carlo "virtual chips" at transistor level. Key findings:

* Chips of one design are identified at 100% at 30 dB SNR (16 and 64 chips); same-design impostors are rejected.
* The fingerprint starts as DAC/mixer mismatch and is amplified about 7x by the PA, which also adds its own; a more
  linear PA shrinks it to 0.62x.
* It survives layout parasitics (0.99x).
* Supply drift, not temperature, breaks it (-10% supply: 100% -> 34%). Design-time drift models recover most of the
  loss; an **on-chip LDO keeps identification at 100% across +-10% supply**.
* Open problem: identifying chips from arbitrary data under temperature drift.

All tests were pre-registered; failures are reported.

## Contents

| Path | What it is |
|---|---|
| `fingerprint_by_design.ipynb` | The notebook (story, figures, results, limitations, reproduction guide) |
| `data/` | Result files (JSON) the figures are made from, including our run of the live demo |
| `gds/` | Layout files (gzipped GDS) of the analog core with LDO, and of the digital front end |
| `images/` | Layout renders and explanatory diagrams |
| `setup_tools.sh` | Installs the pinned SKY130 PDK and builds ngspice 47 for the live demo (Linux / Colab) |
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
