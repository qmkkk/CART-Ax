# run_report_6

## 1. User Request

Round-6 (final C7 rescue), executor-only.  Rounds 1-5 frozen, nothing overwritten.
Single question: between the working add8 compile-once/reweight-many (Round 5) and the
large failing cases, does a stable "medium-scale approximate-adder interval" exist?

1. From the official VACSEM/EvoApproxLib resources find add12/add16/add20/add24 or the
   closest widths; fixed per-width rule (lexicographic dict order), 3-5 cases; missing
   widths recorded, no favorable-case substitution.
2. Per case, fixed order: (a) D0 Ganak exact WMC; (b) Ganak --compile with a single
   180 s timeout (time, NNF size, nodes/arcs); (c) only on compile success: exact reweight
   at D0 and D3, bit-exact vs the Ganak exact values; (d) only after correctness: K={16,64}
   compile-once/reweight-many totals vs K independent Ganak WMC totals.
3. No new NNF semantics; reweight mismatch -> blocked; compile timeout -> timeout; no
   600/1200 s probes.
4. No multiplier/mac, no Vivado, no ML, no algorithm changes.
5. Wall-clock budget ~3 h.
6. Pre-registered PASS: >=3 medium cases (clearly larger than add8) satisfying ALL of:
   compile success, D0/D3 exact match, no unacceptable NNF inflation, and clear
   amortization at K=16 and K=64.  If not met, no further rescue.
7. All failures/timeouts/mismatches kept; inclusion rules not changed by results.

## 2. Execution Status

**COMPLETE** - fixed manifest executed, per-case data recorded, mechanical verdict below.
No scientific judgment made.

## 3. Environment

- Project root (Windows): `D:\paper_project_3` ; (WSL): `/mnt/d/paper_project_3`
- Tools unchanged from Round 5 (official): VACSEM `b11ede7` (Circuit2Cnf built from source),
  Ganak official v2.7.0 binary (exact rational projected-WMC, `--mode 1 --prob 0`;
  d-DNNF compile `--compile`).
- Python `.venv` 3.14.5; scripts `src/python/c5_r6_adder_probe.py`, reusing the R5
  `c5_common` / `c5_compile_reweight` infrastructure.

## 4. Complete adder-width inventory (official VACSEM/EvoApproxLib input set)

Available: **add8 (16 PI), add16 (32 PI), add32 (64 PI), add64 (128 PI), add100, add128,
add192, add256, cla32 (64 PI CLA)**.
**Missing (recorded): add9, add10, add12, add14, add18, add20, add24, cla64.**
Per the instruction "若某位宽不存在，记录缺失，不临时换成有利案例": the target widths
12/20/24 do not exist.  Closest available widths used: add16 (closest to 12/16/20) as the
primary medium probe; add32 (closest to 24) as the scaling boundary; add64 not required
(skipped per instruction).

## 5. Fixed benchmark manifest (lexicographic dict order, 10_ < 1_ < 2_ because '0' < '_')

**Benchmark manifest (fixed, no result-driven choice).**
| width | PIs | outs | case (dict order) | approx |
|---|---|---|---|---|
| add16 | 32 | - | 10_add16_err_0.566452_size_105_depth_13 | D:\paper_project_3\tools\cache\VACSEM\Circuit2Cnf\input\add16\10_add16_err_0.566452_size_105_depth_13.blif |
| add16 | 32 | - | 1_add16_err_0.00215149_size_143_depth_16 | D:\paper_project_3\tools\cache\VACSEM\Circuit2Cnf\input\add16\1_add16_err_0.00215149_size_143_depth_16.blif |
| add16 | 32 | - | 2_add16_err_0.0311737_size_138_depth_13 | D:\paper_project_3\tools\cache\VACSEM\Circuit2Cnf\input\add16\2_add16_err_0.0311737_size_138_depth_13.blif |
| add32 | 64 | - | 10_add32_err_0.197418_size_259_depth_14 | D:\paper_project_3\tools\cache\VACSEM\Circuit2Cnf\input\add32\10_add32_err_0.197418_size_259_depth_14.blif |
| add32 | 64 | - | 11_add32_err_0.223526_size_257_depth_14 | D:\paper_project_3\tools\cache\VACSEM\Circuit2Cnf\input\add32\11_add32_err_0.223526_size_257_depth_14.blif |

**Per-case results.**
| case | D0 WMC (s) | compile (s) | NNF MB | nodes/arcs | reweight D0/D3 (s) | match D0/D3 | K16 rw/WMC (s) | K64 rw/WMC (s) | K16/K64 amort | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 10_add16_err_0.566452_size_105_depth_13 | 0.716 | 4.25 | 0.41 | 8594/17733 | 0.0778/0.0705 | True/True | 1.298/8.455 | 5.719/33.036 | True/True | ok |
| 1_add16_err_0.00215149_size_143_depth_16 | 0.368 | 1.05 | 0.04 | 864/1878 | 0.0115/0.0103 | True/True | 0.156/7.546 | 0.593/26.676 | True/True | ok |
| 2_add16_err_0.0311737_size_138_depth_13 | 0.719 | 4.35 | 19.96 | 283059/603165 | 3.1984/3.8379 | True/True | 51.618/7.688 | 225.974/19.733 | False/False | ok |
| 10_add32_err_0.197418_size_259_depth_14 | 4.345 | 180 | - | - | - | - | - | - | - | compile_timeout |
| 11_add32_err_0.223526_size_257_depth_14 | 7.309 | 180 | - | - | - | - | - | - | - | compile_timeout |



