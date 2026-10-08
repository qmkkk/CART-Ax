# HANDOFF

**Do not reopen method exploration unless a verified scientific correctness
flaw is found.**

## Current final state

- PRE_FREEZE_PASS (2026-10-03) — method/backend/distribution definitions frozen.
- Formal Experiment Campaign executed with the frozen protocol
  (C7_FORMAL_v1, manifest hash 68051b9f8e18006a5b9cf97eedaa1c06b609f72033507e3e7fae1e890e2f4109),
  checkpoint/resume runner, RESUME_SELFTEST_PASS.
- Final ledger: 1950/1950 tasks terminal — PASS 1664, TIMEOUT 25,
  SKIPPED_DEPENDENCY 18, NOT_RUN_RESOURCE_LIMIT 243 (256-bit tail stopped by
  the global wall-clock budget, per user instruction).
- Final Results Consistency Audit: **FINAL_RESULTS_AUDIT_PASS** (18/18).

## Method is frozen — do not rescue

- full-variable/full-Tseitin CNF -> official d4 -> exact rational PI reweighting;
- Ganak projected exact WMC = semantic reference;
- corrected circuit-relative D0–D5 + seed-42 random stream;
- 180 s timeout; K in {16,64}; numeric MED bit order; family-wise tau-b ranking;
- serial latency; cold = fresh compile + parse/build + K evals.

## Formal experiment completion

- **8–192 = complete** (1690/1690 terminal).
- 256 = supplementary stress probe: 17 PASS (10_add256 compile_ER + 16 ER
  reweights, all bit-exact) + 92 partial MED-bit compiles preserved;
  243 tasks NOT_RUN_RESOURCE_LIMIT.

## Main exactness conclusions

- ER: every d4 reweight equals Ganak bit-exactly wherever the d4 representation
  exists (928 rows; 0 mismatches; 0 Ganak timeouts). d4-missing rows exist only
  where the ER compile hit the 180 s cap (128: 1 case, 192: 7 cases).
- MED: per-bit exact everywhere compiled; reconstructed totals bit-exact at
  8/12/16/32/64/128 (all rows) and 36/60 at 192 (rest = compile-timeout
  dependencies, SKIPPED_DEPENDENCY / incomplete, honestly recorded).

## Ranking conclusions

- Under corrected structured D0–D5 distributions, sensitivity is **metric-,
  width-, and distribution-dependent** rather than universal.
- ER strict inversions occur at width 12 (D2: 3; D4/D5: 1 each), width 32
  (D2: 11, tau-b 0.511), and width 64 (D2: 1); widths 8/16/128 show no
  strict ER inversions under D0–D5.
- MED strict inversions occur at widths 8/12/16/32/64; strongest is width 16
  D4/D5 (14 inversions, tau-b 0.263), followed by width 32 D2 (13, tau-b
  0.290). Width 128 shows no strict MED inversions under D0–D5.
- The 192 ranking rows are a boundary subset because compile coverage is
  incomplete and are not used to broaden the main ranking generality claim.

## Break-even conclusions

- Warm reweight amortizes at K16 for every case with a completed K16 warm
  comparison.
- Cold break-even is computed directly from `formal_timing.csv`, independent of
  row order. Among the 58 cases with a completed K64 cold comparison:
  **37/58 amortize by K16, 18/58 first amortize between K16 and K64, and 3/58
  remain non-amortized by K64**.
- The three >K64 cases are compile-dominated large-width cases; this is a
  measured boundary, not a method-rescue target.

## Scalability boundary

- Conventional compile-wall medians among successful ER compiles: 0.158 s
  (8), 0.268 s (12), 0.455 s (16), 1.599 s (32), 18.434 s (64), 43.661 s
  (128), and 154.467 s (192). The single completed 256-bit stress-probe ER
  compile is 134.304 s.
- 192 = transition: 7/10 ER compiles timeout; MED bit compiles median ~73 s with
  frequent 180 s caps. 256: ER compiles in ~134 s but MED bit compiles are
  180 s-timeout-dominated.

## 128/192/256 actual status

- 128: complete; 1/10 compile timeout (4_add128); K16-cold mostly not amortized.
- 192: partial by design (timeouts recorded); 3/10 full pipeline.
- 256: supplementary; ER exact (17 rows); MED partial (92/257 bits of one case).

## Main-paper results vs supplementary

- **Main**: ER/MED exactness (8–128), metric/width/distribution-dependent
  ranking sensitivity, break-even characterization (8–128), scalability trend
  to 128.
- **Supplementary**: 192 boundary data, 256 stress probe (marked
  supplementary_stress_probe=true), negative results table, timeout/skip tables.

## Known limitations

- Empirical scope = approximate adders (public VACSEM + EvoApproxLib sets);
  no multiplier/MAC, no correlated distributions;
- 192/256: not fully scalable under the 180 s cap (recorded boundary);
- Ganak e2e includes process/WSL/file overhead (solver-internal time recorded
  as diagnostic only; workflow speedup is not claimed as pure algorithm speedup);
- add12u_19A excluded (functionally equal to exact; ER=0);
- deviation functions width_13/193/257 were generated from the official
  parametric template (upstream gap), same yosys flow as the provided ones.

## What remains

Only:
1. figures (data ready in `figures/plotting_data/`; scripts in
   `figures/plotting_scripts/`);
2. tables (all in `results/` + `supplementary/`);
3. paper writing (claims per `CLAIMS_AND_SCOPE.md`);
4. submission.

No new experiments, no method changes, no benchmark changes.
