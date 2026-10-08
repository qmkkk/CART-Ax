"""Mandatory pre-freeze MED backend validation for C7.

R7's scalable d4 rescue validated ER.  If the paper keeps an ER+MED main
claim, MED must also be shown to work with the same compile-once/reweight-many
backend.  This script performs a deliberately small, fixed mechanism check on
one public case at each scale: add8, the formerly-hard add16, and add32.

For every absolute-error output bit, it compiles the raw VACSEM MED CNF with
d4 once, reweights for corrected D0-D5, and compares bit-exactly with Ganak
projected WMC.  The total MED is reconstructed as sum_k 2^k P(bit_k=1).
This is a pre-freeze correctness gate, not the final benchmark campaign.
"""
from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))

from c5_common import (DIST_NAMES, named_dist, gen_med_cnfs, to_wmc, run_ganak,
                       active_pi_indices, cnf_meta, save_json, RAW, PARSED,
                       C2C)  # noqa: E402
from c5_r7_phase0 import (parse_nnf_fast, eval_nnf_fast, make_order,
                          build_litw)  # noqa: E402
from c5_r7_phaseB import d4_compile  # noqa: E402

TIMEOUT = 180

# Fixed before execution: one case per scale, including R6's hardest add16.
CASES = [
    {"family": "add8", "n_pi": 16, "width": 9,
     "id": "1_add8_err_0.0299377_size_63_depth_12",
     "file": "1_add8_err_0.0299377_size_63_depth_12.blif"},
    {"family": "add16", "n_pi": 32, "width": 17,
     "id": "2_add16_err_0.0311737_size_138_depth_13",
     "file": "2_add16_err_0.0311737_size_138_depth_13.blif"},
    {"family": "add32", "n_pi": 64, "width": 33,
     "id": "10_add32_err_0.197418_size_259_depth_14",
     "file": "10_add32_err_0.197418_size_259_depth_14.blif"},
]


def make_entry(c):
    folder = C2C / "input" / c["family"]
    return {
        "id": c["id"], "family": c["family"], "n_pi": c["n_pi"],
        "approx": str(folder / c["file"]),
        "exact": str(folder / f"{c['family']}.blif"),
        "output_bits": c["width"],
    }


def const_value(cnf: Path):
    _maxpi, _nv, _nc, const = cnf_meta(cnf)
    if const == 0:
        return Fraction(0, 1)
    if const == 1:
        return Fraction(1, 1)
    return None


def main():
    rows = []
    all_match = True
    mdir = RAW / "med_prefreeze_miters"
    ndir = RAW / "nnf_prefreeze_med"

    for c in CASES:
        entry = make_entry(c)
        cnfs = gen_med_cnfs(entry, c["width"], mdir / c["id"])
        per_dist_d4 = {d: Fraction(0, 1) for d in DIST_NAMES}
        per_dist_ganak = {d: Fraction(0, 1) for d in DIST_NAMES}
        case_ok = True

        for k, cnf in enumerate(cnfs):
            blif = cnf.parent / (cnf.name.replace(".cnf_const0", "")
                                 .replace(".cnf_const1", "")
                                 .replace(".cnf", "") + ".blif")
            cv = const_value(cnf)
            if cv is not None:
                for d in DIST_NAMES:
                    per_dist_d4[d] += (1 << k) * cv
                    per_dist_ganak[d] += (1 << k) * cv
                rows.append({"id": c["id"], "bit": k,
                             "status": f"const{int(cv)}"})
                continue

            idx = active_pi_indices(blif)
            nnf, ct, _nodes, _count, note = d4_compile(cnf, ndir / c["id"], timeout=TIMEOUT)
            if nnf is None:
                rows.append({"id": c["id"], "bit": k, "status": note})
                case_ok = False
                continue
            types, arcs, root, _, _, mode = parse_nnf_fast(nnf)
            order = make_order(types, arcs, root, mode)

            for d in DIST_NAMES:
                dist = named_dist(d, c["n_pi"])
                rv = eval_nnf_fast(types, arcs, order, build_litw(dist, idx), root)
                wmc = to_wmc(cnf, dist, RAW / "wmc_prefreeze_med", pi_indices=idx)
                gv, gt, _, timed_out, err = run_ganak(wmc, timeout=TIMEOUT)
                ok = (not timed_out and gv is not None and rv == gv)
                rows.append({
                    "id": c["id"], "family": c["family"], "bit": k,
                    "distribution": d, "d4": str(rv),
                    "ganak": str(gv) if gv is not None else None,
                    "match": ok, "d4_compile_s": ct,
                    "ganak_runtime_s": round(gt, 4) if gt is not None else None,
                    "error": err if err else "",
                })
                case_ok = case_ok and ok
                if gv is not None:
                    per_dist_d4[d] += Fraction(1 << k, 1) * rv
                    per_dist_ganak[d] += Fraction(1 << k, 1) * gv

        totals_ok = all(per_dist_d4[d] == per_dist_ganak[d] for d in DIST_NAMES)
        case_ok = case_ok and totals_ok
        all_match = all_match and case_ok
        print(f"{c['id']}: {'PASS' if case_ok else 'FAIL'}", flush=True)
        rows.append({
            "id": c["id"], "family": c["family"], "status": "summary",
            "all_bits_match": case_ok, "med_d4": {d: str(per_dist_d4[d]) for d in DIST_NAMES},
            "med_ganak": {d: str(per_dist_ganak[d]) for d in DIST_NAMES},
        })

    save_json(PARSED / "c7_med_backend_probe.json", {
        "purpose": "pre-freeze MED d4 backend exactness gate",
        "cases": CASES, "all_match": all_match, "rows": rows,
    })
    if not all_match:
        raise SystemExit(2)
    print("PRE_FREEZE_MED_BACKEND_PASS")


if __name__ == "__main__":
    main()
