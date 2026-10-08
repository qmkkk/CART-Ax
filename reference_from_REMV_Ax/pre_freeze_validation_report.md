# pre_freeze_validation_report

Pre-Freeze Final Repair & Controlled Regression — C7
Executed on the audited bundle `C7_external_final_audit_bundle_20261003_AUDITED.zip`.
External verdict: CONDITIONALLY_STRONG_BUT_NOT_YET_FREEZABLE.

## A. Version / Environment

| item | value |
|---|---|
| audited bundle | deliverables/C7_external_final_audit_bundle_20261003_AUDITED.zip (138 files, testzip clean) |
| audit documents | EXTERNAL_FINAL_AUDIT.md, LOCAL_AI_TASKS.md, FORMAL_EXPERIMENT_FREEZE_DRAFT.md, audit_metadata/external_audit_source.patch (4867 lines) |
| source alignment | 11 modified c5_*.py + 2 new c7_*.py copied from the audited bundle into src/python/ (blif_sim.py unchanged); pre-audit copies kept in src/python/_prefreeze_backup/ |
| Windows Python | 3.14.5 (D:\paper_project_3\.venv) |
| WSL | Ubuntu 26.04.1 (user k, 32 cores, 7.6 GiB RAM), WSL2 |
| Ganak | official v2.7.0 binary (repo HEAD e8f5184); invocation `ganak --mode 1 --prob 0 <file>.wmc` |
| d4 | official crillab/d4 commit 333370cc1e843dd0749c1efe88516e72b5239174 (built from source, WSL) |
| Yosys | 0.52 (Ubuntu 26.04 .deb, extracted, no sudo) — used in R7 add12, not re-run this round |
| EvoApproxLib | commit ec28be83bfce1b8e8b92bd456be520d323a568b5 (add12 sources) |
| VACSEM Circuit2Cnf | commit b11ede7 (built R5) — used for MED miter generation this round |
| timeout policy | single probe/compile timeout 180 s; no long probes |
| commands | see LOCAL_AI_TASKS.md; executed: c5_ground_truth.py, c5_ranking.py, c7_pre_freeze_regression.py, c7_med_backend_probe.py, c7_pre_freeze_timing.py |

## B. Audit Patch Verification（逐项确认）

| audit fix | present in aligned code | verified by |
|---|---|---|
| D4/D5 circuit-relative distributions (`named_dist`/`named_dists`) | YES (c5_common.py) | guards n∈{16,24,32,64,128}: D4≠D1, D5≠D2; all migrated scripts use them |
| MED numeric bit ordering (`med_bit_index`/`sort_med_artifacts`) | YES (c5_common.py) | ground truth MED per-bit loop uses numeric order; 35 const-bit rows ordered numerically |
| family-wise ranking + Kendall tau-b + strict inversions | YES (c5_ranking.py) | output has `kendall_tau_b_vs_D0`, `inversions_vs_D0`, `rank_shift`, per family; no mixed-family ranking |
| timing/cache fix: cached d4 compile never counts as fresh (cold=None on cache hit) | YES (c5_r7_phaseB.py d4_compile) | plus new c7_pre_freeze_timing.py uses a fresh directory and asserts `ct is not None` |
| run_ganak non-zero exit code treated as error | YES (c5_common.py) | exercised in all tasks |
| c5_scalability serial default (C7_MAX_WORKERS=1) | YES | not executed this round (pilot script) |
| no hard-coded D:/paper_project_3 paths in src/python | YES | audit grep PASS; add12 uses project-relative paths |
| new scripts c7_pre_freeze_regression.py / c7_med_backend_probe.py | YES | executed (Tasks 2/3) |

## C. Task 1 — Corrected Small Ground Truth + Ranking

### Ground truth
- Command: `.venv/Scripts/python.exe src/python/c5_ground_truth.py`
- Output: `experiments/parsed/c5_ground_truth.json` (pre-correction copy kept in
  `experiments/parsed/_prefreeze_historical_backup/`; historical reports unchanged).
- **all_match = true**; 10 circuits (5 add8 + 5 mult8) × 6 corrected distributions;
  exhaustive Fraction == Ganak exact for every ER and MED value.
- D4/D5 probability vectors verified distinct from D1/D2 for n_pi ∈ {16,24,32,64,128}.
- Numerically: all 20 circuit×distribution cells (D4 vs D1, D5 vs D2) now differ
  (e.g. 4_mult8 ER: D4 = 11077479/2^32 vs D1 = 1484743/2^32).
- MED reconstructed via numeric bit ordering; ER-iff-error>0 consistency assertion
  in `enumerate_circuit` passed for all 10 circuits.

