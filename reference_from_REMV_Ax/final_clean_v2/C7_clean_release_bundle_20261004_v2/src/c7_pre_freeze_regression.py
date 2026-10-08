"""Pre-freeze exactness regression for the final C7 ER backend.

Purpose: validate the full-variable d4 reweight path over more than D0/D3,
using corrected circuit-relative D0-D5 distributions plus one frozen random
product-distribution stream.  Every d4 value is compared bit-exactly against
Ganak projected weighted model counting on the same CNF.

This is a validation script, not a benchmark-expansion script.  It uses only
R7's frozen five cases plus the two non-degenerate pre-registered add12 cases.
"""
from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))

from c5_common import (DIST_NAMES, named_dist, random_dists, to_wmc, run_ganak,
                       active_pi_indices, save_json, RAW, PARSED)  # noqa: E402
from c5_r7_phase0 import (parse_nnf_fast, eval_nnf_fast, make_order,
                          build_litw)  # noqa: E402

TIMEOUT = 180
RANDOM_COUNT = 10
RANDOM_SEED = 42

CASES = [
    # family, total PIs, id, miter directory, d4 NNF path
    ("add16", 32, "10_add16_err_0.566452_size_105_depth_13",
     RAW / "miters_r6", RAW / "nnf_r7b" / "10_add16_err_0.566452_size_105_depth_13_er.d4.nnf"),
    ("add16", 32, "1_add16_err_0.00215149_size_143_depth_16",
     RAW / "miters_r6", RAW / "nnf_r7b" / "1_add16_err_0.00215149_size_143_depth_16_er.d4.nnf"),
    ("add16", 32, "2_add16_err_0.0311737_size_138_depth_13",
     RAW / "miters_r6", RAW / "nnf_r7b" / "2_add16_err_0.0311737_size_138_depth_13_er.d4.nnf"),
    ("add32", 64, "10_add32_err_0.197418_size_259_depth_14",
     RAW / "miters_r6", RAW / "nnf_r7b" / "10_add32_err_0.197418_size_259_depth_14_er.d4.nnf"),
    ("add32", 64, "11_add32_err_0.223526_size_257_depth_14",
     RAW / "miters_r6", RAW / "nnf_r7b" / "11_add32_err_0.223526_size_257_depth_14_er.d4.nnf"),
    ("add12", 24, "add12u_054",
     RAW / "add12" / "miters", RAW / "add12" / "nnf_d4" / "add12u_054_er.d4.nnf"),
    ("add12", 24, "add12u_2MB",
     RAW / "add12" / "miters", RAW / "add12" / "nnf_d4" / "add12u_2MB_er.d4.nnf"),
]


def main():
    # Guard against regression of the D4/D5 bug.
    for n in {n for _, n, *_ in CASES}:
        assert named_dist("D4", n) != named_dist("D1", n), ("D4==D1", n)
        assert named_dist("D5", n) != named_dist("D2", n), ("D5==D2", n)
        assert len(named_dist("D4", n)) == n

    rows = []
    all_match = True
    for family, n_total, cid, mdir, nnf in CASES:
        cnf = mdir / f"{cid}_er.cnf"
        blif = mdir / f"{cid}_er.blif"
        if not cnf.exists() or not blif.exists() or not nnf.exists():
            rows.append({"id": cid, "family": family, "status": "missing_artifact"})
            all_match = False
            continue
        idx = active_pi_indices(blif)
        types, arcs, root, _, _, mode = parse_nnf_fast(nnf)
        order = make_order(types, arcs, root, mode)

        dists = {d: named_dist(d, n_total) for d in DIST_NAMES}
        dists.update(random_dists(seed=RANDOM_SEED, count=RANDOM_COUNT, n=n_total))

        case_ok = True
        for dname, dist in dists.items():
            rv = eval_nnf_fast(types, arcs, order, build_litw(dist, idx), root)
            wmc = to_wmc(cnf, dist, RAW / "wmc_prefreeze", pi_indices=idx)
            gv, gt, _, timed_out, err = run_ganak(wmc, timeout=TIMEOUT)
            ok = (not timed_out and gv is not None and rv == gv)
            rows.append({
                "id": cid, "family": family, "distribution": dname,
                "n_pi_total": n_total, "n_pi_active": len(idx),
                "d4_value": str(rv), "ganak_value": str(gv) if gv is not None else None,
                "ganak_runtime_s": round(gt, 4) if gt is not None else None,
                "match": ok, "error": err if err else "",
            })
            case_ok = case_ok and ok
            if not ok:
                print(f"MISMATCH {cid} {dname}: d4={rv} ganak={gv} {err}", flush=True)
        all_match = all_match and case_ok
        print(f"{cid}: {'PASS' if case_ok else 'FAIL'}", flush=True)

    save_json(PARSED / "c7_pre_freeze_regression.json", {
        "purpose": "d4 full-variable ER exactness across corrected D0-D5 and 10 frozen random product distributions",
        "random_seed": RANDOM_SEED,
        "random_count": RANDOM_COUNT,
        "all_match": all_match,
        "rows": rows,
    })
    if not all_match:
        raise SystemExit(2)
    print("PRE_FREEZE_ER_REGRESSION_PASS")


if __name__ == "__main__":
    main()
