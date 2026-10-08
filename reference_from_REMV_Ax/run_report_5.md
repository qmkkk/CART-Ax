# run_report_5

## 1. User Request

Round-5 execution campaign (2026-10-03), executor-only mode per AGENTS.md.  Rounds 1-4
(T1/T2/T3) frozen and archived - not modified, not overwritten.  New **C7 exact-verification
feasibility pilot**, restricted to problem validation and a mechanism probe:

1. Research question: for approximate combinational circuits under factorized non-uniform
   primary-input (PI) distributions, can distribution-weighted ER and MED/MAE be computed
   exactly; how expensive is general exact WMC; does compile-once/reweight-many show reuse
   value.  NOT presented for arbitrary correlated / Gaussian / exponential distributions;
   literal-weight WMC represents only independent, factorized per-PI-bit distributions.
2. Tools: official VACSEM and official Ganak (repos/commits/compile commands recorded); >=3
   VACSEM uniform ER/MED examples reproduced; Ganak exact rational projected-WMC flow verified
   with a small hand-computed CNF; MCAC not executed (no official code) - recorded.
3. Fixed benchmarks (no result-driven selection): 5 8-bit approximate adders + 5 8-bit
   approximate multipliers from EvoApproxLib (via VACSEM input/), dictionary-order of file
   names, exact counterparts; scalability set add32/add64/mult12/mult14/mult15/mac
   (mult14 absent -> documented substitution mult16-new).
4. Exact distributions: D0-D5 (exact rationals) + 16 random product distributions (seed 42,
   p in {1/8,1/4,1/2,3/4,7/8}) for the reuse experiment; not modified by results.
5. Weighted exact verifier: VACSEM Circuit2Cnf miter chain; PI identification and projected
   weighted model counting (projection = original PIs; PI literal weights p / 1-p; internal
   variables must not change the input probability mass).
6. Correctness ground truth: 10 small circuits x 6 distributions: exhaustive enumeration with
   Python Fraction vs Ganak exact projected-WMC, exact equality (no float tolerance); D0
   cross-checked vs VACSEM.  Any mismatch fixed before performance stats.
7. Monte-Carlo proxy gap: N={1000,10000,100000} x seeds={101,202,303,404,505}; MC is NOT an
   exact baseline.
8. Ranking-shift: exact ER/MED rankings per distribution vs D0: pairwise inversions, Kendall
   tau, per-circuit rank shift (data only).
9. Scalability: add32/add64/mult12/mult15/mult16-new/mac x D0-D5 x ER/MED with Ganak exact
   projected-WMC, per-case timeout 180 s, all timeouts kept (not dropped).
10. Compile-once/reweight-many: Ganak official --compile d-DNNF once per error-query CNF; a
    minimal exact rational evaluator reweights PI literals only; internal/aux semantics handled
    correctly; every value cross-checked; K={1,4,16,64}; if the official compile
    representation cannot be reliably reweighted exactly, record the blocker (no fabricated
    results).
11. No Vivado, no board, no new approximate synthesis, no T4/T5, no ML predictor, no correlated
    distributions, no new search algorithm.  No CONTINUE/STOP / paper / journal / novelty /
    next-direction judgment.  Project hygiene: reuse directories, only run_report_5.md as new
    Markdown, delete temporary files.

## 2. Execution Status

**COMPLETE** — tools obtained and built; hand-checked Ganak flow; miters for all 16 circuits;
exhaustive ground truth == Ganak exactly on all 10 small circuits x 6 distributions; MC,
ranking and scalability data complete; compile-once/reweight-many executed on the verified
subset with the remaining cases recorded as blockers.  No scientific judgment made.

## 3. Environment / Tools (official, with URL, commit, build)

- Project root (Windows): `D:\paper_project_3` ; (WSL): `/mnt/d/paper_project_3`
- **VACSEM**: `https://github.com/changmg/VACSEM`, commit `b11ede7` (2024-04-13), local
  `tools/cache/VACSEM`.  Built `Circuit2Cnf` from source (official repo + bundled ABC):
  `cmake -DREADLINE_FOUND=FALSE -DCMAKE_CXX_FLAGS=-I<boost_1_85_0> .. && make` using a
  rootless CMake 3.29.9 tarball; boost 1.85.0 headers (header-only) for `core`.  Prebuilt
  `script/B+E_linux` is the Phase-2 #SAT solver (not needed this round).  Run from the repo
  root: `./Circuit2Cnf/build/core/Circuit2Cnf.out -t ER -e <exact> -a <approx> -o <out>.cnf`
  (and `-t MED -d <deviation.blif>` for MED).
- **Ganak**: `https://github.com/meelgroup/ganak`, cloned HEAD `e8f5184` (2026-09-22) as
  source reference; counting performed with the **official v2.7.0 release binary**
  `ganak-v2.7.0-linux-amd64` (`tools/cache/ganak_linux/ganak`), exact rational projected-WMC
  via `--mode 1 --prob 0` (non-probabilistic).  d-DNNF compile via `--compile <file>.nnf`.
- Windows Python 3.14.5 (`.venv`); Verilator not used this round.
- CMake 3.29.9 rootless tarball + Boost 1.85.0 headers kept in `tools/cache/` for rebuild.

## 4. Ganak flow verification (small hand-computed CNFs)

- `F=(x1 v x2)`, p(x1)=p(x2)=1/2, projection=both: expected 3/4 -> **Ganak exact 3/4**.
- `F=(x1vx2)(x2vx3)(-x1 v -x3)`, p=(1/2,1/4,3/4): hand count 5/32 -> **Ganak exact 5/32**.
- Projection test with an unconstrained auxiliary var (weights 1/3,2/3), projection={x1,x2}:
  result unaffected -> **3/4** (projection works).
- Rational weights use the competition format `c p weight <lit> <num>/<den> 0`; header order
  `c t pwmc` / `p cnf ...` / weight lines / clauses.
- MCAC: **not executed** (no official code; recorded per instruction).

## 5. Benchmark manifest (fixed, dict-order, not result-driven)

