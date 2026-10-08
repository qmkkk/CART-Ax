# run_report_7

## 1. User Request

C7 Round 7: Implementation Audit + Backend Rescue + Technical Freeze Readiness.
Fixed 5 cases (R6, frozen): 3 x add16 + 2 x add32.  No change to the factorized
PI probability model, ER/MED definitions, exactness standard, or the
compile-once/reweight-many idea.  No 600/1200 s brute-force probes; single
compile timeout = 180 s.  Timeouts/mismatches/failures preserved.  Phase 0
(implementation + timing audit) first; bugs fixed directly + regression; then
Phase A (full functional Tseitin compilation), Phase B (circuit-aware d4
rescue), Phase C (safe representation pruning), Phase D (SharpSAT-TD, only if
needed), then add12 (only on STRONG/MEDIUM success, pre-registered selection).
Final mechanical status STRONG / MEDIUM / EXHAUSTED only.  No journal/novelty/
next-direction judgments.

## 2. Execution Status

**COMPLETE** - all phases executed; final mechanical status
**READY_FOR_EXTERNAL_AUDIT_STRONG** (criteria in section 16).

## 3. Environment

- Project root: `D:\paper_project_3` (= `/mnt/d/paper_project_3` in WSL).
- Windows Python 3.14.5 (`.venv`); WSL Ubuntu 26.04.1, g++ 15.2.0, 32 cores,
  7.6 GiB RAM.
- Ganak official v2.7.0 binary (`tools/cache/ganak_linux/ganak`; repo HEAD
  e8f5184) - unchanged from R5/R6.
- d4 official repo `https://github.com/crillab/d4`, commit
  `333370cc1e843dd0749c1efe88516e72b5239174`, built from source (g++ 15.2);
  GMP/zlib headers+libs from official Ubuntu 26.04 `.debs` (libgmp-dev,
  libgmpxx4ldbl, zlib1g-dev) extracted to `tools/cache/deps/aptroot` (no sudo
  available); boost 1.85 headers from `tools/cache/boost_1_85_0`.  Binary:
  `tools/cache/d4/d4`.
- Ganak official `ddnnf-cleanup` built from repo source
  (`src/ddnnf_cleanup.cpp`, g++ -O2 -std=c++17 -I src).
- yosys 0.52 (`git sha1 fee39a3284c90249e1d9684cf6944ffbbcbb8f90`) from the
  official Ubuntu 26.04 `yosys_0.52-2_amd64.deb` + `yosys-abc_0.52-2_amd64.deb`
  + `libtcl8.6` .deb, extracted to `tools/cache/deps/yosysroot` (no sudo).
- EvoApproxLib official repo `https://github.com/ehw-fit/evoapproxlib`, commit
  `ec28be83bfce1b8e8b92bd456be520d323a568b5` (shallow clone).
- VACSEM Circuit2Cnf (`b11ede7`), unchanged from R5.

## 4. Phase 0 Implementation Audit

### 4.1 Profiler (per-case breakdown, 3 add16)

| case | NNF MB | nodes/arcs | read s | parse old s | parse new s | eval old s (warm) | eval new s (warm) | speedup |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 10_add16 | 0.41 | 8594/17733 | - | 0.017 | 0.021 | 0.0371 | 0.0382 | 0.97 |
| 1_add16 | 0.04 | 864/1878 | - | 0.003 | 0.003 | 0.0037 | 0.0039 | 0.97 |
| 2_add16 | 19.96 | 283059/603165 | - | 1.09 | 0.83 | 3.25 | 3.57 | 0.91 |

Key finding: the second (array-based forward-DP) evaluator is **not faster**
than the R6 dict/stack evaluator.  Per-eval cost (~3.3-3.6 s on the 19.96 MB
d-DNNF) is intrinsic exact-rational arithmetic over 283k nodes / 603k arcs,
not traversal/memoization overhead.  **No evaluator performance bug exists.**

### 4.2 Second independent evaluator (Phase 0C)

