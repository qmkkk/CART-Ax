"""tp_synth_tests.py — synthetic unit tests for the EXACT root/regime machinery.

Covered cases (no circuits involved; pure polynomial level):
  T1 endpoint roots: Delta = l*(l-1)*(l-1/2)   -> roots at 0 (endpoint), 1 (endpoint), 1/2 (interior)
  T2 touching (double) root: Delta = (l-1/3)^2*(l-2/3) -> 1/3 mult 2 (touching), 2/3 mult 1 (crossing)
  T3 outside roots filtered exactly: Delta = (l-2)*(l+1)*(l-1/2) -> only 1/2 inside
  T4 tie-aware weak ranking: two designs with identical metric values -> one tie group
  T5 rational interior point strictly between adjacent algebraic roots (exact)
"""
from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tp_paths  # noqa: E402
import sympy as sp  # noqa: E402
from tp1_poly import exact_roots, roots_in_unit, eval_poly  # noqa: E402
from tp2_round2 import (rational_between, weak_ranking, family_regimes_from_polys,
                        certified_sort_and_merge)  # noqa: E402
from tp1_poly import isolate_intervals, _count_open  # noqa: E402

Z = Fraction(0, 1)
ONE = Fraction(1, 1)
L = "l"


def coeffs_from_factors(factors):
    """Ascending coefficient list of the product of (l - r) / (l - r)^k factors.
    factors: list of (Fraction root, int power)."""
    poly = [ONE]
    for r, p in factors:
        lin = [-r, ONE]  # l - r  (ascending)
        for _ in range(p):
            out = [Z] * (len(poly) + 1)
            for i, a in enumerate(poly):
                out[i] += a * lin[0]
                out[i + 1] += a * lin[1]
            poly = out
    return poly


