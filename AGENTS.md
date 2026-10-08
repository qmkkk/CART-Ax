# AGENTS.md — PROJECT_4
# Certified Distribution-Robust Ranking of Approximate Adders under Input Uncertainty

> Project mode: THEORY-FEASIBILITY / EXECUTOR-ONLY
> Created: 2026-10-06
> Research target: certified robust ranking of approximate adders under continuous input-distribution uncertainty.
> This project is the INDEPENDENT THEORY SEQUEL to REMV-Ax (D:/paper_project_REMV_Ax).
> The REMV-Ax project is a completed, frozen experimental paper project and MUST remain permanently unchanged.

---

# 0. ABSOLUTE HIGHEST-PRIORITY RULES

## 0.1 SOURCE project is READ-ONLY forever

- `D:/paper_project_REMV_Ax` is READ-ONLY. No modification, deletion, move, rename, overwrite, git init,
  cleanup, formatting, or script rewriting of any source file.
- All operations are COPY-ONLY into `PROJECT_ROOT` (= the directory containing this AGENTS.md).
- After any copy batch, spot-check source SHA256 to confirm nothing changed.
- Accessing `C:/` is forbidden.
- Files larger than 100 MB are forbidden to copy.

## 0.2 Local AI is an executor, NOT the research planner

The local AI is authorized to:
- write code and small-scale theory probes required by the current user prompt;
- run 8-bit exhaustive / small-scale experiments;
- search literature only when explicitly requested (RQ7);
- collect raw outputs and produce factual reports.

The local AI is NOT authorized to:
- claim novelty;
- declare the research route viable or dead;
- write the paper;
- extend scope beyond the current prompt (no 32/64/128-bit campaigns in Phase 1);
- choose a new research direction;
- modify REMV-Ax or re-package its results as new work.

Each user prompt is a self-contained execution campaign: execute it completely, record data, stop, report.

---

# 1. RESEARCH GOAL

REMV-Ax established POINTWISE exact ER/MED verification: for a fixed factorized product distribution
p (per-PI-bit Bernoulli probabilities), the exact ER/MED of an approximate adder is computed via
d-DNNF compile-once / reweight-many (d4 + Ganak exact reference).

PROJECT_4 moves from POINTWISE verification to CERTIFIED ROBUST RANKING under continuous
distribution uncertainty.

## 1.1 Core question

> Given a nominal PI probability vector p0 and an uncertainty region U (e.g. a box in the
> probability simplex), can we PROVE that approximate adder A always outperforms adder B
> (in ER or MED) over the ENTIRE region U?

## 1.2 Core objects

- `M_C(p)` : exact ER (or MED) of circuit C under factorized product distribution p.
- `Delta_AB(p) = M_A(p) - M_B(p)` : pairwise ranking margin of A vs B.

## 1.3 Target outputs (Phase 2+; NOT Phase 1)

1. exact/sound ranking certificate: sign of Delta_AB(p) for all p in U;
2. certified stability region: subset of the probability simplex where ranking is invariant;
3. certified robustness radius r*: largest uncertainty region around p0 with sign-invariant ranking;
4. ranking flip boundary: locus where Delta_AB(p) = 0;
5. scalable certification algorithm (beyond naive enumeration).

---

# 2. FOUNDATION (REMV-Ax, frozen)

## 2.0 AUTHORITATIVE BASELINE (PROJECT_4_FINAL_BASELINE_IMPORT, 2026-10-06)

- `reference_from_REMV_Ax/C7_clean_release_bundle_20261004_v2.zip` and its unpacked
  content in `reference_from_REMV_Ax/final_clean_v2/` are the UNIQUE AUTHORITATIVE
  SOURCE of all REMV-Ax final experimental facts (SHA256-verified, see run report 2).
- Follow-up theory work MUST use only this package's numbers. Overwriting them with
  older results from the legacy REMV_Ax working directory is FORBIDDEN.
- Where pre-v2 copies in `reference_from_REMV_Ax/` conflict with `final_clean_v2/`,
  the v2 package wins; conflicting legacy statements are void. In particular the
  legacy claim "ER ordering is invariant (tau-b = 1.0)" is RETRACTED: v2 shows
  strict ER inversions at widths 12/32/64 under selected distributions (e.g. D2).

All reference definitions, benchmark rules, and frozen data live in
`reference_from_REMV_Ax/final_clean_v2/` (authoritative), with pre-v2 copies under
`reference_from_REMV_Ax/` (historical, superseded where conflicting) and synchronized
result tables in `experiments/`. Key facts:

- exact rational ER/MED; factorized per-PI-bit product distributions D0-D5 + R0-R9 (seed 42);
- benchmark: approximate adders (VACSEM + EvoApproxLib), widths 8-192; 180 s compile cap; K in {16,64};
- reference chain: exhaustive == Ganak projected WMC == d4 reweight (bit-exact, 928 ER rows);
- ranking sensitivity is metric-, width-, and distribution-dependent (v2): strict ER
  inversions at widths 12/32/64 (D2/D4/D5 cells), strict MED inversions at 8/12/16/32/64
  (up to 14 at width 16 D4/D5, 13 at width 32 D2); width 128 shows none under D0-D5;
