# Circuit, math, notebook, and repository review — 2026-10-24

Reviewed remote commit `bb00f2e`, then made the local fixes described below. The notebook runs, but the analog circuit is **not ready for signoff**. Strict LVS finds device-dimension errors, and LDO startup fails important checks.

## Confirmed circuit problems

### 1. LDO soft-start capacitor is much smaller than specified

`sim/ldo.py` and `layout/ldo_blk.spice` specify a 70 × 70 µm soft-start MIM capacitor. A fresh extraction of the committed GDS gives 30 × 30 µm. Independent inspection of the GDS capacitor-recognition polygons confirms a maximum area of 900 µm², not 4,900 µm², in the LDO block.

This is a real geometry discrepancy, not just a net name or unit conversion. `tx_core` has matching connectivity and 300 merged devices, but Netgen reports **property errors**. The former `layout/check.sh` treated the line “Circuits match uniquely” as sufficient and ignored the subsequent property-error report. That false-pass condition is fixed.

Replacing only the soft-start capacitor value in the schematic bench with the measured 30 × 30 µm dimensions gives these peaks. VIN ramps from 0 to 3.63 V; load is 313 Ω; transient output is measured directly, without window averaging.

| Temperature | VIN ramp | Peak VOUT |
|---|---:|---:|
| −40 °C | 1 µs | 2.196 V |
| −40 °C | 50 µs | 2.313 V |
| 27 °C | 1 µs | 2.334 V |
| 27 °C | 50 µs | 2.153 V |

All exceed the project's 1.95 V criterion. These are capacitor-value sensitivity simulations; see `ldo-layout-values-output/startup.json`.

**Direct capacitance-extracted confirmation:** a fresh Magic extraction of `ldo_blk.gds`, simulated with the same VIN/load conditions, also exceeds the limit in all six tested cases:

| Temperature | 1 µs VIN ramp | 50 µs VIN ramp |
|---|---:|---:|
| −40 °C | 2.247 V | 2.340 V |
| 27 °C | 2.369 V | 2.176 V |
| 85 °C | 2.377 V | 2.126 V |

These transients complete and eventually regulate, but their startup peaks fail. Evidence: `ldo-pex/ldo_blk_pex_c.spice` and `ldo-pex-output/startup.json`. This extraction includes parasitic capacitance, not full wire resistance. Do not interpret steady-state identification results as startup verification.

### 2. Other analog device dimensions also fail strict LVS

| Device | Extracted layout | Schematic |
|---|---:|---:|
| PA coupling capacitors Ccp/Ccn and LO coupling capacitor Clo | 30 × 30 µm | 31 × 31 µm |
| Each limiter's merged feedback resistor length | 139.41 µm | 141 µm |
| Bias-reference n-diffusion resistor length | 78.34 µm | 80 µm |

The primary evidence is in `tx_core_lvs.rpt` and `ldo_blk_lvs.rpt`. The circuits need reconciled geometry and models followed by new extraction and simulation. The GDS was preserved during this review; the circuit was not silently changed to force LVS to pass.

### 3. Zero-volt startup at 85 °C is unresolved even in the intended schematic

The 70 × 70 µm schematic starts and regulates in the tested −40/27 °C cases. At 85 °C, the 1/10/50/200 µs ramps fail numerically or produce incomplete transients. The 1 ms ramp completes but leaves VOUT near zero rather than regulated. A zero return code alone therefore does not establish circuit success. See `ldo-output/startup.json`.

These findings reproduce and extend the convergence limitation already recorded in `PLAN.md`. They do not prove a fabricated chip would fail identically; they mean the available simulations do not establish reliable startup. Startup PVT/mismatch coverage and loop-stability verification remain required.
The extracted circuit does start in the two 85 °C cases above; those runs instead fail the overshoot criterion. Keep schematic convergence failures separate from the demonstrated extracted-circuit overshoot.

## Checks that passed

