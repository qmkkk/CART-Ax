"""tp2_verify.py — semantic-mapping correctness verification (ROUND_2).

Uses pi_map.json (frozen) to assign probabilities by semantic input A[i]/B[i].
For each distribution endpoint pair, per-design:
  A) Verilog exhaustive direct evaluation (bucket / single-point integer-scaled)
  B) d-DNNF polynomial evaluation (tp2_eval)
requires EXACT rational equality, per-coefficient where bucketing applies, or at
single lambda points for fully-asymmetric paths.

Matrix: designs x {D0, D3, D4, R_new} x {ER, MED}; >=2 designs, 3 asymmetric dists.
"""
from __future__ import annotations

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

from tp1_poly import (exhaustive_buckets, exhaustive_buckets_2g, metric_poly,
                      trim, eval_poly, conv, binom_poly)  # noqa: E402
from tp2_eval import nnf_metric_polys, eval_nnf_poly  # noqa: E402
from tp1_verilog import load_design  # noqa: E402

OUT = tp_paths.out_dir()
N = 24
Z = Fraction(0, 1)
ONE = Fraction(1, 1)

PI_MAP = json.loads((OUT / "pi_map.json").read_text(encoding="utf-8"))["pi_map"]
# pi_map: DIMACS var (str) -> 'A[i]'/'B[i]'.  In the packed input x: A[i] = bit i, B[i] = bit 12+i.
assert PI_MAP["1"] == "A[0]" and PI_MAP["12"] == "A[11]" and PI_MAP["13"] == "B[0]"


