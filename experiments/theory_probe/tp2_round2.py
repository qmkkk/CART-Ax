"""tp2_round2.py — THEORY_FEASIBILITY_ROUND_2 main campaign.

Tasks:
  3. d-DNNF vs exhaustive per-coefficient comparison of M_A/M_B/Delta (D0->D1) + roots/endpoints;
  4. new paths: D0->D3 (alternating) and R_i->R_j (random), one transition/stability pair each;
  5. full 12-bit family: all-pair Delta roots on D0->D1, merged sorted transition points,
     complete ranking per adjacent interval (exact root isolation, no float dedup);
  6. key facts (pair counts, transitions, intervals, multi-flips, nominal-best, ER/MED stability,
     timing/representation sizes).
"""
from __future__ import annotations

import itertools
import json
import sys
import time
from fractions import Fraction
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
import tp_paths  # noqa: E402
PROJECT_ROOT = tp_paths.ROOT
sys.path.insert(0, str(PROJECT_ROOT / "experiments" / "theory_probe"))

from tp1_poly import (read_metric_csv, locate_inversions, exhaustive_buckets,
                      exhaustive_buckets_2g, metric_poly, trim, eval_poly,
                      roots_in_unit, sign_at, conv, binom_poly, exact_roots,
                      sort_roots, _count_open, refine_interval)  # noqa: E402
from tp2_eval import parse_nnf, eval_nnf_poly, nnf_metric_polys  # noqa: E402

OUT = tp_paths.out_dir()
CNF = tp_paths.cnf_dir()
DESIGNS = ["add12u_054", "add12u_2MB", "add12u_4FZ", "add12u_4R6",
           "add12u_4RF", "add12u_4XD", "add12u_4YK", "add12u_4YR"]
N = 24
Z = Fraction(0, 1)
ONE = Fraction(1, 1)


def dist_vector(name, n=24):
    """D0-D5 per-PI Fraction vector (c5_common semantics)."""
    if name == "D0":
        return [Fraction(1, 2)] * n
    if name == "D1":
        return [Fraction(1, 4)] * n
    if name == "D2":
        return [Fraction(3, 4)] * n
    if name == "D3":
        return [Fraction(1, 4) if i % 2 == 0 else Fraction(3, 4) for i in range(n)]
    half = n // 2
    if name == "D4":
        return [Fraction(1, 4) if i < half else Fraction(3, 4) for i in range(n)]
    if name == "D5":
        return [Fraction(3, 4) if i < half else Fraction(1, 4) for i in range(n)]
    raise KeyError(name)


# ---------------- task 3: full comparison on the main pair ----------------

