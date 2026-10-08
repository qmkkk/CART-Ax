# CLAIMS_AND_SCOPE

## A. SAFE CLAIMS

1. **Exact distribution-aware verification**: exact (bit-exact vs Ganak
   projected WMC) ER/MED verification of approximate adders under factorized
   per-PI-bit product distributions, for all cases whose d4 representation
   compiles within the 180 s cap (0 mismatches on 928 ER rows, widths 8–192;
   MED totals bit-exact at 8–128 and partially at 192).
2. **Compile-once / reweight-many**: a single d-DNNF compilation of the error
   CNF supports exact reweighting for many distributions (marginal ~0.2 ms–0.1 s
   per evaluation across the measured widths).
3. **Metric-, width-, and distribution-dependent ranking sensitivity**: under
   corrected D0–D5, strict ER inversions appear at widths 12/32/64 for selected
   distributions, while MED inversions appear at 8/12/16/32/64 (up to 14 at
   width 16 / D4-D5 and 13 at width 32 / D2). Width 128 has no strict
   inversions for either metric under D0–D5.
4. **Measured break-even**: with the serial frozen timing protocol and only
   cases having a completed K64 cold comparison, 37/58 cases amortize by K16,
   18/58 first amortize between K16 and K64, and 3/58 remain non-amortized by
   K64.
5. **Measured scalability boundary**: fresh d4 compile times and NNF sizes grow
   with width (0.16 s / 1.8 KB at 8-bit to ~135–180 s / ~5 MB at 192–256);
   192 is the transition width under the 180 s cap; 256 is a supplementary
   stress probe (ER exact, MED bit compiles timeout-dominated).
6. **Exactness of the reference chain**: exhaustive enumeration == Ganak == d4
   reweight on the 10 small circuits (corrected D0–D5), and Ganak never timed
   out in the formal campaign.
7. **Robustness of the pipeline**: checkpoint/resume runner with atomic task
   writes (self-test passed), so multi-hour campaigns survive interruption with
   at most one atomic task lost.

## B. CLAIMS REQUIRING CAREFUL WORDING

1. "d4 / full-Tseitin / knowledge compilation" — enabling prior techniques, NOT
   contributions of this work. Frame as: a reusable exact-evaluation workflow
   built on mature public tools (cite d4, Ganak, VACSEM).
2. Exactness of full-variable d-DNNF reweighting — empirical, scoped statement:
   "bit-exact vs projected exact WMC on the fixed distribution set"; do NOT use
   a blanket 'unique internal extension' argument (some CNFs contain free
   auxiliary variables; neutral-weight reweighting is validated empirically).
3. "Non-uniform distributions change design evaluation" — use the measured
   metric/width/distribution-dependent result. ER is more stable in several
   widths but is not invariant; MED has stronger shifts in several structured
   D0–D5 settings. Do not generalize beyond measured families/distributions.
4. Workflow speedup vs Ganak — end-to-end including process/file overhead;
   never present as pure solver-algorithm speedup (Ganak solver-internal time
   is recorded as a diagnostic).
5. Scale claims — approximate adders only; 8–128 complete, 192 boundary,
   256 supplementary stress probe (NOT_RUN_RESOURCE_LIMIT tail must not be
   described as measured timeout data).
6. Benchmark selection — eligibility excludes functionally exact designs
   (add12u_19A recorded); selection rules frozen pre-run.

## C. FORBIDDEN CLAIMS

1. "First ever non-uniform approximate-circuit analysis" (or similar novelty-
   first phrasing).
2. "New d-DNNF algorithm" / "new SAT solver" / "new knowledge compilation
   method".
3. "All non-uniform distributions change ranking" or "ER ordering is
   invariant under all measured distributions".
4. "Always faster than Ganak".
5. "Scales universally to all 256-bit circuits".
6. Any claim based on the historical D4/D5 distribution bug or the historical
   lexicographic MED bit ordering.
7. Any claim that 256 NOT_RUN_RESOURCE_LIMIT tasks are timeouts or failures.
8. Any claim covering multipliers, MACs, correlated inputs, FPGA, or ML.
