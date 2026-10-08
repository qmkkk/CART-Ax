"""Round-7 Phase B: d4 (official crillab/d4) d-DNNF compilation rescue.

Fixed cases (R6, unchanged): 3 x add16 + 2 x add32, raw ER CNFs
(miters_r6/*_er.cnf, unprojected, unweighted).

Tool: official d4 repository https://github.com/crillab/d4
  - commit 333370cc1e843dd0749c1efe88516e72b5239174 (HEAD at clone time)
  - built from source in WSL with g++ 15.2; GMP/zlib headers+libs extracted
    from the official Ubuntu 26.04 .debs (libgmp-dev / libgmpxx4ldbl /
    zlib1g-dev) into tools/cache/deps/aptroot (no sudo available), boost
    1.85 headers from tools/cache/boost_1_85_0.
  - invocation: ./d4 -dDNNF <cnf> -out=<nnf>  (full-variable d-DNNF; d4's
    own unweighted count 's N' is recorded as an additional D0 cross-check)
  - single compile timeout = 180 s.

Exactness contract (identical math, different implementation):
  - D0/D3 reweight with PI literal weights by BLIF PI index, internal
    (Tseitin) literals neutral (weight 1) -> must be bit-exact vs the Ganak
    exact projected WMC values (Ganak is the reference).
  - d4's raw unweighted count is recorded as a diagnostic only; it is NOT
    a correctness reference because full CNFs may contain free auxiliaries.
  - only after exactness: K in {16,64} compile-once/reweight-many with
    explicit cold-total / warm-total / marginal-per-eval accounting
    (identical to the Phase 0 fixed methodology).
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

from c5_common import (named_dist, random_dists, to_wmc, run_ganak, active_pi_indices,  # noqa: E402
                       cnf_meta, wsl_path, WSL_PREFIX, save_json, RAW, PARSED)
from c5_r7_phase0 import (parse_nnf_fast, eval_nnf_fast, make_order,  # noqa: E402
                          build_litw, random_dist, N_PI_TOTAL)

TIMEOUT = 180
KS = (16, 64)
D4 = PROJECT_ROOT / "tools" / "cache" / "d4" / "d4"
OUTDIR = RAW / "nnf_r7b"

CASES = [
    ("add16", "10_add16_err_0.566452_size_105_depth_13"),
    ("add16", "1_add16_err_0.00215149_size_143_depth_16"),
    ("add16", "2_add16_err_0.0311737_size_138_depth_13"),
    ("add32", "10_add32_err_0.197418_size_259_depth_14"),
    ("add32", "11_add32_err_0.223526_size_257_depth_14"),
]


def d4_compile(cnf: Path, outdir: Path, timeout=TIMEOUT):
    """Official d4 -dDNNF compile (cached; single 180 s attempt)."""
    outdir.mkdir(parents=True, exist_ok=True)
    nnf = outdir / (cnf.stem + ".d4.nnf")
    count = None
    if nnf.exists() and nnf.stat().st_size > 0:
        txt = nnf.read_text(errors="replace")
        nodes = sum(1 for ln in txt.splitlines() if ln[:1] in ("a", "o", "t", "f"))
        return nnf, None, nodes, None, "cached"
    cmd = f"cd {wsl_path(D4.parent)} && ./d4 -dDNNF {wsl_path(cnf)} -out={wsl_path(nnf)}"
    t0 = time.time()
    try:
        r = subprocess.run(WSL_PREFIX + [cmd], capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, timeout, None, None, "timeout"
    dt = time.time() - t0
    m = re.search(r"^s (\d+)", r.stdout, re.M)
    count = int(m.group(1)) if m else None
    if not nnf.exists() or nnf.stat().st_size == 0:
        return None, dt, None, count, "no_output:" + (r.stdout + r.stderr)[-200:]
    txt = nnf.read_text(errors="replace")
    nodes = sum(1 for ln in txt.splitlines() if ln[:1] in ("a", "o", "t", "f"))
    return nnf, dt, nodes, count, "ok"


def main():
    results = []
    miter_dir = RAW / "miters_r6"
    for family, case_id in CASES:
        cnf = miter_dir / f"{case_id}_er.cnf"
        row = {"id": case_id, "family": family}
        idx = active_pi_indices(miter_dir / f"{case_id}_er.blif")
        maxpi, nvars, ncls, const = cnf_meta(cnf)
        row["cnf_maxpi"] = maxpi
        row["cnf_nvars"] = nvars
        n_total = {"add8": 16, "add16": 32, "add32": 64}[family]
        row["n_pi_total"] = n_total
        # a) Ganak exact references D0/D3
        refs = {}
        for d in ("D0", "D3"):
            dist = named_dist(d, n_total)
            wmc_d = to_wmc(cnf, dist,
                           RAW / "wmc", pi_indices=idx)
            g, gt, *_ = run_ganak(wmc_d, timeout=TIMEOUT)
            refs[d] = g
            row[f"ganak_{d}"] = str(g) if g else None
            row[f"ganak_{d}_s"] = round(gt, 3) if gt else None
        if refs["D0"] is None:
            results.append(row | {"status": "wmc_failed"})
            continue
        # b) d4 compile
        nnf, ct, nodes, count, note = d4_compile(cnf, OUTDIR)
        row["d4_compile_s"] = round(ct, 3) if ct is not None else None
        row["d4_note"] = note
        if nnf is None:
            results.append(row | {"status": "compile_timeout" if note == "timeout"
                                  else "compile_failed"})
            print(f"[{case_id}] d4 {note} ({ct:.1f}s)", flush=True)
            continue
        row["nnf_mb"] = round(nnf.stat().st_size / 1e6, 4)
        row["nnf_nodes"] = nodes
        types, arcs, root, n, na, mode = parse_nnf_fast(nnf)
        row["nnf_arcs"] = na
        row["order_mode"] = mode
        row["d4_count_s"] = count
        order = make_order(types, arcs, root, mode)
        # c) D0/D3 reweight vs Ganak
        ok_all = True
        for d in ("D0", "D3"):
            litw = build_litw(named_dist(d, n_total), idx)
            t0 = time.time()
            rv = eval_nnf_fast(types, arcs, order, litw, root)
            row[f"reweight_{d}_s"] = round(time.time() - t0, 4)
            row[f"reweight_{d}"] = str(rv)
            row[f"match_{d}"] = (refs[d] is not None and rv == refs[d])
            ok_all = ok_all and row[f"match_{d}"]
        # Raw d4 unweighted model count is diagnostic only. Full CNFs may
        # contain free auxiliary variables, so count/2**n_total need not equal ER.
        if count is not None:
            row["d4_count_diagnostic"] = count
        if not ok_all:
            results.append(row | {"status": "reweight_mismatch"})
            print(f"[{case_id}] d4 REWEIGHT MISMATCH", flush=True)
            continue
        ctd = f"{ct:.1f}s" if ct is not None else "cached(no fresh time)"
        print(f"[{case_id}] d4 OK: compile {ctd} nnf {row['nnf_mb']} MB "
              f"nodes={nodes} arcs={na} count={count} D0/D3 match", flush=True)
        # d) K in {16,64}
        for K in KS:
            dists = {"D0": named_dist("D0", n_total)}
            dists.update(random_dists(seed=42, count=K - 1, n=n_total))
            t0 = time.time()
            for dname, dist in dists.items():
                litw = build_litw(dist, idx)
                eval_nnf_fast(types, arcs, order, litw, root)
            warm = time.time() - t0
            t0 = time.time()
            for dname, dist in dists.items():
                wmc_d = to_wmc(cnf, [Fraction(p) for p in dist],
                               RAW / "wmc", pi_indices=idx)
                run_ganak(wmc_d, timeout=TIMEOUT)
            ganak_total = time.time() - t0
            t0 = time.time()
            parse_nnf_fast(nnf)  # one-time load/parse/build
            parse_s = time.time() - t0
            cold = None if ct is None else ct + parse_s + warm
            row[f"K{K}_warm_s"] = round(warm, 3)
            row[f"K{K}_cold_s"] = round(cold, 3) if cold is not None else None
            row[f"K{K}_ganak_s"] = round(ganak_total, 3)
            row[f"K{K}_marginal_per_eval_s"] = round(warm / K, 4)
            row[f"K{K}_amort_warm"] = bool(warm < ganak_total)
            row[f"K{K}_amort_cold"] = (bool(cold < ganak_total)
                                                 if cold is not None else None)
        results.append(row | {"status": "ok"})
        print(f"[{case_id}] K16/K64 amort(warm/cold): "
              f"{row['K16_amort_warm']}/{row['K16_amort_cold']} "
              f"{row['K64_amort_warm']}/{row['K64_amort_cold']}", flush=True)
    save_json(PARSED / "c5_r7_phaseB.json", {
        "method": ("official d4 -dDNNF full-variable compilation of the raw "
                   "ER CNF; reweight with PI-index weights, internal vars "
                   "neutral; reference = Ganak exact projected WMC; "
                   "d4 raw count recorded as diagnostic only"),
        "d4_repo": "https://github.com/crillab/d4",
        "d4_commit": "333370cc1e843dd0749c1efe88516e72b5239174",
        "d4_build": ("built from source (g++ 15.2, WSL); GMP/zlib from "
                     "official Ubuntu 26.04 debs extracted to "
                     "tools/cache/deps/aptroot; boost 1.85 headers"),
        "results": results,
    })
    print("phase B done")


if __name__ == "__main__":
    main()
