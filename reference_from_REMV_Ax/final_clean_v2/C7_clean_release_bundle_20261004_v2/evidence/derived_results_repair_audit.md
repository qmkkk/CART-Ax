# C7 Derived-Results Repair Audit

Date: 2026-10-04

## Verdict

**DERIVED_RESULTS_REPAIR_PASS**

No formal task, solver run, benchmark, distribution, timeout, or raw timing value
was changed. The repair is limited to downstream aggregation, documentation,
plotting inputs, and the rollup-only code paths that generated them.

## Checks

1. Raw formal task/result layer unchanged: PASS.
2. `formal_break_even.csv` rebuilt from `formal_timing.csv`, order-independent: PASS.
   - K<=16: 37/58
   - 16<K<=64: 18/58
   - >64: 3/58
3. `cold_K16` is populated whenever a completed K16 cold value exists: PASS.
4. Scalability summaries use `statistics.median` and numeric width sorting: PASS.
5. Width-256 `supplementary_stress_probe` flag is true for every 256-bit row: PASS.
6. Exactness summary is numerically width-sorted and matches source ER/MED rows: PASS.
7. Ranking prose matches `formal_ranking.csv`: PASS. ER is not described as invariant.
8. README task counts distinguish 8–128 (1430 tasks) from 8–192 (1690 tasks): PASS.
9. Clean-release case table contains all 75 manifest cases, including NOT_RUN 256 cases: PASS.
10. Source postprocessing code contains the corrected rollup logic: PASS.
11. Metadata hashes/manifests regenerated after repair: PASS (regenerated last).

## Corrected scientific summary

- Exactness remains unchanged: 928 ER rows with a d4 value match Ganak exactly;
  completed MED totals remain exact.
- Ranking sensitivity is metric-, width-, and distribution-dependent.
- Cold reuse has a measured break-even distribution of 37/58 by K16, 18/58
  between K16 and K64, and 3/58 beyond K64.
- Successful ER compilation shows a stable-to-structure-sensitive transition,
  with 9/10 success at 128 bit and 3/10 at 192 bit under the fixed 180-s cap.
- 256 remains supplementary stress-probe evidence; unexecuted tail tasks are
  NOT_RUN_RESOURCE_LIMIT, not failures.