Small correctness set (EvoApproxLib 8-bit, exact = family BLIF):
- 5 adders (add8 dir, lexicographic first 5): 1_add8_err_0.0299377, 2_add8_err_0.11734,
  3_add8_err_0.188568, 4_add8_err_0.269669, 5_add8_err_0.325058 (9-bit outputs).
- 5 multipliers (mult8 dir, lexicographic first 5): 10_mult8_err_0.0891418, 1_mult8_err_0.00114441,
  2_mult8_err_0.00216675, 3_mult8_err_0.00396729, 4_mult8_err_0.00585938 (16-bit outputs).
  Note: lexicographic "10_" < "1_" because '0' < '_' (verified; selection is fixed and
  documented, not result-driven).
Scalability set (exact vs the lexicographic-last approximate file of each family):
- add32 (64 PI, 33 out), add64 (128 PI, 65 out), mult12 (24 PI, 24 out),
  mult15 (30 PI, 30 out), **mult14 absent from the repo -> documented substitution
  mult16-new** (32 PI, 32 out), mac (12 PI, 8 out).
- Full manifest: `experiments/configs/c5_manifest.json` (created from build_manifest()).
- Deviation functions for MED exist for all required widths (9, 16, 24, 30, 32, 8).

## 6. Distributions (exact rationals, per PI bit; N=16/12/24/30/32/64/128 PIs)

D0: all 1/2;  D1: all 1/4;  D2: all 3/4;  D3: even index 1/4, odd 3/4;
D4: first half 1/4, second half 3/4;  D5: first half 3/4, second half 1/4.
Random reuse distributions: seed 42, 64 draws, p in {1/8,1/4,1/2,3/4,7/8}
(16 used for K<=16, 63 for K=64; the first 16 are recorded).
Weight application: PI literal x_i gets p_i, -x_i gets 1-p_i; internal (Tseitin/auxiliary)
variables weight 1 on both literals so they never change the input probability mass; the
projection is exactly the original PI set (CNF maxPI vars; isolated PIs - which the miter
drops - contribute weight factor 1 and are excluded from the projection, with weights mapped
by original PI index).

## 7. Correctness ground truth (exhaustive == Ganak, bit-exact)

**Exact ER and MED per circuit x distribution (exhaustive == Ganak, bit-exact; all_match=True)**

**ER** (fractions)
| circuit | D0 | D1 | D2 | D3 | D4 | D5 |
|---|---|---|---|---|---|---|
| 1_add8_err_0.0299377_size_63_depth_12 | 15/512 | 65043/33554432 | 585387/33554432 | 443475/33554432 | 65043/33554432 | 585387/33554432 |
| 2_add8_err_0.11734_size_59_depth_10 | 15/128 | 7227/524288 | 65043/524288 | 49275/524288 | 7227/524288 | 65043/524288 |
| 3_add8_err_0.188568_size_56_depth_8 | 3/16 | 99/4096 | 891/4096 | 675/4096 | 99/4096 | 891/4096 |
| 4_add8_err_0.269669_size_53_depth_7 | 69/256 | 46167/1048576 | 394119/1048576 | 191895/1048576 | 46167/1048576 | 394119/1048576 |
| 5_add8_err_0.325058_size_50_depth_7 | 83/256 | 61311/1048576 | 514863/1048576 | 312639/1048576 | 61311/1048576 | 514863/1048576 |
| 10_mult8_err_0.0891418_size_420_depth_26 | 45/512 | 4354061/536870912 | 206432793/536870912 | 40425705/536870912 | 4354061/536870912 | 206432793/536870912 |
| 1_mult8_err_0.00114441_size_450_depth_27 | 1/1024 | 64573/1073741824 | 14764437/1073741824 | 527877/1073741824 | 64573/1073741824 | 14764437/1073741824 |
| 2_mult8_err_0.00216675_size_445_depth_27 | 1/512 | 9493/67108864 | 1619109/67108864 | 82701/67108864 | 9493/67108864 | 1619109/67108864 |
| 3_mult8_err_0.00396729_size_443_depth_27 | 1/256 | 961/4194304 | 175689/4194304 | 9153/4194304 | 961/4194304 | 175689/4194304 |
| 4_mult8_err_0.00585938_size_441_depth_26 | 395/65536 | 1484743/4294967296 | 204830775/4294967296 | 13467735/4294967296 | 1484743/4294967296 | 204830775/4294967296 |

**MED** (fractions)
| circuit | D0 | D1 | D2 | D3 | D4 | D5 |
|---|---|---|---|---|---|---|
| 1_add8_err_0.0299377_size_63_depth_12 | 15/2 | 65043/131072 | 585387/131072 | 443475/131072 | 65043/131072 | 585387/131072 |
| 2_add8_err_0.11734_size_59_depth_10 | 15/2 | 7227/8192 | 65043/8192 | 49275/8192 | 7227/8192 | 65043/8192 |
| 3_add8_err_0.188568_size_56_depth_8 | 15/2 | 495/512 | 4455/512 | 3375/512 | 495/512 | 4455/512 |
| 4_add8_err_0.269669_size_53_depth_7 | 29/4 | 123/128 | 1107/128 | 843/128 | 123/128 | 1107/128 |
| 5_add8_err_0.325058_size_50_depth_7 | 27/4 | 117/128 | 1053/128 | 789/128 | 117/128 | 1053/128 |
| 10_mult8_err_0.0891418_size_420_depth_26 | 416 | 1289327/32768 | 54167535/32768 | 13702077/32768 | 1289327/32768 | 54167535/32768 |
| 1_mult8_err_0.00114441_size_450_depth_27 | 16 | 64573/65536 | 14764437/65536 | 527877/65536 | 64573/65536 | 14764437/65536 |
| 2_mult8_err_0.00216675_size_445_depth_27 | 8 | 9493/16384 | 1619109/16384 | 82701/16384 | 9493/16384 | 1619109/16384 |
| 3_mult8_err_0.00396729_size_443_depth_27 | 16 | 961/1024 | 175689/1024 | 9153/1024 | 961/1024 | 175689/1024 |
| 4_mult8_err_0.00585938_size_441_depth_26 | 65675/4096 | 252421063/268435456 | 46080742455/268435456 | 2403499095/268435456 | 252421063/268435456 | 46080742455/268435456 |


