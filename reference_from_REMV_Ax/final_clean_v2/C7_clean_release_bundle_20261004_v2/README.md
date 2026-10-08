# C7 Clean Release Bundle

## 1. What this is

**C7 = CA-DET-QDP-formalization: exact distribution-aware ER/MED verification of
approximate adders under factorized non-uniform input distributions, with a
compile-once / reweight-many exact evaluation workflow.**

This bundle is the **paper source-of-truth**. Every number in the paper's
supplementary, figures and main tables must be read from `results/` and
`supplementary/` in this bundle only — never from the historical project
`experiments/` directory.

## 2. Research question

Can exact error-rate (ER) / mean-error-distance (MED) verification of
approximate combinational circuits be repeated cheaply across many deployment
distributions by compiling the error miter once into a d-DNNF and reweighting
it exactly per distribution?

## 3. Supported scope

- factorized **per-PI-bit product distributions** (independent PIs);
- corrected D0–D5 (circuit-relative, see `configs/distribution_config.json`)
  + 10 frozen random product distributions (seed 42, pool {1/8..7/8});
- exact ER and MED only (no sampling / approximation);
- **approximate adders**, widths 8/12/16/32/64/128 (formal) + 192 (boundary) +
  256 (supplementary stress probe).

## 4. Exact metrics

- **ER** = probability the approximate output differs from the exact adder;
- **MED** = expected absolute error (reconstructed as sum_k 2^k P(bit_k=1),
  numeric bit ordering, const0 bits handled exactly).

## 5. Final backend

`raw/full-variable/full-Tseitin ER(MED) CNF -> official d4 d-DNNF ->
exact rational PI reweighting` (auxiliary literals neutral, weight 1).
Frozen: d4 commit 333370cc1e843dd0749c1efe88516e72b5239174.

## 6. Ganak's role

Ganak (official v2.7.0) is the **exact semantic reference**: projected exact
weighted model counting. A d4 result is "cross-validated" only when it equals
the Ganak value bit-for-bit. Ganak timeouts are recorded (`GANAK_TIMEOUT`), not
hidden. In this campaign Ganak never timed out.

## 7. Compile-once / exact-reweight-many

- compile the error CNF once (180 s cap per compile);
- evaluate the compiled d-DNNF under many distributions (marginal ~ms);
- compare with K independent Ganak exact WMC runs (end-to-end, serial).

## 8. Formal experiment widths

8 / 12 / 16 / 32 / 64 / 128 = main complete-width campaign (1430/1430 tasks).
Adding the 192-bit boundary width gives the complete frozen 8–192 campaign
(1690/1690 tasks terminal). 192 = transition/boundary (7/10 ER compiles timed
out). 256 = supplementary
stress probe (17 PASS preserved; the unstarted tail is marked
`NOT_RUN_RESOURCE_LIMIT`, reason "global experiment wall-clock budget
exhausted" — **these are NOT timeouts**).

## 9. Timeout policy

180 s per single compile / exact probe. Never raised. Timeouts are results.

## 10. Checkpoint / resume

The formal runner writes every atomic task atomically (tmp -> fsync -> verify ->
replace), keeps a ledger + checkpoint, and never re-runs terminal tasks.
`c7_formal_campaign.py --resume` continues after any interruption with at most
one atomic task lost. Self-test: RESUME_SELFTEST_PASS.

## 11. Paper source-of-truth files

- `results/case_level_summary.csv` — main scalability/table source (one row per case);
- `results/formal_er_results.csv`, `formal_med_results.csv` — exactness;
- `results/formal_ranking.csv` — distribution sensitivity;
- `results/formal_timing.csv`, `formal_break_even.csv` — efficiency;
- `results/formal_scalability.csv` — compile/NNF scaling;
- `figures/plotting_data/*.csv` — figure inputs (derived only from results/);
- `evidence/final_results_audit.md` — ledger/result-integrity audit (PASS);
- `evidence/derived_results_repair_audit.md` — corrected derived-layer semantic audit (PASS).

## 12. Negative / boundary evidence (intended for the paper)

- ranking sensitivity is metric-, width-, and distribution-dependent under D0–D5:
  ER shows strict inversions at widths 12/32/64 for selected distributions, while
  MED shows shifts at 8/12/16/32/64 (up to 14 strict inversions at w16/D4/D5);
  width 128 has no strict inversions for either metric under D0–D5;
- 25 compile/timing timeouts (see `supplementary/timeout_details.csv`);
- 18 SKIPPED_DEPENDENCY rows (MED evals whose compile_MED timed out);
- cold break-even over the 58 cases with completed K64 comparisons: 37 at
  K<=16, 18 at 16<K<=64, and 3 still not amortized by K64;
- `results/formal_failures.csv`, `supplementary/negative_results.csv`.

## 13. Out of scope (explicitly not claimed)

correlated/non-factorized inputs; multiplier/MAC; new compiler or knowledge-
compilation algorithms; FPGA/Vivado; ML; 192/256 formal scalability beyond the
boundary/supplementary role above; any "always faster" or "all distributions
shift ranking" claim (see `CLAIMS_AND_SCOPE.md`).

## 14. Reproduce

See `REPRODUCTION.md` for exact versions, commands and environment setup.
Formal run: `python src/c7_formal_campaign.py`; resume:
`python src/c7_formal_campaign.py --resume`; tables:
`python src/c7_clean_tables.py` (writes into the project formal dir, not this
bundle).

## 15. Re-plot without re-running solvers

All figure data is pre-computed in `figures/plotting_data/`; run
`python figures/plotting_scripts/make_plots.py` (pure Python, reads only this
bundle's `results/` + `figures/plotting_data/`). No solver is invoked.
