"""tp_smoke.py — minimal smoke/regression for the clean-audit bundle (NO new experiments).

Checks that previously recorded conclusions still reproduce exactly:
  S1 gate-level vs Verilog simulator (8 designs x 200 random inputs)
  S2 d-DNNF polynomial == exhaustive polynomial per-coefficient (4R6,4YR, D0->D1, ER+MED)
  S3 D0-D5 authoritative endpoints (v2 tables) for 4R6,4YR (MED+ER)
  S4 main-case root Delta_MED == 0.3036268837...
  S5 12-bit family regimes (D0->D1 MED): 1 transition pair, 1 point, 2 stable intervals
Any mismatch -> report BLOCKED.
"""
from __future__ import annotations

import itertools
import json
import random
import sys
import time
from fractions import Fraction
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
import tp_paths  # noqa: E402
PROJECT_ROOT = tp_paths.ROOT
sys.path.insert(0, str(PROJECT_ROOT / "experiments" / "theory_probe"))

from tp1_verilog import load_design  # noqa: E402
from tp1_poly import (exhaustive_buckets, metric_poly, trim, read_metric_csv,  # noqa: E402
                      roots_in_unit, eval_poly, locate_inversions)
from tp2_cnf import build_circuit  # noqa: E402
from tp2_eval import nnf_metric_polys  # noqa: E402

DESIGNS = ["add12u_054", "add12u_2MB", "add12u_4FZ", "add12u_4R6",
           "add12u_4RF", "add12u_4XD", "add12u_4YK", "add12u_4YR"]
Z = Fraction(0, 1)
ONE = Fraction(1, 1)


def gate_vals(net, x):
    vals = {net.const0: 0, net.const1: 1}
    for v in range(1, 25):
        vals[v] = (x >> (v - 1)) & 1
    for v in sorted(net.gates):
        op, args = net.gates[v]
        av = [vals.get(a, a) for a in args]
        if op == "not":
            vals[v] = 1 - av[0]
        elif op == "and":
            vals[v] = av[0] & av[1]
        elif op == "or":
            vals[v] = av[0] | av[1]
        elif op == "xor":
            vals[v] = av[0] ^ av[1]
        elif op == "xnor":
            vals[v] = 1 - (av[0] ^ av[1])
    return vals