`eval_nnf_fast` in `src/python/c5_r7_phase0.py`: flat arrays, forward DP over a
precomputed children-first order (order mode auto-detected: asc/desc/dfs),
precomputed literal-weight map `{lit: p}`, module-level Fraction constants.
Same math as `eval_nnf`, different code path.  Node-id order sanity-checked
(all Ganak merged `.nnf` files satisfy child-id < parent-id).

Regression (new == old == Ganak/exhaustive reference, D0 and D3):

| case | family | old==ref D0/D3 | new==ref D0/D3 | new==old |
|---|---|---|---|---|
| 1_add8 | add8 (vs exhaustive gt) | T/T | T/T | T |
| 10_add16 | add16 (vs Ganak) | T/T | T/T | T |
| 1_add16 | add16 (vs Ganak) | T/T | T/T | T |
| 2_add16 | add16 (vs Ganak) | T/T | T/T | T |

### 4.3 Timing audit (Phase 0B)

- R5 historical issue: `c5_compile_reweight.py` re-parsed each NNF once per K
  block (4x total).  R6 already fixed (parse once per case); R7 confirmed.
- **R6 accounting bug (fixed in R7)**: the R6 amortization formula
  `compile_s + K*reweight` (a) excluded the one-time load/parse/build cost
  (~0.8-1.1 s for the 19.96 MB file) and (b) `compile_nnf` returns
  `compile_s = 0.0` on cache hits, which would have made re-runs optimistic.
  R7 reports **cold total** (compile + load/parse/build + K evals), **warm
  total** (K evals only) and **marginal per-eval** separately, and flags
  cache-served compiles.
- Ganak per-invocation wall-clock floor (WSL bash + process + parse + count of
  a 3-var CNF, 5 runs): 0.13-0.94 s (min 0.132 s).  Every "K independent
  Ganak" total below includes this overhead plus the .wmc file write; the
  reweight side includes the weight-map construction.  The two sides are never
  mixed across definitions.

### 4.4 Ganak compile configuration audit (Phase 0D)

- Invocation recorded (identical for add16 and add32 in R6, same code path
  `compile_nnf`): `ganak --mode 1 --prob 0 --compile <nnf> <wmc>` with a
  `.wmc` carrying `c p show 1..maxPI` + rational weights.
- Ganak source (`src/main.cpp` 208, 382-399; `src/counter.cpp`
  `find_best_branch` ~1585-1650): `--compile` forces a clean single-threaded
  DPLL (no restarts/vivify/BuDDy/Arjun/Puura); branch variables are chosen
  only among projected (independent) variables when available; internal
  (Tseitin) variables are assigned by the SAT oracle as witnesses.  **The R6
  compiles are therefore PI-projected DPLL-trace d-DNNFs**; the raw (no
  `c p show`) CNF makes ALL variables branchable - a genuinely different
  configuration, tested in Phase A.
- add32 timeout is NOT a config artifact: the killed runs were mid-write of
  0.5-1.0 GB d-DNNF temp files (R6 evidence, kept in `nnf_r6/`): the projected
  add32 representation is intrinsically huge.

### 4.5 Phase 0 marker

**CONFIGURATION_BUG_FIXED** (timing-accounting configuration bug fixed;
evaluator implementation audit CLEAN - no performance bug found; the case-2
blocker is representation size, not evaluator code).

## 5. Bugs / Configuration Issues Found and Fixed