### Ranking
- Command: `.venv/Scripts/python.exe src/python/c5_ranking.py`
- Output: `experiments/parsed/c5_ranking.json` — family-wise (add8, mult8), tau-b.
- add8 MED: D1/D2/D3 inv=4, tau_b=-0.1195 vs D0; **D4/D5 now distinct**
  (inv=0, tau_b=0.8367) — previously D4==D1/D5==D2 by the distribution bug.
- mult8 MED: D1 inv=1 tau_b=0.7379, D2/D4/D5 inv=0 tau_b=0.9487, D3 inv=1
  tau_b=0.7379.
- add8/mult8 ER: no ranking shift under any corrected distribution (tau_b=1.0,
  preserved as a negative result).
- No mixed add8+mult8 ranking is produced or used as a result.

### Monte Carlo
Not rerun: MC is a proxy/sensitivity reference only in the freeze draft and is
not a main paper result. If retained in the formal plan it will be rerun with the
corrected distributions in the formal campaign. Historical c5_montecarlo.json
(with the D4/D5 bug) is preserved in `_prefreeze_historical_backup/` and is not
usable for the paper.

## D. Task 2 — ER Pre-Freeze Regression (final d4 backend)

- Command: `.venv/Scripts/python.exe src/python/c7_pre_freeze_regression.py`
- Output: `experiments/parsed/c7_pre_freeze_regression.json`
- **PRE_FREEZE_ER_REGRESSION_PASS**; all_match = true.
- 7 cases × 16 distributions (corrected D0-D5 + 10 frozen random product
  distributions, seed 42, pool {1/8..7/8}) = **112/112 bit-exact** vs Ganak
  projected exact WMC. Zero mismatches.
- Cases: 3×add16 (frozen), 2×add32 (frozen), 2 non-degenerate add12.
- Backend: full-variable/full-Tseitin CNF → official d4 d-DNNF → exact rational
  PI reweighting (auxiliary literals neutral). Correctness = empirical bit-exact
  agreement with projected WMC (no blanket uniqueness claim).

## E. Task 3 — MED Backend Gate

- Command: `.venv/Scripts/python.exe src/python/c7_med_backend_probe.py`
- Output: `experiments/parsed/c7_med_backend_probe.json`
- **PRE_FREEZE_MED_BACKEND_PASS**; all_match = true; 0 mismatches.
- Cases: 1_add8 (width 9), 2_add16 (width 17, the formerly-hard case),
  10_add32 (width 33), corrected D0-D5, d4 MED bit-CNF compile + reweight vs
  Ganak exact reference.
- 144 non-const bit×distribution rows all bit-exact; 35 const0 rows handled
  exactly (error bit never set for those designs); reconstructed MED totals
  bit-exact per distribution per case (e.g. 10_add32 D0:
  70372513006515/8388608 on both sides).
- Numeric bit ordering confirmed (const-bit pattern consistent across scales).
- No localized repair was needed this round; no hidden mismatch.

## F. Task 4 — Fresh Serial Timing / Fairness Regression

- Command: `.venv/Scripts/python.exe src/python/c7_pre_freeze_timing.py`
- Output: `experiments/parsed/c7_pre_freeze_timing.json`
- Fresh output directory `experiments/raw/c5/nnf_prefreeze_timing/` (created new,
  removed before run); every compile asserted fresh (`ct is not None`); serial.
- Definitions: cold = fresh compile + one-time parse/build + K evaluations;
  warm = K evaluations on the loaded representation; marginal = warm/K;
  ganak e2e = K serial invocations including WSL/process/file overhead and .wmc
  writes; identical frozen distribution IDs (D0 + R0..R{K-2}, seed-42 stream) on
  both sides.

| case | fresh compile s | parse/build s | K16 warm/cold s | K16 ganak e2e s | K64 warm/cold s | K64 ganak e2e s | K16/K64 amort (warm,cold) |
|---|---:|---:|---:|---:|---:|---:|---|
| 10_add16 | 1.88 | 0.0018 | 0.042 / 1.92 | 4.78 | 0.172 / 2.05 | 20.32 | T,T / T,T |
| 1_add16 | 1.56 | 0.0009 | 0.027 / 1.59 | 6.64 | 0.072 / 1.64 | 19.27 | T,T / T,T |
| 2_add16 | 2.91 | 0.0022 | 0.048 / 2.96 | 6.99 | 0.198 / 3.11 | 20.07 | T,T / T,T |
| 10_add32 | 5.48 | 0.0094 | 0.238 / 5.73 | 9.08 | 1.663 / 7.15 | 40.04 | T,T / T,T |
| 11_add32 | 10.60 | 0.0111 | 0.202 / 10.81 | 10.17 | 0.774 / 11.38 | 40.69 | T,F / T,T |

