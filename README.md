# CARS

**Certified Approximate-Adder Ranking and Selection under Continuous Input Distribution Shifts**

CARS is the open-source implementation of a certified, exact analysis of how
the error-metric ranking of approximate adders changes as the *input
distribution itself* changes continuously.

The companion project **REMV-Ax** established *pointwise exact* error-rate (ER)
and mean-error-distance (MED) verification: for a fixed factorized per-bit
Bernoulli product distribution, the exact ER/MED of an approximate adder is
computed by knowledge compilation (d-DNNF via `d4` + exact reweighting). CARS
goes one step further: instead of evaluating one distribution at a time, it
proves *where and how often the ranking of adder designs flips* along a
continuous family of distributions.

---

## 1. Overview

We study the error metrics `M_C(p)` of an approximate adder `C` under a
factorized Bernoulli product distribution `p = (p_1, ..., p_n)` over the `n`
primary inputs (one probability per PI bit, bits independent). Two metrics are
considered:

- **ER** — error rate: the probability that `C` produces a wrong result;
- **MED** — mean error distance: the expected absolute difference between the
  exact and the approximate result.

Along an *affine probability path*

```
p_i(λ) = (1 − λ) · p_i(0) + λ · p_i(1),    λ ∈ [0, 1],
```

the exact ER and MED of every fixed adder become **polynomials in λ with exact
rational coefficients** (compiled once from the circuit, evaluated symbolically
over the path). Consequently, for any pair of designs `(A, B)`, the ranking
margin

```
Δ_AB(λ) = M_A(λ) − M_B(λ)
```

is an exact polynomial in `λ`, and the *ranking transitions* of the pair are
exactly the roots of `Δ_AB` inside `(0, 1)`. CARS isolates those roots with
certified exact arithmetic (Sturm sequences via `sympy`), classifies them
(crossing vs. touching), merges shared roots across pairs with exact
gcd/interval logic, and derives per-path "family regimes": maximal `λ`
intervals on which the **entire ranking of the design family is invariant**.

All scientific decisions are made with exact rational/algebraic arithmetic;
floating point is used only for display and for non-scientific performance
hints.

## 2. Key Features

- **Exact transitions** — certified isolation of all pairwise ranking-flip
  points `λ* ∈ (0,1)` with exact sign verification on both sides; no sampling,
  no numerical root finding.
- **Stable ranking regimes** — for each frozen path × metric, the maximal
  intervals of `λ` on which the full ranking of the design family is invariant,
  with an explicit ranking per interval.
- **Multi-flip pairs** — pairs of designs whose relative order flips more than
  once along a path (e.g., 10 pairs at 64-bit `Rnew` MED, 2 crossings each).
- **Top-1 switching** — detection of when the *best* design changes (a strictly
  weaker phenomenon than pairwise instability: 65 pairwise crossings at 16-bit
  produce only 1 top-1 switch; 19 crossings at 64-bit produce none).
- **Endpoint ties** — exact detection of pairs that tie at the path endpoints
  `λ ∈ {0, 1}` (e.g., all structured paths share the `D0` endpoint).
- **Certified shared-root handling** — exact gcd-based equality checks before
  interval refinement, so roots shared by several pairs (rational or algebraic)
  are merged once and reported with all contributing pairs.
- **Exact arithmetic throughout** — `fractions.Fraction` in all correctness
  paths; per-coefficient equivalence between the compiled (d-DNNF) evaluation
  and exhaustive 2^n simulation.
- **Frozen, resumable formal pipeline** — a checkpointed runner
  (`src/formal_runner.py`) with atomic result writes and SHA256 integrity
  records; all 1396 campaign jobs are committed as DONE, so the frozen state
  is reproducible without re-running any compilation.

## 3. Repository Structure

