# Notebook graph and number audit

The updated notebook's 9 quantitative figures pass 23 independent checks of their actual plotted lines and bar groups against the bundled JSON data. Its two layout figures also render. The audit executes the code from the notebook itself; it does not replace the plots with newly generated approximations. Run `review/audit_notebook_graphs.py`; the extracted plotted coordinates and values are saved in `review/notebook-graph-data.json`.

## Numerical cross-checks

| Claim or graph | Source-derived value | Displayed interpretation |
|---|---:|---|
| 64-chip identification, 30 dB | 100% | 100% |
| 64-chip identification, 20 dB | 90.8854% | 91% |
| Impostor EER, 30 / 20 dB | 0% / 7.36979% | 0% / 7.37% |
| PA-stage / mixer-stage fingerprint energy | 7.24143× | 7.24× energy |
| Corresponding feature-norm ratio | 2.691× | 2.69× |
| PA split-stage prediction increment | 79.6590 percentage points in R² | 79.7 points |
| LO prediction increment | −0.08844 percentage points in R² | −0.09 points in prose; −0.1 on chart |
| Linear PA, mixer / RF fingerprint size | 0.98985× / 0.62353× | 0.99× / 0.62× |
| Linear PA, 20 dB identification | 96.0417% → 84.5833% | 96% → 85% |
| Linear PA, nominal EVM | 11.3669% → 6.13567% | 11.4% → 6.1% |
| Big DAC, mixer / RF fingerprint size | 0.54298× / 0.85132× | 0.54× / 0.85× |
| Extracted / schematic fingerprint size | 0.993366× | 0.99× |
| Unregulated, −10% supply, 30 dB | 33.75% | 34% |
| Combined-drift mean recovery | 92.35197% | 92% |
| LDO supply sweep, 30 dB | 100% at all seven VIN values | 100% across the tested range |
| Arbitrary data at 85 °C, no LDO / LDO | 50.625% / 49.375% | 50.6% / 49.4% |

## Corrections made

1. The attribution chart previously clipped the negative LO increment to zero. It now retains the signed value.
2. Its labels previously described the values as additive shares of fingerprint variance. They are changes in prediction R², assembled from two separate experiments. Their signed sum is 96.845%, not 100%; the chart and prose now explain that they are not an additive partition.
3. “7× amplification” was ambiguous: the plotted ratio is energy, not amplitude. The text now explicitly says 7.24× energy and gives the corresponding feature-norm ratio.
4. The summary now states that zero impostor EER applies at 30 dB; the plotted 20 dB EER is 7.37%.
5. The arbitrary-data temperature comparison now gives 50.6% versus 49.4%, replacing “about 49% with or without.”
6. The live-demo noise-scaled distance is identified as a diagonal metric on correlated features, not independent standard deviations or a significance level. The illustrated I-real peak difference rounds to about 1.6%; the 0.7% RMS concerns all 88 features.
7. The claim that the live fingerprint comes only from transistor mismatch was corrected to include passive-device mismatch. The outstanding analog LVS errors are also disclosed next to the LDO description.

The plots accurately show the archived simulation results. This does not resolve the separate analog geometry and startup problems documented in `REVIEW.md`, and the source result JSON files were not changed.