def dist_vector(name, n=24):
    """Per-semantic-PI vectors (var order 1..24 = A[0..11], B[0..11])."""
    if name == "D0":
        return [Fraction(1, 2)] * n
    if name == "D1":
        return [Fraction(1, 4)] * n
    if name == "D2":
        return [Fraction(3, 4)] * n
    if name == "D3":
        return [Fraction(1, 4) if i % 2 == 0 else Fraction(3, 4) for i in range(n)]
    if name == "D4":
        return [Fraction(1, 4) if i < n // 2 else Fraction(3, 4) for i in range(n)]
    if name == "D5":
        return [Fraction(3, 4) if i < n // 2 else Fraction(1, 4) for i in range(n)]
    raise KeyError(name)


def bucket_poly_2g(buckets, val_idx, p0a, p1a, p0b, p1b, n1, n2):
    sumE, cntE = buckets
    poly = None
    for k, w in enumerate(sumE if val_idx == 0 else cntE):
        if not w:
            continue
        j1 = k // (n2 + 1)
        j2 = k % (n2 + 1)
        bp = conv(binom_poly(p0a, p1a, j1, n1), binom_poly(p0b, p1b, j2, n2))
        if poly is None:
            poly = [Fraction(w) * x for x in bp]
        else:
            for kk in range(len(bp)):
                poly[kk] += Fraction(w) * bp[kk]
    return trim(poly or [Z])


def coeff_diff_pairs(pnnf, pex, cap=5):
    n = max(len(pnnf), len(pex))
    return [(i, str((pnnf[i] if i < len(pnnf) else Z) - (pex[i] if i < len(pex) else Z)))
            for i in range(n) if (pnnf[i] if i < len(pnnf) else Z) != (pex[i] if i < len(pex) else Z)][:cap]


def verify_2g(design, p0vec, p1vec, groups, label):
    """2-group bucketing cross-check (D3: even/odd PI; D4: A-half/B-half). Returns row."""
    row = {"design": design, "path": label}
    t = time.time()
    er_nnf, med_nnf = nnf_metric_polys(design, p0vec, p1vec)
    row["t_nnf_s"] = round(time.time() - t, 2)
    f, _ = load_design(design)
    if groups == "evenodd":
        buckets = exhaustive_buckets_2g(None, f, 12, 12, order="interleave")
        # g1 = even PI (A even + B even), g2 = odd PI; p0 all 1/2; p1: g1->1/4, g2->3/4 (D3)
        p0a = p0b = p0vec[0]
        p1a = p1vec[0]
        p1b = p1vec[1]
    else:  # "halfs": contig A-half vs B-half (D4)
        buckets = exhaustive_buckets_2g(None, f, 12, 12, order="contig")
        p0a = p0b = p0vec[0]
        p1a = p1vec[0]
        p1b = p1vec[12]
    er_ex = bucket_poly_2g(buckets, 1, p0a, p1a, p0b, p1b, 12, 12)
    med_ex = bucket_poly_2g(buckets, 0, p0a, p1a, p0b, p1b, 12, 12)
    row["er_coeff_match"] = (er_nnf == er_ex)
    row["med_coeff_match"] = (med_nnf == med_ex)
    row["er_deg"] = [len(er_nnf) - 1, len(er_ex) - 1]
    row["med_deg"] = [len(med_nnf) - 1, len(med_ex) - 1]
    if not row["er_coeff_match"]:
        row["er_diffs"] = coeff_diff_pairs(er_nnf, er_ex)
    if not row["med_coeff_match"]:
        row["med_diffs"] = coeff_diff_pairs(med_nnf, med_ex)
    row["t_total_s"] = round(time.time() - t, 2)
    return row


def verify_random_singlepoint(design, p0vec, p1vec, lam_list, label):
    """Fully asymmetric path: single-point exhaustive (integer-scaled) vs NNF poly."""
    row = {"design": design, "path": label}
    t = time.time()
    er_nnf, med_nnf = nnf_metric_polys(design, p0vec, p1vec)
    row["t_nnf_s"] = round(time.time() - t, 2)
    f, _ = load_design(design)
    # cache E(x) via one simulation pass, plus group by E to speed weighted sums
    t0 = time.time()
    err = [0] * (1 << 24)
    for x in range(1 << 24):
        o = f(x)
        err[x] = abs((x & 0xFFF) + (x >> 12) - o)
    row["t_sim_s"] = round(time.time() - t0, 2)
    for lam in lam_list:
        p = [p0vec[i] + lam * (p1vec[i] - p0vec[i]) for i in range(N)]
        # integer scaling: p_i = num_i / den, computed exactly then scaled
        lamden = lam.denominator
        den = 8 * lamden
        nums = []
        for i in range(N):
            p = p0vec[i] + lam * (p1vec[i] - p0vec[i])   # exact Fraction
            assert den % p.denominator == 0
            nums.append(p.numerator * (den // p.denominator))
        # w(x) = prod num_i / den^24 ; accumulate integer weighted sums
        totER = 0
        totMED = 0
        for x in range(1 << 24):
            if err[x]:
                w = 1
                xx = x
                for i in range(N):
                    if xx & 1:
                        w *= nums[i]
                    else:
                        w *= den - nums[i]
                    xx >>= 1
                totER += w
                totMED += err[x] * w
        scale = Fraction(1, den ** 24)
        er_ex = Fraction(totER) * scale
        med_ex = Fraction(totMED) * scale
        er_poly = eval_poly(er_nnf, lam)
        med_poly = eval_poly(med_nnf, lam)
        row[f"lam_{str(lam)}"] = {
            "er_ex": str(er_ex), "er_nnf": str(er_poly), "er_match": er_ex == er_poly,
            "med_ex": str(med_ex), "med_nnf": str(med_poly), "med_match": med_ex == med_poly,
        }
        print(f"   [{design}] lambda={lam}: ER match {er_ex == er_poly}, MED match {med_ex == med_poly}")
    row["t_total_s"] = round(time.time() - t, 2)
    return row


def main():
    designs = ["add12u_4R6", "add12u_4YK"]
    D0 = dist_vector("D0")
    D3 = dist_vector("D3")
    D4 = dist_vector("D4")
    # load the FROZEN semantic random distributions (read-only; generation is an
    # explicit standalone command: python tp_freeze_dists.py)
    fp = OUT / "frozen_random_dists.json"
    if not fp.exists():
        raise SystemExit("frozen_random_dists.json missing; run: python tp_freeze_dists.py")
    _frozen = json.loads(fp.read_text(encoding="utf-8"))
    R_new0 = [Fraction(x) for x in _frozen["dists"]["R_new0"]]
    R_new1 = [Fraction(x) for x in _frozen["dists"]["R_new1"]]

    report = {"title": "tp2_verify semantic-mapping correctness", "rows": []}
    # D3 and D4: per-coefficient 2-group cross-check (2 designs each)
    for d in designs:
        r1 = verify_2g(d, D0, D3, "evenodd", "D0->D3")
        r2 = verify_2g(d, D0, D4, "halfs", "D0->D4")
        report["rows"].extend([r1, r2])
        print(f"[{d}] D0->D3 ER match {r1['er_coeff_match']} MED match {r1['med_coeff_match']}"
              f" | D0->D4 ER match {r2['er_coeff_match']} MED match {r2['med_coeff_match']}")
    # D0 (uniform baseline): 1-group per-coefficient
    from tp1_poly import exhaustive_buckets as eb1
    for d in designs:
        er_nnf, med_nnf = nnf_metric_polys(d, D0, D0)
        f, _ = load_design(d)
        sumE, cntE = eb1(None, f, 24)
        er_ex = trim(metric_poly(cntE, D0[0], D0[0], 24))
        med_ex = trim(metric_poly(sumE, D0[0], D0[0], 24))
        report["rows"].append({"design": d, "path": "D0->D0",
                               "er_coeff_match": er_nnf == er_ex, "med_coeff_match": med_nnf == med_ex})
        print(f"[{d}] D0 ER match {er_nnf == er_ex} MED match {med_nnf == med_ex}")
    # R_new asymmetric path: single-point exhaustive (2 designs x 3 lambdas)
    for d in designs:
        r = verify_random_singlepoint(d, D0, R_new0, [Fraction(1, 4), Fraction(1, 2), Fraction(3, 4)],
                                      "D0->R_new0")
        report["rows"].append(r)
    # D0->R_new1 (second random endpoint) for one design as extra
    r = verify_random_singlepoint("add12u_4R6", D0, R_new1, [Fraction(1, 4), Fraction(1, 2)],
                                  "D0->R_new1")
    report["rows"].append(r)
    (OUT / "tp2_verify_results.json").write_text(json.dumps(report, indent=2, default=str),
                                                 encoding="utf-8")
    print("saved tp2_verify_results.json")


if __name__ == "__main__":
    main()
