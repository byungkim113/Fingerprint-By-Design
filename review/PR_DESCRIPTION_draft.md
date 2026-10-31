## ISSCC27: Fingerprint by Design — predicting, tracing and stabilising the RF fingerprint of an open-source SKY130 transmitter

**Folder:** `ISSCC27/submitted_notebooks/fingerprint_by_design/` · **Notebook:** `fingerprint_by_design.ipynb` · **License:** Apache-2.0
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/byungkim113/Fingerprint-By-Design/blob/main/notebook/fingerprint_by_design.ipynb) — by default it replots saved results in seconds; Section 2b runs a transistor-level simulation live.

| Name | Affiliation | IEEE Member | SSCS Member | Email |
|---|---|---|---|---|
| Byung Kim (Leader) | United States Air Force Academy | No | No | c29byung.kim@afacademy.af.edu |
| Yucheng Wang (Representative) | University of Wisconsin-Madison | No | No | ywang3574@wisc.edu |

**Designated representative (attends ISSCC 2027 in person):** Yucheng Wang · **Applicant category:** undergraduate student

### Question

Can a circuit designer predict, explain and control a transmitter's fingerprint at design time, using only the open PDK, before any silicon exists?

### What was built (SKY130, open-source tools only)

- **Transmitter:** I/Q unary current-steering DACs, Gilbert mixers, LO path with RC-CR quadrature, PA, output buffer,
  bias reference, and an on-chip LDO with a bandgap reference. 543 x 398 um; DRC 0 in Magic and KLayout; strict LVS
  match (300 devices, device sizes included); parasitic extraction. The regulator's start-up was checked on the
  extracted layout: 1.80-1.93 V peak across -40/27/85 C and 1-200 us supply ramps (limit 1.95 V).
- **Digital front end** (SPI, 128-sample frame memory, thermometer decoders) through LibreLane: 290 x 301 um, timing met
  at 9 corners, DRC/LVS clean, 947/947 checks at RTL and on the routed gate-level netlist. A separate block, not yet
  integrated with the analog core.

### Main results (transistor-level Monte Carlo; extraction comparison in the notebook)

- **Identification:** 100% at 30 dB SNR per sample for 16 and 64 chips, when each decision averages an 18-frame,
  92 us burst of a known 128-sample frame (89% / 73% from a single frame). Same-design impostors: 0% equal error rate
  at 30 dB.
- **Where it comes from:** DAC and mixer mismatch, 7.24x more chip-specific feature energy after the PA, plus the PA's own
  mismatch.
- **A design lever:** a more linear PA shrinks the fingerprint to 0.62x (prediction confirmed). Increasing DAC transistor area by 4x
  reduces fingerprint size to 0.54x at the mixer and 0.85x at the RF output; the predicted RF reduction was not met.
- **Layout:** the fingerprint survives parasitic extraction (0.99x).
- **Drift:** in this setup (external LO, known repeated frame), supply drift breaks it more than temperature does:
  -10% supply drops identification from 100% to 34%. Drift models learned only from wrong-corner design-time chips
  recover most of the loss, and the on-chip LDO maintains 100% identification at all seven tested supply values spanning +-10% at 30 dB,
  using the known 18-frame burst.

### Rigor and reproducibility

- The main tests were pre-registered (prediction and pass rule written down before running); failed predictions are
  reported, and post hoc analyses are labelled.
- Section 2b installs the pinned PDK, builds ngspice 47, simulates two virtual chips plus the mismatch-free design, and
  checks the result against ours. Tool versions and the script behind every result are listed.
- A review of the verification by co-author Yucheng Wang found seven layout devices drawn at the wrong size (missed by
  our first LVS script). They were fixed and re-verified.

### Limitations (stated in the notebook)

- Simulation only; the only chip-to-chip randomness is the PDK's mismatch model.
- Identification uses a known sequence; arbitrary data under temperature drift remains unsolved.
- The digital front end is not integrated with the analog core; there are no pads or ESD protection.