| Check | Fresh result |
|---|---|
| Real Jupyter execution, launched from repository root | 13 code cells, 11 embedded plots, zero errors |
| Optional live transistor demo, fresh Linux/ngspice 47 run | Two mismatch chips plus nominal, 5.8 minutes |
| Nominal live waveform versus bundled reference | Maximum baseband difference 2.75 × 10⁻⁷ |
| Live chip-pair fingerprint RMS | 0.00633 versus reference 0.00662; platform-dependent mismatch draws are expected |
| Analog core and standalone LDO Magic DRC | Zero errors, Magic 8.3.684 |
| Analog core and standalone LDO KLayout DRC | Zero errors, KLayout 0.30.12 and the pinned PDK deck |
| Metal-only power connectivity probes | All six probes pass; VDD and VSS are distinct |
| Digital RTL | 947 checks, zero errors at each tested SPI rate |
| Committed routed digital netlist | 947 checks, zero errors at each tested SPI rate, unit-delay cell models |
| Digital negative controls | All three mutations detected: 560 / 376 / 555 errors |
| Analog/digital main-study frame agreement | All 128 samples match after portability fix |
| Bundled simulation sources and GDS | Copies agree with project sources/artifacts |
| Python syntax and archived numeric data | Syntax passes; numeric arrays in all 60 source NPZ archives are finite |
| RRC filter | Unit energy |
| Thermometer coding | Correct for all 32 codes |
| Level-fit identifiability | Full rank on observed columns for frames 1–5 and the live demo |
| Mahalanobis and single-component mixture classifier | Agree with independent SciPy distance calculation |
| Git whitespace checks | Pass |

DRC, connectivity, device properties, and electrical behavior are separate checks. The DRC passes do not override the LVS and startup failures above. The archived multi-day Monte Carlo study was not rerun in full.

## Reproducibility fixes made locally

- Notebook setup distinguishes the notebook's result folder from the different `data/` folder at repository root. The executed notebook is `notebook/fingerprint_by_design.ipynb`.
- Main-study sample 44 had an almost-zero Q value; floating-point rounding changed its DAC code across platforms. A canonical copy of the original 128-sample hexadecimal stimulus now preserves the actual study frame, including in the bundled simulator.
- Unobserved DAC levels are excluded from fingerprint features by default. An ideal linear signal otherwise has an artificial residual of about 0.158 RMS on frame 1; with masking the residual is around 7 × 10⁻¹⁶. `--unmasked` retains the old analysis explicitly.
- The SPI interface requires `clk >= 8 × sck`. The former 4× claim fails with 386 errors in the existing testbench. Both 10× and 8× pass at RTL and gate level. Only the interface documentation changed; the routed digital implementation was preserved.
- Digital test failures and timeouts now return failure status. The runner uses the committed final netlist by default, tests 8× operation, and detects compilation/mutation failures reliably.
- Magic/Netgen and KLayout wrappers return failure for failed DRC or device properties. Standard-cell include paths are resolved against the installed PDK, and GDS paths with spaces work.
- Metal probes reject missing nets and report failure through their exit status.
- Shell files use LF endings on Windows checkouts through `.gitattributes`.
- Live-demo reruns reject unsuccessful ngspice processes, incomplete transients, and stale waveform files. LDO recovery checks now require the full 5.12 µs study frame rather than accepting 5.0 µs.
- Notebook and README now disclose the analog verification failures.

## Remaining reproduction and interpretation limits

Some layout generators require ignored, unshipped device assets, including `layout/work/ldo_cells` and `layout/work/passives/r_nd80.gds`. The committed flattened GDS can be checked, but the current checkout does not provide a complete clean-start rebuild of those device cells. Preserve or regenerate and version the missing generator inputs before redesigning the LDO.

Identification percentages concern synthetic virtual chips, a known repeated frame, ideal downconversion, and added AWGN. They are not measured silicon or arbitrary-packet authentication guarantees. The digital and analog blocks remain separate layouts without a complete pad/ESD integration. Model-receiver failures under arbitrary-data temperature drift remain reported honestly.

## Repository state

The initial fast-forward pull encountered rewritten remote history. Both local commits had identical trees to their rewritten equivalents. The original local branch was preserved as `backup/pre-review-20261024`, and `main` was aligned to remote `bb00f2e`. The review fixes and evidence are included together in the subsequent review commit. The original circuit GDS files and archived study result JSON files were preserved.

Verification used the project's pinned SKY130 hash, ngspice 47, Magic 8.3.684, Netgen 1.5.324, and KLayout 0.30.12. The KLayout package came from the [official download page](https://www.klayout.de/build.html); its published package checksum matched. Review scripts in this folder retain the commands and measurements needed to repeat the targeted checks.