## 6. Per-case data (fixed order a -> b -> c -> d)

- **a) D0 Ganak exact WMC** (all solved, 0.7-7.3 s): see table.
- **b) compile** (single 180 s attempt): add16 3/3 success (1.05-4.35 s fresh; cached
  thereafter); add32 2/2 **compile timeout > 180 s**.
- **c) exact reweight D0/D3 vs Ganak exact** (Ganak is the exact reference at this scale):
  add16 3/3 **bit-exact match** (all six values identical).
- **d) K={16,64}**: only for the 3 matching add16 cases.

| case | D0 WMC (s) | compile (s) | NNF MB | nodes/arcs | reweight D0/D3 (s) | match D0/D3 | K16 rw/WMC (s) | K64 rw/WMC (s) | K16/K64 amort | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 10_add16_err_0.566452 | 3.0 | 4.25 | 0.41 | 8594/17733 | 0.08/0.07 | T/T | 1.30/8.46 | 5.72/33.04 | T/T | ok |
| 1_add16_err_0.00215149 | 0.8 | 1.05 | 0.04 | 864/1878 | 0.01/0.01 | T/T | 0.16/7.55 | 0.59/26.68 | T/T | ok |
| 2_add16_err_0.0311737 | 0.9 | 4.35 | 19.96 | 283059/603165 | 3.20/3.84 | T/T | 51.62/7.69 | 225.97/19.73 | F/F | ok (not amortized) |
| 10_add32_err_0.197418 | 4.3 | >180 | - | - | - | - | - | - | - | compile_timeout |
| 11_add32_err_0.223526 | 7.3 | >180 | - | - | - | - | - | - | - | compile_timeout |

## 7. Exactness

- All three add16 reweight evaluations (D0 and D3, six values) are **bit-exact** vs the Ganak
  exact WMC values (e.g. 10_add16 D0: 37195/65536; D3 value in the JSON).  The reweight
  semantics is the R5-verified evaluator; no new semantics was introduced.
- add32 cases have no reweight data: their compiles timed out at the single 180 s attempt
  (recorded as timeout, no long probes per instruction).

## 8. NNF size and scale trend

| width | case | NNF MB | nodes | arcs |
|---|---:|---:|---:|---:|
| add8 (R5) | 1_add8 | 0.002 | 48 | 94 |
| add16 | 1_add16 | 0.04 | 864 | 1878 |
| add16 | 10_add16 | 0.41 | 8594 | 17733 |
| add16 | 2_add16 | **19.96** | **283059** | **603165** |
| add32 | (all) | compile timeout > 180 s | - | - |

Trend: the compiled d-DNNF size is **case-dependent, not width-dependent** - within the same
add16 width the NNF spans 0.04 MB to 20 MB (factor ~500), and the 20 MB case loses the
amortization advantage although exactness holds.  At 64 PIs (add32) the compile itself does
not finish within 180 s.  No clean "medium interval" with a stable size/reweight behavior is
observed.

## 9. Timeouts / mismatches / blockers

- add32 x2: compile timeout > 180 s (single attempt; recorded, kept).
- 2_add16: exact reweight OK, but K16/K64 amortization FAILS (51.6 s vs 7.7 s at K=16;
  226.0 s vs 19.7 s at K=64) because the 20 MB d-DNNF makes each reweight ~3-4 s while the
  Ganak WMC for this small-ER CNF is ~0.7 s.  Recorded as "ok but not amortized" - it does
  NOT count toward the pre-registered PASS.
- No reweight mismatch occurred in this round; no new NNF semantics was attempted.

## 10. Mechanical verdict (pre-registered criteria)

Criteria: >=3 medium cases (>=32 PIs) with ALL of: compile <= 180 s; D0/D3 exact match;
NNF <= 500 MB and reweight/eval <= 60 s; amortized at BOTH K=16 and K=64.

| criterion | 10_add16 | 1_add16 | 2_add16 |
|---|---|---|---|
| compile <= 180 s | T (4.25 s) | T (1.05 s) | T (4.35 s) |
| D0/D3 exact match | T | T | T |
| NNF <= 500 MB, reweight <= 60 s | T (0.41 MB) | T (0.04 MB) | T (19.96 MB, 3.8 s) |
| K16 amortized | T | T | F |
| K64 amortized | T | T | F |
| **meets ALL** | **T** | **T** | **F** |

Medium fully-passing cases: **2** (10_add16, 1_add16).  Required: 3.

**VERDICT: FAIL** - the pre-registered success criterion (>=3 medium cases) is not met.
add32 (the next scale) does not compile within 180 s, and one of the three add16 cases is
exact but loses amortization to d-DNNF size.  Per instruction, no further rescue is
appended.

## 11. Data files

- `experiments/parsed/c5_r6_adder_probe.json` - inventory, manifest, per-case rows, verdict
- `experiments/raw/c5/miters_r6/` - official ER miter BLIF/CNF per case
- `experiments/raw/c5/nnf_r6/` - cached official d-DNNF compiles (0.04/0.41/19.96 MB)
- `experiments/raw/c5/wmc/` - Ganak projected-weighted CNFs
- R5 tools/data unchanged (see run_report_5.md)

## 12. Reproduction commands

```bash
D:/paper_project_3/.venv/Scripts/python.exe src/python/c5_r6_adder_probe.py
```

## 13. Unexecuted items

- add64, add100+ widths: not required (skipped per instruction).
- No multiplier/mac, no Vivado, no ML, no algorithm changes, no new NNF semantics, no long
  probes (per instruction).
- No publishable/journal/novelty/next-direction judgment (per AGENTS.md).