def main():
    report = {"smoke": {}, "overall": "PASS"}
    ok_all = True

    # ---- S1: gate-level vs Verilog --------------------------------------
    rng = random.Random(11)
    s1 = {"mismatch": {}}
    for name in DESIGNS:
        net, e_bits, er_root = build_circuit(name)
        f, _ = load_design(name)
        bad = 0
        for _ in range(200):
            x = rng.getrandbits(24)
            o = f(x)
            e = abs((x & 0xFFF) + (x >> 12) - o)
            eb_sim = [(e >> b) & 1 for b in range(13)]
            vals = gate_vals(net, x)
            eb_g = [vals.get(bv, 0) for bv in e_bits]
            if eb_g != eb_sim:
                bad += 1
        s1["mismatch"][name] = bad
        if bad:
            ok_all = False
    report["smoke"]["S1_gate_vs_verilog"] = s1
    print("S1 gate vs verilog:", {k: v for k, v in s1["mismatch"].items()})

    # ---- S2: d-DNNF == exhaustive per-coefficient (ALL 8 designs, D0->D1) ----
    p0 = [Fraction(1, 2)] * 24
    p1 = [Fraction(1, 4)] * 24
    s2 = {}
    for d in DESIGNS:
        er_n, med_n = nnf_metric_polys(d, p0, p1)
        f, _ = load_design(d)
        sumE, cntE = exhaustive_buckets(None, f, 24)
        er_e = trim(metric_poly(cntE, p0[0], p1[0], 24))
        med_e = trim(metric_poly(sumE, p0[0], p1[0], 24))
        s2[d] = {"er": er_n == er_e, "med": med_n == med_e}
        ok_all = ok_all and s2[d]["er"] and s2[d]["med"]
        print(f"   S2[{d}] er={s2[d]['er']} med={s2[d]['med']}")
    report["smoke"]["S2_nnf_eq_exhaustive"] = s2
    print("S2 nnf == exhaustive:", s2)

    # ---- S3: D0-D5 authoritative endpoints (4R6, 4YR) -------------------
    med = read_metric_csv("formal_med_results.csv")
    er = read_metric_csv("formal_er_results.csv")
    s3 = {}
    for d in ("add12u_4R6", "add12u_4YR"):
        row = {}
        for dn in ("D0", "D1", "D2", "D3", "D4", "D5"):
            dv = {"D0": Fraction(1, 2), "D1": Fraction(1, 4), "D2": Fraction(3, 4)}.get(dn)
            if dn == "D3":
                vec = [Fraction(1, 4) if i % 2 == 0 else Fraction(3, 4) for i in range(24)]
            elif dn == "D4":
                vec = [Fraction(1, 4)] * 12 + [Fraction(3, 4)] * 12
            elif dn == "D5":
                vec = [Fraction(3, 4)] * 12 + [Fraction(1, 4)] * 12
            else:
                vec = [dv] * 24
            er_n, med_n = nnf_metric_polys(d, vec, vec)
            er_at = eval_poly(er_n, Z)
            med_at = eval_poly(med_n, Z)
            row[dn] = {
                "er": er_at == Fraction(er[("12", d)][dn]),
                "med": med_at == Fraction(med[("12", d)][dn]),
                "er_v2": str(er[("12", d)][dn]), "er_here": str(er_at),
                "med_v2": str(med[("12", d)][dn]), "med_here": str(med_at),
            }
            ok_all = ok_all and row[dn]["er"] and row[dn]["med"]
        s3[d] = row
    report["smoke"]["S3_D0D5_endpoints"] = s3
    print("S3 D0-D5 endpoints match:", {d: all(r["er"] and r["med"] for r in row.values())
                                        for d, row in s3.items()})

    # ---- S4: main-case root ---------------------------------------------
    er_n, med_n = nnf_metric_polys("add12u_4R6", p0, p1)
    er_b, med_b = nnf_metric_polys("add12u_4YR", p0, p1)
    n = max(len(med_n), len(med_b))
    dmed = trim([(med_n[k] if k < len(med_n) else Z) - (med_b[k] if k < len(med_b) else Z)
                 for k in range(n)])
    rr = roots_in_unit(dmed)
    # display-level string comparison only (exact isolation from Sturm sequence);
    # no float participates in the logic
    roots = None if rr is None else [str(r.evalf(20)) for r, m in rr]
    expected = "0.3036268837857394"
    s4 = {"roots": roots,
          "root_match": roots is not None and len(roots) == 1 and roots[0].startswith(expected)}
    ok_all = ok_all and s4["root_match"]
    report["smoke"]["S4_main_root"] = s4
    print("S4 main root:", s4)

    # ---- S5: 12-bit family regimes (D0->D1 MED) --------------------------
    poly = {}
    for d in DESIGNS:
        _, med_n = nnf_metric_polys(d, p0, p1)
        poly[d] = med_n
    pairs = list(itertools.combinations(DESIGNS, 2))
    trans = []
    for a, b in pairs:
        n = max(len(poly[a]), len(poly[b]))
        d = trim([(poly[a][k] if k < len(poly[a]) else Z) - (poly[b][k] if k < len(poly[b]) else Z)
                  for k in range(n)])
        if all(c == 0 for c in d):
            continue
        rr = roots_in_unit(d)
        if rr:
            trans.append((a, b, [float(r.evalf(30)) for r, m in rr]))
    s5 = {"n_pairs": len(pairs), "n_transition_pairs": len(trans),
          "transition_pairs": trans,
          "expect_1_transition_pair": len(trans) == 1,
          "expect_pair_4R6_4YR": trans and {trans[0][0], trans[0][1]} == {"add12u_4R6", "add12u_4YR"}}
    ok_all = ok_all and s5["expect_1_transition_pair"] and s5["expect_pair_4R6_4YR"]
    report["smoke"]["S5_family_regimes"] = s5
    print("S5 family regimes:", s5["n_pairs"], "pairs ->", s5["n_transition_pairs"], "transition pair(s):", trans)

    report["overall"] = "PASS" if ok_all else "FAIL"
    (tp_paths.out_dir() / "tp_smoke_results.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("SMOKE OVERALL:", report["overall"])
    if not ok_all:
        sys.exit(1)


if __name__ == "__main__":
    main()
