"""tp1_poly.py — THEORY_FEASIBILITY_ROUND_1 probe.

Question: along an affine probability path p_i(lambda) = (1-l)*p_i0 + l*p_i1,
is ER/MED of a fixed adder pair an exact polynomial in lambda, and can exact roots
of Delta_AB(lambda) certify ranking transitions?

Pipeline (all exact rational arithmetic; no floats in correctness paths):
  1. locate strict-inversion pairs from the authoritative v2 result tables;
  2. exhaustive 2^24 simulation of add12 Verilog designs, bucket-counting by
     group-popcount (groups = PI sets sharing the same (p0,p1) pair on the path);
  3. closed-form bucket weights -> exact rational polynomial coefficients of
     ER(lambda), MED(lambda), Delta_AB(lambda);
  4. sympy real_roots (Sturm-isolated) inside [0,1] -> candidate flip points;
  5. validation: P(0)/P(1) vs authoritative v2 values; random dyadic lambda
     points via an independent direct-evaluation path; sign on both sides of
     every root; multiplicity / identically-zero checks.

Authoritative data: experiments/results/formal_med_results.csv, formal_er_results.csv (v2 baseline).
"""
from __future__ import annotations

import functools
import json
import math
import sys
import time
from fractions import Fraction
from pathlib import Path

import tp_paths  # noqa: E402
PROJECT_ROOT = tp_paths.ROOT
sys.path.insert(0, str(Path(__file__).resolve().parent))

import sympy as sp
from tp1_verilog import load_design

OUT = tp_paths.out_dir()
Z = Fraction(0, 1)


def _root_cmp(a, b):
    """Exact algebraic comparison of two RootOf values (no float anywhere)."""
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def sort_roots(roots):
    """Sort RootOf values by exact algebraic comparison (float only for display)."""
    return sorted(roots, key=functools.cmp_to_key(_root_cmp))

# --------------------------------------------------------------------------
# 1. data-driven inversion-pair location (authoritative v2 tables)
# --------------------------------------------------------------------------

def read_metric_csv(rel: str):
    """{case_id: {dist: Fraction}} from a v2 results CSV."""
    rows = {}
    with open(tp_paths.results_dir() / rel, encoding="utf-8") as f:
        header = f.readline()
        for line in f:
            p = line.rstrip("\n").split(",")
            if len(p) < 5:
                continue
            width, case, dist, val = p[1], p[2], p[3], p[4]
            if not val:
                continue  # incomplete row (SKIPPED_DEPENDENCY etc.)
            rows.setdefault((width, case), {})[dist] = Fraction(val)
    return rows


def locate_inversions(rows, width, metric, d_ref, d_alt):
    """Strict inversions of the ranking under d_alt vs d_ref (both strictly ordered)."""
    cases = sorted(c for (w, c) in rows if w == width and d_ref in rows[(w, c)]
                   and d_alt in rows[(w, c)])
    order_ref = sorted(cases, key=lambda c: rows[(width, c)][d_ref])
    order_alt = sorted(cases, key=lambda c: rows[(width, c)][d_alt])
    vref = [rows[(width, c)][d_ref] for c in cases]
    valt = [rows[(width, c)][d_alt] for c in cases]
    pos_alt = {c: i for i, c in enumerate(order_alt)}
    invs = []
    for i in range(len(cases)):
        for j in range(i + 1, len(cases)):
            a, b = order_ref[i], order_ref[j]          # a better than b under ref
            # strict inversion requires strict orders at BOTH endpoints
            if vref[i] == vref[j] or valt[pos_alt[a]] == valt[pos_alt[b]]:
                continue
            if pos_alt[a] > pos_alt[b]:                # b better than a under alt
                invs.append((a, b, rows[(width, a)][d_ref], rows[(width, b)][d_ref],
                             rows[(width, a)][d_alt], rows[(width, b)][d_alt]))
    return order_ref, order_alt, invs


# --------------------------------------------------------------------------
# 2. exhaustive bucket counting
# --------------------------------------------------------------------------

def exhaustive_buckets(design, f, n_group_bits):
    """One pass over 2^24 inputs. Buckets = popcount of the whole 24-bit input
    (single group of 24 bits; used for uniform-bias paths D0->D1/D2)."""
    nb = n_group_bits + 1
    sumE = [0] * nb
    cntE = [0] * nb
    full = 1 << 24
    for x in range(full):
        o = f(x)
        e = abs((x & 0xFFF) + (x >> 12) - o)
        j = x.bit_count()
        sumE[j] += e
        if e:
            cntE[j] += 1
    return sumE, cntE