- Marginal reweight: 0.0011-0.0260 s/eval (case- and K-dependent).
- Ganak startup baseline: 0.178-3.152 s per invocation (5 runs on a 3-var CNF;
  min 0.178 s; first run 3.15 s = cold WSL start). Ganak e2e includes this
  overhead; the reweight side does not — the two are never mixed.
- Ganak solver-internal time (`c o Total time [Arjun+GANAK]`) recorded as a
  diagnostic (e.g. 10_add32 K64 internal sum 12.64 s vs e2e 40.04 s); the
  workflow speedup is NOT claimed as pure solver-algorithm speedup.
- Note: 11_add32 K16-**cold** is not amortized (10.81 s vs 10.17 s) because the
  10.6 s fresh compile dominates K16 — recorded as a break-even boundary data
  point; K16-warm and K64 warm+cold amortize.
- Note: 10_add32 fresh compile measured 5.48 s here vs 24.4 s in R7 (wall-clock
  variance across runs; both are genuine fresh measurements; the pre-freeze
  serial value is the protocol-conformant one).

## G. All Anomalies / Errors (nothing hidden)

| item | status |
|---|---|
| D4==D1 / D5==D2 historical distribution bug (audit B1) | CONFIRMED in historical data, FIXED, regression passed (Task 1) |
| MED lexicographic two-digit bit-order bug (audit B2) | FIXED (numeric ordering), verified by ground truth + MED probe |
| cache-hit compile counted as 0 s cold (audit B4) | FIXED (cold=None on cache; fresh-dir timing), verified |
| mixed-family ranking + non-tau-b correlation (audit B3) | FIXED (family-wise tau-b), verified |
| any Task 1-4 mismatch | none (0/112 ER rows, 0/144 MED rows, all ground-truth cells) |
| any timeout this round | none (all d4 compiles and Ganak probes < 180 s) |
| non-zero tool return codes | none observed (run_ganak now flags them) |
| 11_add32 K16-cold non-amortized | preserved as a negative timing data point (not a correctness issue) |
| add12u_19A degenerate const0 case | excluded by prospective eligibility rule (functionally equal to exact; ER=0); exclusion recorded |
| Monte Carlo historical data | superseded (D4/D5 bug); not used; rerun deferred to formal phase if retained |

## H. Repair Cutoff Log

| item | classification |
|---|---|
| D4/D5 distribution generator | FIXED_BEFORE_FREEZE (one localized repair by external audit, regression passed) |
| MED numeric bit ordering | FIXED_BEFORE_FREEZE (audit patch, regression passed) |
| family-wise tau-b ranking | FIXED_BEFORE_FREEZE (audit patch, verified) |
| cache-safe fresh timing | FIXED_BEFORE_FREEZE (audit patch + fresh-dir protocol, verified) |
| Ganak return-code check | FIXED_BEFORE_FREEZE (audit patch) |
| serial default for latency | FIXED_BEFORE_FREEZE (audit patch) |
| Monte Carlo rerun | DEFERRED_NON_BLOCKING (proxy-only; formal phase if retained) |
| 11_add32 K16-cold break-even | DEFERRED_NON_BLOCKING (recorded data point; K16-warm and K64 amortize) |
| 64/128/192/256 scalability | DEFERRED_NON_BLOCKING (formal campaign after freeze) |
| correlated distributions / multipliers / new compilers / ML / FPGA | DEFERRED_NON_BLOCKING (out of scope per audit) |
| CLAIM_NARROWED | none required (ER and MED both pass on the final backend) |
| BLOCKING | none |

## Final Mechanical State

**PRE_FREEZE_PASS**

Conditions met:
1. corrected small exhaustive D0-D5 ground truth == Ganak exactly (all_match=true);
2. corrected within-family ranking with tau-b generated;
3. ER pre-freeze regression PASS (112/112 bit-exact);
4. MED backend gate PASS (144/144 bit-exact + totals) — MED remains a main
   claim with evidence, no narrowing needed;
5. fresh serial timing protocol executed and conformant (no cache-as-fresh,
   no concurrent Ganak, same distribution IDs, overhead stated);
6. no error/mismatch hidden or dropped.

---

STOP FIXING

C7 FORMAL METHOD / BACKEND / DISTRIBUTION DEFINITIONS ARE NOW FROZEN.
NO FURTHER METHOD RESCUE IS PERMITTED.
64/128/192/256 AND FULL BENCHMARK EXPANSION BELONG TO THE FORMAL EXPERIMENT CAMPAIGN.