def compare_pair(design_a, design_b, p0, p1, bucket_fn, label):
    """NNF (d-DNNF) vs exhaustive polynomials for both designs; report Delta-AB too."""
    res = {"label": label, "a": design_a, "b": design_b}
    polys_nnf, polys_ex = {}, {}
    t_nnf = t_ex = 0.0
    for d in (design_a, design_b):
        t0 = time.time()
        er, med = nnf_metric_polys(d, p0, p1)
        t_nnf += time.time() - t0
        polys_nnf[d] = (er, med)
        t0 = time.time()
        f = None
        from tp1_verilog import load_design
        f, _ = load_design(d)
        sumE, cntE = bucket_fn(f)
        n_bits = len(sumE) - 1
        er_ex = trim(metric_poly(cntE, p0[0], p1[0], n_bits))
        med_ex = trim(metric_poly(sumE, p0[0], p1[0], n_bits))
        t_ex += time.time() - t0
        polys_ex[d] = (er_ex, med_ex)
    res["t_nnf_s"] = round(t_nnf, 3)
    res["t_exhaustive_s"] = round(t_ex, 3)
    for d in (design_a, design_b):
        for m, (nn, ex) in {"ER": (polys_nnf[d][0], polys_ex[d][0]),
                            "MED": (polys_nnf[d][1], polys_ex[d][1])}.items():
            n = max(len(nn), len(ex))
            diff = [(i, str((nn[i] if i < len(nn) else Z) - (ex[i] if i < len(ex) else Z)))
                    for i in range(n) if (nn[i] if i < len(nn) else Z) != (ex[i] if i < len(ex) else Z)]
            res[f"{m}_{d}_coeff_match"] = (len(diff) == 0)
            res[f"{m}_{d}_deg_nnf"] = len(nn) - 1
            res[f"{m}_{d}_deg_ex"] = len(ex) - 1
            if diff:
                res[f"{m}_{d}_diffs"] = diff[:5]
    # Delta-AB: NNF vs exhaustive
    for m, idx in {"ER": 0, "MED": 1}.items():
        dnn = trim([polys_nnf[design_a][idx][k] - polys_nnf[design_b][idx][k]
                    if k < len(polys_nnf[design_a][idx]) and k < len(polys_nnf[design_b][idx])
                    else (polys_nnf[design_a][idx][k] if k < len(polys_nnf[design_a][idx])
                          else -polys_nnf[design_b][idx][k] if k < len(polys_nnf[design_b][idx]) else Z)
                    for k in range(max(len(polys_nnf[design_a][idx]), len(polys_nnf[design_b][idx])))])
        dex = trim([polys_ex[design_a][idx][k] - polys_ex[design_b][idx][k]
                    if k < len(polys_ex[design_a][idx]) and k < len(polys_ex[design_b][idx])
                    else (polys_ex[design_a][idx][k] if k < len(polys_ex[design_a][idx])
                          else -polys_ex[design_b][idx][k] if k < len(polys_ex[design_b][idx]) else Z)
                    for k in range(max(len(polys_ex[design_a][idx]), len(polys_ex[design_b][idx])))])
        match = (dnn == dex)
        res[f"Delta_{m}_coeff_match"] = match
        res[f"Delta_{m}_deg"] = len(dnn) - 1
        if match:
            rr = roots_in_unit(dnn)
            res[f"Delta_{m}_roots"] = None if rr is None else [[str(r.evalf(30)), m2] for r, m2 in rr]
        else:
            res[f"Delta_{m}_note"] = "nnf/ex mismatch"
    return res, polys_nnf, polys_ex


# ---------------- task 5: family ranking regimes (D0->D1) -------------------

def rational_between(lo, hi, max_iter=300):
    """EXACT rational point q with lo < q < hi, where lo/hi are 0, 1, or RootOf.
    Binary search over the rational grid using exact RootOf-vs-rational comparisons."""
    a, b = Fraction(0), Fraction(1)
    for _ in range(max_iter):
        q = (a + b) / 2
        if q > lo and q < hi:
            return q
        if q <= lo:
            a = q
        else:
            b = q
    raise RuntimeError(f"no rational between {lo} and {hi} after {max_iter} iterations")


