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
- 2026-10-02: PRE-REGISTERED STEP 2b (attribution, before analysis; uses only the step-2a runs):
  Target: chip-specific fingerprint P = noise-free RF features (tx_ident.features, 88) minus the
  mean over the 16 tt_mm chips, at each T. Staged predictions, same feature extraction, NO fitted
  parameters (physical predictions only):
   S_dac : Python-model frame from the chip's op DAC unit currents (cumulative-current ladders,
           ideal LO) = what the Python transmitter model uses.
   S_lo  : S_dac with the chip's measured LO: RC-CR ac outputs (vi, vq) AND, separately,
           limiter-output fundamentals (lo_i, lo_q downconverted) as I/Q gain+phase.
   S_mix : features of the transistor-level mixer output (outp - outn) - contains DAC, data
           switches, switching quads, limiters, shared load.
   RF    : features of rfp - rfn (adds PA + output buffer). = target.
  Metric: explained fraction R2(S) = 1 - sum_c ||P_RF - P_S||^2 / sum_c ||P_RF||^2 (chip-specific
  parts), plus median per-chip correlation; reported at each T. Block increments:
  LO = R2(S_lo) - R2(S_dac); switches/quads/load = R2(S_mix) - R2(S_lo); PA+buffer = 1 - R2(S_mix).
  Decision rule for 2c: if a single increment beyond S_dac is >= 0.25 at 27C, that block is the
  dominant missing content -> extend the Python model with it and rerun (2c). If none is, the
  missing content is spread out -> skip 2c; model results stay labelled model-level only.
  Expectation stated in advance: static LO I/Q gain/phase error keeps each ladder straight, so the
  residual features should be almost insensitive to it (LO increment ~0).