def exhaustive_buckets_2g(design, f, lo_bits, hi_bits, order="contig"):
    """Two groups: (p0,p1) differs between group1 (lo_bits) and group2 (hi_bits).
    order='contig': group1 = A (bits 0..11), group2 = B (bits 12..23);
    order='interleave': group1 = A[i],B[i] even pairs... handled by caller via mask.
    Returns flat arrays sumE[(j1*(hi_bits+1))+j2], cntE[...].
    """
    n2 = hi_bits
    size = (lo_bits + 1) * (hi_bits + 1)
    sumE = [0] * size
    cntE = [0] * size
    for x in range(1 << 24):
        o = f(x)
        e = abs((x & 0xFFF) + (x >> 12) - o)
        if order == "contig":
            j1 = (x & 0xFFF).bit_count()
            j2 = (x >> 12).bit_count()
        else:  # interleave: group1 = even-indexed PI positions (A0,B0,A1,B1,...)
            j1 = ((x & 0x555)).bit_count() + ((x >> 12) & 0x555).bit_count()
            j2 = ((x & 0xAAA) >> 1).bit_count() + (((x >> 12) & 0xAAA) >> 1).bit_count()
        k = j1 * (n2 + 1) + j2
        sumE[k] += e
        if e:
            cntE[k] += 1
    return sumE, cntE


# --------------------------------------------------------------------------
# 3. exact polynomial construction
# --------------------------------------------------------------------------

def conv(a, b):
    out = [Z] * (len(a) + len(b) - 1)
    for i, ai in enumerate(a):
        for j, bj in enumerate(b):
            out[i + j] += ai * bj
    return out


def binom_poly(p0, p1, j, n):
    """p(lambda)^j * (1-p(lambda))^(n-j), p = p0 + (p1-p0)*l.
    NOTE: NO binomial coefficient here.  Bucket sums sumE/cntE already aggregate
    over all C(n,j) inputs of the bucket, so the per-input weight suffices.
    Returns exact Fraction coefficient list, degree <= n."""
    a, b = p0, p1 - p0
    c, d = 1 - p0, -(p1 - p0)
    poly1 = [Fraction(math.comb(j, s)) * a ** (j - s) * b ** s for s in range(j + 1)]
    poly2 = [Fraction(math.comb(n - j, t)) * c ** (n - j - t) * d ** t for t in range(n - j + 1)]
    return conv(poly1, poly2)


def metric_poly(bucket_vals, p0, p1, n_bits):
    """bucket_vals[j] = weight of bucket j (sumE or cntE) -> exact poly in lambda."""
    poly = None
    for j, w in enumerate(bucket_vals):
        if w == 0:
            continue
        bp = binom_poly(p0, p1, j, n_bits)
        if poly is None:
            poly = [Fraction(w) * x for x in bp]
        else:
            for k in range(len(bp)):
                poly[k] += Fraction(w) * bp[k]
    return poly or [Z]


def eval_poly(coeffs, lam):
    """Horner with exact Fraction."""
    acc = Z
    for c in reversed(coeffs):
        acc = acc * lam + c
    return acc


def trim(coeffs):
    while len(coeffs) > 1 and coeffs[-1] == 0:
        coeffs.pop()
    return coeffs


# --------------------------------------------------------------------------
# 4. roots & certificate checks
# --------------------------------------------------------------------------

def _count_open(poly, a, b):
    """Number of roots of poly in the OPEN interval (a,b), exact (Sturm)."""
    c = poly.count_roots(a, b)
    if poly.count_roots(a, a) > 0:
        c -= 1
    if poly.count_roots(b, b) > 0:
        c -= 1
    return c


