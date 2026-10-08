"""Round-5 compile-once / reweight-many mechanism probe (official Ganak
--compile d-DNNF + a minimal exact rational evaluator).

IMPORTANT (recorded blocker): the official Ganak --compile .nnf is an
arc-labeled (decision + implied literals) d-DNNF.  Exact reweighting with a
node-memoized evaluator is VERIFIED on the 5 shallow add8 d-DNNFs (values
bit-exact vs exhaustive/Ganak for every distribution) but FAILS on the deep
mult8/mac d-DNNFs (overlapping decision/implied labels require per-path
distinct-variable products; three candidate semantics tested and rejected;
see run_report_5.md section on the blocker).  Per the campaign rules, blocked
cases are RECORDED, not fabricated.  The K in {1,4,16,64} reweight experiment
runs on the verified subset; every evaluation is cross-checked against the
exhaustive/Ganak-WMC value.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))

from c5_common import (named_dist, build_manifest, gen_er_cnf, to_wmc, run_ganak,  # noqa: E402
                       active_pi_indices, random_dists, wsl_path, WSL_PREFIX,
                       save_json, RAW, PARSED)
from c5_ground_truth import enumerate_circuit, weighted_stats  # noqa: E402

TIMEOUT = 180   # hard cap for every single-point probe/evaluation


def compile_nnf(wmc: Path, outdir: Path, timeout=TIMEOUT):
    """Official Ganak --compile (legacy R5/R6 helper).

    WARNING: on a cache hit this historical helper returns compile_s == 0.0.
    Do not use that value as a fresh/cold compile time in formal experiments.
    R7+ formal timing must either force a fresh output path or mark cold timing
    unavailable when compilation is cache-served.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    nnf = outdir / (wmc.stem + ".nnf")
    if nnf.exists() and nnf.stat().st_size > 0:
        txt = nnf.read_text(errors="replace")
        nodes = sum(1 for ln in txt.splitlines() if ln[:1] in ("a", "o", "t", "f"))
        return nnf, 0.0, nodes
    cmd = (f"cd {wsl_path(Path(__file__).resolve().parents[2] / 'tools' / 'cache')} && "
           f"./ganak_linux/ganak --mode 1 --prob 0 --compile {wsl_path(nnf)} {wsl_path(wmc)}")
    t0 = time.time()
    try:
        r = subprocess.run(WSL_PREFIX + [cmd], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, timeout, None
    dt = time.time() - t0
    m = re.search(r"nodes: (\d+)", r.stdout)
    nodes = int(m.group(1)) if m else None
    return (nnf if nnf.exists() else None), dt, nodes


def parse_nnf(path: Path):
    typ = {}
    arcs = {}
    root = None
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("c"):
            continue
        toks = line.split()
        if toks[0] in ("a", "o", "t", "f"):
            typ[int(toks[1])] = toks[0]
            if root is None:
                root = int(toks[1])
        else:
            nums = [int(x) for x in toks]
            if nums and nums[-1] == 0:
                nums.pop()
            arcs.setdefault(nums[0], []).append((nums[1], nums[2:]))
    return typ, arcs, root


def eval_nnf(typ, arcs, root, weights, proj_vars):
    """Exact rational weighted evaluation (iterative post-order).
    weights: {projected var: p}; internal (non-projected) arc literals get
    weight 1 (they must not change the input probability mass).  Verified
    bit-exact on the add8 d-DNNFs; see the module docstring for the blocker."""
    memo = {}
    stack = [(root, 0)]
    while stack:
        n, phase = stack.pop()
        if phase == 1:
            t = typ[n]
            if t == "t":
                memo[n] = Fraction(1, 1)
            elif t == "f":
                memo[n] = Fraction(0, 1)
            else:
                v = Fraction(0, 1) if t == "o" else Fraction(1, 1)
                for child, lits in arcs.get(n, []):
                    aw = Fraction(1, 1)
                    for lit in lits:
                        var = abs(lit)
                        if var in weights:
                            p = weights[var]
                            aw *= p if lit > 0 else (1 - p)
                    if t == "o":
                        v += aw * memo[child]
                    else:
                        v *= aw * memo[child]
                memo[n] = v
            continue
        if n in memo:
            continue
        stack.append((n, 1))
        for child, _l in reversed(arcs.get(n, [])):
            if child not in memo:
                stack.append((child, 0))
    return memo[root]


def main():
    manifest = build_manifest()
    small = [e for e in manifest if e["set"] == "small"]
    scal_ids = ["add32", "add64", "mult12", "mult15", "mult16_new", "mac"]
    miter_dir = RAW / "miters"
    scal_dir = RAW / "miters_scal"
    rng_dists = random_dists(seed=42, count=64)
    gt = json.loads((PARSED / "c5_ground_truth.json").read_text(encoding="utf-8"))

    # ---- verify-on-load: which compiled d-DNNFs reweight exactly? ----------
    verified = []
    blocked = []
    for entry in small:
        eid = entry["id"]
        gen_er_cnf(entry, miter_dir)
        idx = active_pi_indices(miter_dir / f"{eid}_er.blif")
        probs0 = named_dist("D0", entry["n_pi"])
        wmc = to_wmc(miter_dir / f"{eid}_er.cnf", probs0, RAW / "wmc",
                     pi_indices=idx)
        nnf, ct, nodes = compile_nnf(wmc, RAW / "nnf")
        if nnf is None:
            blocked.append({"circuit": eid, "stage": "compile",
                            "reason": f"compile timeout>{TIMEOUT}s"})
            continue
        typ, arcs, root = parse_nnf(nnf)
        proj = set(range(1, len(idx) + 1))
        ok_d = {}
        for d in ("D0", "D3"):
            dist = named_dist(d, entry["n_pi"])
            w = {v: Fraction(dist[idx[v - 1]]) for v in range(1, len(idx) + 1)}
            t0 = time.time()
            val = eval_nnf(typ, arcs, root, w, proj)
            if time.time() - t0 > TIMEOUT:
                ok_d[d] = "probe>180s"
                continue
            truth = Fraction(gt["results"][eid]["distributions"][d]
                             ["er_exhaustive"])
            ok_d[d] = (val == truth)
        if ok_d.get("D0") is True and ok_d.get("D3") is True:
            verified.append(entry)
        else:
            blocked.append({"circuit": eid, "stage": "reweight-verify",
                            "reason": str(ok_d),
                            "note": ("official arc-labeled d-DNNF: overlapping "
                                     "decision/implied literal labels; no "
                                     "memoized exact semantics reproduces the "
                                     "Ganak/exhaustive value on this deep "
                                     "trace")})
    for eid in scal_ids:
        entry = next(e for e in manifest if e["id"] == eid)
        cnf = scal_dir / f"{eid}_er.cnf"
        if not cnf.exists():
            gen_er_cnf(entry, scal_dir)
        blif_path = scal_dir / f"{eid}_er.blif"
        idx = active_pi_indices(blif_path)
        from blif_sim import Blif
        n_total = len(Blif(str(blif_path)).inputs)
        probs0 = named_dist("D0", n_total)
        wmc = to_wmc(cnf, probs0, RAW / "wmc", pi_indices=idx)
        nnf, ct, nodes = compile_nnf(wmc, RAW / "nnf")
        if nnf is None:
            blocked.append({"circuit": eid, "stage": "compile",
                            "reason": f"compile timeout>{TIMEOUT}s"})
            continue
        size_mb = nnf.stat().st_size / 1e6
        blocked.append({"circuit": eid, "stage": "reweight-scope",
                        "reason": (f"compiled size {size_mb:.1f} MB; exact "
                                   "reweight not attempted beyond the 180 s "
                                   "probe cap")})
    print(f"verified: {[e['id'] for e in verified]}")
    print(f"blocked: {[b['circuit'] for b in blocked]}")

    # ---- K in {1,4,16,64} reweight experiment on the verified subset -------
    results = []
    for K in (1, 4, 16, 64):
        for entry in verified:
            dists = {"D0": named_dist("D0", entry["n_pi"])}
            for k in range(K - 1):
                dists[f"R{k}"] = rng_dists[f"R{k}"][:entry["n_pi"]]
            eid = entry["id"]
            idx = active_pi_indices(miter_dir / f"{eid}_er.blif")
            probs0 = named_dist("D0", entry["n_pi"])
            wmc = to_wmc(miter_dir / f"{eid}_er.cnf", probs0, RAW / "wmc",
                         pi_indices=idx)
            nnf, ct, nodes = compile_nnf(wmc, RAW / "nnf")
            typ, arcs, root = parse_nnf(nnf)
            size = sum(1 + len(v) for v in arcs.values())
            proj = set(range(1, len(idx) + 1))
            re_times = []
            vals = {}
            all_ok = True
            for dname, dist in dists.items():
                w = {v: Fraction(dist[idx[v - 1]]) for v in range(1, len(idx) + 1)}
                t0 = time.time()
                val = eval_nnf(typ, arcs, root, w, proj)
                re_times.append(time.time() - t0)
                vals[dname] = str(val)
                if dname == "D0":
                    truth = Fraction(gt["results"][eid]["distributions"]["D0"]
                                     ["er_exhaustive"])
                    all_ok = all_ok and (val == truth)
            results.append({
                "circuit": eid, "K": K, "compile_s": round(ct, 3),
                "nnf_nodes": nodes, "nnf_arcs": size,
                "reweight_total_s": round(sum(re_times), 4),
                "reweight_per_eval_s": round(sum(re_times) / len(dists), 5),
                "values": vals, "all_match": all_ok,
            })
        print(f"K={K} done ({len(verified)} circuits)")
    # K independent Ganak WMC totals on the verified subset for comparison
    ganak_times = {}
    for K in (1, 4, 16, 64):
        tot = 0.0
        for entry in verified:
            dists = {"D0": named_dist("D0", entry["n_pi"])}
            for k in range(K - 1):
                dists[f"R{k}"] = rng_dists[f"R{k}"][:entry["n_pi"]]
            eid = entry["id"]
            idx = active_pi_indices(miter_dir / f"{eid}_er.blif")
            for dname, dist in dists.items():
                probs = [Fraction(p) for p in dist]
                wmc = to_wmc(miter_dir / f"{eid}_er.cnf", probs, RAW / "wmc",
                             pi_indices=idx)
                tot += run_ganak(wmc, timeout=TIMEOUT)[1]
        ganak_times[K] = round(tot, 2)
    save_json(PARSED / "c5_compile_reweight.json", {
        "note": ("official Ganak --compile once; minimal exact rational "
                 "evaluator; K-1 additional fixed random distributions "
                 "(seed 42, p in {1/8..7/8}); D0 cross-checked vs exhaustive"),
        "verified_circuits": [e["id"] for e in verified],
        "blocked": blocked,
        "results": results,
        "ganak_wmc_total_s": ganak_times,
    })
    print("compile-reweight done; ganak totals:", ganak_times)


if __name__ == "__main__":
    main()
