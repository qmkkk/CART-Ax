# formal_experiment_report

C7 Formal Experiment Campaign — final report.
Campaign version `C7_FORMAL_v1`; manifest hash
`68051b9f8e18006a5b9cf97eedaa1c06b609f72033507e3e7fae1e890e2f4109` (frozen before the
first task ran; never modified).

**Campaign scope decision (user instruction, 2026-10-03):**
widths 8–192 are the **complete formal campaign** (1690/1690 tasks terminal).
Width 256 is a **supplementary stress probe**: its 17 completed tasks (one case:
10_add256 compile_ER + 16 ER reweights, all PASS) and 92 partial MED-bit compiles are
preserved; the remaining 243 unstarted/unfinished 256 tasks are marked
`NOT_RUN_RESOURCE_LIMIT` (reason: "global experiment wall-clock budget exhausted").
No 256 results were deleted or re-run; no selective 256 case was re-run.

Final ledger state (1950/1950 tasks terminal):

| status | count |
|---|---:|
| PASS | 1664 |
| TIMEOUT | 25 |
| SKIPPED_DEPENDENCY | 18 |
| NOT_RUN_RESOURCE_LIMIT | 243 (256-bit tail) |
| ERROR | 0 |

## 1. Exactness (d4 reweight == Ganak projected exact WMC)

### 1.1 ER (per case x distribution: D0–D5 + R0–R9, 16 rows per case)

| width | matched | rows | d4-NNF missing | Ganak timeouts |
|---|---:|---:|---:|---:|
| 8 | 112 | 112 | 0 | 0 |
| 12 | 128 | 128 | 0 | 0 |
| 16 | 160 | 160 | 0 | 0 |
| 32 | 160 | 160 | 0 | 0 |
| 64 | 160 | 160 | 0 | 0 |
| 128 | 144 | 160 | 16 (1 case: 4_add128 ER compile TIMEOUT) | 0 |
| 192 | 48 | 160 | 112 (7 cases: ER compile TIMEOUT) | 0 |
| 256 (suppl.) | 16 | 16 | 0 | 0 |

- **Every row where the d4 representation exists is bit-exact vs Ganak.**
  Zero mismatches across all completed ER rows (928 rows with d4 present).
- d4-NNF-missing rows are cases whose `compile_ER` hit the 180 s cap; their Ganak
  exact values are still recorded (no Ganak timeout anywhere, 0 rows).
- Ganak timeout: 0 in the entire campaign.

### 1.2 MED (per case x distribution, reconstructed total = sum_k 2^k P(bit_k))

| width | totals bit-exact | rows | d4-incomplete | note |
|---|---:|---:|---:|---|
| 8 | 42 | 42 | 0 | |
| 12 | 48 | 48 | 0 | |
| 16 | 60 | 60 | 0 | |
| 32 | 60 | 60 | 0 | |
| 64 | 60 | 60 | 0 | |
| 128 | 60 | 60 | 0 | |
| 192 | 36 | 60 | 6 (10_add192) | 18 rows SKIPPED_DEPENDENCY (compile_MED TIMEOUT, 3 cases) |

- Per-bit numeric ordering; const0 bits handled exactly; per-bit d4 == Ganak for
  every compiled bit (no per-bit mismatch).
- 10_add192 (6 rows): compile_MED TIMEOUT -> d4 totals incomplete, Ganak per-bit
  references recorded where available; not claimed as cross-validated.
- 3 cases at 192 (10/21/25_add192): compile_MED TIMEOUT -> MED evals are
  `SKIPPED_DEPENDENCY` (no d4 MED representation; recorded, not fabricated).

## 2. Distribution Sensitivity (within-width ranking, vs D0)

Family = same-width adder pool; Kendall tau-b (tie-corrected) + strict pairwise
inversions + rank shifts. The structured ranking study uses corrected D0–D5.
Sensitivity is **metric-, width-, and distribution-dependent**; it is not
universal and ER is not invariant.

### 2.1 ER ranking

Strict ER inversions occur in selected structured distributions:

| width | dist | tau-b vs D0 | strict inversions | n |
|---|---:|---:|---:|---:|
| 12 | D2 | 0.786 | 3 | 8 |
| 12 | D4/D5 | 0.929 | 1 | 8 |
| 32 | D2 | 0.511 | **11** | 10 |
| 64 | D2 | 0.956 | 1 | 10 |

Widths 8, 16, and 128 show no strict ER inversions under D0–D5.

### 2.2 MED ranking