- Exhaustive ground truth = exact Fraction enumeration of the OFFICIAL VACSEM miter BLIFs
  (gate-based, unambiguous) over all 2^n PI assignments, weighted by the product distribution.
- Ganak values from exact projected-WMC on the SAME miters; **all 60 circuit x distribution
  ER values and all MED values match bit-exactly** (c5_ground_truth.json all_match = true).
- MED bit order: deviation-circuit PO k = error bit 2^k (LSB first), established by matching
  exhaustive per-bit counts.
- Engineering finding (fixed): miter CNFs drop isolated PIs when numbering variables, so
  weights must be mapped by original PI index, not CNF position (this caused MED mismatches
  at D3 on 4 circuits before the fix; ER was unaffected).
- VACSEM D0 cross-check vs the nominal error in the file names (differences recorded,
  caused by the paper's original run/ABC version vs the bundled ABC's resolution of the
  `.names` don't-care rows; the repo's own pre-generated MED-miter CNF for 1_add8 bit 8 also
  counts 15/512, matching our rebuild):
  1_add8 0.02930 vs 0.02994; 2_add8 0.11719 vs 0.11734; 3_add8 0.18750 vs 0.18857;
  4_add8 0.26953 vs 0.26967; 5_add8 0.32422 vs 0.32506; 10_mult8 0.08789 vs 0.08914;
  1_mult8 0.00098 vs 0.00114; 2_mult8 0.00195 vs 0.00217; 3_mult8 0.00391 vs 0.00397;
  4_mult8 0.00603 vs 0.00586.

## 8. Monte-Carlo proxy gap (MC is a proxy, not a baseline)

**Monte-Carlo proxy gap: mean absolute error over the 5 seeds, per (circuit, dist, N) — ER and MED**

**N=1000**
| circuit | dist | ER abs | MED abs |
|---|---:|---:|---:|
| 1_add8_err_0.0299377_size_63_depth_12 | D0 | 6.141e-03 | 1.572e+00 |
| 1_add8_err_0.0299377_size_63_depth_12 | D1 | 1.412e-03 | 3.616e-01 |
| 1_add8_err_0.0299377_size_63_depth_12 | D2 | 2.068e-03 | 5.293e-01 |
| 1_add8_err_0.0299377_size_63_depth_12 | D3 | 2.757e-03 | 7.057e-01 |
| 1_add8_err_0.0299377_size_63_depth_12 | D4 | 1.412e-03 | 3.616e-01 |
| 1_add8_err_0.0299377_size_63_depth_12 | D5 | 2.068e-03 | 5.293e-01 |
| 2_add8_err_0.11734_size_59_depth_10 | D0 | 1.076e-02 | 6.888e-01 |
| 2_add8_err_0.11734_size_59_depth_10 | D1 | 3.816e-03 | 2.442e-01 |
| 2_add8_err_0.11734_size_59_depth_10 | D2 | 6.012e-03 | 3.848e-01 |
| 2_add8_err_0.11734_size_59_depth_10 | D3 | 8.003e-03 | 5.122e-01 |
| 2_add8_err_0.11734_size_59_depth_10 | D4 | 3.816e-03 | 2.442e-01 |
| 2_add8_err_0.11734_size_59_depth_10 | D5 | 6.012e-03 | 3.848e-01 |
| 3_add8_err_0.188568_size_56_depth_8 | D0 | 1.490e-02 | 5.096e-01 |
| 3_add8_err_0.188568_size_56_depth_8 | D1 | 6.030e-03 | 2.460e-01 |
| 3_add8_err_0.188568_size_56_depth_8 | D2 | 9.506e-03 | 3.834e-01 |
| 3_add8_err_0.188568_size_56_depth_8 | D3 | 1.364e-02 | 5.600e-01 |
| 3_add8_err_0.188568_size_56_depth_8 | D4 | 6.030e-03 | 2.460e-01 |
| 3_add8_err_0.188568_size_56_depth_8 | D5 | 9.506e-03 | 3.834e-01 |
| 4_add8_err_0.269669_size_53_depth_7 | D0 | 8.694e-03 | 5.092e-01 |
| 4_add8_err_0.269669_size_53_depth_7 | D1 | 2.783e-03 | 2.207e-01 |
| 4_add8_err_0.269669_size_53_depth_7 | D2 | 8.572e-03 | 4.633e-01 |
| 4_add8_err_0.269669_size_53_depth_7 | D3 | 9.199e-03 | 5.536e-01 |
| 4_add8_err_0.269669_size_53_depth_7 | D4 | 2.783e-03 | 2.207e-01 |
| 4_add8_err_0.269669_size_53_depth_7 | D5 | 8.572e-03 | 4.633e-01 |
| 5_add8_err_0.325058_size_50_depth_7 | D0 | 1.256e-02 | 4.100e-01 |
| 5_add8_err_0.325058_size_50_depth_7 | D1 | 4.106e-03 | 2.027e-01 |
| 5_add8_err_0.325058_size_50_depth_7 | D2 | 7.807e-03 | 5.149e-01 |
| 5_add8_err_0.325058_size_50_depth_7 | D3 | 1.211e-02 | 4.884e-01 |
| 5_add8_err_0.325058_size_50_depth_7 | D4 | 4.106e-03 | 2.027e-01 |
| 5_add8_err_0.325058_size_50_depth_7 | D5 | 7.807e-03 | 5.149e-01 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D0 | 1.127e-02 | 6.282e+01 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D1 | 2.734e-03 | 1.573e+01 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D2 | 2.750e-02 | 1.070e+02 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D3 | 4.979e-03 | 4.753e+01 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D4 | 2.734e-03 | 1.573e+01 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D5 | 2.750e-02 | 1.070e+02 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D0 | 4.047e-04 | 6.630e+00 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D1 | 6.014e-05 | 9.853e-01 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D2 | 1.550e-03 | 2.540e+01 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D3 | 4.916e-04 | 8.055e+00 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D4 | 6.014e-05 | 9.853e-01 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D5 | 1.550e-03 | 2.540e+01 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D0 | 8.094e-04 | 3.315e+00 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D1 | 1.415e-04 | 5.794e-01 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D2 | 2.625e-03 | 1.075e+01 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D3 | 3.394e-04 | 1.390e+00 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D4 | 1.415e-04 | 5.794e-01 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D5 | 2.625e-03 | 1.075e+01 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D0 | 1.181e-03 | 4.838e+00 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D1 | 2.291e-04 | 9.385e-01 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D2 | 4.022e-03 | 1.648e+01 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D3 | 4.364e-04 | 1.788e+00 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D4 | 2.291e-04 | 9.385e-01 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D5 | 4.022e-03 | 1.648e+01 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D0 | 1.805e-03 | 4.836e+00 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D1 | 4.074e-04 | 9.371e-01 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D2 | 4.662e-03 | 1.649e+01 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D3 | 1.427e-03 | 1.791e+00 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D4 | 4.074e-04 | 9.371e-01 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D5 | 4.662e-03 | 1.649e+01 |