- 2026-10-02: STEP 2b RESULT (sim/tx_attrib.py; results/tx_attrib.json, tx_attrib_aligned.json).
  Run 1 (as pre-registered, fixed-axis features): S_mix 0.73, PA+buffer 0.27, rule -> switches/
  quads/load. NOT TRUSTED: two analysis defects found by cross-checking against the C2 method:
  (a) fixed real/imag axes let the common quadrature angle move DAC INL between features;
  (b) the 128-sample frame never uses I code 26 or Q codes 21, 23; level_fit returns 0 for those
  levels and the line-fit residuals were corrupted. DEVIATION (declared): ladder-aligned features
  on used codes only (= C2's deviation(), along + cross residuals).
  Corrected (R2 of chip-specific RF pattern, no fitted params), 27C: DAC 0.073, LO -0.001,
  switches/quads/load 0.099, PA + output buffer 0.829 (same at all 5 T: 0.828-0.837).
  Cross-checks: C2 method on the new chips: DAC model vs RF r 0.52 (= C2), vs mixer output r 0.95;
  DAC model vs mixer-output pattern r 0.89-0.94 at -40/27/85C; chip-specific energy at RF is
  9.4-10.0x that at the mixer output. LO imbalance contributes ~0 (as predicted in advance).
  CONCLUSION: the Python model is right up to the mixer output (DAC unit currents explain the
  mixer-output fingerprint); the content it misses is added by the PA + output buffer, which
  multiplies chip-specific content ~10x. Pre-registered rule -> 2c: extend the model with a
  per-chip PA + output-buffer nonlinearity. (PA vs buffer split not possible from saved nodes:
  pdp/pdn were not saved.)
  Note for 2a: tx_ident.features also included the unused-code levels; identification is still a
  valid fixed feature map, but a masked-feature sensitivity rerun of 2a is advisable.
- 2026-10-02: DIAGNOSTIC before 2c (existing 2a data, 27C, 16 chips): per-chip memoryless complex
  polynomial mixer-output -> RF (y, y|y|^2, y|y|^4, const) fitted IN-SAMPLE on the frame explains
  the chip-specific RF pattern with R2 0.60, median r 0.82; adding 1-sample memory: 0.61 / 0.82.
  -> memoryless output-stage model is adequate; ~0.82 is an optimistic ceiling.
- 2026-10-02: PRE-REGISTERED STEP 2b-split + 2c (before running sim/tx_split.py):
  Sim: tt_mm seeds 1-16 at 27C (same chips as 2a), stimulus = 64-sample CALIBRATION segment
  (32 samples ci=cq=k, then 32 samples ci=k, cq=31-k, k=0..31) followed by the same 128-sample
  QPSK frame; saves pdp/pdn (PA drains) in addition. Identity check: frame RF vs 2a RF.
  Split: R2 of chip-specific RF pattern (aligned, used codes) from S_mix, S_pa (pdp-pdn), RF:
  PA increment = R2(S_pa) - R2(S_mix); output-buffer increment = 1 - R2(S_pa).
  2c model M1 (extended Python model): DAC-model frame (op unit currents) -> complex mixer gain
  (LS on the calibration segment, model cal frame vs measured mixer output) -> per-chip
  memoryless output stage F_c (basis y, y|y|^2, y|y|^4, 1; fitted mixer-output -> RF on the
  CALIBRATION segment only) -> features on the QPSK frame. Baselines: M0 = DAC only (C2 model);
  M1pop = population-mean F (not chip-specific).
  Metric: C2 metric (median per-chip correlation of chip-specific along-ladder deviation).
  PASS if M1 >= 0.80 at 27C (C2 threshold; in-sample ceiling ~0.82, so the bar is tight).
  If PASS: extend to -40/85C and design-time corners before a method-B rerun (separate entry).
- 2026-10-02: STEP 2a SENSITIVITY RERUN (masked features = unused-code levels dropped; tx_ident.py
  analyze --masked; results/tx_ident_snr*_masked.json). Accuracy -40/0/27/55/85 C:
  30 dB: BASE 1.000 at all T | B 1.000 at all T.
  20 dB: BASE 0.983/0.971/0.963/0.950/0.925 | B 0.969/0.967/0.950/0.923/0.898 (B harms 0.4-2.7 pts).
  -> Identifiable: PASS (robust to the feature fix). The -40C gap in the original 2a run (and B's
  "recovery" there) was an artefact of the unused-code levels: WITHDRAWN. On this core,
  temperature does not hurt identification at 30 dB; at 20 dB the baseline loses ~4 pts toward
  85C and design-time B does not help (slight harm). Method B is not supported at transistor level.
- 2026-10-02: STEP 2b-split + 2c RESULT (sim/tx_split.py; results/tx_split.json; 16 chips, 27C,
  cal segment + frame; identity vs 2a |cos| >= 0.9996).
  SPLIT: chip-specific RF pattern is explained by the PA drains (R2 0.999); PA increment 0.797,
  output buffer 0.001. PA multiplies chip-specific content 7.2x; buffer 1.04x. -> the PA (diff pair
  + loads + tail mirror) is the fingerprint amplifier; the output buffer is transparent.
  2c (pre-registered, C2 metric): M0 DAC only 0.535 | M1pop + mean output stage 0.633 |
  M1 + per-chip output stage 0.643 -> VERDICT FAIL (target 0.80).
  Diagnostic (post hoc): measured mixer output + cal-fitted per-chip PA = 0.804 (frame-fitted
  ceiling 0.776; PA-model rel. error 4.6% cal / 5.1% frame). -> the per-chip PA model is adequate;
  the failure is the DAC-model mixer-output prediction (r ~0.9 to the real mixer output, missing
  ~10% switch/quad/load content), whose error the PA nonlinearity amplifies. Per-chip PA params
  add little over the population-mean PA (0.643 vs 0.633): the PA mostly shapes HOW the
  DAC/mixer mismatch shows up, rather than adding its own independent mismatch.
  Not done (would be beyond this pre-registration): mixer-stage model (switch/quad/load), PA
  characterisation across T and corners, method-B rerun on an extended model.
- 2026-10-03: CHECK: duplicate instance names XRi/XRq (RC-CR resistor and DAC reference device) in
  tx_full netlists. Minimal ngspice test: both duplicates are instantiated (163 uA and 9 uA), so
  all past runs simulated the full circuit. DAC reference renamed XREF{ch}; op unit currents of
  chips 1-2 bit-identical after the rename (MC draws unchanged).
- 2026-10-03: STEP 2d design variants coded in tx_full (TX_VARIANT): palin = source-degenerated PA
  (tail split into 2 x 0.5 mA mirrors, R_DEG = N_DEG x 311-ohm segments between the sources, loads
  2 x 311 ohm); bigdac = DAC unit + reference 1/2 um (4x area, same W/L). Nominal check running
  (sim/tx_variants.py; palin N_DEG 1/2/3).
- 2026-10-03: PRE-REGISTERED STEP 2d (design variants; written before the nominal results are seen):
  palin selection: the largest N_DEG in {1,2,3} with nominal RF >= 0.5x base and EVM <= 1.2x base
  (most linear PA that still transmits usefully); if none qualifies, N_DEG = 1.
  MC: tt_mm seeds 1-16 (same chips as 2a), T = -40/27/85 C, for palin and bigdac; base = 2a runs.
  Features: tx_ident masked features (unused codes dropped). Noise-free metrics per variant:
   S_rf  = chip spread at RF (mean over features of the across-chip std, 27C)
   S_mix = the same at the mixer output (outp-outn): separates the source from the amplifier
   ratio = S_rf / mean |chip-specific drift| (-40 and 85 vs 27C)
  Identification: BASE classifier, 30 and 20 dB, enroll 27C, test -40/27/85 (3 noise seeds).
  Predictions: (P1) bigdac: S_mix and S_rf ~0.5x base (Pelgrom), pass if both within 0.35-0.65x.
  (P2) palin: S_mix unchanged (0.8-1.25x base) and S_rf < 0.7x base (PA = amplifier).
  Anti-fingerprint metric: suppression S_rf(base)/S_rf(palin) and the drop in 20 dB accuracy.
  Fast-model rebuild rule: rebuild + validate (C2 >= 0.8) only if a variant shows a BASE gap >=
  5 pts at -40 or 85C at either SNR, or ratio < 1.5.
- 2026-10-03: STEP 2d NOMINAL (tt, 27C; results/tx_variants_nominal.json): RF Vpp / EVM / PA compression
  at top drive: base 0.191 / 11.4% / -3.50 dB; bigdac 0.192 / 11.5% / -3.52 dB; palin N_DEG=1 0.318 /
  8.8% / -2.99; N_DEG=2 0.299 / 7.1% / -2.68; N_DEG=3 0.285 / 6.1% / -2.47. Pre-registered rule ->
  palin N_DEG = 3. Note: degeneration lowers EVM a lot but compression only ~1 dB (other limits
  in the PA path). MC launched: palin3 + bigdac, 16 chips x {-40,27,85} (tx_variant_mc.py sim 3).
- 2026-10-03: METAL VSS GRID (layout/tx_core.py vss_grid; previous version layout/work/tx_core_v2.py):
  met5 spine at y=-86 (met5 otherwise unused) + met5 drops with via stacks to 7 tie points (LO buffer,
  LO path, bias, I and Q DAC tap rings, output network, output buffer); route.py gained via4/m5.
  tx_core 408.5 x 149.0 um; LVS MATCH (260); DRC only the 2 known rpm.1 (Magic + KLayout).
  LVS cannot see a missed tie (VSS was already one node via the substrate), so verified with a
  metal-only KLayout connectivity probe: all blocks' VSS labels on the spine's net; VDD separate.
- 2026-10-03: PRE-REGISTERED (before running) - three further tests on the base core:
  (V) SUPPLY DRIFT: same 16 chips (tt_mm seeds 1-16, identical MC draws), 27C, VDD 1.62 and 1.98 V
  (data-bit drive follows VDD). Enroll at 1.80 V (2a runs), test at 1.62/1.98, masked features, BASE
  classifier, 30 and 20 dB. Report accuracy and the chip-specific drift / fingerprint ratio.
  "VDD drift matters" if the BASE gap vs 1.80 V is >= 5 pts at either SNR (then design-time
  compensation for supply would be the relevant use of method B; not run here).
  (N) MORE CHIPS: seeds 17-64 at 27C (base circuit) + 2a seeds 1-16 = 64 chips. Descriptive: BASE
  accuracy vs population size N = 16/32/64 at 30/20/15/10 dB (enroll/test 27C, 3 noise seeds).
  Expectation: >= 0.95 at 30 dB for N = 64.
  (P) POST-LAYOUT: Magic C-extracted tx_core (devices + coupling/ground C; layout/pex.sh) driven by
  the tx_full stimulus and off-chip parts (sim/tx_pex.py). Nominal tt 27C: gain and EVM vs the
  schematic. MC 16 chips x {-40,27,85} (draws follow the extracted instance order -> a new
  population; comparisons are population-level). PASS if (i) BASE >= 0.90 at 27C, 30 dB and
  (ii) S_rf within 0.67-1.5x the schematic base. RC extraction deferred (resistor network looks
  suspicious: ~800-ohm segments on VDD; to be checked first).
- 2026-10-03: STEP 2d RESULT (design variants; results/tx_variants_mc.json; 16 chips x {-40,27,85}).
  Fingerprint size (masked features, 27C) RF / mixer output, ratio to chip-specific T drift:
   base   S_rf 0.0034 (1.00x)  S_mix 0.0009 (1.00x)  ratio 4.7
   palin3 S_rf 0.0021 (0.62x)  S_mix 0.0009 (0.99x)  ratio 4.4
   bigdac S_rf 0.0029 (0.85x)  S_mix 0.0005 (0.54x)  ratio 4.5
  Accuracy 30 dB -40/27/85: base 1/1/1; palin 0.992/1.000/0.985; bigdac 1/1/1.
           20 dB:           base 0.983/0.960/0.917; palin 0.844/0.846/0.763; bigdac 0.894/0.885/0.812.
  PRE-REGISTERED: P2 palin PASS (mixer fingerprint unchanged, RF 0.62x: the PA amplifies).
  P1 bigdac FAIL: the mixer-output fingerprint halves exactly as Pelgrom predicts (0.54x) but the
  RF fingerprint only drops to 0.85x. Interpretation (assumes independent, additive variances):
  upstream-amplified part a, PA-own part b: a^2+b^2 = 0.0034^2, a^2/4+b^2 = 0.0029^2 -> a ~0.0021,
  b ~0.0027: the PA's OWN mismatch is ~64% of the RF fingerprint variance, upstream ~36%. This
  REVISES 2b/2c ("PA mostly shapes upstream mismatch", from per-chip vs mean PA model 0.643 vs
  0.633): the PA is both amplifier and a source. Anti-fingerprint: linear PA suppresses the
  fingerprint 1.60x; 20 dB accuracy @27C 0.960 -> 0.846.
  Fast-model rebuild rule: TRIGGERED (20 dB gap 27->85C: palin 8.3, bigdac 7.3 pts >= 5) - smaller
  fingerprints make temperature matter at 20 dB.
- 2026-10-03: TEST V RESULT (supply drift; results/tx_vdd.json; same 16 chips, 27C, enroll 1.80 V):
  accuracy 30 dB: 1.80 V 1.000 | 1.62 V 0.452 | 1.98 V 0.908; 20 dB: 0.973 | 0.433 | 0.800.
  Chip-specific drift ratio 3.4 (1.62) / 3.6 (1.98) - similar to temperature (4.7), so the collapse
  comes from the COMMON (all-chip) shift, which biases nearest-mean decisions. PRE-REGISTERED:
  "VDD drift matters" (gap 55 pts at 30 dB). -10% supply is far worse than +10% (headroom).
  -> Supply, not temperature, is the drift that breaks identification on this core; a shared-
  drift term (method B's m(.)) or an on-chip regulator are the natural fixes.
- 2026-10-03: TEST N RESULT (64 chips, 27C; results/tx_more_chips.json). BASE accuracy:
  N=16: 30 dB 1.000 | 20 dB 0.973 | 15 dB 0.765 | 10 dB 0.352
  N=32: 1.000 | 0.954 | 0.617 | 0.251;  N=64: 1.000 | 0.909 | 0.511 | 0.181.
  Expectation (>= 0.95 at 30 dB, N=64) met. Accuracy falls with N below 20 dB.
- 2026-10-03: TEST P RESULT (post-layout, C-extracted core; results/tx_pex.json). Fingerprint size
  0.99x schematic, ratio 4.6 (schematic 4.9); 30 dB 1.000 at -40/27/85C; 20 dB 0.944/0.979/0.940
  (schematic 0.983/0.960/0.917). PRE-REGISTERED P: PASS - the fingerprint survives parasitics.
  NOMINAL PERFORMANCE ISSUE: post-layout EVM 28.2% (schematic 11.4%), |gain| 0.065 vs 0.077.
  Decomposition: with I/Q imbalance removed EVM 13.6% (schematic 10.8%); fitted quadrature
  phase error -27.7 deg post-layout vs -4.6 deg schematic -> parasitic loading of the RC-CR
  quadrature network (internal net names lost in extraction; to be confirmed). Common to all
  chips (fingerprint unaffected). Fix: retune RC-CR R/C against the extracted layout (post-layout
  iteration), then re-extract.
- 2026-10-03: ITEM 1 DONE - RC-CR RETUNE (chip fix). Diagnosis: the extracted lo_path alone lost ~10 deg
  of quadrature (80.1 vs 89.8 deg); the RC-CR is high-impedance (R ~6.1k, C ~0.13 pF at 200 MHz), so
  fF-level parasitics on VQ (5.9 fF coupling to IN, the Cq bottom plate, the limiter input) shift
  its phase. Fix (layout/rccr.py v2; old saved as layout/work/rccr_v1.py, lo_path_v1.py):
  (a) wide res_high_po_1p41 resistors of the same value (L 25.6 um = 6.14k) -> also removes the
  two rpm.1 DRC flags carried since the start; (b) Cq rotated so its bottom plate is on the driven
  IN node and the top plate on VQ -> extracted lo_path 88.8 deg (schematic 89.7); (c) trim LQ to
  20.3 um (RqCq < RiCi) to cancel the remaining systematic quadrature error.
  Core: DRC 0 in Magic AND KLayout (first fully clean core), LVS MATCH (260).
  Nominal (tt 27C, frame from t=0): quad error / EVM: before (v1) schematic -4.6 / post-layout -27.7
  deg, 28.2% EVM; v2 untrimmed: -4.9 / -6.3 deg, 14.5 / 14.4%; v2 trimmed: -1.4 / -2.0 deg, 14.2 /
  13.8% EVM. (EVM from t=0 includes start-up settling; the 11.4% v1 figure followed a 64-sample
  calibration segment, so it is not directly comparable.) tx_full now simulates RC-CR v2
  (rccr_lines; RCCR_LI/LQ). All runs from here on use the v2 circuit.
- 2026-10-03: PRE-REGISTERED ITEM 2 (supply drift, v2 circuit, 27C; before running):
  2a TOLERANCE: tt_mm seeds 1-16 at VDD 1.62/1.71/1.764/1.80/1.836/1.89/1.98 V (-10/-5/-2/0/+2/+5/+10%).
  Enroll 1.80 V; BASE accuracy at 30 and 20 dB (masked features, 3 noise seeds). Tolerance = the
  widest symmetric +-x% with BASE >= 0.90 at 30 dB.
  2b METHOD B FOR SUPPLY: design-time chips ss_mm and ff_mm seeds 101-106 at VDD grid 1.62/1.71/
  1.80/1.89/1.98 V (wrong corners, different mismatch draws). From their noise-free features:
   M2 = projection removing the design-time shared-drift subspace (SVD of the per-VDD mean drift
        vectors vs 1.80 V, directions holding 95% of the energy), then BASE;
   B  = robust2 M5 mixture: m(V), C(V) linearly interpolated on a 0.01 V grid over 1.62-1.98 V;
        when testing at a grid point (1.71, 1.89) that point is excluded from the interpolation.
  Compare BASE / M2 / B at every test VDD, 30 dB primary, 20 dB secondary.
  PASS (per method) if gap recovery >= 50% at both 1.62 and 1.98 V, cost at 1.80 V <= 2 pts and
  no harm at any VDD (same rules as the temperature study). Gap < 5 pts -> "not testable" there.
  2c LDO only if neither M2 nor B passes and time allows.
- 2026-10-03: ITEM 2 RESULT (supply drift, v2 core, 27C; results/tx_supply.json). Accuracy at
  1.620/1.710/1.764/1.800/1.836/1.890/1.980 V:
  30 dB  BASE 0.337/0.942/1.000/1.000/1.000/0.971/0.762
         M2   0.946/0.954/1.000/1.000/1.000/0.935/0.819
         B    0.919/0.954/0.950/1.000/1.000/1.000/0.942
  20 dB  BASE 0.367/0.858/0.963/0.969/0.938/0.888/0.677
         M2   0.840/0.910/0.952/0.963/0.948/0.875/0.735
         B    0.792/0.865/0.906/0.963/0.950/0.917/0.821
  2a TOLERANCE (BASE >= 0.90): +-5% at 30 dB, +-2% at 20 dB.
  2b PRE-REGISTERED: M2 FAIL (recovery -10% 92%, +10% 24%; harm at 1.89 V: -3.6 pts).
  B FAIL - on the no-harm rule only: recovery -10% 88%, +10% 75%, cost at 1.80 V 0.0 pts, but
  harm at 1.764 V (-5.0 pts at 30 dB). At 20 dB B recovers 71% / 49% (just under 50% at +10%),
  harm at 1.764 V (-5.7). Interpretation: design-time drift knowledge (wrong-corner chips only)
  recovers most of the supply-drift loss at the extremes with no nominal cost; the mixture's
  interpolation between the 1.71 and 1.80 V grid points costs accuracy near nominal. Not tuned
  post hoc (that would need a new pre-registration).
  -> rule for 2c (LDO): triggered (neither method passed), "if time allows".
- 2026-10-04: MISMATCH SCALING CHECK: SKY130 MOSFET mismatch = MC_MM_SWITCH * AGAUSS(0,1) * slope/
  sqrt(LW); overriding '.param mc_mm_switch=s' after the .lib line scales it. Test (2 chips, op DAC
  unit currents): s=0.5 -> 0.54x deviation (corr 0.98 with s=1), s=2 -> 1.96x (corr 0.998): same
  chips, scaled mismatch. (Transistor mismatch only; resistor/cap mismatch not scaled.)
- 2026-10-04: PRE-REGISTERED B v2 (supply compensation revision; reason: B v1 failed only on harm at
  1.764 V, attributed to linear interpolation between the 1.71 and 1.80 V design points):
  change: design-time grid adds 1.764 and 1.836 V (ss_mm/ff_mm seeds 101-106) -> grid = the 7 test
  supplies; nothing else changes (M5 mixture, 0.01 V grid, same features/classifier/SNRs).
  No exclusion of grid points (all drift knowledge comes from the 12 wrong-corner design chips, so
  the test voltage being on the grid is not leakage); with-exclusion reported as secondary.
  FRESH TEST CHIPS: tt_mm seeds 17-32 at all 7 supplies (never used before) -> verdicts on these
  only. Same pass rule: recovery >= 50% at 1.62 and 1.98 V, cost at 1.80 <= 2 pts, no harm at any
  supply; 30 dB primary, 20 dB secondary. Report BASE, M2 and B v2.
- 2026-10-04: PRE-REGISTERED MISMATCH SENSITIVITY (option 1; v2 core, tt_mm seeds 1-16, same draws
  scaled by s = 0.5 and 2): per s: base 27C 1.80 V, base 85C, base 1.62 V, palin 27C.
  Predictions (conclusions robust to model error if all hold at both s):
  S1 PA amplification: S_rf/S_mix within +-30% of the s=1 value (v2 base 27C).
  S2 supply > temperature: BASE accuracy loss at 1.62 V > loss at 85C (30 and 20 dB).
  S3 linear PA suppresses: S_rf(palin)/S_rf(base) < 0.8.
  Also reported: S_rf vs s (expect ~proportional), identification at 30/20 dB.
  Run order: B v2 first, then sensitivity; 2 ngspice max.
- 2026-10-04: LITERATURE CHECK (option 2) - closest prior work and how ours differs:
  * Chatterjee, Das, Sen, "RF-PUF", HOST 2018 / IEEE IoT J. 2019 (arXiv 1805.01374): circuit-level
    simulation with process variation in 65 nm; features LO offset + I/Q imbalance; NN receiver;
    no temperature/supply. Differs: we find LO I/Q imbalance contributes ~0 (limiters remove it);
    full transmitter, layout-verified, attribution, drift study.
  * Xu, Shen, Chen, Chen (CMU), "Bayesian Neural Networks for Identification ... Using Power
    Amplifiers' Nonlinearity Signatures", IEEE OJCAS 2021 (par.nsf.gov 10281481): schematic-level
    65 nm class-E/F PAs across TT/SS/FF corners, -40..125C, VDD +-0.1/0.2 V; "6 transmitters" =
    2 PA designs x 3 corners (NOT mismatch instances of one design), single-tone input, PA only.
    Differs: we identify chips of ONE design via Monte Carlo mismatch (the actual RFF problem),
    full TX chain + layout/PEX, attribution, enroll-at-nominal drift tests, design-time comp.
  * Same group: class-E PA fingerprint augmentation with combinatorial security primitives (65 nm
    silicon, IEEE 2022) and combinatorial-randomness PAs + CNN (IEEE 2022): deliberately DESIGNING
    the PA to enlarge the fingerprint, measured on silicon. Consistent with our finding that the PA
    is the fingerprint lever (we show the opposite direction too: linear PA suppresses it 1.6x).
  * Measured RFF literature names PA nonlinearity as a dominant fingerprint source (e.g. arXiv
    1811.04521; PA nonlinearity quotient arXiv 2302.13724) - consistent with our attribution.
  * Temperature on measured devices: 12 ESP32-C3 BLE devices, accuracy ~97% -> ~40% at unseen
    temperatures, mitigated by temperature-aware CNN (arXiv 2607.25070, 2026); RF-TESI (ACM 2023).
    Mainly via crystal-oscillator CFO. Our "temperature barely matters" applies to the transmitter
    analog core with an EXTERNAL LO and no CFO feature - must be stated as such.
  * SKY130 mismatch: models implement Pelgrom (1/sqrt(WL)) per BSIM4 bin; no published SKY130
    silicon mismatch measurement found in this search (not claimed).
  Novelty statement to use: not "first to simulate RF fingerprints at circuit level" (RF-PUF and
  Xu et al. did); new = identical-design chips via mismatch in a complete, layout-verified open
  transmitter, block attribution with tested design levers, post-layout survival, supply-vs-
  temperature drift and design-time compensation.
- 2026-10-04: B v2 RESULT (fresh chips 17-32, design grid = 7 supplies; results/tx_bv2.json, _excl.json).
  30 dB (primary), 1.620/1.710/1.764/1.800/1.836/1.890/1.980 V:
   BASE 0.238/0.846/1.000/1.000/1.000/0.996/0.800 | M2 0.998/1/1/1/1/1/0.998 | B 1.000 at every supply
   PRE-REGISTERED: B PASS (recovery 100%/100%, cost 0, no harm); M2 PASS (99.7%/99.0%, cost 0, no harm).
  20 dB (secondary): BASE 0.252/0.767/0.946/0.956/0.946/0.883/0.717; B 0.862/0.944/0.940/0.944/0.940/
   0.927/0.915 (recovery 87%/83%, cost 1.3 pts, harm 0.6 pts at 1.764 -> FAIL on no-harm);
   M2 0.871/.../0.852 (88%/57%, harm at 1.764 -> FAIL).
  Secondary (interior grid points excluded, i.e. v1-style interpolation at 1.71-1.80): same 30 dB
  result (B 1.000 everywhere). -> HONEST NOTE: the denser grid was not what made v2 pass; on fresh
  chips B passes with v1-style interpolation too. v1's 5-pt harm at 1.764 V was most likely specific
  to chips 1-16 (chip-set variance), not a grid-resolution flaw. Tolerance without compensation
  also differs by chip set: +-5% (chips 1-16) vs +-2% (chips 17-32) at 30 dB.
  Conclusion: design-time compensation learned only from wrong-corner simulated chips removes the
  supply-drift loss at 30 dB on unseen chips (B and M2), and recovers 83-87% at 20 dB with a ~1-pt
  cost. Over the two chip sets B passed once (v2, fresh) and failed once (v1, on harm by 5 pts).
- 2026-10-04: MISMATCH SENSITIVITY RESULT (results/tx_mm_sensitivity.json):
  s=1: S_rf 0.0034, S_mix 0.0009, PA amplification 3.79.
  s=0.5: S_rf 0.0024 (0.71x), amplification 5.27, palin/base 0.64; 30 dB 27C/85C/1.62V 0.998/0.881/0.258;
         20 dB 0.815/0.642/0.271. S1 FAIL (+39% vs +-30%), S2 PASS, S3 PASS.
  s=2:   S_rf 0.0060 (1.77x), amplification 3.28, palin/base 0.64; 30 dB 1.000/1.000/0.623;
         20 dB 1.000/0.998/0.650. S1 PASS, S2 PASS, S3 PASS.
  PRE-REGISTERED: not all hold (S1 fails at s=0.5). Supply > temperature (S2) and linear-PA
  suppression (palin/base 0.64 at both s, 0.62 at s=1) are robust over a 4x range of mismatch.
  Post hoc interpretation of S1: S_rf does not scale with s because resistor/capacitor mismatch is
  NOT scaled by mc_mm_switch. Fit S_rf^2 = (a s)^2 + p^2 to s=1,2: a=0.00285, p=0.00185 -> predicts
  s=0.5: 0.00233 (observed 0.0024). -> transistor mismatch ~71% of RF fingerprint variance, passive
  (R/C) mismatch ~29%; at small transistor mismatch the passive part (in the PA loads, after the
  mixer) raises the S_rf/S_mix ratio. Also: with half the mismatch, temperature starts to matter
  (20 dB: 81.5% -> 64% at 85C), consistent with the variant results.
- 2026-10-04: PRE-REGISTERED ROUND 3 (before running/analysing):
  (1) POST HOC (labelled): B v2 settings (7-point design grid, no exclusion) on chips 1-16 (where B v1
      failed). Same pass rule. Reported as post hoc, not as a confirmatory result.
  (2) AUTHENTICATION: enrolled = chips 1-16 (v2, 27C, 1.80 V enrollment), impostors = chips 17-32
      (same design, never enrolled). Each test burst claims each enrolled identity; score = negative
      Mahalanobis distance to the claimed template (BASE) or B's mixture log-likelihood. Genuine
      trials: burst from chip k claiming k; impostor trials: bursts from chips 17-32 claiming any k.
      Report EER at 30/20 dB at 1.80 V and at 1.62/1.98 V (genuine and impostors at the same supply),
      BASE vs B. Descriptive; expectation: EER < 5% at 30 dB, 1.80 V.
  (3) TEMPERATURE x SUPPLY: test chips 17-32 at (T, V) in {-40, 85} x {1.62, 1.80, 1.98} (6 conditions),
      enrolled at 27C/1.80 V. Design-time: ss_mm/ff_mm seeds 101-106 at {-40, 27, 85} x {1.62, 1.71,
      1.80, 1.89, 1.98} (27C row exists). B-2D = M5 mixture whose components are the 15 design grid
      conditions themselves (no interpolation); M2-2D = projection of the shared-drift subspace of
      all 14 non-nominal conditions (95% energy). Pass rule per method: at 30 dB, accuracy at each
      of the 6 conditions >= BASE and mean recovery of the BASE gap >= 50%, cost at 27C/1.80 <= 2 pts.
  (4) DIFFERENT DATA FRAMES: chips 1-16 (v2, 27C, 1.80 V) with two new QPSK frames (qpsk_codes seed 2
      and 3). Enroll on frame 1 (existing run), test on frames 2 and 3; features restricted to the codes
      used by all three frames (masked). PASS (fingerprint independent of the data) if BASE accuracy
      on frames 2 and 3 >= 0.90 at 30 dB.
  (5) THIRD CHIP SET: chips 33-48 (v2) at the 7 supplies; B v2 and M2 exactly as pre-registered for
      B v2 (grid = 7 supplies, no exclusion). Same pass rule; adds a third trial to B's record.
  Run order: (4) then (5) then (3); 2 ngspice max.
- 2026-10-04: ROUND 3 (1) RESULT, POST HOC (results/tx_bv2_set1_posthoc.json): B v2 settings on chips
  1-16: 30 dB B 0.919/0.975/0.950/1.000/1.000/0.998/0.942 (BASE 0.337/0.942/1.000/1.000/1.000/0.971/
  0.762) -> FAIL again, same 5-pt harm at 1.764 V although 1.764 V is now a design grid point. ->
  not an interpolation artefact: on this chip set the design-time drift model misleads near -2%.
  B's record: chips 1-16 FAIL (v1 and v2 settings), chips 17-32 PASS; third set pending.
- 2026-10-04: ROUND 3 (2) RESULT, AUTHENTICATION (results/tx_auth.json; enrolled chips 1-16, impostors
  17-32, same design, never enrolled). Equal error rate:
  30 dB: 1.80 V BASE 0.0% / B 0.0% | 1.62 V BASE 17.7% / B 9.8% | 1.98 V BASE 16.3% / B 4.6%
  20 dB: 1.80 V BASE 7.4% / B 10.0% | 1.62 V BASE 22.9% / B 19.7% | 1.98 V BASE 20.8% / B 13.8%
  Expectation (EER < 5% at 30 dB, 1.80 V) met: impostors of the same design are rejected perfectly
  at nominal supply. Supply drift raises EER to 16-18% (it pushes genuine chips past the threshold);
  B roughly halves it at 30 dB but not to nominal. At 20 dB B costs 2.6 pts EER at 1.80 V. Note:
  authentication is harder to protect from drift than identification (B restored identification to
  100% on chips 17-32, but on chips 1-16 the EER stays 5-10% under drift).
- 2026-10-04: ROUND 3 (4) RESULT, DIFFERENT DATA FRAMES (results/tx_frames.json): enroll frame 1, test
  frames 2/3 (chips 1-16, 27C, 1.80 V, 17/18 common codes): 30 dB 1.000 / 0.137 / 0.081; 20 dB 0.963 /
  0.133 / 0.079. PRE-REGISTERED (4): FAIL - near chance (1/16 = 0.06).
  Diagnostics (post hoc, noise-free): the frame causes a COMMON shift of the features ~9-12x the
  chip spread, and the chip-specific patterns also change (corr with frame 1: 0.44 / 0.18; nearest-
  template accuracy after removing each frame's population mean only 0.56 / 0.25). Adding 1-2
  samples of linear memory to the level fit barely helps (0.46/0.29); a joint ladder + PA-polynomial
  fit is ill-posed and worse. -> The level-ladder features are FRAME-SPECIFIC: each code's level
  estimate depends on the data context (which Q codes co-occur with an I code under PA compression,
  and settling), differently per chip. All identification results so far are therefore KNOWN-
  SEQUENCE (preamble-style) fingerprinting: enrollment and test use the same known frame. This is
  the usual operating mode of practical RFF (fixed preambles), but data-independent fingerprinting
  is NOT supported; the claim must be scoped accordingly. A data-independent feature design remains
  open.
- 2026-10-04: ROUND 3 (5) RESULT, THIRD CHIP SET (chips 33-48; results/tx_bv2_set3.json). 30 dB:
  BASE 0.392/0.767/0.938/1.000/0.875/0.858/0.444; M2 0.873/0.931/0.938/1.000/0.875/0.875/0.763;
  B 0.875/0.938/0.938/1.000/0.875/0.875/0.875. PRE-REGISTERED: B PASS (recovery 79%/78%, no cost, no
  harm); M2 PASS (79%/57%). 20 dB: both FAIL (cost 1.9 pts, harm). Uncompensated tolerance on this
  set: none (+-2% already < 0.90; 1.836 V 0.875). B record at 30 dB: 2 PASS (chips 17-32, 33-48), 1 FAIL
  (chips 1-16).
- 2026-10-04: ROUND 3 (3) RESULT, TEMPERATURE x SUPPLY (chips 17-32; results/tx_temp_supply.json). 30 dB,
  conditions 27C/1.80, -40C/1.62, -40C/1.80, -40C/1.98, 85C/1.62, 85C/1.80, 85C/1.98:
  BASE 1.000/0.071/1.000/0.771/0.354/1.000/0.727; M2-2D 1.000/0.125/1.000/0.698/0.279/1.000/0.671;
  B-2D 1.000/0.883/1.000/0.960/1.000/1.000/0.998. PRE-REGISTERED: B-2D PASS (mean recovery 92%, never
  below BASE, no nominal cost); M2-2D FAIL (projection worse than nothing). 20 dB: both FAIL (B-2D
  harms at -40C/1.80 and 85C/1.80; recovers -40C/1.62 0.087 -> 0.648, 85C/1.62 0.327 -> 0.858).
  Combined drift is far worse than either alone (-40C & -10% supply: 7% uncompensated).
- 2026-10-04: PRE-REGISTERED GATED SEQUENCE - model-based (prediction-error) receiver for arbitrary data.
  Receiver: per chip, a linear-in-parameters behavioural model y_k = phi(d_k, d_{k-1})^T theta_c fitted
  at enrollment: one-hot I code (32) + one-hot Q code (31), PA terms on the ideal symbol s0 = (2ci/31-1)
  + j(2cq/31-1): s0|s0|^2, s0|s0|^4, previous-sample s0 and s0|s0|^2, constant. Identification: the chip
  whose model predicts the received burst best after a free complex gain (min_g ||y - g Phi theta_c||).
  The fingerprint is the prediction, not the (possibly non-identifiable) parameters.
  STAGE 1 FEASIBILITY (noise-free; chips 1-16, 27C, 1.80 V, frames 1/2/3): 3-fold, enroll on two
  frames, test on the held-out frame. GO if mean held-out accuracy >= 0.90 (current level features:
  0.08-0.14).
  STAGE 2 NOISY (only if stage 1 GO): enrollment from 20 noisy bursts per training frame, test 10 noisy
  bursts (18 repetitions each, as before) of the held-out frame, 30 and 20 dB, 3 noise seeds, 3 folds.
  GO if held-out accuracy >= 0.90 at 30 dB.
  STAGE 3 COMBINED DRIFT + ARBITRARY DATA (only if stage 2 GO): pre-registered separately before running.
- 2026-10-04: GATED SEQUENCE STAGE 1 RESULT (sim/tx_modelrx.py; results/tx_modelrx_stage1.json): noise-free
  held-out-frame accuracy: frame 1 0.938, frame 2 0.813, frame 3 0.125, mean 0.625 -> STOP (gate 0.90).
  Stages 2 and 3 NOT run, as pre-registered.
  Diagnostic (post hoc, explains, does not change the verdict): frame 3 contains I code 27, never seen in
  frames 1-2 (4% of its samples); the models have no knowledge of it, so those samples give large
  errors for every chip and swamp the chip differences. Held-out frames with full code coverage reach
  0.94 / 0.81 (vs 0.08-0.14 for the level features). -> the prediction-error receiver captures most of
  the data dependence when enrollment covers every code; a revised test would need (a) enrollment that
  covers all codes (designed sequence) or scoring only samples with enrolled codes, decided in advance,
  and (b) FRESH held-out frames (new simulations), since this diagnostic has seen frames 1-3.
- 2026-10-04: PRE-REGISTERED GATED SEQUENCE v2 (revised model-based receiver; fresh test data):
  Receiver v2 = v1 model and score, with (a) ENROLLMENT on frames 1, 2, 3 + a CODE-COVERAGE sequence
  "cov" (128 samples: I = 4 shuffled passes through codes 0-31, Q = 4 differently shuffled passes,
  fixed seed 2026), so every code is enrolled with varied partners; (b) SCORING only samples whose I
  and Q codes both occur in the enrollment data (same mask for all candidate chips).
  FRESH held-out test frames 4 and 5 (qpsk_codes seed 4, 5), chips 1-16, 27C, 1.80 V - never seen.
  STAGE 1 (noise-free): GO if mean accuracy on frames 4 and 5 >= 0.90.
  STAGE 2 (noisy, only if stage 1 GO): enrollment 20 noisy bursts per enrollment sequence, test 10
  noisy bursts of frames 4/5 (18 reps), 30 and 20 dB, 3 seeds; GO if >= 0.90 at 30 dB.
  STAGE 3 (combined drift + arbitrary data, only if stage 2 GO): pre-registered before running.
- 2026-10-04: PRE-REGISTERED STAGE 3 (runs only if v2 stage 2 GO; written before stages 1-2 results):
  COMBINED DRIFT + ARBITRARY DATA. Chips 1-16 enrolled at 27C/1.80 V on {1,2,3,cov} (stage-2 receiver).
  Test: fresh frames 4 and 5 at drifted conditions D = {27C/1.62 V, 27C/1.98 V, 85C/1.80 V, -40C/1.62 V}
  (new simulations, 8 sessions). Methods:
   MRX   = v2 model-based receiver, no drift compensation;
   MRX-B = model-space design-time compensation: design chips ss_mm/ff_mm seeds 101-106 simulated on the
           coverage sequence at nominal and each condition in D (new simulations); per condition k,
           dtheta_k = mean over design chips of theta(k) - theta(nominal) (models fitted noise-free);
           a test burst is scored for chip c as min over k in {nominal} + D of the residual with
           theta_c + dtheta_k (the receiver does not know the condition).
  Noisy bursts as in stage 2, 30 dB primary, 20 dB secondary, 3 seeds.
  PASS (MRX-B) if at 30 dB mean accuracy over the 4 conditions >= 0.80 and >= MRX at every condition.
  Also reported: MRX-B at the nominal condition (fresh frames, 27C/1.80 V) vs stage-2 MRX (cost).
- 2026-10-05: GATED v2 RESULTS (sim/tx_modelrx.py; results/tx_modelrx_v2_stage1.json, _stage2.json; fresh
  frames 4 and 5, never seen before): STAGE 1 noise-free 0.938 / 0.875, mean 0.906 -> GO (gate 0.90, just).
  STAGE 2 noisy (enrollment 20 bursts per sequence on frames 1-3 + cov): 30 dB 0.928, 20 dB 0.930 -> GO.
  -> First evidence of identification on data the chips were not enrolled on (vs 0.08-0.14 for the
  level features). Margin is small (stage 1 passed by 0.6 pts). Stage 3 launched as pre-registered.
- 2026-10-05: STAGE 3 RESULT, COMBINED DRIFT + ARBITRARY DATA (results/tx_modelrx_stage3.json; chips 1-16,
  fresh frames 4/5). 30 dB, conditions 27C/1.80, 27C/1.62, 27C/1.98, 85C/1.80, -40C/1.62:
   MRX   0.928/0.588/0.487/0.506/0.312
   MRX-B 0.918/0.447/0.420/0.472/0.250   (20 dB nearly identical)
  PRE-REGISTERED: FAIL (MRX-B mean over drift 0.397 < 0.80, and below MRX at every condition).
  Interpretation: the model-based receiver, which works on unseen data at nominal conditions (0.93),
  is far MORE drift-sensitive than the level features on a known frame (e.g. 85C: 0.51 vs 1.00 for the
  level features on chips 1-16 at 30 dB), because it scores absolute waveform predictions in which the
  common drift dominates. The model-space design-time offsets (mean dtheta from ss/ff chips) make it
  worse: the drift in model space does not transfer from wrong-corner design chips as a simple shift.
  -> Arbitrary-data identification is shown only at nominal conditions; drift + arbitrary data is NOT
  solved. Gated sequence complete.
- 2026-10-05: PRE-REGISTERED MRX-S (drift-subspace model receiver), two steps:
  Method: design-time drift vectors dtheta = theta(k) - theta(nominal) for each ss/ff design chip (seeds
  101-106) and each condition k in D, models fitted noise-free on the coverage sequence (existing stage-3
  data). SVD of the 48 vectors; keep the top r directions V_r holding 95% of the energy. Score for chip c
  on a burst y of frame f: residual of the least-squares fit y ~ g * Phi_f theta_c + Phi_f V_r beta (free
  complex g and beta per burst). Enrollment as stage 2/3. Otherwise identical to stage 3.
  STEP A EXPLORATORY (labelled; stage-3 test data frames 4/5 already seen): "promising" if at 30 dB the mean
  accuracy over the 4 drift conditions >= 0.80, MRX-S >= MRX at every drift condition, and nominal cost
  <= 2 pts vs MRX.
  STEP B CONFIRMATORY (only if A promising): FRESH frames 6 and 7 (qpsk seeds 6, 7), chips 1-16 at nominal
  + the 4 drift conditions (new simulations); receiver unchanged; PASS by the same criteria.
- 2026-10-05: MRX-S STEP A RESULT (exploratory; results/tx_modelrx_S_stepA.json): drift subspace r = 2.
  30 dB nominal/1.62/1.98/85C/-40C&1.62: MRX 0.928/0.588/0.487/0.506/0.312; MRX-S 0.820/0.560/0.611/0.844/0.266.
  Mean over drift 0.570 < 0.80, below MRX at 1.62 V and -40C/1.62, nominal cost 10.8 pts -> NOT PROMISING;
  step B (fresh frames) NOT run, as pre-registered. Observation: absorbing 2 design-time drift directions
  fixes temperature (85C 0.51 -> 0.84) and partly +10% supply, but the same freedom also absorbs some chip
  differences (nominal -11 pts) and cannot follow low-supply drift (headroom loss, likely nonlinear and
  chip-specific). Arbitrary-data identification under drift remains unsolved in this work.
- 2026-10-05: PRE-REGISTERED PREDICTABILITY CHECK (is chip-specific drift predictable from the nominal
  fingerprint?): chips 1-16, behavioural models fitted noise-free on frames 4+5 at nominal and at each
  drift condition in D. Representation: predicted output on the coverage sequence (real+imag). Nominal
  fingerprint f_c = prediction - chip mean; chip-specific drift d_c(k) = (pred(k) - pred(nom)) - chip mean.
  Leave-one-chip-out ridge regression d(k) ~ f (ridge chosen by inner leave-one-out on the 15 training
  chips from {1e-6..1e2}); out-of-sample R^2 per condition. ALIVE if mean R^2 over the 4 conditions >= 0.3.
- 2026-10-05: PREDICTABILITY CHECK RESULT (sim/predict_drift.py): held-out R^2 of chip-specific drift from the
  nominal fingerprint: 1.62 V -0.74, 1.98 V +0.36, 85C -0.38, -40C/1.62 V -0.70; mean -0.36 -> DEAD (bar 0.3).
  Chip-specific drift relative to fingerprint size: 0.42 / 0.34 / 0.21 / 0.99. Only high-supply drift shows
  some predictability. Caveat: 16 chips vs a 256-dim representation is low power; a large design-time
  population could still find structure, but there is no signal here to justify the multi-night run.
  -> Conclusion for the write-up: under low supply (and cold + low supply, where chip-specific drift is as
  large as the fingerprint itself) the drift is chip-specific and not predictable from design-time data or
  the nominal fingerprint in our tests; it must be removed at the source (supply regulation) or measured.
- 2026-10-05: PRE-REGISTERED MRX-A (amplitude-limited scoring; design-time feature selection by drift):
  Design-time (ss/ff design chips seeds 101-106, coverage sequence, nominal + 4 drift conditions, noise-
  free): per sample n, spread_n = std over chips within corner of |y_c[n]| ... computed on complex y;
  chip-specific drift_n = mean over chips and conditions of |(y_c^k[n] - y_c^nom[n]) - corner mean|.
  Amplitude cutoff A* = the |s0| quantile in {0.3, 0.4, ..., 1.0} of the coverage sequence maximising
  mean(spread)/mean(drift) over samples with |s0| <= A (>= 30% of samples kept).
  Receiver: v2 model receiver (enrollment unchanged) scoring only samples with |s0| <= A*.
  STEP A exploratory on stage-3 data (frames 4/5, seen): promising if 30 dB mean over 4 drift conditions
  >= 0.80, >= MRX at each, nominal cost <= 2 pts. STEP B (only if promising): fresh frames 6/7.
- 2026-10-05: MRX-A RESULT (results/tx_modelrx_A_stepA.json): design-time spread/drift ratio is FLAT at 0.07
  across all amplitude bins (30-100% of samples) -> premise "small amplitudes are drift-stable" false; A* =
  0.966 (70% quantile) by argmax of a flat curve (scores 95-98% of the test samples). Step A: 30 dB MRX-A
  0.903/0.565/0.463/0.433/0.312 vs MRX 0.928/0.588/0.487/0.506/0.312 -> NOT PROMISING; step B not run.
  Receiver-side approaches to arbitrary data under drift are exhausted for this submission (fixed offsets,
  drift subspace, per-chip drift prediction, amplitude selection).
- 2026-10-05/06: ITEM 2c FULL LDO (sim/bandgap.py, sim/ldo.py; tx_full variant ldo<VIN>):
  Bandgap: 2 vertical PNP pairs (2:16) + 1 output PNP, xhigh-poly R1/R2 (same type), two-stage error
  amplifier (5 V devices) with start-up; VBG 1.213-1.217 V over -40..85C x 2.97-3.63 V (+-0.17%).
  Bugs fixed on the way: inverted OTA polarity; start-up detector below the 5 V NMOS threshold; OTA
  output ceiling at high VIN; systematic offset (ob tracked VIN) -> second stage (line +-2.3% -> 0.03%).
  LDO: NMOS-input OTA (tail mirrored from the bandgap), 5 V PMOS pass W200/L0.5, Miller 1 pF, divider
  VOUT = VBG(1 + R1/R2), 15 x 20x20 um MOS decoupling. Nominal: 1.802 V, load reg ~1 ohm (5.75->7 mA),
  stable (no ringing), start-up ~12 us with 1.92 V overshoot (limitation). Core with LDO: EVM 14.18%
  (14.16% without), vdd ripple 9.4 mV pp. Mismatch: first version VOUT sd 108 mV over 16 MC chips ->
  matched devices 16x area -> sd 30 mV (1.7%), 1.749-1.843 V (a real chip would trim). A non-physical
  op solution (-16 V) appeared for one MC chip -> .nodeset fixes it. The LDO is placed LAST in the netlist
  so core devices keep their MC draws (unit currents corr 0.999 with the unregulated chips 1-16).
  Earlier prototype (beta-multiplier I*R reference) rejected: VOUT 1.23-2.40 V over temperature.
- 2026-10-06: PRE-REGISTERED LDO TESTS (chips 1-16, same MC draws as the unregulated core):
  L1 SUPPLY: external VIN 2.97/3.135/3.234/3.30/3.366/3.465/3.63 V (+-2/5/10%), 27C, frame 1; enroll
     3.30 V; BASE, masked features, 30/20 dB. PASS if BASE >= 0.90 at every VIN at 30 dB (unregulated
     chips 1-16: tolerance +-5%, 34% at -10%).
  L2 TEMPERATURE x SUPPLY: {-40, 85}C x VIN {2.97, 3.30, 3.63}, frame 1, enroll 27C/3.30 V. PASS if
     BASE mean over the 6 conditions >= 0.80 at 30 dB (unregulated, chips 17-32: 7-100%, mean 0.65).
  L3 ARBITRARY DATA UNDER DRIFT: model-based receiver v2 (enroll frames 1,2,3,cov at 27C/3.30 V; test
     fresh frames 4,5) at 27C/2.97, 27C/3.63, 85C/3.30, -40C/2.97 and nominal. No compensation. PASS if
     mean over the 4 drift conditions >= 0.80 and nominal >= 0.90 at 30 dB (unregulated: 0.31-0.59).
- 2026-10-05/06: LDO LAYOUT (layout/ldo_block.py; previous core layout saved as layout/work/tx_core_v3.py).
  Devices generated by Magic's SKY130 cell generator (19 cell types incl. 5 V MOS, rf_pnp W3p40L3p40,
  xhigh-poly resistors, MIM, thin-oxide MOS decap; each DRC 0) placed in 3 rows; per row TOP/BOT met3
  channels, met2 stubs, met4 trunks join nets across channels/rows; MIM terminals on met4. The two
  ideal 1 pF compensation caps of sim/ldo.py are 22x22 um MIM caps in the layout (small difference to
  the simulated LDO; noted). Bugs fixed: label parser stripped digits from R1/R2/C1/C2 (resistor and
  MIM terminals never routed); generated S/D strips 0.23 um need a 0.32 um met1 patch under via1;
  unlabelled end strip of the 20-finger pass device; met3 min-area patches only on short tracks;
  same-net via2 within 0.45 um merged into an oversized cut. ldo_blk: 455.2 x 176.6 um, 64 devices
  (31 after merging fingers/parallels), DRC 0 Magic + KLayout, LVS MATCH.
  CORE + LDO (tx_core): LDO below the core (top edge y=-92); VOUT -> core VDD via met4 up the east side
  to the VDD run (y=45); LDO VSS -> met5 spine (extended); VIN is the chip supply pin (VDD now internal).
  tx_core 455.2 x 330.8 um, DRC 0 Magic + KLayout, LVS MATCH (291 devices = 260 + 31). Metal-only probe:
  LDO VSS on the spine's net, LDO VOUT = core VDD net, VIN separate.
- 2026-10-05 20:00: L1 PREVIEW (descriptive, not the verdict; 4 of 7 supplies done, chip 4 excluded): with the LDO,
  enroll 3.30 V: 30 dB 2.97/3.135/3.30/3.63 V = 1.000/1.000/1.000/1.000; 20 dB 0.973/0.982/0.976/0.969
  (same chips unregulated, 30 dB: 0.337 at -10%, 0.762 at +10%).
  ISSUE: chip 4 at VIN 3.30 V (the enrollment condition) aborted at t = 3.70 us ("timestep too small",
  node vdd#branch) - a transient convergence failure with the LDO in the loop. 1 of 64 chip-runs so far.
  Plan: after the queue, rerun failed chips with .option method=gear (2-ngspice limit kept).
- 2026-10-06 07:30: L1 PROVISIONAL RESULT (all 7 supplies; chip 4 excluded until its rerun - its 3.30 V run aborted):
  30 dB 2.97/3.135/3.234/3.30/3.366/3.465/3.63 V = 1.000 at every supply; 20 dB 0.973/0.982/0.976/0.971/0.962/
  0.982/0.971. Pre-registered rule (>= 0.90 everywhere at 30 dB): PASS (provisional, 15 chips).
  More failed chip-runs (convergence): chip 5 at 3.63 V on frames 4 and 5 (L3), aborting at t = 0. To rerun
  after the queue with .option method=gear.
- 2026-10-06 14:30: L3 PREVIEW (descriptive; 14 chips - 4 and 5 excluded pending reruns; -40C condition still running).
  Model-based receiver v2 on fresh frames 4/5 with the LDO, 30 dB: nominal 27C/3.30 V 0.855; 27C/2.97 V 0.854;
  27C/3.63 V 0.781; 85C/3.30 V 0.507 (20 dB similar). Unregulated (stage 3): 0.928 / 0.588 / 0.487 / 0.506.
  Reading: the LDO removes most of the SUPPLY-drift loss for arbitrary data (0.59/0.49 -> 0.85/0.78), but not
  TEMPERATURE (85C unchanged at 0.51), and the nominal arbitrary-data accuracy is lower than without the LDO
  (0.93 -> 0.86; possibly supply ripple dynamics the behavioural model does not capture - unverified).
  The pre-registered L3 rule (mean over drift >= 0.80 and nominal >= 0.90) will very likely FAIL.
- 2026-10-06 17:15: L3 PREVIEW incl. -40C (14 chips): 30 dB nominal 0.855 | 2.97 V 0.854 | 3.63 V 0.781 | 85C 0.507 |
  -40C/2.97 V 0.651 (unregulated: 0.312). Mean over drift 0.698 -> pre-registered L3 will FAIL (needs >= 0.80 and
  nominal >= 0.90). The LDO roughly doubles the worst case (cold + low supply 0.31 -> 0.65) but temperature limits
  arbitrary-data identification. Only failed chip-runs: chip 4 @3.30 V frame 1, chip 5 @3.63 V frames 4/5 (reruns
  queued after L2). L2 running ahead of estimate.
- 2026-10-06: DEADLINE EXTENDED: the Code-a-Chip README was updated 2026-10-06 02:16 UTC: notebook deadline now
  October 31, 2026, 11:59 AM PT (was Oct 9). Up to 10 travel grants; graduate/other US$1,000-5,000,
  undergraduate up to US$2,500, secondary school up to US$500; in-person ISSCC attendance + poster required.
- 2026-10-06 23:30: L2 PROVISIONAL RESULT (14 chips; 4 and 7 excluded pending reruns - chip 7's -40C/3.30 V run
  aborted, a 4th failed chip-run). 30 dB, enroll 27C/3.30 V: -40C x 2.97/3.30/3.63 V = 0.929/0.929/0.929;
  85C x 2.97/3.30/3.63 V = 0.929/0.929/0.874; mean 0.919 -> pre-registered L2 (>= 0.80): PASS (provisional).
  20 dB: 0.910/0.893/0.905/0.833/0.867/0.779. Unregulated combined drift (chips 17-32, 30 dB): 0.071/1.000/0.771/
  0.354/1.000/0.727. One chip is misidentified at both temperature extremes (13/14): a temperature residual
  remains with the supply regulated. Reruns of the 4 failed chip-runs (Gear integration) in progress.
- 2026-10-07..10: STORAGE INCIDENT: internal disk 99% full (2.2 GB free); macOS evicted iCloud-synced Desktop files
  (sources, git internals) to free space and re-downloads timed out. Fix (approved): sim/work (simulation waveforms,
  ~55 GB) copied to /Volumes/PortableSSD/code-a-chip-rffp-work/work and verified (sizes all files + byte-compare
  sample) before deleting the Desktop copies; evicted placeholders downloaded one by one, copied, verified, then
  removed; sim/work is now a symlink to the SSD. 44 old variant waveforms (palin -40C, nominal_palin3, ...) could not
  be downloaded in time: parked untouched in sim/work_icloud_leftover (still in iCloud; results already in results/).
  The SSD is exFAT: after an unplug it needed a long macOS consistency check before mounting.
- 2026-10-10: FAILED CHIP-RUNS RESOLVED: chip 7 (-40C, 3.30 V) by Gear integration; chip 4 (27C, 3.30 V) and chip 5
  (27C, 3.63 V, frames 4/5) by Gear + replacing the 0 V ammeter between LDO output and core with 1 milliohm
  (6 uV at 6 mA; deviation for these three chip-runs only).
- 2026-10-10: LDO TESTS - FINAL PRE-REGISTERED VERDICTS (all 16 chips; results/tx_ldo_L1.json, _L2.json, _L3.json):
  L1 SUPPLY (known sequence): 30 dB 1.000 at every VIN 2.97-3.63 V; 20 dB 0.963-0.977 -> PASS.
     (unregulated, same chips: 0.337 at -10%, 0.762 at +10%)
  L2 TEMPERATURE x SUPPLY (known sequence): 30 dB -40C 0.938/0.875/0.938, 85C 0.938/0.938/0.896 (2.97/3.30/3.63 V),
     mean 0.920 -> PASS. 20 dB 0.910/0.856/0.915/0.867/0.871/0.798. (unregulated chips 17-32: 0.071 ... 1.000)
  L3 ARBITRARY DATA UNDER DRIFT: 30 dB nominal 0.844; 2.97 V 0.843; 3.63 V 0.811; 85C 0.494; -40C/2.97 V 0.596;
     mean over drift 0.686 -> FAIL (needs nominal >= 0.90 and mean >= 0.80). Unregulated: 0.928/0.588/0.487/0.506/0.312.
  CONCLUSION: the on-chip LDO removes supply drift as a threat to identification on a known sequence (L1) and keeps
  combined temperature x supply identification >= 0.875 at 30 dB (L2; worst unregulated corner was 0.071). For
  arbitrary data it removes most of the supply part (0.59 -> 0.84 at -10%) but temperature remains the limit
  (85C ~0.49 with or without the LDO), and the nominal arbitrary-data accuracy is lower with the LDO (0.93 -> 0.84).
- 2026-10-11/12: HOUSEKEEPING. Project moved off the iCloud Desktop: fresh clone from GitHub at ~/code-a-chip-rffp
  (+ gitignored layout/work cells and results/*.log copied; sim/work -> SSD link). Rebuilt chip from the new location:
  identical (DRC 0 both tools, LVS 291). Old Desktop copy renamed ~/Desktop/code-a-chip-rffp_OLD_icloud (holds the 44
  iCloud-only leftovers; not deleted). Waveform backup: ~/rffp-backup/sim_work_waveforms.tar.zst (13.6 GB zstd of the
  ~55 GB SSD waveforms, zstd -t integrity OK) -> two copies (SSD + internal, outside iCloud).
- 2026-10-11/12: LDO VERIFICATION (item 4):
  4a MIM vs ideal compensation caps: identical within noise (VOUT 1.7998/1.8017/1.7961 V at -40/27/85C, load reg,
     settling; MC16 sd 29.5 vs 29.9 mV) -> the ideal caps in L1-L3 did not matter. sim now defaults to the MIM caps
     (BG_IDEAL_CC / LDO_IDEAL_CC reproduce the L1-L3 netlists).
  4c START-UP: measuring the true peak (not a 0.5 us window mean) showed VOUT overshooting to ~3.0 V on power-up (pass
     device on before the bandgap/OTA are alive) - the earlier "1.92 V" was a windowed average (CORRECTION). Fixes in
     sim/ldo.py: (1) guard that holds the pass gate at VIN until VREF is up (+ power-up-default caps); (2) RC soft-start
     (500k x ~10 pF MIM, tau ~5 us) between VREF and the OTA. Result: 1-10 us ramps peak <= 1.85 V at -40/27/85C.
     Remaining: 50 us-1 ms ramps still peak ~1.9-2.0 V, traced to a dynamic overshoot of the bandgap output during the
     ramp (no static overshoot in DC sweeps; some DC points at 27C, VIN 1.2-1.5 V do not converge). A VIN-threshold
     condition on the guard was tried and reverted (never released at 2.97 V; non-physical results at -40C).
     85C transient starts from 0 V stall numerically (timestep collapse at t ~ 5e-14 s); with the ramp starting at
     0.3 V and in DC sweeps the circuit starts normally.
     None of this affects L1-L3 (all start from the settled operating point).
- 2026-10-12: LDO LAYOUT UPDATED for the start-up fixes (guard: 5 MOS + 2 MIM 10x10; soft-start: 10 x 50k + MIM 70x70;
  OTA input -> soft-started ref): ldo_blk 508.9 x 223.4 um, 82 devices (40 after merging), DRC 0 Magic + KLayout,
  LVS MATCH. Netgen also matches the SIMULATED LDO netlist (sim/ldo.py) against the layout netlist (40 devices,
  "Circuits match uniquely") -> layout == simulated circuit. LDO placement in tx_core now computed from the block
  bbox. Chip 508.9 x 377.6 um, DRC 0 both tools, LVS MATCH (300 = 260 + 40); metal-only probe (layout/probe_nets.py):
  LDO VSS on the spine, LDO VOUT = core VDD, VIN separate.
  Steady state after the fixes: VOUT 1.8016 V, 5.75->7 mA -0.6 mV, dip 101 mV, stable; reaches 1.7 V at 18.4 us.
  Start-up peak (ramp to 3.63 V, -40/27/85C): 1 us 1.839/1.802/1.797; 10 us 1.841/1.802/1.797; 50 us 1.944/1.910/
  1.936; 200 us 1.919/1.885/1.905 V -> all below the 1.95 V limit (thin margin for 50-200 us ramps; limitation).
- 2026-10-12: ITEM 4b POST-LAYOUT WITH LDO: full chip extracted (C only): 472 devices, 1930 caps. Nominal, tt 27C,
  VIN 3.3 V, same frame (sim/pex_nominal_ldo.py): schematic+LDO |gain| 0.0763, EVM 14.23%, Q/I -1.5 deg;
  post-layout+LDO 0.0748, 13.82%, -2.3 deg -> layout (incl. LDO) preserves performance.
- 2026-10-12: DIGITAL FRONT END blocked on disk space: 13 GB free; LibreLane needs Colima + a multi-GB Docker image
  (existing Colima VM 4.2 GB, up to 20 GB). Awaiting the user's choice (free space / VM on SSD / skip).
- 2026-10-12: Waveform backup moved to /Volumes/PortableSSD/rffp-backup/sim_work_waveforms.tar.zst (user request;
  size identical, zstd -t OK on the SSD copy before the internal copy was deleted). NOTE: original waveforms and backup
  are now on the same drive (no protection against SSD failure). Internal disk free: 31 GB.
- 2026-10-24: NOTEBOOK GAPS 1-5 (user: "run this and then fix the front end"):
  1 LIVE DEMO: sim/live_demo.py simulates n Monte Carlo chips + the mismatch-free nominal chip (tt, no mm) on a
    66-sample frame (codes 5..26, 3x each), two ngspice processes in parallel; 2 chips + nominal = 5.1 min on the Mac.
    notebook/setup_tools.sh installs the pinned PDK (volare, c6d73a35) and builds ngspice 47 from source (2 min on 4
    cores, Ubuntu 22.04). Reference run saved as notebook/data/live_reference.json; notebook Section 2b.
    FINDING (portability): ngspice's RNG gives different values for the same seed on macOS vs Linux (agauss/sgauss
    test: seed 1 -> -0.446 Mac, -1.140 Linux), so "chip k" is platform-specific. Linux ngspice 41 (conda-forge) and
    47 agree to 7e-5; the nominal chip agrees Mac vs Linux to 2e-9 (EVM 17.19% both). The study's results are
    unaffected (all runs on one machine); the notebook checks nominal equality + chip-to-chip size instead.
    (An earlier note in this session blaming ngspice 41 was wrong and was corrected before anything was published.)
    FINDING (demo): the two chips share most of their offset from the nominal design (corr 0.97; shared 2.5e-2 rms vs
    nominal curve 4.8e-2); chip 1 vs chip 2 differs by 6.6e-3 rms = 26 noise units at 30 dB, 8 at 20 dB (one
    18-frame burst). Mismatch shifts the average chip away from the mismatch-free design (tt vs tt_mm differ only in
    mc_mm_switch). Observed on 3 draws only.
  2 GDS: notebook/gds/tx_core.gds.gz (1.1 MB) drawn with gdstk in the notebook. 3 tool-version table added.
  5 Colab badge added; PR description drafted (not opened).
- 2026-10-24: DIGITAL FRONT END (digital/): SPI (mode 0, 32-bit frames) + 128-word frame memory + thermometer decode,
  registered true/complement outputs (124 lines). LibreLane 3.0.16 (Docker, PDK 8afc8346), 50 MHz clock target.
  Iterations: v1 addressed memory -> 413x424 um, setup -1.46 ns, 2020 slew violations (128-way read muxes).
  v2 ring buffer (rotates per sample; no read mux) -> 342x353, timing met, 138 slew. v3 + ICG clock gate on the ring
  -> 290x301, power 5.8 -> 1.05 mW. Then repair settings: exclude clkdlybuf4s*/buf_1/clkbuf_1, post-GRT design
  repair on, slew repair margin 45%, hold margin 0.05 ns, CTS cluster 10 (run7 = final).
  FINAL (run7): 290.2 x 300.9 um, 4647 cells, 1482 flops (1280 ring), setup WS >= +11.0 ns and hold WS >= +0.057 ns
  over 9 corners; DRC 0 Magic + KLayout + route, LVS 0, antenna 0; power 1.02 mW (vectorless); IR 0.44 mV.
  Residual: 12 pin slew flags at ss_100C_1v60 only (4 nets driven by dlygate4sd3_1 hold cells, worst 0.884 ns vs flow
  target 0.75 ns; lib limit 1.5 ns) + clock-gate root clkbuf_16 fanout 16 vs guideline 10. Excluding dlygate4sd3_1
  makes hold repair fail (max buffer count) -> accepted and documented.
  TESTS (digital/tb/run_tests.sh): 947 checks 0 errors at RTL and on the routed gate-level netlist (unit delay;
  outputs sampled mid-cycle); main frame playback == sim/tx_full.py thermometer; 3 mutants all fail.
  Not wired to the analog core in one layout; no pads.