| width | dist | tau-b vs D0 | strict inversions | n |
|---|---:|---:|---:|---:|
| 8 | D1/D2 | 0.206 | **7** | 7 |
| 8 | D3 | 0.309 | 6 | 7 |
| 12 | D1 | 0.929 | 1 | 8 |
| 12 | D4/D5 | 0.857 | 2 | 8 |
| 16 | D1/D2 | 0.501 | **9** | 10 |
| 16 | D3 | 0.645 | 6 | 10 |
| 16 | D4/D5 | 0.263 | **14** | 10 |
| 32 | D2 | 0.290 | **13** | 10 |
| 64 | D2 | 0.685 | 3 | 10 |
| 64 | D3 | 0.738 | 2 | 10 |

Width 128 shows no strict MED inversions under D0–D5. The 192 ranking rows are
a boundary subset because compile coverage is incomplete and are not used to
broaden the main ranking generality claim. `formal_ranking.csv` contains the
full structured ranking table.

## 3. Multi-Distribution Efficiency (compile-once/reweight-many, K=16/64)

Serial protocol; cold = fresh compile + parse/build + K evals; warm = K evals on
the loaded representation; marginal = warm/K; Ganak e2e = K serial invocations
including WSL/process/file overhead, with the same distributions on both sides.

### 3.1 Amortized cases per width (warm / cold)

| width | K16 warm | K16 cold | K64 warm | K64 cold |
|---|---:|---:|---:|---:|
| 8 | 7/7 | 7/7 | 7/7 | 7/7 |
| 12 | 8/8 | 8/8 | 8/8 | 8/8 |
| 16 | 10/10 | 10/10 | 10/10 | 10/10 |
| 32 | 10/10 | 8/10 | 10/10 | 10/10 |
| 64 | 10/10 | 3/10 | 10/10 | 9/10 |
| 128 | 9/9* | 1/9* | 10/10 | 8/10 |
| 192 | 4/4* | 0/4* | 3/3* | 3/3* |

\* Denominators reflect timing rows with a completed comparison at that K;
large-width timing tasks can terminate at the 180-s fresh-compile cap.

- Correct cold break-even buckets, recomputed directly from `formal_timing.csv`
  and independent of row order: **37/58 at K<=16, 18/58 at 16<K<=64, and
  3/58 remain non-amortized by K64**.
- Warm reweight marginal is orders of magnitude below repeated end-to-end WMC in
  the small/moderate widths and remains low relative to fresh compilation at
  larger widths.
- Ganak solver-internal time is retained only as a diagnostic; workflow speedup
  is not presented as a pure solver-algorithm speedup.

## 4. Scalability (fresh d4 compile of the ER CNF)

Conventional medians are the arithmetic median of the successful case-level
observations at each width.

| width | compiled | compile wall median / max (s) | NNF median / max (MB) | nodes median / max |
|---|---:|---:|---:|---:|
| 8 | 7/7 | 0.158 / 2.242 | 0.0018 / 0.0025 | 48 / 64 |
| 12 | 8/8 | 0.268 / 1.809 | 0.00465 / 0.1159 | 111.5 / 1769 |
| 16 | 10/10 | 0.455 / 0.705 | 0.0146 / 0.0213 | 325 / 448 |
| 32 | 10/10 | 1.599 / 17.773 | 0.06825 / 0.1385 | 1188 / 2555 |
| 64 | 10/10 | 18.4335 / 47.641 | 0.31385 / 0.8687 | 5671.5 / 15702 |
| 128 | 9/10 | 43.661 / 103.114 | 1.0435 / 2.4226 | 16512 / 36815 |
| 192 | 3/10 | 154.467 / 178.735 | 3.5592 / 4.9312 | 49077 / 74117 |
| 256 (suppl.) | 1/1 | 134.304 | 4.7485 | 62620 |

- The successful-case distribution broadens markedly with width, and the 180-s
  cap produces a clear structure-sensitive boundary at 128/192 rather than a
  single deterministic width limit.
- `formal_scalability.csv` preserves every per-case PASS/TIMEOUT row.

## 5. Applicability Boundary

- **8–64**: all ER compiles succeed; exactness is complete; cold reuse already
  amortizes by K16 for all cases at 8–16 and for most 32-bit cases.
- **128**: 9/10 ER compiles succeed; conventional successful-case median is
  43.661 s. K16 cold is mostly compile-dominated, while K64 cold amortizes in
  8/10 timing comparisons.
- **192**: clear boundary region — 3/10 ER compiles succeed within 180 s, with a
  154.467-s successful-case median; MED compilation/evaluation is correspondingly
  partial and dependency-limited for several cases.
- **256 (supplementary stress probe)**: the completed ER case compiles in
  134.304 s and all 16 ER reweights match exactly; the remaining tail was not
  executed under the global wall-clock budget and is not counted as timeout.