| # | issue | root cause | fix | affected regression |
|---|---|---|---|---|
| 1 | R6 amortization excluded one-time load/parse/build; `compile_s=0.0` on cache hits | accounting method | R7 reports cold/warm/marginal separately; cache-served compiles flagged | 3 add16 K16/K64 re-measured (section 9) |
| 2 | R5 re-parsed NNF once per K block | loop structure | already fixed in R6; confirmed in R7 | - |
| 3 | (new code) `eval_nnf_fast` returned `values[order[-1]]`, wrong for root-first formats (d4 files) | my Phase-0 code | return `values[root]`; root passed explicitly | re-verified: all 4 regression cases still pass |
| 4 | (new code) dist slicing by `len(idx)` instead of family PI count (10_add16 has 24 active PIs of 32) | my Phase-0 code | slice by family count `N_PI_TOTAL` | fairness re-measured |
| 5 | 11_add32 raw NNF not evaluable by path-product semantics | Ganak raw-compile emits OR arcs with non-exclusive literal sets (50 same-polarity overlaps) + 40 orphaned nodes; no alternate root reproduces the Ganak value | recorded as BLOCKER (no new NNF semantics per rules); resolved by d4 (Phase B) | phaseA row blocked |

## 6. Timing Fairness Definition (used for all K data in R7)

- **Independent Ganak total (K)**: K separate `.wmc` files (identical clauses;
  weight lines differ) + K separate `ganak` processes; timed block includes
  `.wmc` file writes + WSL startup + parse + exact count.  Per-invocation
  startup floor measured: ~0.13-0.94 s.
- **Reweight warm total (K)**: K evaluations on the in-memory parsed NNF
  (loaded/parsed once); includes per-distribution weight-map construction.
- **Reweight cold total (K)**: fresh compile (single 180 s attempt; fresh
  times re-measured where the first attempt was cache-served) + one-time
  load/parse/build + K evaluations.
- **Marginal**: warm total / K.
- Amortization flags are reported for warm and cold **separately**; no mixed
  definitions.

## 7. Fixed 5-Case Manifest (unchanged from R6)

| width | case | PIs | ER CNF |
|---|---|---|---|
| add16 | 10_add16_err_0.566452_size_105_depth_13 | 32 | experiments/raw/c5/miters_r6/10_add16_..._er.cnf |
| add16 | 1_add16_err_0.00215149_size_143_depth_16 | 32 | .../1_add16_..._er.cnf |
| add16 | 2_add16_err_0.0311737_size_138_depth_13 | 32 | .../2_add16_..._er.cnf |
| add32 | 10_add32_err_0.197418_size_259_depth_14 | 64 | .../10_add32_..._er.cnf |
| add32 | 11_add32_err_0.223526_size_257_depth_14 | 64 | .../11_add32_..._er.cnf |

## 8. Ganak Projected (R6) vs Raw Full-Tseitin Compile (Phase A)

| case | R6 projected | Phase A raw | D0/D3 exact (raw) | K16 amort warm/cold | K64 amort warm/cold |
|---|---|---:|---:|---|---|---|
| 10_add16 | 4.25 s / 0.41 MB | 2.57 s* / 0.0078 MB / 190 nodes | T/T | T/T | T/T |
| 1_add16 | 1.05 s / 0.04 MB | 0.96 s / 0.0027 MB / 93 | T/T | T/T | T/T |
| 2_add16 | 4.35 s / **19.96 MB** | 1.00 s / **0.0086 MB** / 96 | T/T | T/T | T/T |
| 10_add32 | **>180 s timeout** | **2.46 s** / 0.0275 MB / 183 | T/T | T/T | T/T |
| 11_add32 | **>180 s timeout** | 0.96 s / 0.0413 MB / 219 | **BLOCKED (mismatch)** | - | - |

\* fresh re-measurement; the on-disk cache came from an earlier R7 attempt
(same invocation, byte-identical output 7839 B).

Phase A conclusion: full-Tseitin compilation collapses the projected
representation (2_add16: 19.96 MB -> 8.6 KB; 10_add32: timeout -> 2.5 s) and is
bit-exact on 4/5 cases.  11_add32's raw NNF cannot be evaluated by the
path-product semantics (blocker recorded; no new NNF semantics invented).

## 9. d4 Backend (Phase B) - all 5 fixed cases