**N=10000**
| circuit | dist | ER abs | MED abs |
|---|---:|---:|---:|
| 1_add8_err_0.0299377_size_63_depth_12 | D0 | 8.994e-04 | 2.302e-01 |
| 1_add8_err_0.0299377_size_63_depth_12 | D1 | 3.123e-04 | 7.995e-02 |
| 1_add8_err_0.0299377_size_63_depth_12 | D2 | 9.892e-04 | 2.532e-01 |
| 1_add8_err_0.0299377_size_63_depth_12 | D3 | 9.633e-04 | 2.466e-01 |
| 1_add8_err_0.0299377_size_63_depth_12 | D4 | 3.123e-04 | 7.995e-02 |
| 1_add8_err_0.0299377_size_63_depth_12 | D5 | 9.892e-04 | 2.532e-01 |
| 2_add8_err_0.11734_size_59_depth_10 | D0 | 1.048e-03 | 6.704e-02 |
| 2_add8_err_0.11734_size_59_depth_10 | D1 | 6.031e-04 | 3.860e-02 |
| 2_add8_err_0.11734_size_59_depth_10 | D2 | 1.732e-03 | 1.108e-01 |
| 2_add8_err_0.11734_size_59_depth_10 | D3 | 1.271e-03 | 8.133e-02 |
| 2_add8_err_0.11734_size_59_depth_10 | D4 | 6.031e-04 | 3.860e-02 |
| 2_add8_err_0.11734_size_59_depth_10 | D5 | 1.732e-03 | 1.108e-01 |
| 3_add8_err_0.188568_size_56_depth_8 | D0 | 2.540e-03 | 9.136e-02 |
| 3_add8_err_0.188568_size_56_depth_8 | D1 | 7.140e-04 | 3.624e-02 |
| 3_add8_err_0.188568_size_56_depth_8 | D2 | 1.354e-03 | 5.863e-02 |
| 3_add8_err_0.188568_size_56_depth_8 | D3 | 2.281e-03 | 1.308e-01 |
| 3_add8_err_0.188568_size_56_depth_8 | D4 | 7.140e-04 | 3.624e-02 |
| 3_add8_err_0.188568_size_56_depth_8 | D5 | 1.354e-03 | 5.863e-02 |
| 4_add8_err_0.269669_size_53_depth_7 | D0 | 4.221e-03 | 9.992e-02 |
| 4_add8_err_0.269669_size_53_depth_7 | D1 | 1.374e-03 | 3.387e-02 |
| 4_add8_err_0.269669_size_53_depth_7 | D2 | 3.237e-03 | 6.657e-02 |
| 4_add8_err_0.269669_size_53_depth_7 | D3 | 2.979e-03 | 1.283e-01 |
| 4_add8_err_0.269669_size_53_depth_7 | D4 | 1.374e-03 | 3.387e-02 |
| 4_add8_err_0.269669_size_53_depth_7 | D5 | 3.237e-03 | 6.657e-02 |
| 5_add8_err_0.325058_size_50_depth_7 | D0 | 3.769e-03 | 1.115e-01 |
| 5_add8_err_0.325058_size_50_depth_7 | D1 | 1.078e-03 | 3.681e-02 |
| 5_add8_err_0.325058_size_50_depth_7 | D2 | 3.138e-03 | 8.115e-02 |
| 5_add8_err_0.325058_size_50_depth_7 | D3 | 1.927e-03 | 1.325e-01 |
| 5_add8_err_0.325058_size_50_depth_7 | D4 | 1.078e-03 | 3.681e-02 |
| 5_add8_err_0.325058_size_50_depth_7 | D5 | 3.138e-03 | 8.115e-02 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D0 | 2.954e-03 | 2.006e+01 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D1 | 5.260e-04 | 4.925e+00 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D2 | 2.327e-03 | 1.993e+01 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D3 | 1.381e-03 | 1.119e+01 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D4 | 5.260e-04 | 4.925e+00 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D5 | 2.327e-03 | 1.993e+01 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D0 | 1.741e-04 | 2.852e+00 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D1 | 4.797e-05 | 7.860e-01 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D2 | 5.697e-04 | 9.334e+00 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D3 | 1.417e-04 | 2.321e+00 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D4 | 4.797e-05 | 7.860e-01 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D5 | 5.697e-04 | 9.334e+00 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D0 | 5.681e-04 | 2.327e+00 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D1 | 6.829e-05 | 2.797e-01 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D2 | 7.653e-04 | 3.135e+00 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D3 | 2.465e-04 | 1.010e+00 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D4 | 6.829e-05 | 2.797e-01 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D5 | 7.653e-04 | 3.135e+00 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D0 | 4.938e-04 | 2.022e+00 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D1 | 1.142e-04 | 4.677e-01 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D2 | 1.538e-03 | 6.298e+00 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D3 | 2.164e-04 | 8.866e-01 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D4 | 1.142e-04 | 4.677e-01 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D5 | 1.538e-03 | 6.298e+00 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D0 | 7.728e-04 | 2.027e+00 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D1 | 1.291e-04 | 4.676e-01 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D2 | 1.462e-03 | 6.292e+00 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D3 | 2.729e-04 | 8.858e-01 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D4 | 1.291e-04 | 4.676e-01 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D5 | 1.462e-03 | 6.292e+00 |