def certified_sort_and_merge(cross_items, max_refine=300):
    """Sort and dedupe crossing roots by EXACT rational isolating intervals.
    cross_items: list of dicts {poly, interval:(a,b), info} — each interval
    contains exactly one root of its poly.  Returns (sorted_merged, stats).
    Ordering: intervals are mutually disjoint after refinement (exact Sturm).
    SHARED-ROOT CORRECTNESS (FINAL_CORRECTNESS_CLOSURE): when two intervals
    overlap, an EXACT equality-possibility check (polynomial gcd + Sturm
    root-count on the overlap) runs BEFORE any refinement.  Identical algebraic
    roots are merged into one global transition point (contributing pairs are
    preserved) — refining can never separate two intervals of the SAME root,
    so equality must be decided first.  Different roots are then separated by
    certified interval refinement.  No float/evalf decides equality or order."""
    import sympy as _sp
    stats = {"refines": 0, "gcd_equal_checks": 0, "exact_fallback": 0,
             "close_pairs": 0, "sort_passes": 0}
    items = [dict(it) for it in cross_items]
    for it in items:
        it["info_list"] = [it["info"]]
    _l_sym = _sp.symbols("l")

    def _same_root(it_i, it_j):
        """Exact equality test on overlap of two intervals; returns True iff
        both isolate the SAME algebraic root."""
        a1, b1 = it_i["interval"]
        a2, b2 = it_j["interval"]
        lo, hi = max(a1, a2), min(b1, b2)
        g = _sp.gcd(it_i["poly"], it_j["poly"])
        if g == 1:
            return False
        gp = _sp.Poly(g, _l_sym)
        if lo == hi:
            return gp.eval(lo) == 0
        return _count_open(gp, lo, hi) == 1

    # sort-scan loop: on overlap, equality-check first (merge) else refine the
    # wider interval, until all intervals are mutually disjoint and sorted.
    while True:
        items.sort(key=lambda d: d["interval"])
        stats["sort_passes"] += 1
        refined_any = False
        for i in range(len(items) - 1):
            a1, b1 = items[i]["interval"]
            a2, b2 = items[i + 1]["interval"]
            if b1 < a2:
                continue
            if b1 == a2:
                # touching endpoints: separate intervals unless BOTH are the
                # same degenerate point (identical exact rational root), which
                # must go through the equality check below
                if not (a1 == b1 == a2 == b2):
                    continue
            # overlap: exact equality-possibility check BEFORE refinement
            stats["gcd_equal_checks"] += 1
            if _same_root(items[i], items[i + 1]):
                # identical algebraic root: merge, keep all contributing pairs
                lo = max(a1, a2)
                hi = min(b1, b2)
                items[i]["interval"] = (lo, hi)
                items[i]["info_list"].extend(items[i + 1]["info_list"])
                del items[i + 1]
                stats["exact_fallback"] += 1
                refined_any = True
                break
            # different roots: refine the wider interval (exact Sturm bisection)
            if (b1 - a1) >= (b2 - a2):
                a1, b1 = refine_interval(items[i]["poly"], a1, b1,
                                         max_iter=max_refine)
                items[i]["interval"] = (a1, b1)
            else:
                a2, b2 = refine_interval(items[i + 1]["poly"], a2, b2,
                                         max_iter=max_refine)
                items[i + 1]["interval"] = (a2, b2)
            stats["refines"] += 1
            refined_any = True
            if stats["refines"] > 10 * max_refine:
                raise RuntimeError("certified sorting did not converge")
            break
        if not refined_any:
            break
    for it in items:
        it["info"] = tuple(it["info_list"])
    return items, stats


def rational_between_iv(iv_lo, iv_hi):
    """Exact rational point strictly between two roots given by mutually
    disjoint isolating intervals; iv_lo/iv_hi = (a,b) tuple or None for the
    endpoints 0 / 1.  Returns an exact Fraction q."""
    if iv_lo is None and iv_hi is None:
        return Fraction(1, 2)            # whole interval (0,1), no transition roots
    if iv_lo is None:
        a2, b2 = iv_hi
        return a2 / 2                       # 0 < a2/2 < r2
    a1, b1 = iv_lo
    if iv_hi is None:
        return (b1 + 1) / 2                 # r1 < (b1+1)/2 < 1
    a2, b2 = iv_hi
    if not (b1 <= a2):
        raise RuntimeError(f"intervals not disjoint: {iv_lo} {iv_hi}")
    return (b1 + a2) / 2


def weak_ranking(poly, designs, lam):
    """Tie-aware weak ordering at lambda: returns list of tie groups (lists of designs),
    ordered by the metric value (best first). No artificial strict order inside a group."""
    vals = {d: eval_poly(poly[d], lam) for d in designs}
    groups = []
    for d in sorted(designs, key=lambda d: vals[d]):   # ordering only; ties merged below
        if groups and vals[d] == vals[groups[-1][0]]:
            groups[-1].append(d)
        else:
            groups.append([d])
    return groups