| case | d4 compile s | NNF MB | nodes/arcs | reweight D0/D3 s | D0/D3 exact | K16 warm/cold vs ganak | K64 warm/cold vs ganak |
|---|---:|---:|---:|---:|---|---|---|
| 10_add16 | 3.47 | 0.0156 | 355/723 | 0.0024/0.0024 | T/T | 0.046/0.047 vs 7.85 | 0.208/0.212 vs 17.51 |
| 1_add16 | 2.27 | 0.0050 | 124/253 | 0.0006/0.0007 | T/T | 0.036/0.037 vs 7.47 | 0.125/0.126 vs 25.70 |
| 2_add16 | 0.90 | 0.0158 | 362/745 | 0.0018/0.0017 | T/T | 0.053/0.057 vs 8.23 | 0.244/0.246 vs 30.85 |
| 10_add32 | 24.37 | 0.1385 | 2555/5478 | 0.028/0.033 | T/T | 0.461/**24.85** vs 10.45 | 1.788/26.18 vs 32.68 |
| 11_add32 | 6.29 | 0.0687 | 1174/2550 | 0.012/0.012 | T/T | 0.234/6.53 vs 7.65 | 0.569/6.87 vs 28.44 |

All timings are bit-exact vs Ganak exact WMC (D0 and D3, 10 values).  The only
non-amortized cell is 10_add32 K16-**cold** (24.85 s vs 10.45 s): its 24.4 s
compile dominates K16; K16-warm and both K64 cells are amortized.

Additional diagnostics:
- d4's own unweighted count `s` is recorded; for both add32 CNFs
  `s = ER_count * 2^24` exactly (853029939 and 960702897 error inputs x
  16777216), i.e. the VACSEM CNFs contain ~24 free (unconstrained) internal
  variables; the neutral-weight reweight correctly sums them out (this is why
  the D0 cross-check `eval == s/2^64` is expected-false for add32 and true for
  add16, e.g. 1_add16: s = 8355840 = 255/131072 x 2^32).
- d4's `-fpv` (projected compile) option is declared in `core/Main.cc` but not
  wired into the compilation path (source audit) - noted; full-variable d4
  compilation was used and is exact by the unique-extension argument.
- IJCAI 2025 "circuit-aware d-DNNF compilation" official implementation: NOT
  located after GitHub searches (closest find: VincentDerk/
  ICTAI2024-PruningTseitinCircuits, an ICTAI 2024 tool, not IJCAI 2025; dblp
  blocked by bot-check, Semantic Scholar rate-limited).  Recorded as a
  tool-availability blocker; the official d4 (mature, publicly released,
  commit-pinned) was used instead, per the "普通 d4/CNF compile" fallback.

## 10. Safe Representation Pruning (Phase C)

Target: the R6 19.96 MB 2_add16 projected d-DNNF.

- Structural audit: 283059 nodes / 603165 arcs; 96 distinct variables on arcs
  (32 PI + 64 internal); 1 node unreachable from the root (the false sink);
  5138 same-polarity OR-arc literal overlaps (benign here: the R6/R7
  evaluation is bit-exact, so exclusivity is established by other literals);
  380665 opposite-polarity pairs.
- Official Ganak `ddnnf-cleanup` (built from the ganak repo source), both
  strict and --no-strict-decomp: flattened-nested-and = 0, elided-unary-and =
  0, dropped = 1 (the dead false node); output 20.75 MB (input 19.96 MB).
  Cleaned files still bit-exact on D0/D3 (checked with both evaluators).
- **Conclusion: no safe exact pruning exists for this representation; the
  size is intrinsic to the projected DPLL-trace.  The representation fix is
  the compiler: d4 produces 0.0158 MB for the same CNF (~1260x smaller).**
  No approximate/heuristic pruning was applied (prohibited).

## 11. SharpSAT-TD (Phase D)

**Skipped** - per the round rule, backend rescue stops once STRONG_SUCCESS is
reached (achieved in Phase B, see section 16); installing/testing a further
tool was not required.

## 12. Third add16 (2_add16) - before / after

| metric | R6 (Ganak projected) | R7 Phase A (Ganak raw) | R7 Phase B (d4) |
|---|---:|---:|---:|
| compile | 4.35 s | 1.00 s | 0.90 s |
| NNF size | 19.96 MB | 0.0086 MB | 0.0158 MB |
| nodes/arcs | 283059/603165 | 96/430 | 362/745 |
| reweight per eval | 3.20-3.84 s | ~0.002-0.005 s | ~0.002 s |
| K16 (reweight vs ganak) | 51.6 s vs 7.7 s (FAIL) | 0.03 s vs 8.95 s | 0.05/0.06 vs 8.23 |
| K64 (reweight vs ganak) | 226.0 s vs 19.7 s (FAIL) | 0.12 s vs 31.6 s | 0.24/0.25 vs 30.85 |
| K16/K64 amortized | F/F | T/T | T/T (warm and cold) |

The representation blocker is resolved (per-eval ~2000x faster, amortization
restored at both K).

## 13. add32 rescue

- 10_add32: R6 projected compile >180 s timeout -> Phase A raw 2.46 s /
  0.0275 MB exact; Phase B d4 24.37 s / 0.1385 MB exact.  K16 warm amortized,
  K16 cold NOT (compile-dominated), K64 warm AND cold amortized
  (26.18 s vs 32.68 s).
- 11_add32: R6 projected >180 s timeout; Phase A raw compiles in 0.96 s but its
  NNF is not evaluable (blocked, section 5); **Phase B d4 6.29 s / 0.0687 MB,
  D0/D3 bit-exact, K16 warm+cold and K64 warm+cold amortized** (6.53 s vs
  7.65 s at K16 cold; 6.87 s vs 28.44 s at K64 cold).
- Both fixed add32s are therefore rescued (one fully, one with a
  compile-dominated K16-cold caveat).

## 14. add12 scaling-chain probe (STRONG_SUCCESS bonus)

Pre-registered selection (fixed before any result): official EvoApproxLib
`adders/12_unsigned/pareto_pwr_ep`, lexicographically first 3 design names
(no _pdk45 variant): **add12u_054, add12u_19A, add12u_2MB**.
Exact counterpart: `assign O = A + B` (12-bit), same yosys 0.52 flow
(read_verilog; synth -top; write_blif) -> gate-level .names BLIF consumed by
the official Circuit2Cnf ER miter.

| case | nominal (from .v header) | D0 Ganak | ganak projected compile | d4 compile / NNF | D0/D3 exact (both reps) | K16 warm/cold vs ganak | K64 warm/cold vs ganak |
|---|---|---:|---:|---:|---|---|---|
| add12u_054 | EP 89.56% | 7337/8192 | 0.94 MB | 2.28 s / 0.0107 MB | T/T | 0.042/2.325 vs 9.81 | 0.142/2.425 vs 21.65 |
| add12u_19A | **MAE=0, WCE=0, EP=0** | - | - | - | - | - | - |
| add12u_2MB | (Pareto point) | 2097151/2097152 | 6.42 MB | 12.14 s / 0.1159 MB | T/T | 0.316/12.46 vs 8.58 | 1.511/13.66 vs 40.00 |

add12u_19A: the ER miter is **const0** (Circuit2Cnf output `_er.cnf_const0`,
UNSAT) - the nominal "approximate" design is functionally equal to the exact
adder; ER = 0 for every distribution.  Recorded as a degenerate/equal case
(the add8-scale `equal_diagnostic` analogue), NOT as a verification result.

Scaling chain (d4 NNF sizes, MB): add8 (R5, 0.002) -> add12 (0.011-0.116) ->
add16 (0.005-0.016) -> add32 (0.069-0.139).  Compile times: 1-24 s.

## 15. All Timeouts / Mismatches / Blockers

1. R6 projected add32 compiles >180 s: kept as R6 evidence (temp files show
   mid-write of 0.5-1.0 GB d-DNNFs); not re-run (identical invocation).
2. Phase A 11_add32 raw NNF: **reweight mismatch vs Ganak** (D0
   460592835/2^31 vs 960702897/2^32) - blocked; no new NNF semantics per the
   rules; resolved by d4.
3. d4 `-fpv` projected-compile option: declared but not wired (source audit) -
   noted, full-variable compile used.
4. IJCAI 2025 circuit-aware d-DNNF official implementation: not located
   (tool-availability blocker, recorded).
5. add12u_19A: degenerate const0 (equal to exact) - recorded, no results.
6. 10_add32 K16-cold: not amortized (compile-dominated 24.4 s) - recorded,
   all other cells amortized.
7. No reweight mismatch occurred on any d4 representation (10/10 values
   bit-exact).

## 16. Final Mechanical Status

**READY_FOR_EXTERNAL_AUDIT_STRONG**

Mechanical check against the pre-registered STRONG criterion ("at least one
fixed add32 successfully exact-compiled/reweighted with actual K16/K64
benefit"):
- 11_add32: compile success (d4, 6.29 s), D0/D3 bit-exact vs Ganak,
  K16 amortized (warm AND cold), K64 amortized (warm AND cold).  **satisfied**
- 10_add32: compile success, D0/D3 bit-exact, K16 warm + K64 warm/cold
  amortized (K16-cold caveat recorded).  **satisfied**
- Additionally all 3 fixed add16 are exact and amortized at K16 and K64
  (the MEDIUM criteria are also fully met).

Backend rescue stopped after Phase B per the success rule; Phase D skipped.

## 17. Data Files for External Analysis

- experiments/parsed/c5_r7_phase0.json (profiler, regression, startup
  baseline, fairness)
- experiments/parsed/c5_r7_phaseA.json (raw full-Tseitin Ganak compile)
- experiments/parsed/c5_r7_phaseB.json (d4 backend, all 5 cases)
- experiments/parsed/c5_r7_add12.json (add12 probe)
- experiments/raw/c5/nnf_r7a/ (raw-compile NNFs, incl. 11_add32 blocked one)
- experiments/raw/c5/nnf_r7b/ (d4 NNFs, 5 cases)
- experiments/raw/c5/nnf_r7c/ (ddnnf-cleanup outputs)
- experiments/raw/c5/add12/ (blif, miters, wmc, nnf_ganak, nnf_d4)
- experiments/logs/r7_phaseA.log, r7_phaseB.log, r7_add12.log
- state/experiment_ledger.csv (5 new R7 rows), state/executor_state.json,
  state/toolchain.json

## 18. Reproduction Commands

```bash
D:/paper_project_3/.venv/Scripts/python.exe src/python/c5_r7_phase0.py
D:/paper_project_3/.venv/Scripts/python.exe src/python/c5_r7_phaseA.py
D:/paper_project_3/.venv/Scripts/python.exe src/python/c5_r7_phaseB.py
D:/paper_project_3/.venv/Scripts/python.exe src/python/c5_r7_add12.py
# d4 build (WSL): make CXX="g++ -std=c++17 -I<aptroot>/usr/include
#   -I<aptroot>/usr/include/x86_64-linux-gnu -I<boost>" \
#   LFLAGS="-L<aptroot>/usr/lib/x86_64-linux-gnu -L/opt/local/lib
#   -I/opt/local/include -lz -lgmpxx -lgmp patoh/libpatoh.a"
# ddnnf-cleanup build (WSL): g++ -O2 -std=c++17 -I src
#   src/ddnnf_cleanup.cpp -o /tmp/ddnnf-cleanup
# yosys (extracted .deb, WSL):
#   LD_LIBRARY_PATH=<aptroot-lib> yosys -p "read_verilog f.v;
#   synth -top <top>; write_blif f.blif"
```

## 19. Unexecuted Items

- Phase D (SharpSAT-TD): skipped by the STRONG_SUCCESS stop rule.
- IJCAI 2025 circuit-aware tool: not located (recorded blocker); official d4
  used instead.
- add12u_19A: no verification possible by construction (design equals exact).
- No multiplier/mac, no Vivado, no ML, no T1-T5, no long probes (per rules).