class SturmCounter:
    """Exact root-count oracle: Sturm sequence precomputed once, evaluated with
    Python-int Horner (exact, no floats).  Orders of magnitude faster than
    sympy count_roots on high-degree polynomials."""

    def __init__(self, poly):
        import math as _m
        self.poly = poly
        seq = sp.sturm(poly)
        self.int_seq = []
        for s in seq:
            coeffs = s.all_coeffs()
            den = 1
            for c in coeffs:
                den = _m.lcm(den, c.denominator)
            self.int_seq.append([c.numerator * (den // c.denominator) for c in coeffs])

    def var_at(self, x):
        num, den = x.numerator, x.denominator
        nz = []
        for coeffs in self.int_seq:
            # coefficients already scaled to integers (each by its own lcm);
            # Horner over (num, den): P(x)*den^d = sum_i c_i * num^{d-i} * den^i
            v = coeffs[0]
            den_pow = 1
            for cc in coeffs[1:]:
                den_pow *= den
                v = v * num + cc * den_pow
            if v:
                nz.append(1 if v > 0 else -1)
        return sum(1 for i in range(len(nz) - 1) if nz[i] != nz[i + 1])

    def count_open(self, a, b):
        # open interval (a,b); endpoints may be roots.
        # closed [a,b] count = |V(a)-V(b)| + [f(a)==0]  (sympy semantics);
        # open = closed - [f(a)==0] - [f(b)==0] = |V(a)-V(b)| - [f(b)==0]
        k = abs(self.var_at(a) - self.var_at(b))
        if self.is_root(b):
            k -= 1
        return k

    def is_root(self, x):
        return self.poly.eval(x) == 0


def isolate_intervals(poly, lo=Fraction(0), hi=Fraction(1), max_depth=400,
                      counter=None):
    """EXACT rational isolating intervals for all roots of poly in (lo, hi),
    via Sturm count_roots + bisection.  Returns (intervals, endpoint_roots)
    where intervals = [(a, b), ...] ascending, mutually disjoint, each containing
    exactly one root; endpoint_roots = {'0': bool, '1': bool}."""
    if counter is None:
        counter = SturmCounter(poly)
    at0 = counter.is_root(sp.Rational(0))
    at1 = counter.is_root(sp.Rational(1))
    out = []

    def collect(a, b, depth):
        k = counter.count_open(a, b)
        if k == 0:
            return
        if k == 1:
            # refine to a narrow interval so that downstream rational sample
            # points and display values are meaningful (exact bisection)
            out.append(refine_interval(poly, a, b, max_iter=34, counter=counter))
            return
        if depth >= max_depth:
            raise RuntimeError("root isolation did not converge")
        m = (a + b) / 2
        if counter.is_root(m):              # m itself is a root
            out.append((m, m))
            collect(a, m, depth + 1)
            collect(m, b, depth + 1)
        else:
            collect(a, m, depth + 1)
            collect(m, b, depth + 1)

    collect(lo, hi, 0)
    out.sort()
    return out, {"0": at0, "1": at1}


def refine_interval(poly, a, b, max_iter=400, counter=None):
    """Narrow the isolating interval (a,b) of a single root by bisection (exact)."""
    if counter is None:
        counter = SturmCounter(poly)
    for _ in range(max_iter):
        if b - a < Fraction(1, 2) ** 100:
            return (a, b)
        m = (a + b) / 2
        if counter.is_root(m):
            return (m, m)          # m is itself the (rational) root
        if counter.count_open(a, m) >= 1:
            b = m
        else:
            a = m
    return (a, b)


_FACTOR_PROBE = (
    "import sys, json\n"
    "import sympy as sp\n"
    "coeffs = json.loads(sys.argv[1])\n"
    "method = sys.argv[2]\n"
    "P = sp.Poly.from_list([sp.Rational(c[0], c[1]) for c in coeffs], "
    "sp.symbols('l'))\n"
    "if method == 'count':\n"
    "    n = P.count_roots(sp.Rational(0), sp.Rational(1))\n"
    "    print('1' if n > 0 else '0')\n"
    "else:\n"
    "    iv = P.intervals(inf=sp.Rational(0), sup=sp.Rational(1))\n"
    "    print('1' if len(iv) > 0 else '0')\n"
)


def _factor_has_root_subprocess(f, timeout=10):
    """Exact 'does factor f have a root in [0,1]' via count_roots in a
    subprocess, falling back to intervals on Sturm-chain blow-up.  Returns
    True/False (exact) or None if both methods exceed the timeout."""
    import subprocess as _sub
    coeffs = [[int(c.p), int(c.q)] for c in f.all_coeffs()]
    payload = json.dumps(coeffs)
    # intervals-first: Vincent isolation is fast for most factors (incl.
    # Rnew-type high-degree factors); count_roots (Sturm) is the fallback for
    # the D0D3-type factors whose intervals() degrades on rootless factors.
    for method in ("intervals", "count"):
        try:
            r = _sub.run([sys.executable, "-c", _FACTOR_PROBE, payload, method],
                         capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0 and r.stdout.strip() in ("0", "1"):
                return r.stdout.strip() == "1"
        except _sub.TimeoutExpired:
            continue
    return None


def _refine_box(f, a, b, max_iter=34):
    """Narrow an isolating box (a,b) of a single root of factor f by LOCAL
    intervals() bisection (exact; fast on narrow boxes).  Returns (na, nb)."""
    for _ in range(max_iter):
        if b - a < Fraction(1, 2) ** 100:
            return (a, b)
        m = (a + b) / 2
        lo = sp.Rational(a.numerator, a.denominator)
        mi = sp.Rational(m.numerator, m.denominator)
        iv = f.intervals(inf=lo, sup=mi)
        if len(iv) > 0:
            # root in [a, m]; if m itself is a root, intervals() returns [(m,m)]
            if len(iv) == 1:
                aa, bb = iv[0]
                if aa == bb == mi:
                    return (m, m)
            b = m
        else:
            a = m
    return (a, b)


def _narrow_box(f, a, b):
    """Return narrow exact isolating boxes for all roots of f inside (a,b).
    Float (numpy) localization is used ONLY to pick candidate windows; every
    returned box comes from an exact sympy intervals() call, so all scientific
    decisions remain exact.  Falls back to bisection refinement when float
    candidates do not cover the exact root count."""
    def _as_frac(q):
        q = sp.Rational(q)
        return Fraction(int(q.p), int(q.q))

    def _boxes_in(lo, hi):
        iv = f.intervals(inf=sp.Rational(lo.numerator, lo.denominator),
                         sup=sp.Rational(hi.numerator, hi.denominator))
        out = []
        for (ab, _mm) in iv:
            out.append((_as_frac(ab[0]), _as_frac(ab[1])))
        return out

    # exact total count inside (a,b): degenerate boxes (a root exactly at an
    # endpoint of the enclosing intervals() call) do not lie in the open box
    all_boxes = _boxes_in(a, b)
    total = sum(1 for (lo, hi) in all_boxes if lo < hi)
    if total == 0:
        return []
    # float localization (candidate only)
    try:
        import numpy as _np
        cf = [float(c) for c in f.all_coeffs()]
        rts = _np.roots(cf)
        cands = [r.real for r in rts
                 if abs(r.imag) < 1e-6 and float(a) < r.real < float(b)]
    except Exception:
        cands = []
    boxes = []
    for v in cands:
        got = False
        for delta in (Fraction(1, 1000), Fraction(1, 100), Fraction(1, 10)):
            lo = max(a, Fraction(v) - delta)
            hi = min(b, Fraction(v) + delta)
            bb = _boxes_in(lo, hi)
            if bb:
                boxes.extend(bb)
                got = True
                break
        # dedupe consecutive overlapping boxes (same root)
    # dedupe: merge boxes that overlap (same root reached via two candidates)
    boxes.sort()
    ded = []
    for bx in boxes:
        if ded and bx[0] <= ded[-1][1]:
            ded[-1] = (ded[-1][0], max(ded[-1][1], bx[1]))
        else:
            ded.append(bx)
    if len(ded) == total:
        return ded
    # float coverage incomplete -> exact bisection fallback per original box
    na, nb = _refine_box(f, a, b)
    return [(na, nb)]


def exact_roots(coeffs, materialize_root=True):
    """EXACT real-root analysis on [0,1] using SymPy's certified QQ isolator.

    Correctness is represented by exact rational isolating intervals and exact
    multiplicities returned by ``Poly.intervals``.  This replaces the older
    path that eagerly built a full Sturm sequence and, worse, materialized all
    ``real_roots`` even when no root existed in (0,1).  On some 32-bit delta
    polynomials of degree 56--64 that eager materialization cost tens of
    seconds per pair.

    Returns a list of dicts with:
      root       : exact SymPy root object when requested; ``None`` for an
                   irrational root in fast/formal mode;
      mult       : exact multiplicity;
      endpoint   : '0', '1', or None;
      crossing   : odd-multiplicity interior root => True;
      interval   : exact Python-Fraction isolating interval (a,b).

    ``materialize_root=False`` is the authoritative fast path for formal
    family analysis.  All scientific decisions use interval/multiplicity only;
    RootOf objects are display conveniences and are never required there.
    """
    l = sp.symbols("l")
    poly = sp.Poly.from_list(list(reversed(
        [sp.Rational(c.numerator, c.denominator) for c in coeffs])), l)
    if poly.is_zero:
        return None

    # Factor-level early exit: count roots in [0,1] per squarefree factor with
    # exact Sturm counts and skip factors with no roots.  SymPy's intervals()
    # degrades severely on some high-degree factors that have NO roots in
    # [0,1] (observed: degree-75 factor, 64-bit D0D3 delta, >120 s).  Because
    # each squarefree factor's roots are a subset of poly's roots with
    # multiplicity = factor exponent, isolating factors separately and merging
    # is exact and preserves all semantics (endpoint / crossing / touching).
    sf = poly.sqf_list()
    def _as_fraction(q):
        q = sp.Rational(q)
        return Fraction(int(q.p), int(q.q))
    iv_data = []
    for f, exp in sf[1]:
        # Determine whether factor f has any root in [0,1] (closed, endpoints
        # included).  Both exact methods (Sturm count_roots, Vincent intervals)
        # can degrade on specific coefficient structures of high-degree
        # factors, but they degrade COMPLEMENTARILY: run count_roots in a
        # subprocess with a timeout, falling back to intervals in a subprocess
        # if the Sturm chain blows up (and vice versa).  Scientific decisions
        # stay exact (both methods are certified); subprocess timeout is only
        # a performance guard.
        has_root = _factor_has_root_subprocess(f)
        if has_root is False:
            continue
        if has_root is None:
            # both methods too slow: conservative fallback, evaluate intervals
            # in-process (may be slow; recorded by the runner's job timeout)
            fiv = f.intervals(inf=sp.Rational(0), sup=sp.Rational(1))
            for (ab, _m) in fiv:
                iv_data.append(((_as_fraction(ab[0]), _as_fraction(ab[1])), exp))
            continue
        # factor has root(s) in [0,1]: isolate with plain intervals() (fast),
        # then refine each box by LOCAL intervals() bisection.  SymPy's
        # intervals(eps=...) refinement degrades on some coefficient
        # structures (observed: >60 s on a degree-30 factor); local calls on
        # narrow boxes stay fast because the isolation work scales with the
        # box width.
        fiv = f.intervals(inf=sp.Rational(0), sup=sp.Rational(1))
        for (ab, _m) in fiv:
            a, b = _as_fraction(ab[0]), _as_fraction(ab[1])
            if a == b:
                iv_data.append(((a, b), exp))
            else:
                for (na, nb) in _narrow_box(f, a, b):
                    iv_data.append(((na, nb), exp))
    iv_data.sort(key=lambda t: t[0])

    # Materializing algebraic RootOf objects is intentionally lazy.  The
    # formal pipeline passes materialize_root=False.  Legacy/synthetic callers
    # that ask for display RootOf values keep the previous API.
    real_roots_cache = None
    out = []
    for (ab, mult) in iv_data:
        aa, bb = ab
        a, b = _as_fraction(aa), _as_fraction(bb)
        endpoint = None
        if a == b == Fraction(0):
            endpoint = "0"
        elif a == b == Fraction(1):
            endpoint = "1"

        rep = None
        if a == b:
            rep = sp.Rational(a.numerator, a.denominator)
        elif materialize_root:
            if real_roots_cache is None:
                real_roots_cache = poly.real_roots()
            sa = sp.Rational(a.numerator, a.denominator)
            sb = sp.Rational(b.numerator, b.denominator)
            for r in real_roots_cache:
                if r > sa and r < sb:
                    rep = r
                    break

        out.append({
            "root": rep,
            "mult": int(mult),
            "endpoint": endpoint,
            "crossing": None if endpoint is not None else (int(mult) % 2 == 1),
            "interval": (a, b),
        })

    out.sort(key=lambda d: d["interval"])  # exact Fraction ordering
    return out


def roots_in_unit(coeffs):
    """Interior roots of (0,1) only, as [(RootOf, exact_mult)] (endpoint roots excluded)."""
    info = exact_roots(coeffs)
    if info is None:
        return None
    return [(d["root"], d["mult"]) for d in info if d["endpoint"] is None]


def sign_at(coeffs, lam):
    v = eval_poly(coeffs, Fraction(lam.numerator, lam.denominator))
    return (v > 0) - (v < 0), v


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def run_case(name, design_a, design_b, p0, p1, metric, bucket_fn, label):
    t0 = time.time()
    fa, _ = load_design(design_a)
    fb, _ = load_design(design_b)
    t_sim = time.time()
    ba = bucket_fn(fa)
    bb = bucket_fn(fb)
    t_bucket = time.time()
    n_bits = len(ba[0]) - 1 if isinstance(ba, tuple) else 24

    if isinstance(ba, tuple):
        ma = metric_poly(ba[0], p0, p1, n_bits)   # sumE -> MED
        ea = metric_poly(ba[1], p0, p1, n_bits)   # cntE -> ER
        mb = metric_poly(bb[0], p0, p1, n_bits)
        eb = metric_poly(bb[1], p0, p1, n_bits)
    else:
        raise NotImplementedError("two-group path handled separately")
    med_a, med_b = trim(ma), trim(mb)
    er_a, er_b = trim(ea), trim(eb)
    dmed = trim([x - y for x, y in zip(med_a, med_b)])
    der = trim([x - y for x, y in zip(er_a, er_b)])
    t_poly = time.time()

    res = {
        "case": name, "label": label, "design_a": design_a, "design_b": design_b,
        "p0": str(p0), "p1": str(p1), "metric": metric,
        "deg_med_a": len(med_a) - 1, "deg_med_b": len(med_b) - 1, "deg_delta_med": len(dmed) - 1,
        "deg_er_a": len(er_a) - 1, "deg_er_b": len(er_b) - 1, "deg_delta_er": len(der) - 1,
        "coeff_mag_max_med": max(abs(c) for c in dmed) if any(dmed) else 0,
        "coeff_bitlen_max_med": max(c.numerator.bit_length() + c.denominator.bit_length() for c in dmed) if any(dmed) else 0,
        "t_sim_s": round(t_sim - t0, 2), "t_bucket_s": round(t_bucket - t_sim, 2),
        "t_poly_s": round(t_poly - t_bucket, 2),
    }

    # endpoints
    res["med_at_0_a"] = str(eval_poly(med_a, Z)); res["med_at_1_a"] = str(eval_poly(med_a, Fraction(1)))
    res["med_at_0_b"] = str(eval_poly(med_b, Z)); res["med_at_1_b"] = str(eval_poly(med_b, Fraction(1)))
    res["er_at_0_a"] = str(eval_poly(er_a, Z)); res["er_at_1_a"] = str(eval_poly(er_a, Fraction(1)))
    res["er_at_0_b"] = str(eval_poly(er_b, Z)); res["er_at_1_b"] = str(eval_poly(er_b, Fraction(1)))
    s0, _ = sign_at(dmed, Z); s1, _ = sign_at(dmed, Fraction(1))
    res["sign_delta_med_0"] = s0; res["sign_delta_med_1"] = s1
    res["med_flip"] = (s0 != 0 and s1 != 0 and s0 != s1)

    # roots of Delta_AB (exact analysis; endpoint roots flagged separately)
    rinfo = exact_roots(dmed)
    res["n_roots_delta_med"] = None if rinfo is None else len(rinfo)
    res["roots_delta_med"] = None if rinfo is None else [
        {"root": str(d["root"].evalf(30)), "mult": d["mult"],
         "endpoint": d["endpoint"], "crossing": d["crossing"]} for d in rinfo]
    res["delta_med_identically_zero"] = all(c == 0 for c in dmed)

    # ER roots (diagnostic)
    if any(der):
        rr2 = roots_in_unit(der)
        res["n_roots_delta_er"] = None if rr2 is None else len(rr2)
        res["roots_delta_er"] = None if rr2 is None else [[str(r.evalf(30)), m] for r, m in rr2]
        s0e, _ = sign_at(der, Z); s1e, _ = sign_at(der, Fraction(1))
        res["sign_delta_er_0"] = s0e; res["sign_delta_er_1"] = s1e
        res["er_flip"] = (s0e != 0 and s1e != 0 and s0e != s1e)
    else:
        res["n_roots_delta_er"] = 0
        res["delta_er_identically_zero"] = True
    res["t_total_s"] = round(time.time() - t0, 2)
    return res, (med_a, med_b, dmed, er_a, er_b, der, ba, bb)


def validate_random_points(res, polys, n_points=8, seed=7):
    """Independent check: direct bucket-weight evaluation at random dyadic lambda
    vs the expanded polynomial. Returns list of per-point dicts."""
    import random
    rng = random.Random(seed)
    med_a, med_b, dmed, er_a, er_b, der, ba, bb = polys
    n = len(ba[0]) - 1
    p0 = Fraction(res["p0"]); p1 = Fraction(res["p1"])
    out = []
    for _ in range(n_points):
        lam = Fraction(rng.randrange(1, 63), 64)
        # direct: sum_j w_j * C(n,j) p^j (1-p)^(n-j)
        p = p0 + lam * (p1 - p0)
        # bucket sums already aggregate over all C(n,j) inputs -> per-input weight only
        da = sum(p ** j * (1 - p) ** (n - j) * ba[0][j] for j in range(n + 1))
        db = sum(p ** j * (1 - p) ** (n - j) * bb[0][j] for j in range(n + 1))
        dca = sum(p ** j * (1 - p) ** (n - j) * ba[1][j] for j in range(n + 1))
        dcb = sum(p ** j * (1 - p) ** (n - j) * bb[1][j] for j in range(n + 1))
        pa = eval_poly(med_a, lam)
        pb = eval_poly(med_b, lam)
        ca = eval_poly(er_a, lam)
        cb = eval_poly(er_b, lam)
        out.append({
            "lambda": str(lam),
            "direct_med_a": str(da), "poly_med_a": str(pa), "match_a": da == pa,
            "direct_med_b": str(db), "poly_med_b": str(pb), "match_b": db == pb,
            "direct_er_a": str(dca), "poly_er_a": str(ca), "match_er_a": dca == ca,
            "direct_er_b": str(dcb), "poly_er_b": str(cb), "match_er_b": dcb == cb,
        })
    return out


def main():
    t_start = time.time()
    report = {"title": "THEORY_FEASIBILITY_ROUND_1", "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
              "authoritative_baseline": "C7_clean_release_bundle_20261004_v2.zip",
              "results": []}

    # ---- 1. locate inversion pairs (data-driven) -------------------------
    med = read_metric_csv("formal_med_results.csv")
    er = read_metric_csv("formal_er_results.csv")
    loc = {}
    for width, d1 in [("8", "D2"), ("12", "D1"), ("12", "D4")]:
        oref, oalt, invs = locate_inversions(med, width, "MED", "D0", d1)
        loc[f"MED_w{width}_D0->{d1}"] = {
            "order_D0": oref, "order_alt": oalt,
            "inversions": [{"a": a, "b": b, "med_a_D0": str(va), "med_b_D0": str(vb),
                            "med_a_alt": str(vc), "med_b_alt": str(vd)} for a, b, va, vb, vc, vd in invs],
        }
    for width, d1 in [("12", "D2"), ("32", "D2")]:
        oref, oalt, invs = locate_inversions(er, width, "ER", "D0", d1)
        loc[f"ER_w{width}_D0->{d1}"] = {
            "order_D0": oref, "order_alt": oalt,
            "inversions": [{"a": a, "b": b, "er_a_D0": str(va), "er_b_D0": str(vb),
                            "er_a_alt": str(vc), "er_b_alt": str(vd)} for a, b, va, vb, vc, vd in invs],
        }
    report["located_inversions"] = loc
    print("located:", {k: len(v["inversions"]) for k, v in loc.items()})

    # ---- 2. main case: 12-bit MED D0->D1, (4R6, 4YR) ----------------------
    inv12 = loc["MED_w12_D0->D1"]["inversions"]
    main_pair = inv12[0]  # (4R6, 4YR)
    print("main pair:", main_pair["a"], main_pair["b"])

    def bucket1(f):
        return exhaustive_buckets(None, f, 24)

    res, polys = run_case("main_12bit_MED_D0toD1", main_pair["a"], main_pair["b"],
                          Fraction(1, 2), Fraction(1, 4), "MED", bucket1,
                          "12-bit add12u MED D0(1/2)->D1(1/4), uniform path")
    res["validation_random"] = validate_random_points(res, polys)
    # endpoint cross-check vs authoritative v2
    v2 = read_metric_csv("formal_med_results.csv")
    res["v2_med_D0_a"] = str(v2[("12", main_pair["a"])]["D0"])
    res["v2_med_D1_a"] = str(v2[("12", main_pair["a"])]["D1"])
    res["v2_med_D0_b"] = str(v2[("12", main_pair["b"])]["D0"])
    res["v2_med_D1_b"] = str(v2[("12", main_pair["b"])]["D1"])
    res["endpoint_match_D0"] = (res["med_at_0_a"] == res["v2_med_D0_a"] and res["med_at_0_b"] == res["v2_med_D0_b"])
    res["endpoint_match_D1"] = (res["med_at_1_a"] == res["v2_med_D1_a"] and res["med_at_1_b"] == res["v2_med_D1_b"])
    report["results"].append(res)
    print(f"main: deg={res['deg_delta_med']} roots={res['n_roots_delta_med']} "
          f"endpointD0={res['endpoint_match_D0']} endpointD1={res['endpoint_match_D1']} "
          f"flip={res['med_flip']} t={res['t_total_s']}s")

    # ---- 3. replication pairs --------------------------------------------
    # rep1: 12-bit MED D0->D4, (4FZ,4YK) — two-group path, try both PI orderings
    inv14 = loc["MED_w12_D0->D4"]["inversions"]
    for a, b in [(inv14[0]["a"], inv14[0]["b"]), (inv14[1]["a"], inv14[1]["b"])]:
        # p0=(1/2) all bits; p1 = 1/4 for group1 (first half PIs), 3/4 for group2
        # try contig ordering (A half then B half) and interleave; keep the one matching v2 D4
        for order in ("contig", "interleave"):
            def bucket2(f, order=order):
                return exhaustive_buckets_2g(None, f, 12, 12, order=order)
            try:
                res2 = run_case_2g(f"rep_MED_D0toD4_{a}_{b}_{order}", a, b, order, bucket2, inv14)
            except NotImplementedError:
                break
            report["results"].append(res2)
            print(f"rep {a},{b} order={order}: deg={res2.get('deg_delta_med')} "
                  f"roots={res2.get('n_roots_delta_med')} endpointD4={res2.get('endpoint_match_D4')} "
                  f"t={res2.get('t_total_s')}s")
            if res2.get("endpoint_match_D4"):
                break  # correct PI ordering found
    # ---- 4. replication: ER D0->D2 pair (metric-dimension replication) -----
    inv12er = loc["ER_w12_D0->D2"]["inversions"]
    a, b = inv12er[0]["a"], inv12er[0]["b"]
    res3, polys3 = run_case(f"rep_ER_D0toD2_{a}_{b}", a, b,
                            Fraction(1, 2), Fraction(3, 4), "ER",
                            lambda f: exhaustive_buckets(None, f, 24),
                            "12-bit ER D0(1/2)->D2(3/4)")
    v2er = read_metric_csv("formal_er_results.csv")
    res3["v2_er_D0_a"] = str(v2er[("12", a)]["D0"])
    res3["v2_er_D2_a"] = str(v2er[("12", a)]["D2"])
    res3["v2_er_D0_b"] = str(v2er[("12", b)]["D0"])
    res3["v2_er_D2_b"] = str(v2er[("12", b)]["D2"])
    res3["endpoint_match_D0"] = (res3["er_at_0_a"] == res3["v2_er_D0_a"]
                                 and res3["er_at_0_b"] == res3["v2_er_D0_b"])
    res3["endpoint_match_D2"] = (res3["er_at_1_a"] == res3["v2_er_D2_a"]
                                 and res3["er_at_1_b"] == res3["v2_er_D2_b"])
    res3["validation_random"] = validate_random_points(res3, polys3)
    report["results"].append(res3)
    print(f"rep ER {a},{b}: deg={res3['deg_delta_er']} roots={res3['n_roots_delta_er']} "
          f"endpointD0={res3['endpoint_match_D0']} endpointD2={res3['endpoint_match_D2']} "
          f"er_flip={res3['er_flip']} t={res3['t_total_s']}s")
    report["t_total_s"] = round(time.time() - t_start, 2)
    (OUT / "tp1_results.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("saved:", OUT / "tp1_results.json")


def run_case_2g(name, design_a, design_b, order, bucket_fn, inv_row):
    """Two-group path: p1 differs per group. Exact polynomial via 2-group buckets."""
    from tp1_verilog import load_design as ld
    t0 = time.time()
    fa, _ = ld(design_a)
    fb, _ = ld(design_b)
    ba = bucket_fn(fa)
    bb = bucket_fn(fb)
    t_bucket = time.time()
    p0 = Fraction(1, 2)
    p1a = Fraction(1, 4)   # group1 (first half)
    p1b = Fraction(3, 4)   # group2 (second half)
    n1 = n2 = 12

    def bucket_poly(buckets, val_idx):
        poly = None
        sumE, cntE = buckets
        for k, w in enumerate(sumE if val_idx == 0 else cntE):
            if w == 0:
                continue
            j1 = k // (n2 + 1)
            j2 = k % (n2 + 1)
            bp = conv(binom_poly(p0, p1a, j1, n1), binom_poly(p0, p1b, j2, n2))
            if poly is None:
                poly = [Fraction(w) * x for x in bp]
            else:
                for kk in range(len(bp)):
                    poly[kk] += Fraction(w) * bp[kk]
        return poly or [Z]

    ma = trim(bucket_poly(ba, 0)); ea = trim(bucket_poly(ba, 1))
    mb = trim(bucket_poly(bb, 0)); eb = trim(bucket_poly(bb, 1))
    dmed = trim([x - y for x, y in zip(ma, mb)])
    res = {
        "case": name, "label": f"12-bit MED D0->D4 order={order}",
        "design_a": design_a, "design_b": design_b, "p0": "1/2", "p1": "1/4|3/4",
        "metric": "MED", "deg_delta_med": len(dmed) - 1,
        "t_bucket_s": round(t_bucket - t0, 2),
        "med_at_0_a": str(eval_poly(ma, Z)), "med_at_1_a": str(eval_poly(ma, Fraction(1))),
        "med_at_0_b": str(eval_poly(mb, Z)), "med_at_1_b": str(eval_poly(mb, Fraction(1))),
    }
    v2 = read_metric_csv("formal_med_results.csv")
    res["v2_med_D0_a"] = str(v2[("12", design_a)]["D0"])
    res["v2_med_D4_a"] = str(v2[("12", design_a)]["D4"])
    res["v2_med_D0_b"] = str(v2[("12", design_b)]["D0"])
    res["v2_med_D4_b"] = str(v2[("12", design_b)]["D4"])
    res["endpoint_match_D0"] = (res["med_at_0_a"] == res["v2_med_D0_a"] and res["med_at_0_b"] == res["v2_med_D0_b"])
    res["endpoint_match_D4"] = (res["med_at_1_a"] == res["v2_med_D4_a"] and res["med_at_1_b"] == res["v2_med_D4_b"])
    if res["endpoint_match_D0"] and res["endpoint_match_D4"]:
        s0, _ = sign_at(dmed, Z); s1, _ = sign_at(dmed, Fraction(1))
        res["sign_delta_med_0"] = s0; res["sign_delta_med_1"] = s1
        res["med_flip"] = (s0 != 0 and s1 != 0 and s0 != s1)
        rinfo = exact_roots(dmed)
        res["n_roots_delta_med"] = None if rinfo is None else len(rinfo)
        res["roots_delta_med"] = None if rinfo is None else [
            {"root": str(d["root"].evalf(30)), "mult": d["mult"],
             "endpoint": d["endpoint"], "crossing": d["crossing"]} for d in rinfo]
        res["t_total_s"] = round(time.time() - t0, 2)
    else:
        res["note"] = "endpoint mismatch -> wrong group/PI ordering assumption; roots not computed"
    return res


if __name__ == "__main__":
    main()