def family_regimes_from_polys(poly, designs, metric="MED"):
    """Core family analysis over a dict {design: metric-poly}.
    Transition semantics (FINAL_PRE_FORMAL_HOTFIX):
      - a ranking transition requires a CROSSING root (odd multiplicity);
      - touching roots (even multiplicity) are recorded in touching_points only:
        they do NOT increment transition_pairs, do NOT split stable regimes,
        and do NOT count as multi-flip;
      - endpoint roots (0/1) are recorded separately and are NOT regime boundaries.
    Ordering/dedup of roots: EXACT algebraic comparisons (no float in logic)."""
    t0 = time.time()

    pairs = list(itertools.combinations(designs, 2))
    transitions = {}     # (a,b) -> info (crossing roots only)
    touching = {}        # (a,b) -> touching roots (even multiplicity, interior)
    endpoint_roots = {}  # (a,b) -> endpoint roots (0/1)
    multi_flip = []
    n_transition_pairs = 0
    cross_items = []     # global crossing-root pool (for certified interval sort)
    import sympy as _sp
    _l = _sp.symbols("l")
    for a, b in pairs:
        n = max(len(poly[a]), len(poly[b]))
        d = trim([(poly[a][k] if k < len(poly[a]) else Z) - (poly[b][k] if k < len(poly[b]) else Z)
                  for k in range(n)])
        if all(c == 0 for c in d):
            transitions[(a, b)] = "identical"
            continue
        rinfo = exact_roots(d, materialize_root=False)
        if rinfo is None:
            continue
        cross = [dd for dd in rinfo if dd["endpoint"] is None and dd["crossing"]]
        touch = [dd for dd in rinfo if dd["endpoint"] is None and not dd["crossing"]]
        endp = [dd for dd in rinfo if dd["endpoint"] is not None]
        if endp:
            endpoint_roots[(a, b)] = [dd["endpoint"] for dd in endp]
        if touch:
            # RootOf materialization is intentionally disabled in formal family
            # analysis.  Preserve the certified interval for exact provenance;
            # decimal display is derived from its rational midpoint only.
            touching[(a, b)] = [(dd["root"], dd["mult"], dd["interval"]) for dd in touch]
        if cross:
            n_transition_pairs += 1
            transitions[(a, b)] = {
                "roots": [(dd["root"], dd["mult"]) for dd in cross],
                "endpoint_roots": [dd["endpoint"] for dd in endp],
            }
            if len(cross) > 1:
                multi_flip.append((a, b, len(cross)))
            d_poly = _sp.Poly.from_list(list(reversed(
                [_sp.Rational(c.numerator, c.denominator) for c in d])), _l)
            for dd in cross:
                cross_items.append({"poly": d_poly, "interval": dd["interval"],
                                    "info": (a, b, dd["mult"])})
    # certified global ordering/dedup of crossing roots via exact intervals
    merged, sort_stats = certified_sort_and_merge(cross_items)
    distinct = merged

    # ranking per adjacent interval; interior point from disjoint intervals
    regimes = []
    ivs = [None] + [m["interval"] for m in distinct] + [None]
    for i in range(len(ivs) - 1):
        lam = rational_between_iv(ivs[i], ivs[i + 1])
        groups = weak_ranking(poly, designs, lam)
        lo_s = "0" if ivs[i] is None else str((ivs[i][0] + ivs[i][1]) / 2)
        hi_s = "1" if ivs[i + 1] is None else str((ivs[i + 1][0] + ivs[i + 1][1]) / 2)
        regimes.append({"interval": [lo_s, hi_s],
                        "test_lambda": str(lam), "ranking": groups,
                        "n_tie_groups": len(groups)})
    return {
        "metric": metric, "n_designs": len(designs), "n_pairs": len(pairs),
        "n_transition_pairs": n_transition_pairs,
        "n_distinct_transition_points": len(distinct),
        "distinct_transition_points": [
            str((m["interval"][0] + m["interval"][1]) / 2) for m in distinct],
        "distinct_transition_info": [
            {"point": str((m["interval"][0] + m["interval"][1]) / 2),
             "contributing_pairs": [list(inf) for inf in m["info"]]}
            for m in distinct],
        "sort_stats": sort_stats,
        "touching_points": {
            f"{a}|{b}": [[
                str(r.evalf(30)) if r is not None else
                str(_sp.N(_sp.Rational((iv[0] + iv[1]).numerator,
                                      (iv[0] + iv[1]).denominator) / 2, 30)),
                m
            ] for r, m, iv in roots]
            for (a, b), roots in touching.items()
        },
        "n_touching_points": sum(len(v) for v in touching.values()),
        "endpoint_roots": {f"{a}|{b}": v for (a, b), v in endpoint_roots.items()},
        "multi_flip_pairs": multi_flip,
        "n_stable_intervals": len(regimes),
        "regimes": regimes,
        "t_total_s": round(time.time() - t0, 2),
    }


