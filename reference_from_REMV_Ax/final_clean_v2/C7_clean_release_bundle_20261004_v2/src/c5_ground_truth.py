"""Round-5 correctness ground truth: exhaustive enumeration.

For the 10 small 8-bit circuit pairs the PI space is fully enumerable.  We
simulate the OFFICIAL VACSEM miter BLIFs (gate-based, unambiguous) over all
2^n PI assignments once per circuit and derive, per assignment, the absolute
error value (from the MED miter bits) and the ER indicator (from the ER
miter).  Per distribution the exact weighted ER/MED are computed with Python
Fraction.  These are cross-checked bit-exactly against Ganak exact
projected-WMC on the same miters, and the ER-vs-MED miter consistency is
checked (ER indicator iff error > 0).

MED bit-order: PO index k of the deviation circuit is bit weight 2^k (LSB
first) - established empirically by matching exhaustive per-bit counts.
"""
from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))

from blif_sim import Blif  # noqa: E402
from c5_common import (DIST_NAMES, named_dist, build_manifest, gen_er_cnf, gen_med_cnfs,  # noqa: E402
                       to_wmc, run_ganak, active_pi_indices, sort_med_artifacts, save_json, RAW, PARSED)


def enumerate_circuit(entry, miter_dir):
    """One pass over all PI assignments; returns (errs, er_flags) where
    errs[a] = absolute error value, er_flags[a] = ER miter output."""
    er_blif = miter_dir / f"{entry['id']}_er.blif"
    mit = Blif(str(er_blif))
    med_cnfs = sort_med_artifacts(miter_dir.glob(f"{entry['id']}_med_*.cnf*"))
    med_blifs = [Blif(str(miter_dir / (c.name.replace(".cnf_const0", "")
                                       .replace(".cnf_const1", "")
                                       .replace(".cnf", "") + ".blif")))
                 for c in med_cnfs]
    n = len(mit.inputs)
    nbit = len(med_blifs)
    errs = []
    flags = []
    for mask in range(1 << n):
        assign = {mit.inputs[i]: (mask >> i) & 1 for i in range(n)}
        f = mit.eval(assign)[mit.outputs[0]]
        flags.append(f)
        e = 0
        for k, bm in enumerate(med_blifs):
            if bm.eval(assign)[bm.outputs[0]]:
                e |= 1 << k
        errs.append(e)
    # consistency: ER flag iff error > 0
    assert all((f == 1) == (e > 0) for f, e in zip(flags, errs)), \
        "ER miter and MED miter disagree"
    return errs, flags, n


def weighted_stats(errs, flags, n, probs):
    er = Fraction(0, 1)
    med = Fraction(0, 1)
    tot = Fraction(0, 1)
    for mask in range(1 << n):
        w = Fraction(1, 1)
        for i in range(n):
            bit = (mask >> i) & 1
            w *= probs[i] if bit else 1 - probs[i]
        if flags[mask]:
            er += w
        if errs[mask]:
            med += w * errs[mask]
        tot += w
    return er / tot, med / tot


def main():
    manifest = build_manifest()
    small = [e for e in manifest if e["set"] == "small"]
    miter_dir = RAW / "miters"
    results = {}
    all_ok = True
    for entry in small:
        eid = entry["id"]
        gen_er_cnf(entry, miter_dir)
        gen_med_cnfs(entry, entry["output_bits"], miter_dir)
        errs, flags, n = enumerate_circuit(entry, miter_dir)
        per_dist = {}
        for dname in DIST_NAMES:
            probs = named_dist(dname, n)
            er, med = weighted_stats(errs, flags, n, probs)
            # Ganak ER
            er_indices = active_pi_indices(miter_dir / f"{eid}_er.blif")
            wmc = to_wmc(miter_dir / f"{eid}_er.cnf", probs, RAW / "wmc",
                         pi_indices=er_indices)
            g = run_ganak(wmc)
            g_er = g[0]
            er_ok = (g_er is not None and g_er == er)
            # Ganak MED bits (LSB-first mapping; count = bit set probability)
            med_cnfs = sort_med_artifacts(miter_dir.glob(f"{eid}_med_*.cnf*"))
            g_med = None
            med_ok = False
            g_bits = []
            for k, c in enumerate(med_cnfs):
                blif = miter_dir / (c.name.replace(".cnf_const0", "")
                                    .replace(".cnf_const1", "")
                                    .replace(".cnf", "") + ".blif")
                idx = active_pi_indices(blif)
                bc = run_ganak(to_wmc(c, probs, RAW / "wmc", pi_indices=idx))[0]
                g_bits.append(bc)
            if all(x is not None for x in g_bits):
                g_med = sum(Fraction(2 ** k, 1) * x for k, x in enumerate(g_bits))
                med_ok = (g_med == med)
            per_dist[dname] = {
                "er_exhaustive": str(er), "er_ganak": str(g_er) if g_er else None,
                "er_match": er_ok,
                "med_exhaustive": str(med), "med_ganak": str(g_med),
                "med_match": med_ok,
                "er_ganak_runtime_s": round(g[1], 3),
            }
            if not er_ok or not med_ok:
                all_ok = False
                print(f"  MISMATCH {eid} {dname}: ER {er} vs ganak {g_er}; "
                      f"MED {med} vs {g_med}")
        results[eid] = {"id": eid, "family": entry["family"],
                        "output_bits": entry["output_bits"], "n_pi": n,
                        "distributions": per_dist}
        print(f"{eid}: done")
    save_json(PARSED / "c5_ground_truth.json", {
        "scope": ("10 small 8-bit circuits x 6 distributions; exhaustive "
                  "Fraction enumeration of the official VACSEM miters vs Ganak "
                  "exact projected-WMC"),
        "all_match": all_ok,
        "results": results,
    })
    print("ALL MATCH" if all_ok else "MISMATCHES PRESENT")


if __name__ == "__main__":
    main()