```
CARS/
├── README.md
├── LICENSE                     MIT (original code; see §9/§13 for benchmarks)
├── requirements.txt
├── AGENTS.md                   research-contract notes (frozen)
├── src/
│   ├── formal_runner.py        campaign runner: cnf / poly / family jobs
│   └── python/                 frozen REMV-Ax implementation (pointwise ER/MED
│                               pipeline; adaptation allowed in this project only)
├── experiments/
│   ├── configs/                frozen protocol + manifests + distribution configs
│   ├── ground_truth/           REMV-Ax final parsed results (exact reference values)
│   ├── results/                REMV-Ax v2 authoritative result tables
│   └── theory_probe/           Phase-1 theory probes (CARS core algorithm):
│       ├── tp1_poly.py         exact path-polynomial construction + root isolation
│       ├── tp2_cnf.py          CNF construction from miter BLIFs (pure Python)
│       ├── tp2_eval.py         exact d-DNNF polynomial evaluator
│       ├── tp2_round2.py       family regimes, certified root sort/merge, weak ranking
│       ├── tp_synth_tests.py   T1–T11 correctness tests
│       ├── tp_smoke.py         S1–S5 smoke/regression checks
│       ├── tp_paths.py         portable path resolution (PROJECT4_ROOT aware)
│       └── cnf/                frozen 12-bit CNF/NNF bank (smoke-test inputs)
├── formal/
│   ├── assets/                 miter BLIFs (ER + per-bit MED) for 16/32/64-bit,
│   │                           VACSEM design BLIFs, benchmark manifest, provenance
│   ├── config/                 frozen campaign config + frozen path endpoints
│   ├── checkpoints/            1396 job checkpoints (status = DONE, result SHA256)
│   ├── logs/                   recovery baseline
│   ├── manifests/              frozen benchmark + campaign manifests
│   └── results/                all 1399 frozen job results + per-width summaries
├── workloads/
│   ├── imported/add12/         EvoApproxLib 12-bit adders (MIT, attribution in headers)
│   └── manifests/              benchmark manifest + source pointers
├── reference_from_REMV_Ax/     frozen authoritative REMV-Ax reference (v2 bundle)
├── paper_material/figures/     plotting data + script
└── reports/                    numbered campaign reports (0.md–13.md)
```

`formal/nnf/` (the regenerable d4 compilation outputs for the 16/32/64-bit
campaign, ≈33 MB) is intentionally **not** committed: every downstream result
that depends on it is frozen in `formal/results/`. See §7 and §11 for
regeneration instructions and for the SHA256-pinned archive published as a
GitHub Release.

## 4. Requirements

- **Python ≥ 3.10** (developed and validated on 3.13/3.14, stdlib + packages below)
- **sympy ≥ 1.13** — exact polynomial arithmetic, Sturm isolation, gcd
- **numpy ≥ 2.0** *(optional)* — float localization used only as a performance
  hint for high-degree 64-bit root isolation; never in correctness paths
- **matplotlib** *(optional)* — only to re-render figures
  (`paper_material/figures/make_plots.py`)
- **No other Python dependencies.** No CNF/NNF compilation is required to
  verify any committed result (see §7).

Tools needed **only** for the optional full re-compilation of the formal
pipeline (all frozen results are already committed):

| tool | purpose | version pin |
|---|---|---|
| `d4` (crillab/d4, LGPL-3.0) | CNF → d-DNNF compilation | commit `333370cc1e843dd0749c1efe88516e72b5239174` |
| WSL (Windows) or bash (Linux) | d4 invocation transport | — |
| Yosys (ISC) | legacy Verilog → BLIF flow (manifest generation only) | 0.52 |

## 5. Installation

```bash
git clone https://github.com/qmkkk/CARS.git
cd CARS
python -m venv .venv
# Windows: .venv\Scripts\activate ; Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

No build step. All frozen inputs and results are part of the repository.

## 6. Quick Start

```bash
# 1. Show the frozen campaign state (expect 1396/1396 DONE, FAILED=0)
python src/formal_runner.py --status

# 2. Run the full correctness suite T1–T11 (certified-root/regime semantics)
python experiments/theory_probe/tp_synth_tests.py

