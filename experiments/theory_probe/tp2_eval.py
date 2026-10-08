"""tp2_eval.py — polynomial-semiring evaluator over d4 d-DNNF + exact comparison
with the Round-1 exhaustive-bucket polynomials.

Semiring (task spec):
  PI literal     = a + b*lambda  (exact rational poly, degree 1)
  aux literal    = 1
  AND            = polynomial multiplication
  OR             = polynomial addition
  MED            = sum_b 2^b * poly(bit b)

Comparison (task 3): per-coefficient exact equality of M_A, M_B, Delta_AB,
plus roots and endpoint values.
"""
from __future__ import annotations

import sys
import time
from fractions import Fraction
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
import tp_paths  # noqa: E402
PROJECT_ROOT = tp_paths.ROOT
sys.path.insert(0, str(PROJECT_ROOT / "experiments" / "theory_probe"))

from tp1_poly import (read_metric_csv, exhaustive_buckets, metric_poly, trim,
                      eval_poly, roots_in_unit, sign_at, locate_inversions)  # noqa: E402
from tp2_cnf import build_circuit  # noqa: E402

CNF = tp_paths.cnf_dir()
Z = Fraction(0, 1)
O = Fraction(1, 1)


# ---------------- NNF parsing (d4 output format) -------------------------

def parse_nnf(path: Path):
    """d4 -dDNNF output: node lines '<type> <id> 0', arc lines '<parent> <child> <lits...> 0'."""
    types = {}
    arcs = {}
    root = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line[0] == "c":
            continue
        toks = line.split()
        c = toks[0]
        if c in ("a", "o", "t", "f"):
            nid = int(toks[1])
            types[nid] = c
            if root is None:
                root = nid
        else:
            nums = [int(x) for x in toks]
            if nums and nums[-1] == 0:
                nums.pop()
            arcs.setdefault(nums[0], []).append((nums[1], nums[2:]))
    return types, arcs, root


# ---------------- polynomial ops ------------------------------------------

def poly_mul(a, b):
    out = [Z] * (len(a) + len(b) - 1)
    for i, ai in enumerate(a):
        for j, bj in enumerate(b):
            out[i + j] += ai * bj
    return out


def poly_add(a, b):
    n = max(len(a), len(b))
    out = [Z] * n
    for i in range(n):
        if i < len(a):
            out[i] += a[i]
        if i < len(b):
            out[i] += b[i]
    return out


def lit_poly(lit, p0, p1, n_pi):
    """Weight of a literal as a poly in lambda (degree 1 for PI literals, const 1 for aux)."""
    v = abs(lit)
    if 1 <= v <= n_pi:
        p = p0 + (p1 - p0)  # p0/p1 are per-PI Fraction vectors; called with the vector
        raise NotImplementedError
    return [O]


# ---------------- evaluator -----------------------------------------------

def eval_nnf_poly(types, arcs, root, pi_probs0, pi_probs1, n_pi):
    """Exact rational polynomial evaluation (ascending coeff lists, Fractions).
    pi_probs0/1: lists of length n_pi with per-PI endpoint probabilities."""
    n = max(types) + 1 if types else 0
    memo = [None] * n
    # PI literal polys
    litw = {}
    for v in range(1, n_pi + 1):
        p0 = pi_probs0[v - 1]
        p1 = pi_probs1[v - 1]
        litw[v] = [p0, p1 - p0]          # p(lambda)
        litw[-v] = [1 - p0, -(p1 - p0)]  # 1 - p(lambda)
    stack = [(root, 0)]
    while stack:
        node, phase = stack.pop()
        if phase == 1:
            t = types[node]
            if t == "t":
                memo[node] = [O]
            elif t == "f":
                memo[node] = [Z]
            elif t == "o":
                acc = [Z]
                for child, lits in arcs.get(node, []):
                    aw = [O]
                    for lit in lits:
                        if abs(lit) <= n_pi:
                            aw = poly_mul(aw, litw[lit])
                        # aux literals: weight 1 (no-op)
                    acc = poly_add(acc, poly_mul(aw, memo[child]))
                memo[node] = acc
            elif t == "a":
                acc = [O]
                for child, lits in arcs.get(node, []):
                    aw = [O]
                    for lit in lits:
                        if abs(lit) <= n_pi:
                            aw = poly_mul(aw, litw[lit])
                    acc = poly_mul(acc, poly_mul(aw, memo[child]))
                memo[node] = acc
            else:
                raise ValueError(f"unknown node type {t}")
            continue
        if memo[node] is not None:
            continue
        stack.append((node, 1))
        for child, _lits in reversed(arcs.get(node, [])):
            if memo[child] is None:
                stack.append((child, 0))
    return memo[root]