## 6. Negative / Boundary Results (retained, not repaired away)

1. Ranking changes are not universal: many metric/width/distribution cells have
   zero strict inversions, while selected ER and MED cells do change.
2. Width 128 has no strict ER or MED inversions under D0–D5 in the tested pool.
3. 25 formal TIMEOUT task records and 18 SKIPPED_DEPENDENCY records are retained.
4. Three cases with completed K64 comparisons remain non-amortized cold by K64.
5. Large-width compile success is case-dependent under the fixed 180-s cap.
6. 256 unexecuted tail tasks remain `NOT_RUN_RESOURCE_LIMIT`, not timeout/failure.
7. One functionally exact design (add12u_19A) remains excluded by the frozen
   eligibility rule.

## 7. Campaign Execution / Engineering Log (all fixes recorded)

1. **Resume self-test**: RESUME_SELFTEST_PASS (kill-simulation: completed task
   not re-run; interrupted task re-run on attempt 2; ledger/checkpoint/JSON/
   hashes intact).
2. **Manifest hash self-reference bug** (manifest_digest included the hash field)
   fixed before the campaign started; manifest regenerated once before the first
   task (still within the freeze window).
3. **MED miter invocation bug**: Circuit2Cnf generates the full per-bit set from
   a base name; per-bit `-o` naming produced no CNF. Fixed; affected artifacts
   cleaned and 2 compile_MED tasks re-run; 12 stale MED eval tasks re-run
   (transient Ganak failures during an aborted chunk reproduced in-process:
   code path verified correct, results re-generated cleanly).
4. **GBK decoding crash** on solver ANSI-escape output -> subprocess calls now
   use `encoding="utf-8", errors="replace"`.
5. **checkpoint replace PermissionError** (Windows transient lock) ->
   `write_atomic` retries with backoff.
6. **Rollup width-type bug** (str vs int) -> formal_ranking.csv was empty; fixed
   + MED ranking filter; full 84-row ranking regenerated from stored results.
7. **checkpoint/rollup None-guard** for NOT_RUN rows.
8. 192 MED evals whose compile_MED TIMEOUT'd re-classified SKIPPED_DEPENDENCY.
9. Deviation functions width_13/193/257 were **missing from the official VACSEM
   input set**; instantiated mechanically from the official parametric template
   (`abs_err = (a>b)?(a-b):(b-a)`, same module pattern as width_9/17/33/65/129)
   and synthesized with the frozen yosys 0.52 flow. Tool-input gap, not a method
   change.

## 8. Ledger Consistency Audit (post-campaign)

- ledger rows 1950 == manifest tasks 1950; every task has a terminal status.
- every PASS/TIMEOUT/SKIPPED task has a valid result JSON (task_id match,
  SHA256 matches the ledger); no orphan result files.
- checkpoint manifest_hash == manifest hash; manifest self-hash consistent.
- 8–192: 1690/1690 terminal. 256: 17 PASS + 243 NOT_RUN_RESOURCE_LIMIT;
  92 partial MED-bit metas preserved for 10_add256.
- the clean-release `case_level_summary.csv` contains all 75 manifest cases;
  unexecuted 256 cases are explicitly represented as NOT_RUN_RESOURCE_LIMIT.
- **AUDIT: NONE — ledger consistent.**

## 9. Files

- experiments/formal/formal_manifest.json/.csv (frozen)
- experiments/formal/formal_ledger.csv (1950 rows)
- experiments/formal/checkpoint.json
- experiments/formal/formal_er_results.csv (1056 rows; 928 with d4 values, 128 d4-missing rows)
- experiments/formal/formal_med_results.csv
- experiments/formal/formal_ranking.csv (84 rows)
- experiments/formal/formal_scalability.csv
- experiments/formal/formal_timing.csv
- experiments/formal/formal_break_even.csv
- experiments/formal/formal_failures.csv (all TIMEOUTs)
- experiments/formal/formal_summary.json
- experiments/formal/results/ (per-task JSONs + artifacts + per-bit MED metas)
- experiments/formal/logs/ (per-task logs)
- experiments/formal/_selftest/ (self-test data, isolated, not part of results)

## 10. Final Status

The frozen formal protocol (definitions, backend, distributions, timing, timeout
policy, K values, benchmark rules) was executed unchanged. 8–192 is the complete
formal campaign (1690/1690 terminal, zero mismatches on all completed exactness
rows). 256 is a supplementary stress probe stopped by the global wall-clock
budget (17 PASS preserved, 243 NOT_RUN_RESOURCE_LIMIT, partial MED bits
preserved). No method rescue, no selective re-runs, no outcome-driven changes.
