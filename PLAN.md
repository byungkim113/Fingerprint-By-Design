# Fingerprint-by-Design — ISSCC 2027 Code-a-Chip submission

Goal: transistor-level (SKY130, ngspice) study of where a transmitter's RF
fingerprint originates, why it drifts with temperature, and which block gives
a fingerprint that is both unique and temperature-stable.

Deadline: **2026-10-09 11:59 AM PT** (GitHub README). SSCS page says Oct 31 —
treat Oct 9 as binding unless organizers confirm otherwise.
Submission: PR to sscs-ose/sscs-ose-code-a-chip.github.io under
`ISSCC27/submitted_notebooks/<project_name>/` with notebook + Apache-2.0 LICENSE.

## Environment (done 2026-09-30)
- ngspice 47 (Homebrew), Python 3.12 venv at `.venv`
- SKY130 via volare, version c6d73a35…, root `~/.volare/sky130A`
- Mismatch: `.lib ... tt_mm` (mc_mm_switch=1); per-instance independent.
  Loop chips in one session with `setseed N` + `mc_source` (lib load ≈11 s,
  per-chip cost small). `.spiceinit` copied from PDK `spinit`.

## Transmitter model (baseband-equivalent, per virtual chip)
- I-DAC, Q-DAC: 5-bit unary (31 unit NMOS current sources) → gain/offset
  imbalance, code-dependent nonlinearity
- PA: CS NMOS (W10/L0.15, mirror-biased, 1k‖100f load) driven at 200 MHz;
  AM/AM and AM/PM from `fourier` fundamental vs input amplitude (8 levels)
- LO quadrature: RC-CR network (res_high_po_0p35 L=5, cap_mim_m3_1 7.8x7.8)
  at 200 MHz; res_high_po has per-instance mismatch (~1%, verified)
- Conditions: T ∈ {-40, 0, 27, 55, 85} °C, VDD ±10%

