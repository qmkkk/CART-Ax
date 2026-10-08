"""Task 4 (pre-freeze): one fresh serial timing/fairness regression.

Runs the frozen R7 five cases only, in a fresh output directory so that every
d4 compile is genuinely fresh (no cache-hit compile is ever treated as zero).
Everything is serial; no concurrent Ganak jobs.

Recorded per case:
  - fresh d4 compile wall time
  - one-time NNF read/parse/build
  - K=16/64 warm total (K evaluations on the already-loaded representation)
  - K=16/64 cold total (fresh compile + parse/build + K evaluations)
  - marginal = warm / K
  - K independent Ganak end-to-end (same distribution IDs, serial; includes
    WSL/process/file overhead)
  - Ganak solver-internal time (line 'c o Total time [Arjun+GANAK]: X') as an
    extra diagnostic when present (not a blocker otherwise)

Definitions (identical on both sides, no mixing):
  cold = fresh compile + one-time parse/build + K evaluations
  warm = K evaluations on the loaded representation
  marginal = warm / K
Distributions: D0 plus K-1 random product distributions from ONE frozen
seed-42 stream (values in {1/8,1/4,1/2,3/4,7/8}), same IDs on both sides.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))

from c5_common import (named_dist, random_dists, to_wmc, run_ganak,  # noqa: E402
                       active_pi_indices, wsl_path, WSL_PREFIX, CACHE,
                       save_json, RAW, PARSED)
from c5_r7_phase0 import (parse_nnf_fast, eval_nnf_fast, make_order,  # noqa: E402
                          build_litw)
from c5_r7_phaseB import d4_compile  # noqa: E402

TIMEOUT = 180
KS = (16, 64)
CASES = [
    ("add16", 32, "10_add16_err_0.566452_size_105_depth_13"),
    ("add16", 32, "1_add16_err_0.00215149_size_143_depth_16"),
    ("add16", 32, "2_add16_err_0.0311737_size_138_depth_13"),
    ("add32", 64, "10_add32_err_0.197418_size_259_depth_14"),
    ("add32", 64, "11_add32_err_0.223526_size_257_depth_14"),
]
OUTDIR = RAW / "nnf_prefreeze_timing"


def ganak_internal_s(cmd_stdout: str):
    m = re.search(r"Total time \[Arjun\+GANAK\]:\s*([\d.]+)", cmd_stdout)
    return float(m.group(1)) if m else None


def run_ganak_timed(wmc: Path, timeout=TIMEOUT):
    """Like run_ganak but also returns solver-internal time and stdout."""
    cmd = f"cd {wsl_path(CACHE)} && ./ganak_linux/ganak --mode 1 --prob 0 {wsl_path(wmc)}"
    t0 = time.time()
    try:
        r = subprocess.run(WSL_PREFIX + [cmd], capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, timeout, None, True, "timeout", None
    dt = time.time() - t0
    intern = ganak_internal_s(r.stdout)
    if r.returncode != 0:
        return None, dt, None, False, (r.stdout + r.stderr)[-500:], intern
    m = re.search(r"c s exact arb frac (\d+)/(\d+)", r.stdout)
    if m:
        return Fraction(int(m.group(1)), int(m.group(2))), dt, None, False, "", intern
    m = re.search(r"c s exact arb frac (\d+)", r.stdout)
    if m:
        return Fraction(int(m.group(1)), 1), dt, None, False, "", intern
    return None, dt, None, False, (r.stdout + r.stderr)[-300:], intern


def startup_baseline():
    """Ganak process/startup baseline: 5 runs on a trivial 3-var CNF."""
    tiny = RAW / "wmc_prefreeze_timing" / "_tiny_startup.wmc"
    tiny.write_text("c t pwmc\np cnf 3 1\nc p show 1 2 3 0\n"
                    "c p weight 1 1/2 0\nc p weight -1 1/2 0\n"
                    "c p weight 2 1/2 0\nc p weight -2 1/2 0\n"
                    "c p weight 3 1/2 0\nc p weight -3 1/2 0\n"
                    "1 2 3 0\n", encoding="utf-8")
    per = []
    intern = []
    for _ in range(5):
        t0 = time.perf_counter()
        _g, dt, _r, _to, _e, it = run_ganak_timed(tiny, timeout=30)
        per.append(time.perf_counter() - t0)
        if it is not None:
            intern.append(it)
    return {
        "per_invocation_wall_s": [round(t, 3) for t in per],
        "min_wall_s": round(min(per), 3),
        "solver_internal_s": [round(t, 4) for t in intern] if intern else None,
        "note": ("wall includes WSL bash + ganak process start + CNF parse; "
                 "solver-internal = 'Total time [Arjun+GANAK]' line when present"),
    }


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (RAW / "wmc_prefreeze_timing").mkdir(parents=True, exist_ok=True)
    baseline = startup_baseline()
    print("[startup baseline]", baseline, flush=True)

    results = []
    for family, n_total, cid in CASES:
        mdir = RAW / "miters_r6"
        cnf = mdir / f"{cid}_er.cnf"
        blif = mdir / f"{cid}_er.blif"
        row = {"id": cid, "family": family, "n_pi_total": n_total}
        idx = active_pi_indices(blif)
        row["n_pi_active"] = len(idx)

        # a) FRESH d4 compile (fresh directory; cache-safe)
        nnf, ct, nodes, count, note = d4_compile(cnf, OUTDIR / family, timeout=TIMEOUT)
        assert ct is not None, f"fresh compile returned cache time for {cid}"
        row["fresh_compile_s"] = round(ct, 4)
        row["compile_note"] = note
        if nnf is None:
            results.append(row | {"status": "compile_timeout"})
            continue
        row["nnf_mb"] = round(nnf.stat().st_size / 1e6, 4)
        row["nnf_nodes"] = nodes
        # b) one-time parse/build
        t0 = time.perf_counter()
        types, arcs, root, n, na, mode = parse_nnf_fast(nnf)
        order = make_order(types, arcs, root, mode)
        row["parse_build_s"] = round(time.perf_counter() - t0, 4)
        row["nnf_arcs"] = na

        # c) + d) K warm/cold/marginal and K independent Ganak e2e (serial,
        #    same frozen distribution IDs on both sides)
        for K in KS:
            dists = {"D0": named_dist("D0", n_total)}
            dists.update(random_dists(seed=42, count=K - 1, n=n_total))
            t0 = time.perf_counter()
            for dname, dist in dists.items():
                litw = build_litw(dist, idx)
                eval_nnf_fast(types, arcs, order, litw, root)
            warm = time.perf_counter() - t0
            cold = ct + row["parse_build_s"] + warm
            t0 = time.perf_counter()
            g_total = 0.0
            g_intern_sum = 0.0
            g_intern_ok = True
            for dname, dist in dists.items():
                wmc = to_wmc(cnf, dist, RAW / "wmc_prefreeze_timing",
                             pi_indices=idx)
                _g, dt, _r, timed_out, err, it = run_ganak_timed(wmc, timeout=TIMEOUT)
                g_total += dt
                if it is None:
                    g_intern_ok = False
                else:
                    g_intern_sum += it
                if timed_out or _g is None:
                    g_intern_ok = False
            ganak_e2e = time.perf_counter() - t0
            row[f"K{K}_warm_s"] = round(warm, 4)
            row[f"K{K}_cold_s"] = round(cold, 4)
            row[f"K{K}_marginal_per_eval_s"] = round(warm / K, 6)
            row[f"K{K}_ganak_e2e_s"] = round(ganak_e2e, 3)
            row[f"K{K}_ganak_internal_sum_s"] = (round(g_intern_sum, 4)
                                                 if g_intern_ok else None)
            row[f"K{K}_amort_warm"] = bool(warm < ganak_e2e)
            row[f"K{K}_amort_cold"] = bool(cold < ganak_e2e)
        results.append(row | {"status": "ok"})
        print(f"{cid}: fresh_compile={row['fresh_compile_s']}s "
              f"K16 amort(warm/cold)={row['K16_amort_warm']}/{row['K16_amort_cold']} "
              f"K64 amort(warm/cold)={row['K64_amort_warm']}/{row['K64_amort_cold']}",
              flush=True)

    save_json(PARSED / "c7_pre_freeze_timing.json", {
        "purpose": ("pre-freeze fresh serial timing regression on the frozen "
                    "five cases (d4 full-variable backend)"),
        "definitions": {
            "cold": "fresh compile + one-time parse/build + K evaluations",
            "warm": "K evaluations on the already loaded representation",
            "marginal": "warm / K",
            "ganak_e2e": ("K independent ganak invocations, serial; includes "
                          "WSL/process/file overhead and .wmc writes"),
            "distributions": ("D0 + K-1 random product distributions from one "
                              "frozen seed-42 stream (pool {1/8..7/8}); same "
                              "IDs on the reweight and ganak sides"),
            "no_cache_as_fresh": True,
            "no_concurrent_ganak": True,
        },
        "startup_baseline": baseline,
        "results": results,
    })
    print("TASK4_TIMING_DONE")


if __name__ == "__main__":
    main()