def run():
    res = {}
    ok_all = True

    # T1 endpoint roots
    d1 = coeffs_from_factors([(Z, 1), (ONE, 1), (Fraction(1, 2), 1)])
    r1 = exact_roots(d1)
    t1 = {"roots": [{"v": str(r["root"].evalf(30)), "mult": r["mult"],
                     "endpoint": r["endpoint"], "crossing": r["crossing"]} for r in r1],
          "interior": [str(r.evalf(30)) for r, _ in roots_in_unit(d1)]}
    t1["pass"] = (len(r1) == 3 and
                  {r["endpoint"] for r in r1} == {"0", "1", None} and
                  len(roots_in_unit(d1)) == 1 and
                  roots_in_unit(d1)[0][0] == sp.Rational(1, 2))   # exact equality
    ok_all = ok_all and t1["pass"]
    res["T1_endpoint_roots"] = t1
    print("T1 endpoint roots:", t1["pass"], t1["interior"])

    # T2 touching double root
    d2 = coeffs_from_factors([(Fraction(1, 3), 2), (Fraction(2, 3), 1)])
    r2 = exact_roots(d2)
    t2 = {}
    for r in r2:
        if r["root"] == sp.Rational(1, 3):
            t2["r13"] = {"mult": r["mult"], "crossing": r["crossing"], "endpoint": r["endpoint"]}
        if r["root"] == sp.Rational(2, 3):
            t2["r23"] = {"mult": r["mult"], "crossing": r["crossing"], "endpoint": r["endpoint"]}
    t2["pass"] = (t2.get("r13", {}).get("mult") == 2 and
                  t2.get("r13", {}).get("crossing") is False and
                  t2.get("r23", {}).get("mult") == 1 and
                  t2.get("r23", {}).get("crossing") is True)
    ok_all = ok_all and t2["pass"]
    res["T2_touching_double"] = t2
    print("T2 touching/double:", t2["pass"], t2)

    # T3 outside roots filtered exactly
    d3 = coeffs_from_factors([(Fraction(2), 1), (Fraction(-1), 1), (Fraction(1, 2), 1)])
    r3 = exact_roots(d3)
    in3 = roots_in_unit(d3)
    t3 = {"n_roots_in_unit_or_endpoint": len(r3), "n_interior": len(in3),
          "interior": [str(r.evalf(30)) for r, _ in in3]}
    t3["pass"] = (len(r3) == 1 and len(in3) == 1 and
                  in3[0][0] == sp.Rational(1, 2))                  # exact equality
    ok_all = ok_all and t3["pass"]
    res["T3_outside_filtered"] = t3
    print("T3 outside filtered:", t3["pass"], t3["interior"])

    # T4 tie-aware weak ranking
    lam = Fraction(1, 3)
    base = coeffs_from_factors([(Fraction(1, 4), 1), (Fraction(3, 4), 1)])
    poly = {"a": base, "b": base[:], "c": coeffs_from_factors([(Fraction(1, 5), 1), (Fraction(4, 5), 1)])}
    groups = weak_ranking(poly, ["a", "b", "c"], lam)
    t4 = {"groups": [[g for g in grp] for grp in groups]}
    t4["pass"] = (len(groups) == 2 and set(groups[-1]) == {"a", "b"})
    ok_all = ok_all and t4["pass"]
    res["T4_tie_groups"] = t4
    print("T4 tie groups:", t4["pass"], t4["groups"])

    # T5 exact rational interior point between adjacent algebraic roots
    # roots of d2: 1/3 and 2/3; also test with irrational roots
    q1 = rational_between(Fraction(1, 3), Fraction(2, 3))
    t5a = {"q": str(q1), "strict": Fraction(1, 3) < q1 < Fraction(2, 3)}
    ok_all = ok_all and t5a["strict"]
    # irrational case: roots of l^3 - 2l + 1 in (0,1): r = (-1+sqrt5)/2 ~ 0.618
    x = sp.symbols("x")
    rr = sorted([r for r in sp.Poly(x ** 3 - 2 * x + 1, x).real_roots() if r > 0 and r < 1])
    q2 = rational_between(Z, rr[0])
    q3 = rational_between(rr[0], ONE)
    t5b = {"q_below": str(q2), "q_above": str(q3),
           "strict_below": Z < q2 < rr[0], "strict_above": rr[0] < q3 < ONE}
    ok_all = ok_all and t5b["strict_below"] and t5b["strict_above"]
    res["T5_rational_interior"] = {"rational_case": t5a, "irrational_case": t5b}
    print("T5 rational interior:", t5a["strict"], t5b["strict_below"], t5b["strict_above"])

    # T6 integration: two synthetic designs with Delta(lambda) = (lambda - 1/3)^2
    # M_A = (l-1/3)^2 + 1 = l^2 - (2/3)l + 10/9 ; M_B = 1  (ascending coeffs)
    M_A = [Fraction(10, 9), Fraction(-2, 3), ONE]
    M_B = [ONE]
    fam = family_regimes_from_polys({"a": M_A, "b": M_B}, ["a", "b"], metric="MED")
    t6 = {
        "n_transition_pairs": fam["n_transition_pairs"],
        "n_distinct_transition_points": fam["n_distinct_transition_points"],
        "n_touching_points": fam["n_touching_points"],
        "touching_points": fam["touching_points"],
        "n_stable_intervals": fam["n_stable_intervals"],
        "multi_flip_pairs": fam["multi_flip_pairs"],
        "endpoint_roots": fam["endpoint_roots"],
    }
    # exact assertions on the touching root (re-derive from exact_roots)
    touch_root_ok = False
    touch_mult_ok = False
    touch_cross_ok = False
    # Delta = M_A - M_B = (l - 1/3)^2 = [1/9, -2/3, 1]
    rinfo = exact_roots([M_A[0] - M_B[0], M_A[1], M_A[2]])
    for dd in rinfo:
        if dd["root"] == sp.Rational(1, 3):
            touch_root_ok = True
            touch_mult_ok = (dd["mult"] == 2)
            touch_cross_ok = (dd["crossing"] is False)
    t6["touching_root_exact"] = {"found": touch_root_ok, "mult2": touch_mult_ok,
                                 "crossing_false": touch_cross_ok}
    t6["pass"] = (touch_root_ok and touch_mult_ok and touch_cross_ok and
                  fam["n_transition_pairs"] == 0 and
                  fam["n_distinct_transition_points"] == 0 and
                  fam["n_touching_points"] == 1 and
                  fam["n_stable_intervals"] == 1 and
                  fam["multi_flip_pairs"] == [] and fam["endpoint_roots"] == {})
    ok_all = ok_all and t6["pass"]
    res["T6_touching_integration"] = t6
    print("T6 touching integration:", t6["pass"], "| transition_pairs", fam["n_transition_pairs"],
          "| touching_points", fam["n_touching_points"], "| intervals", fam["n_stable_intervals"])

    # T7: certified sorting of roots from DIFFERENT degree>10 polynomials
    x = sp.symbols("x")
    def mkpoly(r, d):
        return sp.Poly((x - sp.Rational(r)) * (x ** d + 1), x)
    polys = {
        "p1": mkpoly(Fraction(1, 7), 11),
        "p2": mkpoly(Fraction(1, 3), 13),
        "p3": mkpoly(Fraction(5, 9), 11),
        "p4": mkpoly(Fraction(3, 4), 12),
        "p5": sp.Poly((x - sp.Rational(2, 5)) * (x ** 13 + x ** 3 - 1), x),  # + irrational root
    }
    items = []
    known = []
    for name, pl in polys.items():
        ivs, _ = isolate_intervals(pl)
        for (a, b) in ivs:
            items.append({"poly": pl, "interval": (a, b), "info": name})
            known.append((name, a, b))
    merged, stats = certified_sort_and_merge(items)
    # ground truth: order by exact midpoint containment of rational roots and
    # by the irrational root position (0.9 < r* < 1 from f(0.9)<0<f(0.95))
    def root_of(item):
        a, b = item["interval"]
        # exact: which known poly has a root in the CLOSED interval [a, b]
        for name, pl in polys.items():
            if _count_open(pl, a, b) == 1 or pl.eval(a) == 0 or pl.eval(b) == 0:
                return name
        return "?"
    order = [root_of(m) for m in merged]
    # sequence of roots: 1/7(p1) < 1/3(p2) < 2/5(p5) < 5/9(p3) < 3/4(p4) < r*(p5)
    # where r* ~ 0.93 is the (0,1) root of x^13 + x^3 - 1 (f(0.9)<0<f(0.95))
    expected = ["p1", "p2", "p5", "p3", "p4", "p5"]
    t7 = {"order": order, "expected": expected, "stats": stats,
          "intervals_disjoint": all(
              merged[i]["interval"][1] <= merged[i + 1]["interval"][0]
              for i in range(len(merged) - 1))}
    t7["pass"] = (order == expected and t7["intervals_disjoint"])
    ok_all = ok_all and t7["pass"]
    res["T7_certified_sort_multi_poly"] = t7
    print("T7 certified sort:", t7["pass"], order)

    # T8: two numerically-close but distinct algebraic roots, overlapping initial
    # intervals, separated by refinement (no float tolerance)
    pa = sp.Poly((x - sp.Rational(499, 1000)) * (x ** 3 - 2), x)
    pb = sp.Poly((x - sp.Rational(501, 1000)) * (x ** 3 - 2), x)
    # deliberately WIDE overlapping initial intervals (0,1) for both polynomials
    # (each contains exactly one root in (0,1)) — refinement must separate them
    items8 = [{"poly": pa, "interval": (Fraction(0), Fraction(1)), "info": "a"},
              {"poly": pb, "interval": (Fraction(0), Fraction(1)), "info": "b"}]
    init_overlap = True
    m8, s8 = certified_sort_and_merge(items8)
    a_iv = m8[0]["interval"]; b_iv = m8[1]["interval"]
    t8 = {"init_intervals": ["(0, 1)", "(0, 1)"],
          "init_overlap": init_overlap,
          "final_intervals": [tuple(str(v) for v in iv) for iv in (a_iv, b_iv)],
          "disjoint": a_iv[1] <= b_iv[0],
          "order_correct": Fraction(499, 1000) < Fraction(501, 1000) and
                           a_iv[0] < Fraction(499, 1000) < a_iv[1] and
                           b_iv[0] < Fraction(501, 1000) < b_iv[1],
          "stats": s8}
    t8["pass"] = init_overlap and t8["disjoint"] and t8["order_correct"]
    ok_all = ok_all and t8["pass"]
    res["T8_close_roots_refine"] = t8
    print("T8 close roots:", t8["pass"], "| overlap:", init_overlap, "| disjoint:", t8["disjoint"])

    # T9: real 64-bit slow-pair performance regression (exact semantics)
    # Input: saved real delta (10_add64 vs 7_add64, D0D3 ER, deg 96) whose
    # whole-polynomial Poly.intervals took >120s before the factor-level
    # early-exit fix (no roots in (0,1)); must now finish fast with 0 roots.
    import json as _json
    from pathlib import Path as _P
    import time as _time
    from tp1_poly import exact_roots as _er
    _f = _P(__file__).resolve().parent / "t9_slow_pair.json"
    t9 = {"input": str(_f.name), "present": _f.exists()}
    if _f.exists():
        _data = _json.loads(_f.read_text(encoding="utf-8"))
        _coeffs = [Fraction(x) for x in _data["delta_coeffs_asc"]]
        _t0 = _time.time()
        _r = _er(_coeffs, materialize_root=False)
        _dt = _time.time() - _t0
        t9["runtime_s"] = round(_dt, 3)
        t9["n_roots"] = len(_r)
        # CORRECTNESS is the hard pass condition; timing is recorded as
        # performance-regression information only (machine-dependent, must not
        # fail correctness tests on slow hardware).  Warning threshold kept as
        # a diagnostic field, not a pass condition.
        t9["pass"] = (len(_r) == 0)
        t9["timing_warning"] = _dt > 60.0
        t9["timing_note"] = ("performance only; correctness = root count/classification. "
                             "Before fix this input took >120s (whole-poly Poly.intervals).")
        print(f"T9 slow-pair regression: {_dt:.3f}s roots={len(_r)} "
              f"(before fix >120s)", flush=True)
    else:
        t9["pass"] = False
    ok_all = ok_all and t9["pass"]
    res["T9_64bit_slow_pair"] = t9

    # T10: shared RATIONAL crossing root across ALL pairs (clean construction)
    # Delta_ab = (l-1/2)(l^2+1)   (only root in (0,1) is 1/2; l^2+1 no real roots)
    # Delta_ac = (l-1/2)(l^2+2)
    # Delta_bc = Delta_ac - Delta_ab = l - 1/2
    # -> all three pairs cross at the SAME root 1/2; must merge to ONE point
    # with 3 contributing pairs.
    p1 = [Fraction(-1, 2), Fraction(1), Fraction(-1, 2), Fraction(1)]   # asc: (l-1/2)(l^2+1)
    p2 = [Fraction(-1), Fraction(2), Fraction(-1, 2), Fraction(1)]      # asc: (l-1/2)(l^2+2)
    fam10 = family_regimes_from_polys({"a": [Z], "b": p1, "c": p2},
                                      ["a", "b", "c"], metric="MED")
    info10 = fam10["distinct_transition_info"]
    shared = [d for d in info10 if str(Fraction(1, 2)) == d["point"]]
    t10 = {
        "n_transition_pairs": fam10["n_transition_pairs"],
        "n_distinct": fam10["n_distinct_transition_points"],
        "points": fam10["distinct_transition_points"],
        "shared_point_entries": shared,
        "n_stable_intervals": fam10["n_stable_intervals"],
    }
    # expected: 3 transition pairs, exactly 1 distinct point (1/2),
    # 3 contributing pairs, 2 stable intervals (no duplicated boundary)
    t10["pass"] = (fam10["n_transition_pairs"] == 3 and
                   fam10["n_distinct_transition_points"] == 1 and
                   len(shared) == 1 and
                   len(shared[0]["contributing_pairs"]) == 3 and
                   fam10["n_stable_intervals"] == 2)
    ok_all = ok_all and t10["pass"]
    res["T10_shared_rational_root"] = t10
    print("T10 shared rational root:", t10["pass"],
          "| distinct:", t10["n_distinct"], "| shared contrib:",
          len(shared[0]["contributing_pairs"]) if shared else 0, flush=True)

    # T11: shared IRRATIONAL crossing root (irreducible factor x^2 + x - 1,
    # root r* = (sqrt(5)-1)/2 ~ 0.618 inside (0,1)) shared by ALL pairs:
    # Delta_ab = (x-1/3)(x^2+x-1) ; Delta_ac = (x-2/3)(x^2+x-1)
    # Delta_bc = (x^2+x-1)/3 -> only r*
    x = sp.symbols("x")
    irr = x ** 2 + x - 1
    q1 = sp.Poly((x - sp.Rational(1, 3)) * irr, x)
    q2 = sp.Poly((x - sp.Rational(2, 3)) * irr, x)
    q1c = [Fraction(int(c.p), int(c.q)) for c in q1.all_coeffs()][::-1]
    q2c = [Fraction(int(c.p), int(c.q)) for c in q2.all_coeffs()][::-1]
    q3c = [Fraction(int(c.p), int(c.q)) for c in sp.Poly(irr / 3, x).all_coeffs()][::-1]
    fam11 = family_regimes_from_polys({"a": [Z], "b": q1c, "c": q2c},
                                      ["a", "b", "c"], metric="MED")
    info11 = fam11["distinct_transition_info"]
    # the shared irrational root must appear exactly once, with 2 contributors
    t11 = {
        "n_transition_pairs": fam11["n_transition_pairs"],
        "n_distinct": fam11["n_distinct_transition_points"],
        "points": fam11["distinct_transition_points"],
        "contrib_counts": [len(d["contributing_pairs"]) for d in info11],
        "n_stable_intervals": fam11["n_stable_intervals"],
        "sort_stats": fam11["sort_stats"],
    }
    # distinct = {1/3, r*, 2/3} = 3, one entry with 2 contributors (r*),
    # no RuntimeError (no infinite refinement), intervals = 4
    t11["pass"] = (fam11["n_transition_pairs"] == 3 and
                   fam11["n_distinct_transition_points"] == 3 and
                   sorted(t11["contrib_counts"]) == [1, 1, 3] and
                   fam11["n_stable_intervals"] == 4)
    ok_all = ok_all and t11["pass"]
    res["T11_shared_irrational_root"] = t11
    print("T11 shared irrational root:", t11["pass"],
          "| distinct:", t11["n_distinct"],
          "| contrib:", t11["contrib_counts"], flush=True)

    res["overall"] = "PASS" if ok_all else "FAIL"
    out = tp_paths.out_dir() / "tp_synth_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print("SYNTH OVERALL:", res["overall"], "->", out)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(run())