**N=100000**
| circuit | dist | ER abs | MED abs |
|---|---:|---:|---:|
| 1_add8_err_0.0299377_size_63_depth_12 | D0 | 3.646e-04 | 9.334e-02 |
| 1_add8_err_0.0299377_size_63_depth_12 | D1 | 1.236e-04 | 3.163e-02 |
| 1_add8_err_0.0299377_size_63_depth_12 | D2 | 2.495e-04 | 6.388e-02 |
| 1_add8_err_0.0299377_size_63_depth_12 | D3 | 2.580e-04 | 6.604e-02 |
| 1_add8_err_0.0299377_size_63_depth_12 | D4 | 1.236e-04 | 3.163e-02 |
| 1_add8_err_0.0299377_size_63_depth_12 | D5 | 2.495e-04 | 6.388e-02 |
| 2_add8_err_0.11734_size_59_depth_10 | D0 | 5.135e-04 | 3.286e-02 |
| 2_add8_err_0.11734_size_59_depth_10 | D1 | 4.151e-04 | 2.657e-02 |
| 2_add8_err_0.11734_size_59_depth_10 | D2 | 7.139e-04 | 4.569e-02 |
| 2_add8_err_0.11734_size_59_depth_10 | D3 | 5.368e-04 | 3.435e-02 |
| 2_add8_err_0.11734_size_59_depth_10 | D4 | 4.151e-04 | 2.657e-02 |
| 2_add8_err_0.11734_size_59_depth_10 | D5 | 7.139e-04 | 4.569e-02 |
| 3_add8_err_0.188568_size_56_depth_8 | D0 | 6.360e-04 | 1.594e-02 |
| 3_add8_err_0.188568_size_56_depth_8 | D1 | 4.620e-04 | 2.434e-02 |
| 3_add8_err_0.188568_size_56_depth_8 | D2 | 1.268e-03 | 4.884e-02 |
| 3_add8_err_0.188568_size_56_depth_8 | D3 | 3.430e-04 | 2.301e-02 |
| 3_add8_err_0.188568_size_56_depth_8 | D4 | 4.620e-04 | 2.434e-02 |
| 3_add8_err_0.188568_size_56_depth_8 | D5 | 1.268e-03 | 4.884e-02 |
| 4_add8_err_0.269669_size_53_depth_7 | D0 | 7.447e-04 | 1.902e-02 |
| 4_add8_err_0.269669_size_53_depth_7 | D1 | 7.023e-04 | 2.546e-02 |
| 4_add8_err_0.269669_size_53_depth_7 | D2 | 1.137e-03 | 4.425e-02 |
| 4_add8_err_0.269669_size_53_depth_7 | D3 | 3.649e-04 | 2.402e-02 |
| 4_add8_err_0.269669_size_53_depth_7 | D4 | 7.023e-04 | 2.546e-02 |
| 4_add8_err_0.269669_size_53_depth_7 | D5 | 1.137e-03 | 4.425e-02 |
| 5_add8_err_0.325058_size_50_depth_7 | D0 | 1.049e-03 | 2.269e-02 |
| 5_add8_err_0.325058_size_50_depth_7 | D1 | 6.796e-04 | 2.358e-02 |
| 5_add8_err_0.325058_size_50_depth_7 | D2 | 1.014e-03 | 3.896e-02 |
| 5_add8_err_0.325058_size_50_depth_7 | D3 | 9.272e-04 | 3.164e-02 |
| 5_add8_err_0.325058_size_50_depth_7 | D4 | 6.796e-04 | 2.358e-02 |
| 5_add8_err_0.325058_size_50_depth_7 | D5 | 1.014e-03 | 3.896e-02 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D0 | 7.979e-04 | 5.193e+00 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D1 | 4.320e-04 | 1.940e+00 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D2 | 2.070e-03 | 1.164e+01 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D3 | 7.343e-04 | 3.445e+00 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D4 | 4.320e-04 | 1.940e+00 |
| 10_mult8_err_0.0891418_size_420_depth_26 | D5 | 2.070e-03 | 1.164e+01 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D0 | 5.931e-05 | 9.718e-01 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D1 | 2.597e-05 | 4.255e-01 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D2 | 1.479e-04 | 2.423e+00 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D3 | 3.832e-05 | 6.279e-01 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D4 | 2.597e-05 | 4.255e-01 |
| 1_mult8_err_0.00114441_size_450_depth_27 | D5 | 1.479e-04 | 2.423e+00 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D0 | 8.337e-05 | 3.415e-01 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D1 | 4.429e-05 | 1.814e-01 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D2 | 2.453e-04 | 1.005e+00 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D3 | 7.034e-05 | 2.881e-01 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D4 | 4.429e-05 | 1.814e-01 |
| 2_mult8_err_0.00216675_size_445_depth_27 | D5 | 2.453e-04 | 1.005e+00 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D0 | 1.292e-04 | 5.294e-01 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D1 | 5.418e-05 | 2.219e-01 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D2 | 2.285e-04 | 9.359e-01 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D3 | 1.082e-04 | 4.434e-01 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D4 | 5.418e-05 | 2.219e-01 |
| 3_mult8_err_0.00396729_size_443_depth_27 | D5 | 2.285e-04 | 9.359e-01 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D0 | 2.274e-04 | 5.310e-01 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D1 | 7.286e-05 | 2.222e-01 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D2 | 3.518e-04 | 9.379e-01 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D3 | 1.317e-04 | 4.437e-01 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D4 | 7.286e-05 | 2.222e-01 |
| 4_mult8_err_0.00585938_size_441_depth_26 | D5 | 3.518e-04 | 9.379e-01 |