## Steps
- [x] 1. Tools + PDK + mismatch smoke test
- [x] 2. DAC unit-current extraction across chips × temps (data/dac_200.npz)
- [x] 3. PA extraction (data/pa_200.npz, 5 T × 3 VDD)
- [x] 4. LO quadrature block: RC-CR, res_high_po + cap_mim (data/lo_200.npz)
- [x] 5. Python: compose QPSK I/Q waveforms per chip/condition + AWGN (analysis/txmodel.py)
- [~] 6. Classifier (analysis/train.py, results/*.json); first runs done, single seed, SNR 20 dB only
- [ ] 7. Design fix: temperature-stable fingerprint features/block
- [ ] 8. DAC unit-array layout (gLayout/Magic), DRC/LVS
- [ ] 9. Notebook, README, LICENSE, PR

## Log
- 2026-09-30: env set up, mismatch MC verified (2 NMOS, 4 seeds, independent).
- 2026-09-30: seed 0 in ngspice setseed is not deterministic -> seeds start at 1;
  always call mc_source after setseed. Same seed = same chip across T (corr ≥0.998).
- 2026-09-30: all 3 blocks simulated (200 chips × 5 T; PA also × 3 VDD).
  Score = between-chip σ / within-chip-over-T σ (raw | common-mode drift removed):
  LO I/Q phase 71 | 71; DAC unit pattern ~13 | 13; LO I/Q gain 1.1 | 52;
  PA gain 0.08 | 3.9; PA compression 0.14 | 4.3; PA AM/PM 2.8 | 5.1.
  -> PA features drift most; LO phase error is unique AND stable. (analysis/features.py)
- 2026-09-30: user confirms permission to reuse code from
  github.com/Richard-Y-W/FeedGuard-market-data-integrity-and-fault-detection-coprocessor
  (repo has no LICENSE file) -> credit it in notebook References.
- 2026-09-30: step 5-6 first results (1D CNN, 200 chips, train 27C, 40 bursts/chip, SNR 20 dB, 1 seed):
  all blocks:  -40 .30 | 0 .73 | 27 .96 | 55 .64 | 85 .18
  DAC only:    -40 .26 | 0 .56 | 27 .86 | 55 .43 | 85 .16
  LO only:     -40 .01 | 0 .05 | 27 .23 | 55 .04 | 85 .01
  PA only:     chance (0.5%) at all T  (PA fingerprint ~0.06% of signal, below noise)
  Mechanism for DAC drift: mismatch pattern SHAPE is stable (corr ≥0.999 vs 27C) but its
  AMPLITUDE scales with T (×1.16 at -40C, ×0.90 at 85C). CNN keys on absolute amplitude.
  LO gain imbalance has common drift 0.4 dB > chip σ 0.156 dB.
  -> parameter-level stability ≠ classifier robustness. Candidate fixes: amplitude-normalized
  (shape-only) DAC matching; circuit bias with T-insensitive mismatch (step 7).
- 2026-09-30: BUG FIXES in analysis: (1) txmodel PA clamped amplitude below first measured
  drive (now interpolates gain); (2) receiver symbol reconstruction must use the same
  constellation expression as TX (mid-code rounding flips at x=0). CNN rerun after fix:
  -40 .30 | 0 .75 | 27 .96 | 55 .65 | 85 .19 (results/full_snr20_v2.json) — unchanged.
- 2026-09-30: shape-only test (analysis/feature_match.py). Features = deviation of each
  observed DAC level (codes 5-26, I and Q) from ideal, per burst, LDA fitted on 27C
  enrollment (40 bursts/chip), 1 burst per decision, SNR 20 dB:
    absolute (Euclid in LDA space): -40 .59 | 0 .94 | 27 .99 | 55 .89 | 85 .45
    shape (cosine in LDA space):    -40 .48 | 0 .79 | 27 .91 | 55 .72 | 85 .30
  -> HYPOTHESIS FAILED: shape-only is worse at every T.
  -> Explicit LDA features beat the CNN at every T (2x at -40/85C).
  Drift decomposition (noise-free, 60 chips): 89-95% of drift energy is a COMMON shift
  shared by all chips; per-chip scaling only 3-8% (k=1.15 @-40, 0.91 @85); other 2-3%.
  Next candidate: remove common-drift subspace learned from a separate design-time chip
  population (no per-device temperature needed if subspace is low-dimensional).
- 2026-09-30: seeds 1,2 of 200-chip LDA test: absolute -40 .58/.59 | 27 .99/.99 | 85 .47/.46;
  shape consistently worse. Stable to ~±1%.
- 2026-09-30: SHARED-DRIFT TEST (analysis/drift_test.py, results/drift_test.json).
  Design-time pop = chips 150-199 (noise-free), deployed = chips 0-149, 3 seeds, SNR 20.
  Design drift is rank 1 (99.0% energy in one direction).
    baseline   -40 .630 | 0 .954 | 27 .990 | 55 .905 | 85 .498
    subspace   -40 .852 | 0 .972 | 27 .978 | 55 .958 | 85 .881   (no temp sensor)
    known_temp -40 .907 | 0 .989 | 27 .990 | 55 .978 | 85 .928   (needs temp sensor)
  Gap recovered by subspace: 61.7% @-40, 78.0% @85 -> pre-set criterion (>=50%) MET.
  Cost: -1.2 pts at 27C. Caveat: design & deployed chips share the same simulator
  (circularity) -> next: learn drift from a mis-specified model (other corner).
- 2026-09-30: REALISM CHECK (mis-specified design model). Design-time 50 chips re-simulated
  at wrong corners (data/design_<corner>_{dac,pa,lo}.npz, seeds 151-200); deployed 150
  chips stay tt_mm. 3 seeds each. Gap recovered by subspace (-40C / 85C), cos(drift dir, true):
    tt_mm (exact)  61.7% / 78.0%   cos 1.000
    ss_mm          61.3% / 75.1%   cos 0.998
    ff_mm          59.4% / 73.6%   cos 0.998
    ss_hh_mm       64.1% / 67.3%   cos 0.987
    ff_ll_mm       56.8% / 72.0%   cos 0.979
  Criterion (>=50%) MET for every corner. Drift direction is set by circuit topology,
  not by process corner. Limitation: corners are the PDK's own model family; real
  model-to-silicon error and unmodeled effects are not covered.
  (results/drift_test_<corner>.json; drift_test.json = tt 3 seeds, regenerated after an
  accidental overwrite by a seed-0 regression check.)
- 2026-09-30: sim scripts now take SKY130_CORNER and CHIP_SEED0 env vars; refactor
  verified bit-identical (DAC chips 151-153, drift_test seed 0).
- 2026-09-30: NOISE SWEEP (drift_test, tt, 3 seeds). Gap recovered by subspace (-40 / 85C):
    10 dB 19% / 30% (NOT MET; subspace also costs 27C acc .61->.53)
    15 dB 45% / 59% (-40 NOT MET)   20 dB 62% / 78%   25 dB 68% / 85%   30 dB 68% / 88%
  -> fix works at >=20 dB; fails at low SNR. Report as limitation.
- 2026-09-30: LAYOUT TOOLS: KLayout 0.30.12 (brew cask; PDK has drc/lvs decks),
  Netgen 1.5.324 + Magic built from source into ~/.local/bin (Tcl via brew tcl-tk@8,
  X11 via brew libx11; CFLAGS -Wno-implicit-function-declaration etc.). Magic needs
  PDK_ROOT=~/.volare. gLayout 0.2.0 in .venv-layout (Python 3.11; 3.12 fails on numpy pin).
- 2026-09-30: MODEL-ASSUMPTION CHECK: DAC offset referenced to fixed nominal (default) vs
  differential (own total current). Differential (drift_test_diff.json): common-drift
  fraction 97-99% (vs 87-94%) -> finding NOT an artifact. Baseline lower (27C .86, 85C .08);
  subspace: -40 .28->.75, 85 .08->.63 (82% / 71% gap recovered); 27C cost .86->.74.
- 2026-09-30: second DAC design sim/dac_cascode.py (cascoded, W2/L0.5 src, W2/L0.15 cas,
  Iref 20u, Vcas 1.0 V; Vcas 0.7 starved units). Unit ~17.7 uA, mismatch 3.9%->3.6% over T.
- drift_test.py now argparse: --seeds --corner --snr --dac {dac,dac2} --differential;
  result file tagged by options (non-default seeds tagged too, after 2 accidental overwrites).
- 2026-09-30: SECOND DESIGN (cascode DAC, dac2), 3 seeds, SNR 20:
    tt design model: common-drift 79-83% (design 1: 87-94%); gap recovered -40 54% MET,
      85 45% NOT MET. baseline -40 .12 | 27 1.00 | 85 .35; subspace -40 .60 | 85 .64;
      known_temp only .61/.73 -> more per-chip (non-common) drift than design 1.
    ss_hh_mm design model: cos(drift dir) 0.873 (design 1: 0.987); gap recovered 43% / 7%
      NOT MET; known_temp with wrong model makes it WORSE (-40 .07, 85 .34).
  -> "drift direction set by topology, robust to corner" holds for design 1 only.
     Design-dependent: simple long-L mirror DAC -> common, corner-robust drift; cascode
     short-L DAC -> less common, corner-sensitive drift. (2 designs only: not a general law.)
- 2026-09-30: LAYOUT dac_array (layout/dac_array.py, check.sh): 1x32 row, 31 units + ref
  diode, centre-out unit order, met1 gate/source buses, p+ tap ring. 89.6 x 5.8 um.
  Magic drc(full): 0 errors. Netgen LVS: MATCH, 32 devices.
  Fixes on the way: gLayout sky130 glayer names shifted (its met1 = li1) -> pin layer from
  port; ring centred on bbox that included itself; flatten() renames cell (-> DRC ran on
  empty cell!); ring move must be grid-snapped (licon.1/.2 errors otherwise).
- 2026-09-30: NN queue restarted: ResNet ch=32 (0.69M params; ch=64 took 2.7 min/epoch);
  all-T training uses same 40 bursts/chip total (8 per T), not 200.
- 2026-09-30: CNN baselines (200 chips, SNR 20, 3 seeds, same 40 bursts/chip budget):
    trained 27C only : -40 .32 | 0 .76 | 27 .96 | 55 .65 | 85 .19
    trained all 5 T  : -40 .92 | 0 .91 | 27 .93 | 55 .93 | 85 .86   (needs every device
      recorded at every temperature). Physics+subspace (150 chips, no multi-T recordings):
      -40 .85 | 85 .88 -> comparable to the all-T CNN upper bound.
- 2026-09-30: LAYOUT rccr (layout/rccr.py, gen_rccr_cells.sh): Magic-generated
  res_high_po_0p35 L=5 x2, cap_mim_m3_1 7.8x7.8 x2, metal-4 routing. 23.9 x 37.0 um.
  LVS MATCH (4 devices). Magic drc(full): 2 x rpm.1 intrinsic to Magic's generated
  0p35 resistor (standalone generated cell shows it too; adding a wider 86/20 marker has
  no effect since Magic regenerates RPM). KLayout official deck blocked: Homebrew
  KLayout.app is quarantined by macOS (user decision needed to clear).
- 2026-09-30: KLayout unquarantined (user approved). Official deck (FEOL+BEOL+offgrid):
  dac_array 0 errors (clean in Magic AND KLayout). rccr: fixed ct.1_b (my via stacks
  added a 2nd mcon over the resistor's own contacts -> start at metal 1); remaining
  rpm.1a x2 confirmed by both tools = Magic-generated res_high_po_0p35 marker 0.75 um
  < 1.27 um. Known limitation (fix = wider resistor, would change the simulated LO).
  KLayout renders with sky130A.lyp: figures/klayout_*.png. PA layout: skipped (user).
- 2026-09-30: PRE-REGISTERED generalization test (written before running):
  Designs: D1 dac (simple W0.5/L1, 10u), D2 dac2 (cascode W2/L0.5+W2/L0.15, 20u),
    D3 short-L simple, D4 high-current simple, D5 ZTC-biased simple, D6 long-L cascode.
  Methods: M2 = drift subspace from union of wrong corners {ss,ff,ss_hh,ff_ll} (tt,
    the deployed process, excluded); M3 = M2 + per-chip bounded scale fit.
  Pass per design: >=50% gap recovered at BOTH -40 and 85C (SNR 20, 3 seeds, 150 chips).
  "Generalizes" = pass on all 6 designs; "partial" = pass on a majority.
  Circuit hypothesis: ZTC bias (D5) reduces baseline drift vs D1.
  ZTC (tt, W0.5/L1 NMOS, -40 vs 85C): Vgs ~0.95 V, Id ~7.1 uA. D1 (10u) sits at ~1.02 V,
  already near ZTC. ADDED before running: D7 low-current simple (1 uA, far below ZTC).
  Bias axis: D7 1u | D5 7.1u (ZTC) | D1 10u | D4 40u. Now 7 designs; "generalizes" = all 7.
  M3 scale bounds fixed before running: k in [0.7, 1.4]. Script: analysis/generalize.py.
- 2026-09-30: LVS negative control: via added at VSS-strap/VI-wire crossing -> LVS MISMATCH (3 vs 4 nets, VI merged with VSS). Confirms LVS catches overlap shorts; files removed.
- 2026-09-30: generalize D1 (dac): M2 (wrong-corner union) PASS -40 63% / 85 77%; M3 (+scale) PASS 73% / 79% but costs 27C (.98 -> .93); M1 62/78%.
- 2026-09-30: generalize D4 dac_hi (40u): baseline collapses (27 .93, -40 .07, 85 .02); drift
  98-99% common, align .995. M2 PASS 56%/56% but 27C cost .93->.76; M3 PASS 51%/52% (27C .64).
- 2026-09-30: generalize D5 dac_ztc (7.1u): most T-robust baseline so far (-40 .69 | 27 1.00 |
  85 .58; D1 .63/.50). M2 FAIL 49%/69% (-40 just under); M3 PASS 66%/73% (27C .96).
- 2026-09-30: NN baselines complete (200 chips, SNR 20, 3 seeds, 40 bursts/chip):
    CNN    t27  -40 .32 | 27 .96 | 85 .19     all-T  -40 .92 | 27 .93 | 85 .86
    ResNet t27  -40 .26 | 27 .93 | 85 .15     all-T  -40 .87 | 27 .91 | 85 .82
  ResNet (0.69M) is no better than the small CNN. Physics+M2 (D1, 150 chips, 27C-only
  enrollment): -40 .86 | 27 .98 | 85 .88.
- 2026-09-30: generalize D3 dac_sl (short L, ~10% mismatch): common drift only 22-39%;
  baseline -40 .79 | 27 1.00 | 85 .76 (robust w/o fix). M2 FAIL -30%/-20% (hurts);
  M3 FAIL 30%/24%.
- 2026-09-30: generalize D7 dac_lo (1u, ~9% mismatch): common drift 19-39%; baseline
  -40 .41 | 27 1.00 | 85 .77. M2 FAIL -8%/-18% (hurts); M3 FAIL 2%/-3%.
  PATTERN: subspace removal helps only when the common-drift fraction is high
  (D4 98%, D1 87-94%, D5 82-92% -> recover ~50-77%; D3/D7 19-39% -> hurts).
  Common-drift fraction is computable from design-time simulation alone -> candidate
  predictor of whether to apply the fix (to test across all 7 designs).
- 2026-09-30: PRE-REGISTERED PREDICTOR (written before dac_casL / dac2 results):
  Rule: apply drift removal (M2) iff the design-time common-drift fraction >= 0.60, where
  the fraction is the mean over T in {-40,0,55,85} computed ONLY from the four wrong-corner
  design populations (noise-free), never from deployed tt chips. Threshold 0.60 set from the
  first 5 designs (helps: >=0.82; hurts: <=0.39). "Correct" = rule says apply and M2 improves
  both extremes over baseline, or rule says don't and M2 does not improve both.
  Held-out test designs: dac_casL, dac2.
- 2026-09-30: generalize D6 dac_casL: common 94-98%; baseline collapses (-40 .04, 85 .01);
  M1 PASS 64/71%; M2 FAIL 35/24% (big absolute gain .04->.36, .01->.25); M3 FAIL 41/26%.
- 2026-09-30: generalize D2 dac2 (multi-corner now): M2 44/43% FAIL (was 43/7% with a single
  wrong corner -> multi-corner model fixes most of the corner problem); M3 PASS 61/59%.
- PRE-REGISTERED TALLY (pass = >=50% gap at both extremes):
    M2 (multi-wrong-corner): D1, D4 pass -> 2/7  -> does NOT generalize
    M3 (+scale fit)        : D1, D2, D4, D5 pass -> 4/7 -> "partial" (majority)
    Fails for all methods: D3 dac_sl, D7 dac_lo (low common drift), D6 dac_casL (M1 passes,
    wrong-corner model misaligned: align .976 still not enough when baseline ~0).
- PREDICTOR (analysis/predictor.py, results/predictor.json): design-time common-drift
  fraction (wrong corners only) >= 0.60 -> apply. Correct on 7/7 designs incl. 2/2 held out
  (dac_casL .946 apply, helps; dac2 .824 apply, helps). Caveat: threshold set on 5 designs,
  only 2 held out, and the two groups are far apart (<=0.33 vs >=0.82).
  "Correct" = sign of M2 effect at both extremes, not the 50% criterion.
- 2026-09-30: PRE-REGISTERED M4 "simulation-informed drift covariance" (before running):
  Drift field from the four WRONG-corner design populations only (noise-free): for every
  design-time chip and T != 27C, d = f(T) - f(27C) (common + per-chip parts together).
  Sigma_T = mean(d d^T) (uncentred, so the shared shift is penalised too).
  Receiver: enrollment noise covariance S_w (Ledoit-Wolf on within-chip residuals, 27C)
  + lambda * Sigma_T with lambda = 1 fixed (no tuning); nearest enrolled chip mean under
  the Mahalanobis distance of S = S_w + Sigma_T.
  Pass per design: >=50% gap recovered at both -40 and 85C (3 seeds, SNR 20, 150 chips).
  "Generalizes" = all 7 designs. Secondary: no-harm = M4 >= baseline at both extremes on
  every design. Script: analysis/drift_cov.py.
- 2026-09-30: M4 RESULTS (analysis/drift_cov.py, results/drift_cov_<design>.json, 3 seeds):
  control M4_0 (lambda=0) tracks the LDA baseline on all designs (classifier check OK).
  design     base -40/27/85    M4 -40/27/85    gap rec -40/85   pass  no-harm
  D1 dac     .63/.99/.50       .94/.96/.90     87% / 81%        PASS  yes
  D2 dac2    .12/1.0/.35       .86/.92/.86     84% / 79%        PASS  yes
  D5 ztc     .69/1.0/.58       .95/.97/.91     86% / 80%        PASS  yes
  D4 hi      .07/.93/.02       .66/.68/.56     68% / 59%        PASS  yes
  D7 lo      .41/1.0/.77       .98/1.0/1.0     96% / 100%       PASS  yes
  D3 sl      .79/1.0/.76       1.0/1.0/1.0     100% / 100%      PASS  yes
  D6 casL    .04/.98/.01       .63/.76/.49     63% / 49%        FAIL (85C, 1.2 pts short)  yes
  PRE-REGISTERED VERDICT: 6/7 pass -> "partial" (majority), NOT "generalizes" (needs 7/7).
  No-harm met on 7/7. Cost at 27C is large on low-mismatch designs (D4 .93->.68,
  D6 .98->.76, D2 1.0->.92). lambda 0.25/4 are diagnostics only (0.25 trades less 27C
  cost for less extreme-T gain); not used for the verdict.
- 2026-09-30: LITERATURE CHECK (novelty of M4). Temperature-robust RFF methods found all use
  measured data: multi-temperature training, per-temperature models, temperature-sensor
  input, or CFO removal (TeRFF, RF-TESI, TEA-RFF, arXiv 2607.25070 and its cited work).
  Closest: "RF Impairment Model-Based IoT PHY Identification for Domain Generalization"
  (2022) and arXiv 2607.09760 (physics-informed, cross-environment) use behavioural
  impairment models for augmentation, not transistor-level simulation, not temperature.
  M4's math = WCCN / nuisance-covariance (Hatch et al. 2006; NAP) -> must cite.
  Not checked: MDPI Electronics 15(6):1309 (2026 review on feature drift modelling, 403).
- 2026-09-30: FRESH HELD-OUT DESIGNS (defined before any method sees them):
  F1 dac_big  : simple W1/L2, Iref 10u (large area, low mismatch)
  F2 dac_mid  : simple W0.5/L0.5, Iref 15u
  F3 dac_cas2 : cascode src W1/L1 + cas W1/L0.5, Iref 20u, Vcas 1.3 V
- 2026-09-30: PRE-REGISTERED A and B (written before running either):
  A = M4A: lambda chosen per design from design-time data only. Leave-one-wrong-corner-out:
      Sigma_T from 3 corners, held-out corner's 50 chips simulated at SNR 20 (20 enroll bursts
      at 27C, 5 test bursts per T), grid lambda in {0,.03,.1,.25,.5,1,2,4}; pick lambda with
      the best mean accuracy over the 5 temperatures averaged over the 4 folds. Deployed tt
      chips are never used for selection.
  B = M5: temperature-marginalised likelihood. Score(chip c) = log sum_k N(v; mu_c + m(T_k),
      S_w + C(T_k)), uniform over T_k on a 5 C grid -40..85; m(T) = mean wrong-corner drift,
      C(T) = covariance of chip-specific drift around m(T); both linearly interpolated in T
      from the simulated temperatures. When testing at 0 or 55 C the simulated point at that
      temperature is EXCLUDED from the interpolation (no exact-temperature leakage); -40/85
      are the range ends and stay. No free parameters.
  Criteria (each method): pass = >=50% gap recovered at both extremes; secondary = 27C
      accuracy within 2 points of baseline; no-harm at both extremes.
  The 7 earlier designs are DEVELOPMENT designs (already seen). The generalization claim is
  made ONLY on the 3 fresh designs F1-F3: "generalizes" = pass on 3/3 fresh designs.
- 2026-09-30: ENVIRONMENT MOVE. Desktop is iCloud-synced; disk ~90% full -> macOS evicted
  project files (dataless placeholders) -> EOFError crashes in parallel runs. Fixes:
  (1) generalize._npz loads each archive once into memory and closes it; (2) evicted data
  re-downloaded (brctl); (3) Python envs rebuilt OUTSIDE iCloud: ~/venvs/rffp (py3.12) and
  ~/venvs/rffp-layout (py3.11) from requirements.txt / requirements-layout.txt (versions
  taken from installed dist-info names). Desktop alias "venvs" -> ~/venvs. Old .venv dirs
  deleted. Verified: drift_test seed 0 reproduces exactly; dac_array DRC 0 (Magic+KLayout),
  LVS match. Use ~/venvs/rffp/bin/python and ~/venvs/rffp-layout/bin/python from now on.
- 2026-09-30: HELD-OUT VERDICT (fresh F1-F3, 3 seeds, SNR 20; methods fixed beforehand):
  design      base -40/27/85   M4 -40/27/85    M4A -40/27/85   M5 -40/27/85
  F1 dac_big  .40/.93/.26      .80/.85/.73 P   .81/.91/.67 P   .83/.90/.80 P (27C cost 3.8)
  F2 dac_mid  .74/1.0/.68      .97/.99/.95 P   .96/1.0/.93 P   .98/1.0/.97 P (cost 0.3)
  F3 dac_cas2 .01/.95/.01      .57/.63/.46 F   .55/.77/.44 F   .61/.84/.46 F (85C 48.3%)
  All three methods: 2/3 fresh designs -> pre-registered "generalizes" (3/3) NOT met.
  No-harm: 3/3 for all methods. lambda selected 0.25 on all fresh designs.
  Cascoded DACs (D6 dev, F3 fresh) fail every method at 85C (~46-49% gap recovered):
  their fingerprint is ~1% identifiable at the extremes without correction.
- 2026-09-30: FULL TABLE (accuracy % at -40/27/85C; P/F = >=50% gap at both extremes):
         base        M4          A (M4A)     B (M5)      M4/A/B
  D1     63/99/50    94/95/90    93/98/88    95/98/93    P/P/P
  D2     12/100/35   86/92/86    86/96/85    87/99/92    P/P/P
  D5     69/100/58   95/97/91    93/99/89    96/99/94    P/P/P
  D4     7/93/2      66/68/56    69/79/56    73/83/59    P/P/P
  D7     41/100/77   98/100/100  98/100/100  99/100/100  P/P/P
  D3     79/100/76   100/100/100 100/100/100 100/100/100 P/P/P
  D6     4/98/1      63/76/49    64/82/48    70/92/45    F/F/F
  F1     40/93/26    80/85/73    81/91/67    83/90/80    P/P/P   (held out)
  F2     74/100/68   97/99/95    96/100/93   98/100/97   P/P/P   (held out)
  F3     1/95/1      57/63/46    55/76/44    61/84/46    F/F/F   (held out)
  All three methods 8/10 overall, 2/3 held out. B (M5) best: highest extreme-T accuracy on
  9/10 designs and lowest 27C cost on most. Failures D6, F3: NOT "all cascodes" (D2 is a
  cascode and passes); common factor = near-zero baseline at the extremes (1-4%), i.e.
  fingerprint tiny relative to drift. Correction to earlier note claiming cascodes fail.
- 2026-10-02: PRE-REGISTERED (before running):
  (1) RC-CR PEX: extract layout/rccr.gds with parasitic C (Magic), simulate nominal (tt, no
      mismatch) I/Q gain imbalance and phase error at 200 MHz vs the schematic at -40/27/85C,
      and 50-chip mismatch MC for chip-to-chip spread. Report the shift; "layout-safe" if the
      nominal phase error moves < 1 deg and the chip-to-chip spread changes < 20%.
  (2) NOISE SWEEP for B (M5): SNR 10, 15, 25, 30 dB on D1, F1, F2 (3 seeds). Baseline = the
      same Mahalanobis matcher with no drift model (lambda = 0). Operating range claimed =
      lowest SNR at which M5 passes (>=50% gap at both extremes) AND no-harm on all 3 designs.
  (3) LEARNED FEATURES: replace DAC level-deviation features with the 128-d embedding of the
      27C-trained CNN (penultimate layer); apply M5 unchanged in that space (drift model from
      wrong-corner design chips passed through the same CNN, noise-free, mean of 4 bursts).
      Designs D1 and F2, 3 seeds, SNR 20. Pass = >=50% gap at both extremes vs the CNN's own
      embedding baseline (no drift model). Compared also to the CNN softmax accuracy.
- 2026-10-02: RC-CR PEX (sim/rccr_pex.py; layout/work/rccr_pex/rccr_pexc.spice). Magic C-only
  extraction (connectivity identical to schematic: 4 devices + 5 parasitic C: VI-VSS 9.1 fF,
  IN-VQ 5.9 fF, VQ-VSS 4.7 fF, IN-VSS 3.2 fF). R extraction (extresist) corrupted net names
  (VI merged into VQ) -> not used; C-only is a stated limitation.
  Result: layout adds a COMMON offset (+0.34 dB gain, -0.31 deg phase) identical at -40/27/85C
  and on every chip; temperature drift of the imbalance unchanged (0.40 dB over -40..85C);
  chip-to-chip spread gain -13%, phase +1.5%. Pre-registered verdict: LAYOUT-SAFE.
- 2026-10-02: NOISE SWEEP for B (M5), 3 seeds, gap recovered -40/85C (P/F), all no-harm:
          10 dB        15 dB        20 dB (earlier)  25 dB        30 dB
  D1      30/29 F      59/61 P      88/88 P          98/98 P      100/100 P
  F1      58/36 F      64/57 P      81/81 P          90/93 P      97/98 P
  F2      22/22 F      62/60 P      91/91 P          99/99 P      100/100 P
  Pre-registered operating range: B passes on all 3 designs from 15 dB up; fails at 10 dB
  (but never hurts, unlike the earlier projection method). 27C cost at 15 dB: 3-9 pts.
- 2026-10-02: LEARNED FEATURES (CNN 128-d embedding + M5), 3 seeds, SNR 20:
          softmax -40/27/85   BASE -40/27/85   M5 -40/27/85   gap rec    verdict
  D1      33/95/18            53/98/39         70/98/61       38%/38%    FAIL (no-harm, 0 cost)
  F2      38/95/23            56/98/45         67/98/57       28%/22%    FAIL (no-harm, 0 cost)
  -> design-time drift model still adds +12..22 pts at the extremes on learned features with
  no 27C cost, but pre-registered target NOT met. DAC-aware features are needed for the
  strong result (D1 95/98/93, F2 98/100/97). Hand-built-feature limitation stands, softened.
- 2026-10-02: USER DECISION: build the full transmitter core now (accepting notebook-time risk).
  Scope ("full chip" = transmitter core macro): data bits -> I/Q unary current-steering DACs
  WITH data switches -> current-mode Gilbert switching quads (DAC currents = mixer tails) ->
  shared RC load (I+Q summing) -> PA driver -> RF out; LO path: external LO -> RC-CR ->
  inverter-chain limiters -> LO_I/LO_Ib/LO_Q/LO_Qb. Bias: mirror from reference current.
  OUT of scope: PLL/VCO (external LO input), pads/ESD/Caravel padframe.
  Steps: (C1) transistor-level transient of whole chain, 1 chip; (C2) validate the Python
  transmitter model against it (downconvert RF, compare per-chip I/Q errors), few chips x T;
  (C3) layout of new blocks (switches, quads, limiters, loads, PA); (C4) top integration,
  DRC/LVS. Notebook must still ship by Oct 8.
- 2026-10-02: C1 DONE. sim/tx_full.py: whole transmitter at transistor level (2x31 DAC cells +
  data switches, 2 Gilbert switching quads with DAC tails, shared RC load, PA diff pair,
  RC-CR + inverter limiters). 32 DAC samples simulate in 37 s. Nominal tt: LO rail-to-rail,
  mixer CM 1.35 V, RF 0.6 Vpp. Error vs ideal codes (normalised by |gain| 0.37): 13.2% gain
  only; 12.0% with I/Q image; 8.5% with 1-sample memory. Systematic quadrature phase error
  8.8 deg (image -22 dB) from limiter/RC-CR loading; sample memory from load/switch settling.
  KEY MODEL DISCREPANCY FOUND: limiters remove LO amplitude imbalance, which the Python
  model passes through. C2 will test whether per-chip fingerprints match the model.
- 2026-10-02: PRE-REGISTERED C2 (model validation, before running): 8 MC chips (tt_mm, seeds
  1-8) x {-40, 27, 85C}, 128-sample QPSK burst, noise-free. Per chip: in-situ op unit currents;
  transistor-level RF -> downconvert -> one-hot level fit -> I and Q DAC level-deviation
  patterns. Chip-specific part = pattern minus mean over the 8 chips at that T. Model
  prediction = cumulative-unit-current deviation from the same chip's op currents (what the
  Python transmitter model uses). PASS if median per-chip correlation (chip-specific parts,
  pooled I and Q) >= 0.8 at every temperature. Also report per-chip I/Q gain-imbalance
  agreement (model incl. vs excl. LO amplitude imbalance).
- 2026-10-02: LAYOUT dac_sw_array (layout/dac_sw_array.py): 3 rows (source W0.5/L1, SP and SN switches W1/L0.15) x 31 + ref; per-column met2 strap with hand-drawn 0.15 um via1 inside the 0.29 um met1 bars. 89.6 x 12.9 um. Magic DRC 0, KLayout DRC 0, LVS MATCH (94 devices). Bug fixed: corner-wise grid snapping made 0.16 um cuts -> centre-snapped exact shapes.
- 2026-10-02: tx_full REAL now = layout parts: wide xhigh/high_po resistors (200k = 4 x 35.25 um serpentine), MIM caps, PA mirror + divider, LO limiters from sky130_fd_sc_hd inv_2/inv_4/inv_8/inv_8. Nominal 32-sample: RF 0.43 Vpp, EVM 10.3%, quad phase err 4.1 deg. All passive cells DRC 0 in Magic+KLayout; mixer_quad, pa_pair, pa_mirror DRC 0 (both tools), LVS match.
- 2026-10-02: LAYOUT lo_limiter (layout/limiter.py): sky130_fd_sc_hd tap|inv_2|inv_4|inv_8|inv_8|tap + Cc (MIM 3x3) + Rfb (xhigh_po_1p41 4x35.25 serpentine, 200k). 20.1 x 45.6 um. Magic DRC 0, KLayout 0, LVS MATCH. Fixes: g/a1 pins 0.46 um apart -> g routed out on met2 before rising; a dangling met3 left the cap floating (LVS caught it); std-cell labels stripped (became ports when flat); resistor guard ring = substrate = VGND (netlist corrected). Blocks done: dac_sw_array, mixer_quad, pa_pair, pa_mirror, lo_limiter, rccr, 8 passive cells.
- 2026-10-02: ASSEMBLY A dac_mixer (layout/dac_mixer.py, route.py): dac_sw_array + mixer_quad, met2 stubs/met3 tracks, DAC tails into quad sources. 108.3 x 18.2 um. Magic DRC 0, KLayout 0, LVS MATCH (98 devices). Fixes: quad S/D bars only 0.94 um wide (vias at +-0.25 not +-0.35); gLayout met2->met3 via_stack makes 1.5 um pads -> own via2_min/via3_min.
- 2026-10-02: ASSEMBLY B lo_path (layout/lo_path.py): rccr + 2 lo_limiters, VI/VQ on met4 into limiter caps, VDD/VSS rails tied (VDD met3, VSS met3+met4). 54.4 x 121.4 um. DRC: only the 2 known rpm.1 from rccr's 0p35 resistors (both tools). LVS MATCH (24 devices). Bug found by LVS: VDD/VSS met3 routes crossed (short) -> VSS vertical on met4, west of VDD vertical.
- 2026-10-02: ASSEMBLY C out_net (layout/out_net.py): mixer loads, load caps, PA coupling caps,
  bias resistors + divider, PA pair, PA loads, tail mirror. 118.3 x 76.4 um. DRC 0 (both),
  LVS MATCH (16). Fixes: met3 min-area patches; PAB drain/gate via2 0.25 um apart -> joined on
  met2; metal VSS was separate from the substrate (LVS VSS_uq1) -> tied at a guard-ring tap.
- 2026-10-02: TOP LEVEL tx_core (layout/tx_core.py): 2 x dac_mixer (data pins renamed DI/DBI,
  DQ/DBQ) + lo_path + out_net. 307.3 x 139.4 um. LVS MATCH, 236 devices (full transmitter
  core, data bits to RF out). DRC: only the 2 known rpm.1 from rccr's res_high_po_0p35 (both
  tools); everything else clean after met3 min-area patches. Out of scope: PLL, pads/ESD,
  data decoder (62 thermometer inputs per channel are macro pins).
- 2026-10-02: MEMORY INCIDENT: tx_validate MC session had no 'save' -> ngspice kept every node/branch at 20 ps for every chip and never freed plots (~1.4 GB/chip); 3 parallel runs reached ~40-50 GB on a 17 GB Mac and froze it. Logs were only written at the end, so op currents of the 20 finished chips were lost. Fix: delete all/op/ac, then 'save' 6 vectors before tran, 'destroy all' after wrdata; log streamed to disk; max 2 parallel. Test: 0.46 GB peak per ngspice. Full validation relaunched.
- 2026-10-02: C2 MODEL VALIDATION RESULT (sim/tx_validate.py; 8 chips x 3 T, full transistor-level
  transmitter = layout circuit, mismatch on every device): median per-chip correlation of the
  chip-specific DAC level pattern, transistor-level vs Python model (unit-current prediction):
  -40C 0.52 | 27C 0.55 | 85C 0.59 (range 0.25-0.84). PRE-REGISTERED VERDICT: FAIL (target 0.8).
  Diagnostics: (1) transistor-level patterns are stable per chip across T (self-corr 0.96-0.99;
  model 0.996-0.999) -> real, repeatable signature, not measurement noise; (2) wrong-chip pairs
  -0.07 +- 0.26 -> 0.55 is above chance; (3) restricting to well-sampled levels: 0.57-0.65 ->
  not a sampling artefact. INTERPRETATION: the real circuit's chip-specific fingerprint has
  substantial content the model omits (likely data-switch / mixer / limiter mismatch and its
  interaction with settling); DAC unit currents explain ~30% of the pattern variance.
  Consequence: method-B results are model-based; transfer to the real circuit is NOT yet shown.
- 2026-10-02: USER DECISION (plan): (1) finish the fingerprint-shaping analog parts first:
  bias reference (replaces ideal 10/10/100 uA), LO input buffer, output buffer; each verified
  (sim, layout, DRC, LVS) and integrated into tx_core / tx_full. (2) then tests on the
  fingerprint-complete core: identification on transistor-level chips, block attribution of
  the extra fingerprint, model extension + method-B rerun if needed. (3) then digital control
  (decoder/registers/SPI, OpenLane) + Caravan pads + final verification (no effect on results).
  Bias reference design: beta-multiplier (constant-gm) self-biased reference with start-up;
  PMOS mirror outputs source 10 uA (I DAC), 10 uA (Q DAC), 100 uA (PA tail) into the existing
  diode-connected references. Its own mismatch and temperature dependence enter the fingerprint.
- 2026-10-02: BIAS REFERENCE (sim/bias_ref.py): beta-multiplier, M1 2/1, M2 8/1, pmos mirror 2/1,
  start-up (long pmos + 2 nmos). Rs xhigh_po (-16% over T) gave 6.8->13.5 uA over -40..85C
  (+99%); switched to n-diffusion res_generic_nd W1/L80 (+19.5% over T): 8.98 -> 10.55 uA
  (+17%), 9.94 uA @27C. MC 50 chips: 7.1% current spread, I/Q ratio sd 2.9%. Start-up OK
  (VDD ramp 1 us). Outputs: 10 uA (I), 10 uA (Q), 100 uA (PA, 10x).
- 2026-10-02: FINGERPRINT-COMPLETE ANALOG CORE in sim (tx_full REAL): on-chip bias reference
  (prefixed nodes; an unprefixed 'pg' once shorted it to the PA gate), LO input buffer
  (off-chip 50-ohm source -> 2 pF MIM -> NMOS follower W20 biased VDD/2, 200 uA sink) and
  output buffer (NMOS followers W40, 2 mA sinks each, off-chip 10 pF + 50 ohm loads).
  Nominal 32-sample: RF into 50 ohm 0.165 Vpp diff, EVM 10.7%, quad phase err 3.2 deg.
  Remaining ideal/off-chip: VDD, LO source, data bits, 50-ohm loads.
- 2026-10-02: device rows bias_n, bias_p (PMOS own n-wells, 10-finger x10 mirrors), lo_buf, out_buf: DRC 0 both tools, LVS MATCH. Sim updated to the same finger counts (nf). bias_ref mirror branches as nf=N (a single wide finger mirrored ~15% low: 84 vs 97 uA).
- 2026-10-02: LAYOUT bias_ref (layout/bias_block.py): bias_p row + mirrored bias_n row + r_nd80, channels top/middle/bottom + left trunks. 100.2 x 68.9 um. DRC 0 (Magic+KLayout), LVS MATCH (13). Fixes: tie vias at ring bar centre (label = edge); resistor terminals already have met1 (no 2nd mcon); MS1's lower tie bar (floating n-well found by LVS).
- 2026-10-02: LAYOUT lo_buf_blk + out_buf_blk (layout/buffers.py). out_buf_blk 20.0 x 24.9 um (OFP/OFN followers, OSP/OSN sinks, OBB diode); lo_buf_blk 69.2 x 68.1 um (2 pF MIM c_31, 2 x 50k xhigh-poly divider, LOF/LOB/LOS). Both DRC 0 (Magic+KLayout), LVS MATCH (5 / 6 devices). Fixes: diode gate joined to its drain stub by a met2 jog (two parallel stubs were 0.07 um apart); no extra via3 on the MIM strap (the cell's own via3 column already ties C2 met3->met4; met3 track lands on the bottom plate).
- 2026-10-02: STEP 1 LAYOUT DONE - fingerprint-complete tx_core (layout/tx_core.py; old version saved as layout/work/tx_core_v1.py). bias_ref at (75,-0.3) between the channels, lo_buf_blk at (-30,20), out_buf_blk at (315,25). Ideal IREF_I/IREF_Q/IREF_PA pins removed: BI -> I DAC gate bus (met4 + stack), BQ -> Q gate bus (met2 up), BPA -> PA mirror and BOB -> output buffer (met4 down, met3 under the OUTP/OUTN met4 trunks), BLO over the LO path on met3. LO_PAD -> buffer -> LO path IN; PA drains RFP/RFN -> follower gates. VDD met4 run at y=45 extended to all three blocks. Top pins now LO_PAD, TXP, TXN, VDD, VSS + 124 data bits. 408.5 x 142.0 um. LVS MATCH (260 devices = 236 + 13 + 6 + 5); DRC Magic 2 / KLayout 2, both the known rpm.1 on the RC-CR 0p35 resistors. Figure: figures/klayout_tx_core.png.
  Open for step 3: VSS is still joined only through each block's substrate taps (no metal VSS grid); ok for LVS, must become a metal grid before PEX / tape-out. rpm.1 flags remain.
- 2026-10-02: PILOT for step 2 (on the OLD C2 waveforms, 8 chips, circuit without bias/buffers; used
  only to choose burst length and SNR, no new-circuit data seen): 128-sample bursts are noise-
  dominated; 2304-sample bursts (18 frames, same length as the model bursts) at 20 dB: 81% @27C
  with a ~2-pt temperature gap (noise-dominated); at 30 dB: 100% @27C, 85-88% at -40/85C.
- 2026-10-02: PRE-REGISTERED STEP 2a (transistor-level identification + method B, before running):
  Circuit: tx_full REAL = fingerprint-complete core (on-chip bias reference, LO input buffer,
  output buffer; same netlist as the LVS-matched layout). Deployed chips: tt_mm seeds 1-16 at
  T = {-40, 0, 27, 55, 85} C. Design-time chips (for B only): ss_mm seeds 101-106 and ff_mm seeds
  101-106 at the same 5 T (wrong corners, different mismatch draws, no deployed chip reused).
  Stimulus: the 128-sample QPSK frame of C2 (qpsk_codes seed 1). Per chip/T also recorded for
  the later attribution study: op DAC unit currents (2x31), bias node voltages (gi, gq, pab,
  lob_bias, ob_bias), RC-CR ac outputs (vi, vq).
  Burst = 18 frames (2304 samples) of the chip's noise-free downconverted output, random carrier
  phase + independent complex AWGN per sample at SNR (rel. to the chip's mean power); receiver
  LS complex gain on the known codes; features = one-hot level fit over codes 5..26, I and Q
  ladders, real and imag residuals from their best straight lines (88 features).
  Enroll 27C, 40 bursts/chip; test 10 bursts/chip at each T; 3 noise seeds (0,1,2).
  BASE = Mahalanobis nearest mean with Ledoit-Wolf within-chip covariance (from enrollment).
  B = robust2 M5 mixture over the 5 C grid, m(T)/C(T) from the 12 design-time chips (noise-free
  features), interior exclusion when testing at 0 and 55 C.
  PRIMARY SNR 30 dB (secondary 20 dB, reported).
  Criteria: (I) identifiable: BASE accuracy at 27C >= 0.90 (16 chips, 30 dB).
  (II) B: gap recovery >= 50% at both -40 and 85C, 27C cost <= 2 pts, no harm at any T.
  If BASE's gap at an extreme is < 5 pts, recovery there is reported as "not testable".
  Run order: deployed first (5 sessions x 16 chips), then design-time (10 x 6); 2 ngspice max.
- 2026-10-02: BUG (found in step-2 smoke test): the LO source had no AC magnitude, so every 'ac'
  readout of vi/vq was 0 - including all of C2 (C2's verdict did not use them; its secondary LO
  imbalance report was never valid). Fixed: Vlo 'dc 0 ac {lo_amp} sin(...)' (transient unchanged).
- 2026-10-02: STEP 2a sweep launched (sim/tx_ident.py sim deployed design; log results/tx_ident_sim.log;
  15 sessions, 2 parallel, waveforms in sim/work/tx/ident_<corner>_T<T>/).
- 2026-10-02: STEP 2a RESULT (sim/tx_ident.py; 16 tt_mm chips + 12 design-time chips x 5 T, 140 runs,
  all completed; results/tx_ident_snr30.json, _snr20.json). Accuracy -40/0/27/55/85 C:
  30 dB (primary): BASE 0.944/1.000/1.000/1.000/1.000 | B 1.000/1.000/1.000/1.000/1.000
  20 dB:           BASE 0.896/1.000/0.998/0.990/0.994 | B 0.981/0.998/0.996/0.985/0.975
  PRE-REGISTERED VERDICTS: (I) identifiable: PASS at both SNRs. (II) B: NOT TESTABLE (BASE gap at
  85C is 0.0 pts @30 dB and 0.4 pts @20 dB, under the 5-pt rule). Where a gap exists (-40C) B
  recovers 100% (30 dB) and 84% (20 dB); at 20 dB B costs 1.9 pts at 85C and 0.5 at 55C (harm).
  Diagnostic (noise-free features): chip spread 0.0050/feature (pilot old circuit: 0.0030);
  drift from 27C: -40C 0.0020, 85C 0.0010 -> the complete core's fingerprint is ~1.7x larger
  and drift is small relative to it, so the temperature problem is mild on this circuit.
  Interpretation: the fingerprint-complete transistor core is reliably identifiable; temperature
  robustness is only stressed at -40C, where design-time B fixes it. Attribution (2b) should
  explain the larger fingerprint (bias/buffer content?) using the recorded op/ac data.