# 3. Run the smoke/regression checks S1–S5 (12-bit exhaustive-vs-compiled etc.)
python experiments/theory_probe/tp_smoke.py
```

All three are exact-arithmetic only and complete in seconds to a few minutes
(no external tools, no network, no compilation).

## 7. Reproducing the Experiments

### 7.1 Frozen results (zero computation)

The complete formal campaign is committed under `formal/results/`:

- `formal/results/16bit/16bit_summary.{json,csv}`,
  `formal/results/32bit/32bit_summary.{json,csv}`,
  `formal/results/64bit/64bit_summary.{json,csv}` — per-width family analyses
  (36 families = 3 widths × 6 paths × 2 metrics);
- `formal/results/formal_summary.{json,csv}` — campaign roll-up;
- `formal/results/w{16,32,64}_poly_*.json` — per-design exact ER/MED path
  polynomials (rational coefficients);
- `formal/results/w{16,32,64}_family_*.json` — per-family regime analyses;
- `formal/results/w{16,32,64}_cnf_*.json` — per-job compilation records with
  NNF SHA256 fingerprints;
- `formal/checkpoints/*.json` — 1396 job checkpoints (status `DONE`, result
  SHA256, portable result paths).

### 7.2 Re-derive a family analysis from the frozen polynomials (no NNF needed)

The family stage reads only the frozen per-design polynomials. For example,
the 16-bit `D0D1` MED family:

```python
import json, sys
from fractions import Fraction
from pathlib import Path
sys.path.insert(0, "experiments/theory_probe")
from tp2_round2 import family_regimes_from_polys

width, pth, metric = 16, "D0D1", "MED"
cfg = json.loads(Path("formal/config/campaign_v1.json").read_text(encoding="utf-8"))
designs = cfg[f"designs_{width}"]
poly = {}
for d in designs:
    data = json.loads(Path(f"formal/results/w{width}_poly_{d}_{pth}.json").read_text(encoding="utf-8"))
    key = "er_coeffs" if metric == "ER" else "med_coeffs"
    poly[d] = [Fraction(x) for x in data[key]]
fam = family_regimes_from_polys(poly, designs, metric=metric)
print({k: fam[k] for k in ("n_transition_pairs", "n_distinct_transition_points",
                            "n_touching_points", "n_stable_intervals")})
```

The output must match the corresponding frozen
`formal/results/w16_family_D0D1_MED.json` fields.

### 7.3 Full re-compilation of the formal pipeline (optional, heavy)

The 12-bit NNF bank is committed (`experiments/theory_probe/cnf/`), so the
12-bit correctness checks run without `d4`. The 16/32/64-bit NNF banks are
regenerable as follows:

```bash
# a) regenerate CNFs from the committed miter BLIFs (pure Python, no tools)
python -c "import sys; sys.path.insert(0,'experiments/theory_probe'); from tp2_cnf import write_cnfs_miter; ..."

# b) compile CNF -> NNF with d4
export CART_D4=/path/to/d4            # crillab/d4, commit 333370c...
python src/formal_runner.py --resume  # only PENDING/FAILED jobs are executed
```

Environment variables (all optional):

| variable | meaning |
|---|---|
| `PROJECT4_ROOT` | project root override (path resolution is automatic otherwise) |
| `CART_D4` | path to the `d4` binary (otherwise looked up on `PATH`) |
| `CART_WSL_DISTRO` | WSL distro used for the Windows d4 transport (default `Ubuntu`) |
| `CART_YOSYS`, `CART_YOSYS_LD` | Yosys binary / `LD_LIBRARY_PATH` for the legacy Verilog→BLIF flow |

On native Linux/macOS the runner invokes `d4` directly; on Windows it uses the
`wsl.exe` transport.

## 8. Correctness Validation

All theory claims are validated against exact values; adversarial
counterexample construction is part of the test suite.

**T1–T11** (`experiments/theory_probe/tp_synth_tests.py`) — certified-root and
regime semantics, all exact:

| test | property |
|---|---|
| T1 | endpoint roots (`λ = 0, 1`) vs. interior roots |
| T2 | touching (double) roots are not counted as crossings |
| T3 | roots outside `[0,1]` are filtered exactly |
| T4 | tie-aware weak ranking (identical metrics form one group) |
| T5 | exact rational interior point strictly between adjacent algebraic roots |
| T6 | end-to-end integration: synthetic family with a touching root |
| T7 | certified sorting of roots from *different* high-degree polynomials |
| T8 | two numerically close but distinct algebraic roots (overlapping initial intervals) |
| T9 | real 64-bit slow-pair performance regression (exact semantics preserved) |
| T10 | shared *rational* crossing root across three pairs (dedup) |
| T11 | shared *irrational* crossing root (dedup via gcd, no float equality) |

**S1–S5** (`experiments/theory_probe/tp_smoke.py`):
- S1 gate-level vs. Verilog simulator equivalence (8 designs × 200 random inputs);
- S2 d-DNNF polynomial == exhaustive per-coefficient (12-bit, ER + MED);
- S3 D0–D5 authoritative endpoints vs. the frozen REMV-Ax v2 tables;
- S4 main-case root `Δ_MED(λ) = 0` at `0.303626883785739420486452162361…`;
- S5 12-bit family regimes (D0→D1 MED: 1 transition pair, 1 point, 2 stable intervals).

Validation against the frozen campaign:
- 1396/1396 jobs `DONE`, `FAILED=0` (`python src/formal_runner.py --status`);
- per-width summaries are byte-frozen and re-derived only from committed inputs;
- checkpoint `result_sha256` fields verify against the committed result files.

## 9. Benchmark Sources and Provenance

All benchmark designs are public; full pointers are in
`formal/assets/source_pointers.md` and `workloads/manifests/source_pointers.md`
(frozen). Summary:

| component | source | pin | license |
|---|---|---|---|
| 16/32/64-bit adder design BLIFs + miter BLIFs | VACSEM (`github.com/changmg/VACSEM`, historical pointer `ehw-fit/vacsem` in frozen docs) | commit `b11ede7` | MIT |
| 12-bit adders (`workloads/imported/add12/`) | EvoApproxLib (`github.com/ehw-fit/evoapproxlib`) | commit `ec28be83bfce1b8e8b92bd456be520d323a568b5` | MIT (attribution in each file header) |
| deviation functions | VACSEM official `absolute_error` template; widths missing upstream instantiated mechanically from the official parametric template and synthesized with the frozen Yosys 0.52 flow | — | MIT (template) |
| `d4` (external, not redistributed) | `github.com/crillab/d4` | commit `333370cc1e843dd0749c1efe88516e72b5239174` | LGPL-3.0 |
| Yosys (external, not redistributed) | official Yosys | 0.52 | ISC |
| Ganak (external, pointwise baseline only) | official v2.7.0 | repo HEAD `e8f5184` | BSD-3-Clause |

Design selection is frozen and result-independent: stable filename sort; if
≥ 10 eligible designs, a deterministic equal-interval selection of 10
(indices `floor(i·n/10)`); 5–9 → all; < 5 → all with a pool-limited note.
`add12u_19A` is excluded (functionally identical to the exact adder, ER = 0).

## 10. Results

The frozen campaign covers **16/32/64-bit**, **10 designs per width**
(deterministic equal-interval selection), **6 frozen paths**
(`D0D1, D0D2, D0D3, D0D4, D0D5, Rnew`), **2 metrics** (ER, MED) — **1396 jobs,
all DONE, FAILED = 0** (252 + 404 + 732 per width).

Per-width aggregates (36 family analyses):

| width | transition pairs | distinct transition points | endpoint tie pairs (MED, λ=0) | stable intervals (ER/MED) | multi-flip pairs | top-1 switches |
|---|---|---|---|---|---|---|
| 16 | 65 | 65 | 6 | 6 / 71 | 0 | 1 (Rnew MED: 1→3 at λ≈0.52) |
| 32 | 27 | 28 | 7 | 18 / 22 | 1 (Rnew MED: 1↔3, 2 crossings) | 2 (Rnew MED: 1→3→1) |
| 64 | 19 | 29 | 13 | 7 / 34 | 10 (Rnew MED, 2 crossings each) | 0 |

Main empirical findings (all exact, all frozen):

1. **ER and MED are exact polynomials in `λ` along affine Bernoulli paths**;
   pairwise margins `Δ_AB(λ)` are exact polynomials too (degree ≤ 2·width
   theoretically; observed maxima 32/64/96 for 16/32/64-bit, within the
   theoretical bounds 32/64/128).
2. **Ranking transitions are rare but real**: e.g., 65 pairwise crossings at
   16-bit vs. only 19 at 64-bit across the same 6 paths; several occur only
   under MED, not ER.
3. **Multi-flip pairs exist**: at 64-bit `Rnew` MED, 10 pairs cross twice
   (rank order restores at the far end of the path).
4. **Top-1 instability is much weaker than pairwise instability**:
   pairwise crossings do not imply winner switches — 64-bit has 19 crossings
   and **zero** top-1 switches; the only top-1 switches are on 16/32-bit
   `Rnew` MED.
5. **Endpoint ties are path-independent**: all structured paths share the
   `D0` endpoint; MED ties at `λ = 0` number 6/7/13 pairs for 16/32/64-bit.
6. **Structured paths show no identical pairs** (`Δ ≡ 0` count = 0 at all
   widths).

12-bit theory probe (exhaustive-validated): for the main pair
`add12u_4R6` vs. `add12u_4YR` on D0→D1 MED, `Δ_MED` has degree 12 with a single
interior root `0.303626883785739420486452162361…`; the family analysis reports
1 transition pair / 1 distinct point / 2 stable intervals.

## 11. Reproducibility Notes

- **Exact arithmetic only** in correctness paths; `float` appears solely for
  display or as a non-scientific performance hint (numpy window localization).
- **Frozen inputs**: campaign config, path endpoints (seed 42, probability pool
  {1/8, 1/4, 1/2, 3/4, 7/8}), manifests, benchmark assets, and all results are
  committed. The authoritative REMV-Ax reference package is mirrored under
  `reference_from_REMV_Ax/` (SHA256-pinned; archive `C7_clean_release_bundle_20261004_v2.zip`
  published as a GitHub Release).
- **No re-compilation needed for verification**: the 12-bit NNF bank is
  committed so all tests/smoke checks run offline. The 16/32/64-bit NNF banks
  are regenerable with `d4` (see §7.3); the self-contained final bundle archive
  (`paper_project_4_formal_final_clean_bundle_v2.zip`, SHA256-pinned) is
  published as a GitHub Release for users who want the full NNF banks without
  compiling anything.
- **Portable paths**: the runner and probes resolve everything relative to the
  repository root (or `PROJECT4_ROOT`); frozen checkpoint files use
  repository-relative result paths.
- **Known limitations**:
  - the 16/32/64-bit NNF/CNF banks are not in the Git tree (≈33 MB, d4-regenerable);
  - the frozen VACSEM provenance note in `source_pointers.md` reflects the
    historical repository pointer (`ehw-fit/vacsem`); the resolvable upstream
    is `changmg/VACSEM` at the same commit (MIT);
  - timing numbers in the results/checkpoints reflect the original machine and
    are informational only (no hard performance gates in T1–T11);
  - `reports/` are internal campaign records (in Chinese) and are committed for
    provenance; they may reference the original machine paths historically.

## 12. Citation

This repository accompanies a manuscript that is **not yet published**.
Until a DOI/venue exists, please cite the repository itself:

```bibtex
@misc{CARS2026,
  title  = {{CARS}: Certified Approximate-Adder Ranking and Selection under Continuous Input Distribution Shifts},
  author = {CARS contributors},
  year   = {2026},
  howpublished = {\url{https://github.com/qmkkk/CARS}},
  note   = {Software release; paper forthcoming. Update this entry with the
            DOI and venue once the manuscript is published.}
}
```

The companion pointwise-verification foundation is the REMV-Ax project
(exact ER/MED verification via d-DNNF compilation and reweighting); its frozen
reference data and documentation are mirrored in `reference_from_REMV_Ax/`.

## 13. License

- Original code in this repository: **MIT License** (see `LICENSE`).
- Redistributed benchmark designs:
  - EvoApproxLib 12-bit adders (`workloads/imported/add12/`): **MIT**,
    attribution in each file header;
  - VACSEM design/miter BLIFs and deviation functions (`formal/assets/`):
    **MIT**, source `github.com/changmg/VACSEM` @ `b11ede7`.
- External tools (not redistributed, invoked only when re-compiling): `d4`
  (LGPL-3.0), Yosys (ISC), Ganak (BSD-3-Clause).

If you use or extend this work, please keep the provenance and license
attributions intact.