def nnf_metric_polys(design, p0, p1, n_pi=24, n_bits=13, cnf_dir=None):
    """ER poly + MED poly of one design from its compiled NNF bank.
    n_pi: number of PI variables; n_bits: number of MED magnitude bits (width+1)."""
    d = cnf_dir or CNF
    types, arcs, root = parse_nnf(d / f"{design}_er.nnf")
    er = eval_nnf_poly(types, arcs, root, p0, p1, n_pi)
    med = [Z]
    for b in range(n_bits):
        p = d / f"{design}_med_{b}.nnf"
        if not p.exists():
            continue
        tb, ab, rb = parse_nnf(p)
        pb = eval_nnf_poly(tb, ab, rb, p0, p1, n_pi)
        # 2^b * pb
        med = poly_add(med, [Fraction(2 ** b) * x for x in pb])
    return trim(er), trim(med)


# ---------------- comparison ----------------------------------------------

def compare(design, p0, p1, bucket_fn):
    """Return dict: nnf vs exhaustive per-coefficient comparison for ER and MED."""
    t0 = time.time()
    er_nnf, med_nnf = nnf_metric_polys(design, p0, p1)
    t_nnf = time.time() - t0

    t0 = time.time()
    f = None
    from tp1_verilog import load_design
    f, _ = load_design(design)
    sumE, cntE = bucket_fn(f)
    n_bits = len(sumE) - 1
    er_ex = trim(metric_poly(cntE, p0[0], p1[0], n_bits))
    med_ex = trim(metric_poly(sumE, p0[0], p1[0], n_bits))
    t_ex = time.time() - t0

    n = max(len(er_nnf), len(er_ex))
    er_diff = [Z] * n
    for i in range(n):
        a = er_nnf[i] if i < len(er_nnf) else Z
        b = er_ex[i] if i < len(er_ex) else Z
        er_diff[i] = a - b
    n = max(len(med_nnf), len(med_ex))
    med_diff = [Z] * n
    for i in range(n):
        a = med_nnf[i] if i < len(med_nnf) else Z
        b = med_ex[i] if i < len(med_ex) else Z
        med_diff[i] = a - b
    return {
        "design": design,
        "er_nnf_deg": len(er_nnf) - 1, "er_ex_deg": len(er_ex) - 1,
        "er_coeff_match": all(d == 0 for d in er_diff),
        "med_nnf_deg": len(med_nnf) - 1, "med_ex_deg": len(med_ex) - 1,
        "med_coeff_match": all(d == 0 for d in med_diff),
        "er_diff_nonzero": [(i, str(er_diff[i])) for i, d in enumerate(er_diff) if d != 0][:5],
        "med_diff_nonzero": [(i, str(med_diff[i])) for i, d in enumerate(med_diff) if d != 0][:5],
        "t_nnf_s": round(t_nnf, 2), "t_exhaustive_s": round(t_ex, 2),
    }


def main():
    p0 = [Fraction(1, 2)] * 24
    p1 = [Fraction(1, 4)] * 24  # D1 path
    bucket_fn = lambda f: exhaustive_buckets(None, f, 24)  # noqa: E731
    out = {"title": "ROUND2 d-DNNF vs exhaustive per-coefficient", "results": []}
    for design in ["add12u_4R6", "add12u_4YR"]:
        r = compare(design, p0, p1, bucket_fn)
        out["results"].append(r)
        print(design, "ER match:", r["er_coeff_match"], "MED match:", r["med_coeff_match"],
              "| ER deg", r["er_nnf_deg"], "/", r["er_ex_deg"],
              "| MED deg", r["med_nnf_deg"], "/", r["med_ex_deg"],
              "| t_nnf", r["t_nnf_s"], "s, t_ex", r["t_exhaustive_s"], "s")
        if not r["er_coeff_match"]:
            print("  ER diffs:", r["er_diff_nonzero"][:3])
        if not r["med_coeff_match"]:
            print("  MED diffs:", r["med_diff_nonzero"][:3])
    (tp_paths.out_dir() / "tp2_compare.json").write_text(
        __import__("json").dumps(out, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