def family_regimes(p0, p1, bucket_fn, metric="MED", designs=DESIGNS):
    """All-pair Delta roots on one path -> merged sorted transition points -> full rankings.
    Computes per-design polynomials from the d-DNNF bank, then delegates to
    family_regimes_from_polys."""
    t0 = time.time()
    poly = {}
    for d in designs:
        er, med = nnf_metric_polys(d, p0, p1)
        poly[d] = med if metric == "MED" else er
    t_eval = time.time() - t0
    res = family_regimes_from_polys(poly, designs, metric=metric)
    res["t_eval_s"] = round(t_eval, 2)
    return res


def main():
    report = {"title": "THEORY_FEASIBILITY_ROUND_2", "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
              "results": {}}
    p0 = [Fraction(1, 2)] * N
    p1_D1 = [Fraction(1, 4)] * N

    # ---- task 3: main pair D0->D1, exhaustive 1-group bucket ------------
    bucket1 = lambda f: exhaustive_buckets(None, f, 24)  # noqa: E731
    t = time.time()
    r3, _, _ = compare_pair("add12u_4R6", "add12u_4YR", p0, p1_D1, bucket1, "task3 D0->D1")
    r3["t_total_s"] = round(time.time() - t, 2)
    report["results"]["task3_main_D0toD1"] = r3
    print("[task3] Delta_ER coeff match:", r3["Delta_ER_coeff_match"],
          "Delta_MED coeff match:", r3["Delta_MED_coeff_match"],
          "roots:", r3.get("Delta_MED_roots"))

    # ---- task 4a: D0->D3 alternating (2-group interleave exhaustive cross-check) ----
    p1_D3 = dist_vector("D3")
    # locate potential transitions in data first: 12-bit MED D0->D3 has 0 strict inversions
    med = read_metric_csv("formal_med_results.csv")
    oref, oalt, invs = locate_inversions(med, "12", "MED", "D0", "D3")
    print("[task4a] 12-bit MED D0->D3 strict inversions:", len(invs))
    # NNF scan of all pairs for internal roots (double-crossing) on D0->D3
    poly = {}
    for d in DESIGNS:
        er, medp = nnf_metric_polys(d, p0, p1_D3)
        poly[d] = medp
    d3_transitions = []
    for a, b in itertools.combinations(DESIGNS, 2):
        n = max(len(poly[a]), len(poly[b]))
        d = trim([(poly[a][k] if k < len(poly[a]) else Z) - (poly[b][k] if k < len(poly[b]) else Z)
                  for k in range(n)])
        if all(c == 0 for c in d):
            continue
        rr = roots_in_unit(d)
        if rr:
            d3_transitions.append({"pair": (a, b), "roots": [[str(r.evalf(30)), m] for r, m in rr]})
    report["results"]["task4a_D0toD3"] = {
        "n_strict_inversions_endpoints": len(invs),
        "pairs_with_internal_roots": d3_transitions,
    }
    print("[task4a] D0->D3 pairs with internal Delta roots:", len(d3_transitions))
    for t_ in d3_transitions[:6]:
        print("   ", t_["pair"], t_["roots"])

    # ---- task 4b: R_i->R_j random path ------------------------------------
    # NOTE (recorded limitation): authoritative v2 R0-R9 ER values could NOT be
    # reproduced from frozen random_dists + any structured PI-order hypothesis
    # (8 orderings x 5 stream slices x 4 seeds tested; D0-D5 all match, so the
    # circuit semantics are correct; the VACSEM miter BLIF .inputs order is not
    # available in TARGET and copying from the legacy project is forbidden).
    # We therefore define the random path with the frozen random_dists(seed=42,
    # n=24) stream (identical to the frozen c5_common implementation) and verify
    # the NNF polynomials against single-point exhaustive evaluation (self-
    # consistent closed loop, independent of the authoritative R tables).
    # load the FROZEN semantic random distributions (read-only file)
    fp = OUT / "frozen_random_dists.json"
    if not fp.exists():
        raise SystemExit("frozen_random_dists.json missing; run: python tp_freeze_dists.py")
    _frozen = json.loads(fp.read_text(encoding="utf-8"))
    pa = [Fraction(x) for x in _frozen["dists"]["R_new0"]]
    pb = [Fraction(x) for x in _frozen["dists"]["R_new1"]]
    # find a transition pair on this path via NNF scan
    poly_r = {}
    for d in DESIGNS:
        e, _ = nnf_metric_polys(d, pa, pb)
        poly_r[d] = e
    rpairs = []
    for a, b in itertools.combinations(DESIGNS, 2):
        n = max(len(poly_r[a]), len(poly_r[b]))
        d = trim([(poly_r[a][k] if k < len(poly_r[a]) else Z) -
                  (poly_r[b][k] if k < len(poly_r[b]) else Z) for k in range(n)])
        if all(c == 0 for c in d):
            continue
        rr = roots_in_unit(d)
        if rr:
            s0, _ = sign_at(d, Z); s1, _ = sign_at(d, ONE)
            rpairs.append({"pair": (a, b), "deg": len(d) - 1,
                           "roots": [[str(r.evalf(30)), m] for r, m in rr],
                           "signs": [s0, s1],
                           "flip": (s0 != 0 and s1 != 0 and s0 != s1)})
    report["results"]["task4b_random"] = {
        "endpoints": "R_new0->R_new1 from frozen_random_dists.json (frozen semantic)",
        "note": "authoritative R tables not reproducible (PI-order asset gap); "
                "semantic-mapping exhaustive vs NNF verification in tp2_verify_results.json",
        "n_transition_pairs": len(rpairs),
        "transition_pairs": rpairs[:6],
    }
    print("[task4b] R0->R1 transition pairs:", len(rpairs), "xcheck matches:",
          "see tp2_verify_results.json")

    # ---- task 5: family D0->D1 MED regimes --------------------------------
    t = time.time()
    fam = family_regimes(p0, p1_D1, bucket1, metric="MED")
    fam["t_total_s"] = round(time.time() - t, 2)
    report["results"]["task5_family_D0toD1_MED"] = fam
    print("[task5] pairs:", fam["n_pairs"], "transition pairs:", fam["n_transition_pairs"],
          "distinct points:", fam["n_distinct_transition_points"],
          "intervals:", fam["n_stable_intervals"], "multi-flip:", fam["multi_flip_pairs"])

    (OUT / "tp2_round2_results.json").write_text(json.dumps(report, indent=2, default=str),
                                                 encoding="utf-8")
    print("saved tp2_round2_results.json")


if __name__ == "__main__":
    main()