(Full per-seed/per-N rows: `experiments/parsed/c5_montecarlo.json`, 900 rows.)

## 9. Ranking shift (exact ER / exact MED, data only)


**Ranking shifts vs D0 — exact ER**
| dist | inversions | Kendall tau | rank shift (10 circuits) |
|---|---:|---:|---|
| D0 | 0 | 1.0 | [0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| D1 | 0 | 1.0 | [0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| D2 | 6 | 0.733333 | [-3, -1, -1, -1, 0, 3, 0, 1, 1, 1] |
| D3 | 0 | 1.0 | [0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| D4 | 0 | 1.0 | [0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| D5 | 6 | 0.733333 | [-3, -1, -1, -1, 0, 3, 0, 1, 1, 1] |

**Ranking shifts vs D0 — exact MED**
| dist | inversions | Kendall tau | rank shift (10 circuits) |
|---|---:|---:|---|
| D0 | 0 | 1.0 | [0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| D1 | 13 | 0.365854 | [-2, 0, 5, 5, 3, 0, 2, -4, -2, -3] |
| D2 | 5 | 0.756098 | [-2, -1, 2, 2, 2, 0, 2, 0, 0, -1] |
| D3 | 8 | 0.609756 | [-2, 0, 3, 3, 3, 0, 0, -4, 1, 0] |
| D4 | 13 | 0.365854 | [-2, 0, 5, 5, 3, 0, 2, -4, -2, -3] |
| D5 | 5 | 0.756098 | [-2, -1, 2, 2, 2, 0, 2, 0, 0, -1] |


## 10. Ganak exact-WMC scalability (timeout 180 s per invocation; timeouts kept)

**Ganak exact projected-WMC scalability (timeout 180 s)**

**add32**
| dist | metric | solved | runtime_s | result |
|---|---:|---:|---:|---|
| D0 | ER | 1/1 | 1.186 | 5613615/33554432 |
| D0 | MED | 33/33 | 2.3 | 16777215/2 |
| D1 | ER | 1/1 | 0.333 | 109493248865240261835/9444732965739290427392 |
| D1 | MED | 33/33 | 0.2 | 72749359683/131072 |
| D2 | ER | 1/1 | 0.382 | 960085443291754743315/9444732965739290427392 |
| D2 | MED | 33/33 | 0.2 | 654744237147/131072 |
| D3 | ER | 1/1 | 0.37 | 732552028344852014475/9444732965739290427392 |
| D3 | MED | 33/33 | 0.2 | 496018361475/131072 |
| D4 | ER | 1/1 | 0.371 | 109493248865240261835/9444732965739290427392 |
| D4 | MED | 33/33 | 0.2 | 72749359683/131072 |
| D5 | ER | 1/1 | 0.403 | 960085443291754743315/9444732965739290427392 |
| D5 | MED | 33/33 | 0.2 | 654744237147/131072 |

**add64**
| dist | metric | solved | runtime_s | result |
|---|---:|---:|---:|---|
| D0 | ER | 1/1 | 1.01 | 5448932958975/140737488355328 |
| D0 | MED | 65/65 | 2.2 | 1099511627775/2 |
| D1 | ER | 1/1 | 0.767 | 92900660659176360849459841328990572539/43556142965880123323311949751266331066368 |
| D1 | MED | 65/65 | 0.4 | 111362764912241133555/8589934592 |
| D2 | ER | 1/1 | 0.628 | 835364656742408871232959635608591548867/43556142965880123323311949751266331066368 |
| D2 | MED | 65/65 | 0.3 | 1002264884210170201995/8589934592 |
| D3 | ER | 1/1 | 0.645 | 633005160219440253647419215074244082875/43556142965880123323311949751266331066368 |
| D3 | MED | 65/65 | 0.3 | 759291578947098637875/8589934592 |
| D4 | ER | 1/1 | 0.61 | 5099526347683605193732133132333467299375/43556142965880123323311949751266331066368 |
| D4 | MED | 65/65 | 0.4 | 24570967457234591469375/8589934592 |
| D5 | ER | 1/1 | 0.604 | 5099526347683605193732133132333467299375/43556142965880123323311949751266331066368 |
| D5 | MED | 65/65 | 0.5 | 24570967457234591469375/8589934592 |

**mult12**
| dist | metric | solved | runtime_s | result |
|---|---:|---:|---:|---|
| D0 | ER | 1/1 | 75.759 | 358911/16777216 |
| D0 | MED | 24/24 | 65.7 | 66177/128 |
| D1 | ER | 1/1 | 76.169 | 566674007941/281474976710656 |
| D1 | MED | 24/24 | 66.0 | 65940329455/1073741824 |
| D2 | ER | 1/1 | 75.929 | 34905878657469/281474976710656 |
| D2 | MED | 24/24 | 66.3 | 1117690398009/1073741824 |
| D3 | ER | 1/1 | 76.137 | 4289384233845/281474976710656 |
| D3 | MED | 24/24 | 66.4 | 511542454977/1073741824 |
| D4 | ER | 1/1 | 76.122 | 566674007941/281474976710656 |
| D4 | MED | 24/24 | 66.5 | 65940329455/1073741824 |
| D5 | ER | 1/1 | 75.849 | 34905878657469/281474976710656 |
| D5 | MED | 24/24 | 65.9 | 1117690398009/1073741824 |

**mult15**
| dist | metric | solved | runtime_s | result |
|---|---:|---:|---:|---|
| D0 | ER | 0/1 | 180 | timeout |
| D0 | MED | 29/30 | -- | timeout bits: [24] |
| D1 | ER | 0/1 | 180 | timeout |
| D1 | MED | 29/30 | -- | timeout bits: [24] |
| D2 | ER | 0/1 | 180 | timeout |
| D2 | MED | 29/30 | -- | timeout bits: [24] |
| D3 | ER | 0/1 | 180 | timeout |
| D3 | MED | 29/30 | -- | timeout bits: [24] |
| D4 | ER | 0/1 | 180 | timeout |
| D4 | MED | 29/30 | -- | timeout bits: [24] |
| D5 | ER | 0/1 | 180 | timeout |
| D5 | MED | 29/30 | -- | timeout bits: [24] |

**mult16_new**
| dist | metric | solved | runtime_s | result |
|---|---:|---:|---:|---|
| D0 | ER | 0/1 | 180 | timeout |
| D0 | MED | 31/32 | -- | timeout bits: [24] |
| D1 | ER | 0/1 | 180 | timeout |
| D1 | MED | 31/32 | -- | timeout bits: [24] |
| D2 | ER | 0/1 | 180 | timeout |
| D2 | MED | 31/32 | -- | timeout bits: [24] |
| D3 | ER | 0/1 | 180 | timeout |
| D3 | MED | 31/32 | -- | timeout bits: [24] |
| D4 | ER | 0/1 | 180 | timeout |
| D4 | MED | 31/32 | -- | timeout bits: [24] |
| D5 | ER | 0/1 | 180 | timeout |
| D5 | MED | 31/32 | -- | timeout bits: [24] |

**mac**
| dist | metric | solved | runtime_s | result |
|---|---:|---:|---:|---|
| D0 | ER | 1/1 | 1.515 | 355/2048 |
| D0 | MED | 8/8 | 2.1 | 63/16 |
| D1 | ER | 1/1 | 0.607 | 117917/8388608 |
| D1 | MED | 8/8 | 0.1 | 80327/262144 |
| D2 | ER | 1/1 | 0.605 | 4809861/8388608 |
| D2 | MED | 8/8 | 0.1 | 2546559/262144 |
| D3 | ER | 1/1 | 0.61 | 1058949/8388608 |
| D3 | MED | 8/8 | 0.1 | 977607/262144 |
| D4 | ER | 1/1 | 0.608 | 117917/8388608 |
| D4 | MED | 8/8 | 0.1 | 80327/262144 |
| D5 | ER | 1/1 | 0.61 | 4809861/8388608 |
| D5 | MED | 8/8 | 0.1 | 2546559/262144 |


- add32/add64/mac solved all cases (max ~2.3 s); mult12 solved all (max 76 s);
  mult15: ER (all 6 dists) and MED bit 24 (all 6 dists) time out at 180 s (and a 600 s
  probe of mult15 ER also timed out -> effectively intractable at this size);
  mult16-new: same pattern (ER + MED bit 24 time out).
- Full per-invocation records (runtime, CNF vars/clauses, solved/timeout/error, exact
  result): `experiments/parsed/c5_scalability.csv` / `.json` (1188 rows).

## 11. Compile-once / reweight-many (official Ganak --compile + minimal exact rational evaluator)

**Compile-once / reweight-many (official Ganak --compile d-DNNF + minimal exact rational evaluator; verified circuits only).**
| circuit | K | compile_s | nnf_nodes | nnf_arcs | reweight_total_s | reweight_per_eval_s | all_match |
|---|---:|---:|---:|---:|---:|---:|---|
| 1_add8_err_0.0299377_size_63_depth_12 | 1 | 0.0 | 48 | 140 | 0.0004 | 0.00044 | True |
| 2_add8_err_0.11734_size_59_depth_10 | 1 | 0.0 | 46 | 132 | 0.0005 | 0.00052 | True |
| 3_add8_err_0.188568_size_56_depth_8 | 1 | 0.0 | 136 | 401 | 0.0013 | 0.00125 | True |
| 4_add8_err_0.269669_size_53_depth_7 | 1 | 0.0 | 153 | 452 | 0.0012 | 0.00116 | True |
| 5_add8_err_0.325058_size_50_depth_7 | 1 | 0.0 | 168 | 498 | 0.0013 | 0.00131 | True |
| 1_add8_err_0.0299377_size_63_depth_12 | 4 | 0.0 | 48 | 140 | 0.0015 | 0.00037 | True |
| 2_add8_err_0.11734_size_59_depth_10 | 4 | 0.0 | 46 | 132 | 0.0015 | 0.00038 | True |
| 3_add8_err_0.188568_size_56_depth_8 | 4 | 0.0 | 136 | 401 | 0.0044 | 0.00111 | True |
| 4_add8_err_0.269669_size_53_depth_7 | 4 | 0.0 | 153 | 452 | 0.0051 | 0.00128 | True |
| 5_add8_err_0.325058_size_50_depth_7 | 4 | 0.0 | 168 | 498 | 0.0073 | 0.00183 | True |
| 1_add8_err_0.0299377_size_63_depth_12 | 16 | 0.0 | 48 | 140 | 0.0066 | 0.00041 | True |
| 2_add8_err_0.11734_size_59_depth_10 | 16 | 0.0 | 46 | 132 | 0.0059 | 0.00037 | True |
| 3_add8_err_0.188568_size_56_depth_8 | 16 | 0.0 | 136 | 401 | 0.0239 | 0.0015 | True |
| 4_add8_err_0.269669_size_53_depth_7 | 16 | 0.0 | 153 | 452 | 0.0231 | 0.00144 | True |
| 5_add8_err_0.325058_size_50_depth_7 | 16 | 0.0 | 168 | 498 | 0.0228 | 0.00143 | True |
| 1_add8_err_0.0299377_size_63_depth_12 | 64 | 0.0 | 48 | 140 | 0.0236 | 0.00037 | True |
| 2_add8_err_0.11734_size_59_depth_10 | 64 | 0.0 | 46 | 132 | 0.0307 | 0.00048 | True |
| 3_add8_err_0.188568_size_56_depth_8 | 64 | 0.0 | 136 | 401 | 0.0903 | 0.00141 | True |
| 4_add8_err_0.269669_size_53_depth_7 | 64 | 0.0 | 153 | 452 | 0.0953 | 0.00149 | True |
| 5_add8_err_0.325058_size_50_depth_7 | 64 | 0.0 | 168 | 498 | 0.0947 | 0.00148 | True |

**K independent Ganak exact-WMC totals (same circuits/distributions, comparison):** {'1': 4.54, '4': 9.77, '16': 26.5, '64': 126.31}

**Blocked cases (recorded, not fabricated):**
- 10_mult8_err_0.0891418_size_420_depth_26: reweight-verify - {'D0': False, 'D3': False}
- 1_mult8_err_0.00114441_size_450_depth_27: reweight-verify - {'D0': False, 'D3': False}
- 2_mult8_err_0.00216675_size_445_depth_27: reweight-verify - {'D0': False, 'D3': False}
- 3_mult8_err_0.00396729_size_443_depth_27: reweight-verify - {'D0': False, 'D3': False}
- 4_mult8_err_0.00585938_size_441_depth_26: reweight-verify - {'D0': False, 'D3': False}
- add32: compile - compile timeout>180s
- add64: compile - compile timeout>180s
- mult12: reweight-scope - compiled size 996.6 MB; exact reweight not attempted beyond the 180 s probe cap
- mult15: compile - compile timeout>180s
- mult16_new: compile - compile timeout>180s
- mac: reweight-scope - compiled size 0.2 MB; exact reweight not attempted beyond the 180 s probe cap


**Blocker (recorded, not fabricated):** the official `--compile` .nnf is an arc-labeled
(decision + implied literal) d-DNNF.  Exact reweighting with a node-memoized evaluator is
VERIFIED bit-exact on the 5 shallow add8 d-DNNFs (all K, all values vs exhaustive).  On the
deep mult8/mac d-DNNFs the same semantics deviates from the Ganak/exhaustive value (e.g.
10_mult8 D0: evaluator 0.07677 vs exact 45/512 = 0.08789; distribution-dependent ratio
1.02-1.50 across D0-D5).  Three candidate semantics were tested and rejected (full per-arc
literal multiplication, decision-only, internal-weight variants); the format's overlapping
labels would require per-path distinct-variable products, which defeats the purpose of a
memoized compile-once evaluator.  All 5 mult8 + mac are therefore recorded as
not-reliably-exactly-reweightable (blocked); the 6 scalability compiles were not
reweightable within the 180 s probe budget (compile timeout or 996 MB mult12 d-DNNF).
Per the campaign rules, no substitute/fabricated results are reported.

## 12. Engineering issues / failures

1. WSL lacks cmake/sudo: used an official rootless CMake 3.29.9 tarball; ABC required
   `-DREADLINE_FOUND=FALSE`; `core` needed boost headers (downloaded 1.85.0 headers, header-only).
2. Windows path <-> WSL path conversion in tool invocation (added wsl_path()).
3. VACSEM `.names` truth-table semantics: rows with value 0 are OFF-set cubes and unlisted
   patterns are don't-cares; ABC's completion is authoritative (the miter CNFs are the
   ground truth); exhaustive ground truth is computed on the gate-based miter BLIFs, not by
   re-interpreting the original circuits.
4. Miter CNF isolated-PI variable numbering requires PI-index weight mapping (fixed; see 7).
5. Ganak weight-file header order (`p cnf` before `c p weight`/`c p show`); `c s exact arb
   frac N` / `frac N/D` parsing (const0 -> `frac 0`).
6. compile-reweight evaluator: recursion overflow risk -> iterative post-order (verified
   identical to the recursive version on all small/medium d-DNNFs); the remaining failure
   on deep d-DNNFs is the semantics blocker (section 11), not a coding bug.
7. Vivado round's `.Xil` lock issue did not recur; this round used no Vivado.
8. All failures are engineering/format-level; no scientific semantics were changed.

## 13. Data files for external analysis

- `experiments/configs/c5_manifest.json` - benchmark manifest (dict-order selection)
- `experiments/parsed/c5_ground_truth.json` - exhaustive vs Ganak, all_match flag
- `experiments/parsed/c5_montecarlo.json` - 900 MC rows
- `experiments/parsed/c5_ranking.json` - ranking inversions / Kendall tau / rank shifts
- `experiments/parsed/c5_scalability.csv/.json` - 1188 Ganak invocations (runtime/size/result)
- `experiments/parsed/c5_compile_reweight.json` - K=1/4/16/64 + blocked list + ganak totals
- `experiments/raw/c5/miters/`, `miters_scal/` - official miter BLIFs and CNFs (16 circuits)
- `experiments/raw/c5/wmc/` - Ganak projected-weighted CNFs per (circuit, dist)
- `experiments/raw/c5/nnf/` - official compiled d-DNNFs (cached; mult12 is 996 MB)
- `experiments/logs/c5_scalability.log`, `c5_compile_reweight.log`
- Tools (official sources/builds): `tools/cache/VACSEM` (b11ede7), `tools/cache/ganak`
  (e8f5184), `tools/cache/ganak_linux` (official v2.7.0 binary)

## 14. Reproduction commands

```bash
# tools (one-time; see section 3)
#   VACSEM Circuit2Cnf build and Ganak v2.7.0 binary are in tools/cache/

# ground truth (exhaustive vs Ganak, 10 small circuits x 6 dists)
D:/paper_project_3/.venv/Scripts/python.exe src/python/c5_ground_truth.py

# Monte-Carlo proxy gap
D:/paper_project_3/.venv/Scripts/python.exe src/python/c5_montecarlo.py

# ranking shifts
D:/paper_project_3/.venv/Scripts/python.exe src/python/c5_ranking.py

# scalability (Ganak, 1188 invocations, 180 s cap)
D:/paper_project_3/.venv/Scripts/python.exe src/python/c5_scalability.py

# compile-once / reweight-many (cached d-DNNFs reused; never recompiles)
D:/paper_project_3/.venv/Scripts/python.exe src/python/c5_compile_reweight.py
```

## 15. Unexecuted items

- MCAC: no official code -> recorded "not executed" (per instruction).
- mult14: absent from the official repo -> documented substitution mult16-new.
- Compile-once/reweight-many on the deep mult8/mac d-DNNFs and the scalability compiles:
  BLOCKED with the exact reason (sections 11) - no fabricated substitute results.
- No Vivado/board/new-synthesis/T4-T5/ML/correlated distributions (per instruction).
- No CONTINUE/STOP, paper-worthiness, journal-tier, publishable or next-direction judgment.
