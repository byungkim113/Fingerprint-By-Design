# Submission validation — 2026-10-31

The submission folder passes the targeted checks below after integrating upstream `f86a0c0`
with the language edits. The six upstream commits preserve the representative designation,
repository rename, review attribution, mismatch-scaling correction and pinned-PDK installer.

## Fresh checks

| Check | Result |
|---|---|
| Actual Jupyter execution from repository root | 14 code cells, 12 embedded figures, no errors |
| Standalone submission copy outside the repository | All 14 code cells execute; 12 figures render using bundled assets |
| Notebook and generator consistency | All 42 cell sources match |
| Figure audit | 28 series/bar-group comparisons across 10 quantitative figures; 2 layout figures render |
| Math/data audit | Python syntax, full-rank observed-level fits, linear-signal residual, downconversion, thermometer codes, RRC energy and classifier comparison pass |
| Bundled artifacts | Simulation scripts and GDS copies match; result JSON agrees with project results; 60 NPZ archives contain finite numeric arrays |
| Digital RTL | 947 checks, zero errors at both supported SPI rates |
| Committed routed gate-level netlist | 947 checks, zero errors at both supported SPI rates, functional/unit-delay cell models |
| Digital negative controls | All three mutations rejected: 560, 376 and 555 errors |
| Analog core: Magic and KLayout DRC | Zero errors in each |
| Analog core: strict LVS | Match, 300 devices, no property errors |
| Standalone LDO: Magic and KLayout DRC | Zero errors in each |
| Standalone LDO: strict LVS | Match, 40 devices, no property errors |
| Metal-only power connectivity | All six probes pass |
| Live-demo installer | Existing pinned PDK and ngspice 47 accepted; version check passes |
| Bundled live transistor simulation | Two mismatch chips plus nominal complete in 6.6 minutes; maximum nominal baseband difference from reference 3.69e-7; distinct finite chip fingerprints |
| Extracted-LDO startup | All 12 cases complete and regulate: -40/27/85 C × 1/10/50/200 us VIN ramps to 3.63 V, 313 ohm load; maximum VOUT 1.93255501 V, below 1.95 V |
| Public access | Project repository and replacement Colab notebook target return HTTP 200 without authentication |

Linux circuit checks used ngspice 47, Magic 8.3.684, Netgen 1.5.324,
KLayout 0.30.12 and SKY130 open_pdks `c6d73a35f524070e85faff4a6a9eef49553ebc2b`.
The live and startup measurements are retained in [final-validation-data.json](final-validation-data.json).

## Changes from the final review

- Retained the upstream withdrawal of the transistor/passive percentage split. The PDK mismatch switch scales
  transistors, poly resistors and MIM capacitors together, so that experiment cannot isolate their contributions.
- Removed repetitive summaries and broad takeaways; tied identification claims to the known 18-frame burst,
  tested SNRs and simulated populations.
- Distinguished normalized feature energy from RF output power and from the mean feature standard deviation
  used as fingerprint size. Explained that stage comparisons do not allocate causal percentages.
- Qualified confidence intervals as approximate noise-trial intervals on fixed virtual chips and shared templates.
- Replaced the dead fork-branch Colab badge with the public project notebook. Updated the PR draft and READMEs.
- Corrected the layout discrepancy count from six to seven devices, matching the original LVS report and
  Appendix A: two limiter resistors, the soft-start capacitor, three coupling capacitors and the bias resistor.
- Made existing math-audit checks fail on artifact or numerical inconsistencies instead of only printing booleans.

## Repeat the checks

With the notebook Python dependencies installed:

```bash
python review/check_submission.py
python review/audit_math.py
python review/audit_notebook_graphs.py
```

In the prepared Linux EDA environment, with the tools and pinned PDK already installed:

```bash
bash review/final_checks.sh tools
bash review/final_checks.sh all
```

The latter writes ignored logs and scratch simulation files under `review/`. The full results can be inspected
in `final-digital.log`, `final-layout.log`, `final-live.log`, `final-setup.log` and `final-ldo.log` after a run.

## Scope and remaining limitations

This check did not rerun the multi-day Monte Carlo study or regenerate every layout. Its raw study waveforms
are not tracked in this repository. The saved results were checked for consistency, while fresh representative
simulations and physical checks exercised the submitted code and committed layouts. The digital place-and-route
flow and nine-corner timing analysis were not rerun; the committed routed netlist was functionally tested.

All identification results remain simulation results. The receiver uses ideal downconversion, an external LO
and, for the headline results, a known repeated frame. Arbitrary-data identification under temperature drift
remains unresolved. The LDO startup check uses archived capacitance extraction at typical process without
mismatch or wire resistance; its worst-case margin is about 17 mV. Schematic zero-volt startup convergence
at 85 C remains unresolved. Analog and digital layouts remain separate, without pads or ESD integration.

The contest pull request has not been opened by this validation run.