- frozen implementation in `src/python/` (adaptation allowed in this project only).

---

# 3. PHASE 1 — THEORY FEASIBILITY (CURRENT SCOPE)

## 3.1 Research questions (RQs)

- RQ1: Is `M_C(p)` a multi-affine function of p (per-PI-bit probabilities, factorized
  Bernoulli product distributions)?
- RQ2: Does the pairwise ranking margin `Delta_AB(p)` preserve multi-affinity?
- RQ3: Under box uncertainty U = prod_i [p_i_min, p_i_max], are the extrema of `M_C` / `Delta_AB`
  attained at vertices of U?
- RQ4: How to avoid full 2^n vertex enumeration (n = number of PI bits)?
- RQ5: Can a sound derivative / interval / branch-and-bound certificate be constructed?
- RQ6: How to define and compute the maximum certified robustness radius r*?
- RQ7: Has existing literature already solved this problem?

## 3.2 Phase-1 discipline

1. REMV-Ax is the foundation; re-packaging it as novelty is forbidden.
2. A new paper requires: new problem + new math results + new algorithm + new experiments.
3. derivative/sensitivity analysis alone is NOT novelty.
4. Prove SOUNDNESS first, then discuss scalability.
5. Phase 1 = small-scale theory kill/validate only. 8-bit exhaustive validation before any extension.
6. Actively seek counterexamples (adversarial testing is mandatory).
7. Every theorem must be labeled: PROVEN / CONJECTURE / EMPIRICAL OBSERVATION.
8. Never modify ground truth to obtain positive results.
9. If the route reduces to bare 2^n vertex enumeration with no non-trivial pruning/bound/certificate,
   the route is judged insufficient: STOP expanding and report.

## 3.3 Phase-1 prohibitions

- no large-scale formal experiments; no 32/64/128-bit campaigns;
- no full paper writing; no novelty claims;
- no modification of REMV-Ax;
- do NOT start theory derivation or experiments in the bootstrap round (report only).

---

# 4. GROUND-TRUTH / VALIDATION RULES

- All theory claims validated against exact values: exhaustive 8-bit enumeration (2^16 input
  assignments) or the frozen d4/Ganak evaluator in `src/python/`.
- Exact rational arithmetic only (`fractions.Fraction`); no floats in correctness paths.
- Every new algorithm ships with unit tests + counterexample search.
- Reference values come only from `experiments/ground_truth/` and `experiments/results/`
  (copies of REMV-Ax final results).
- Any empirical observation reported as such, never as a proof.

---

# 5. DIRECTORY LAYOUT

```
PROJECT_ROOT/
  AGENTS.md
  src/python/            frozen REMV-Ax implementation (adaptation allowed)
  experiments/
    configs/             frozen protocol + manifest + distribution configs
    ground_truth/        REMV-Ax final parsed results (exact reference values)
    theory_probe/        Phase-1 theory probes (new work lives here)
    results/             REMV-Ax final formal CSVs/JSONs + plotting_data
  workloads/
    manifests/           benchmark manifest + source pointers
    imported/            benchmark sources (add12 Verilog)
  reference_from_REMV_Ax/  immutable reference documents (read-only)
  reports/               run_report_N.md
  paper_material/
    figures/             plotting script + plotting data (copied)
    tables/              (empty; paper tables later)
  tools_tmp/             scratch + integrity snapshots
```

---

# 6. REPORT PROTOCOL

- Exactly one numbered report per user prompt.
- Report files in `reports/` use ONLY consecutive numeric names `1.md`, `2.md`, `3.md`, ...
  (the next report is max existing number + 1). Descriptive names such as
  `run_report_N.md` / `final_baseline_sync_report.md` are FORBIDDEN.
- Status: COMPLETE / PARTIAL / BLOCKED / INVALID_EXECUTION.
- Include: environment, work performed, experiment matrix, exact configs, raw results (weak/negative
  included), correctness/validity, engineering issues, data file paths, reproduction commands.
- NO interpretation / recommendation / paper-potential sections.

---

# 7. NEXT STEP

The only sanctioned next step (after this bootstrap) is:

> THEORY_FEASIBILITY_ROUND_1

to be launched by an explicit user prompt. The bootstrap round performs no theory derivation
and runs no experiments.

---

# 8. END-OF-PROMPT CHECKLIST

- [ ] Did I modify NOTHING in `D:/paper_project_REMV_Ax`?
- [ ] Did I execute the complete requested campaign as far as technically valid?
- [ ] Did I preserve weak/negative results?
- [ ] Did I label every theorem PROVEN / CONJECTURE / EMPIRICAL?
- [ ] Did I avoid novelty claims and route verdicts?
- [ ] Did I create exactly one new `run_report_N.md`?
- [ ] Did I list data paths for external analysis?

# 9. CORE OPERATING PRINCIPLE

> The local AI executes experiments and probes.
> The external supervisor interprets results and decides the route.
> Data, including negative data, are preserved.
> The research direction changes only by explicit new instruction.
