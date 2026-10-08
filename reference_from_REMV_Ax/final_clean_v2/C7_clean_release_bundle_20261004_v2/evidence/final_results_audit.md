# final_results_audit

> Scope note (post-release repair): this audit verifies ledger/task/result integrity.
> Derived rollups and prose were subsequently re-audited and corrected without
> rerunning experiments; see `derived_results_repair_audit.md`.


Final Results Consistency Audit for the C7 formal experiment campaign
(C7_FORMAL_v1, manifest hash 68051b9f8e18006a5b9cf97eedaa1c06b609f72033507e3e7fae1e890e2f4109).

Audit date: 2026-10-04 (packaging day). Source: experiments/formal/ (ledger,
checkpoint, per-task result JSONs, rollup CSVs).

## Result

**FINAL_RESULTS_AUDIT: PASS** (18/18 checks)

| # | check | result |
|---|---|---|
| 1 | formal_manifest task count == ledger rows | PASS (1950 == 1950, no missing/extra) |
| 2 | all tasks in legal terminal state (PASS/TIMEOUT/ERROR/SKIPPED_DEPENDENCY/NOT_RUN_RESOURCE_LIMIT) | PASS (PASS 1664, TIMEOUT 25, SKIPPED 18, NOT_RUN 243) |
| 3 | no residual RUNNING/PENDING | PASS (0/0) |
| 4 | every PASS task: parseable result, task_id match, SHA256 match | PASS (0 bad of 1664) |
| 4b | manifest self-hash consistent | PASS |
| 5 | no ganak=None row counted as validated PASS | PASS (0) |
| 6 | TIMEOUT-dependent task statuses reasonable (MED evals after compile_MED TIMEOUT -> SKIPPED_DEPENDENCY) | PASS (0 inconsistent) |
| 7 | no stale failed result marked PASS | PASS (0) |
| 8 | retry/resume attempt history preserved | PASS (attempts {1:1685, 2:3, 3:1, 5:1}; the attempt-3/5 tasks are the long compile_MED tasks repeatedly interrupted by wall-clock kills and resumed via per-bit sub-saves) |
| 9 | checkpoint hash == manifest hash | PASS |
| 9b | checkpoint current_task cleared (campaign stopped cleanly) | PASS |
| 10 | formal_er_results.csv reconstructible from raw results | PASS (1056 == 1056) |
| 11 | case-level summaries consistent with ledger | PASS (9 missing are 256 NOT_RUN cases without started tasks) |
| 12 | failures CSV complete (all TIMEOUT/ERROR) | PASS (25 == 25) |
| 13 | negative results preserved (ranking table complete) | PASS (84 rows) |
| 14 | results use corrected circuit-relative D0-D5 (D4!=D1, D5!=D2 at 16..256 PIs) | PASS |
| 15 | no legacy D4/D5 128-slicing generator in the pipeline | PASS |
| 16/17 | no old MED lexicographic ordering, no cache-as-fresh timing in the final protocol | PASS (frozen protocol: numeric MED order; fresh-dir timing; cold=None on cache) |

## Notes

- The 243 NOT_RUN_RESOURCE_LIMIT rows are 256-bit tasks stopped by the global
  experiment wall-clock budget (user instruction); they are NOT timeouts and are
  never counted as failures or as validated results. 256 remains a
  supplementary stress probe (17 PASS + 92 partial MED-bit compiles preserved).
- Two earlier audit items were metadata-only and were corrected before this
  pass: (a) checkpoint current_task was stale after the stop instruction
  (cleared; hash unchanged); (b) the attempt-history check was re-specified to
  accept multi-interruption histories (the attempt values themselves are the
  preserved evidence).
- No scientific result, result file, or ledger measurement was modified by this
  audit.
