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
