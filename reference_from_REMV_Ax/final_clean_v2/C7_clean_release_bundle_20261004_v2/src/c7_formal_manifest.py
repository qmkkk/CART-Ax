"""C7 formal campaign manifest generator (run once, BEFORE the campaign).

Frozen selection rules (result-independent, fixed before any formal run):
  1. Public benchmark pools only: VACSEM add8/16/32/64/128/192/256 input
     sets + official EvoApproxLib 12_unsigned pareto_pwr_ep (yosys-converted).
  2. Eligibility (frozen rule): a design is excluded ONLY if it is
     functionally identical to the exact adder (ER miter is a constant),
     i.e. ER == 0 for every input.  Exclusions are recorded with reason.
  3. Per width, candidates sorted by stable filename; then:
       eligible >= 10 -> deterministic equal-interval selection of 10
       (indices floor(i*n/10), i=0..9);
       eligible 5..9 -> all;
       eligible < 5  -> all, with pool-limited note.
  4. No result-based selection (no timing/NNF/ranking knowledge used here).
  5. The manifest is written once and must never be modified after the
     first formal task starts (hash-protected by the campaign runner).

Task granularity per case (frozen):
  - compile_ER            (fresh d4 compile of the ER CNF, 180 s cap)
  - ER__<DIST> x16        (D0-D5 + R0-R9; d4 reweight vs Ganak exact)
  - compile_MED           (per-bit MED d4 compiles, atomic per-bit saves)
  - MED__<DIST> x6        (D0-D5; per-bit exact + reconstructed total)
  - timing_K16 / timing_K64 (fresh serial timing protocol)
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))

from c5_common import (C2C, wsl_path, WSL_PREFIX, save_json,  # noqa: E402
                       cnf_meta)

FORMAL = PROJECT_ROOT / "experiments" / "formal"
MITERS = FORMAL / "miters"
BLIF12 = FORMAL / "blif" / "add12"

TIMEOUT = 180
DIST_NAMES = ("D0", "D1", "D2", "D3", "D4", "D5")
RANDOM_NAMES = tuple(f"R{i}" for i in range(10))
RANDOM_SEED = 42

# width -> (family, n_pi, output_bits, exact_blif_name)
WIDTHS = [
    (8, "add8", 16, 9, "add8.blif"),
    (12, "add12", 24, 13, "add12exact.blif"),
    (16, "add16", 32, 17, "add16.blif"),
    (32, "add32", 64, 33, "add32.blif"),
    (64, "add64", 128, 65, "add64.blif"),
    (128, "add128", 256, 129, "add128.blif"),
    (192, "add192", 384, 193, "add192.blif"),
    (256, "add256", 512, 257, "add256.blif"),
]

YOSYS = ("/mnt/d/paper_project_3/tools/cache/deps/yosysroot/usr/bin/yosys -p")
YOSYS_LD = ("LD_LIBRARY_PATH=/mnt/d/paper_project_3/tools/cache/deps/"
            "yosysroot/usr/lib/x86_64-linux-gnu")


def yosys_to_blif(vfile: Path, top: str, out: Path):
    """Official yosys 0.52 conversion (same flow as the frozen add12 probe)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size > 0:
        return out
    cmd = (f"cd {wsl_path(PROJECT_ROOT / 'tools' / 'cache' / 'deps')} && "
           f"{YOSYS_LD} {YOSYS} "
           f'"read_verilog {wsl_path(vfile)}; synth -top {top}; '
           f'write_blif {wsl_path(out)}"')
    r = subprocess.run(WSL_PREFIX + [cmd], capture_output=True, text=True,
                       timeout=300)
    if r.returncode != 0 or not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"yosys failed for {vfile.name}: "
                           f"{(r.stdout + r.stderr)[-400:]}")
    return out


def gen_er_cnf(entry, outdir: Path):
    """Official Circuit2Cnf ER miter (cached)."""
    outdir.mkdir(parents=True, exist_ok=True)
    cnf = outdir / f"{entry['id']}_er.cnf"
    if cnf.exists():
        return cnf
    cmd = (f"cd {wsl_path(PROJECT_ROOT / 'tools' / 'cache' / 'VACSEM')} && "
           f"./Circuit2Cnf/build/core/Circuit2Cnf.out -t ER "
           f"-e {wsl_path(entry['exact'])} -a {wsl_path(entry['approx'])} "
           f"-o {wsl_path(outdir)}/{entry['id']}_er.cnf")
    try:
        r = subprocess.run(WSL_PREFIX + [cmd], capture_output=True, text=True,
                           timeout=600)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0:
        return None
    for suf in ("_const0", "_const1"):
        p = outdir / f"{entry['id']}_er.cnf{suf}"
        if p.exists():
            return p
    return cnf if cnf.exists() else None


def candidates_for_width(width, family):
    if family == "add12":
        src = (PROJECT_ROOT / "tools" / "cache" / "evoapproxlib" / "adders"
               / "12_unsigned" / "pareto_pwr_ep")
        out = []
        for v in sorted(src.glob("*.v")):
            if "_pdk45" in v.name:
                continue
            top = v.stem
            blif = BLIF12 / f"{top}.blif"
            yosys_to_blif(v, top, blif)
            out.append(blif)
        return out
    folder = C2C / "input" / family
    return sorted(p for p in folder.glob("*.blif") if p.name != f"{family}.blif")


def make_entry(case_id, family, width, approx, exact):
    return {
        "id": case_id, "family": family, "n_pi": None,
        "approx": str(approx), "exact": str(exact),
        "output_bits": next(w[3] for w in WIDTHS if w[1] == family),
        "width": width,
    }


def main():
    FORMAL.mkdir(parents=True, exist_ok=True)
    MITERS.mkdir(parents=True, exist_ok=True)
    cases = []
    excluded = []
    for width, family, n_pi, out_bits, exact_name in WIDTHS:
        if family == "add12":
            exact = BLIF12 / exact_name
            if not exact.exists():
                v = (PROJECT_ROOT / "tools" / "cache" / "evoapproxlib"
                     / "adders" / "12_unsigned" / "pareto_pwr_ep" / ".."
                     / ".." / "12_unsigned")
                # exact adder verilog lives with the campaign artifacts
                srcv = PROJECT_ROOT / "experiments" / "raw" / "c5" / "add12" \
                       / "add12exact.v"
                yosys_to_blif(srcv, "add12exact", exact)
        else:
            exact = C2C / "input" / family / exact_name
        cands = candidates_for_width(width, family)
        elig = []
        for blif in cands:
            case_id = blif.stem
            entry = make_entry(case_id, family, width, blif, exact)
            cnf = gen_er_cnf(entry, MITERS)
            if cnf is None:
                excluded.append({"case_id": case_id, "width": width,
                                 "reason": "er_miter_generation_failed"})
                print(f"  [{width}] {case_id}: miter FAILED (excluded)",
                      flush=True)
                continue
            if cnf.name.endswith("_const0") or cnf.name.endswith("_const1"):
                excluded.append({"case_id": case_id, "width": width,
                                 "reason": ("functionally_exact_ER0_"
                                            "degenerate")})
                print(f"  [{width}] {case_id}: DEGENERATE (excluded)",
                      flush=True)
                continue
            elig.append(blif)
        n = len(elig)
        if n >= 10:
            sel = [elig[i * n // 10] for i in range(10)]
            rule = f"equal_interval_10_of_{n}"
        else:
            sel = elig
            rule = f"all_eligible_{n}" + ("_pool_limited" if n < 5 else "")
        for blif in sel:
            case_id = blif.stem
            cases.append({
                "case_id": case_id, "width": width, "family": family,
                "n_pi": n_pi, "output_bits": out_bits,
                "approx_blif": str(blif), "exact_blif": str(exact),
                "selection_rule": rule, "eligible_pool_size": n,
            })
        print(f"width {width}: eligible={n} selected={len(sel)} "
              f"rule={rule}", flush=True)

    # ---- task list (frozen order: width asc, case asc, kind order) ----
    tasks = []
    order = 0
    for case in cases:
        cid = case["case_id"]
        w = case["width"]
        kinds = ["compile_ER"]
        kinds += [f"ER__{d}" for d in DIST_NAMES]
        kinds += [f"ER__{d}" for d in RANDOM_NAMES]
        kinds += ["compile_MED"]
        kinds += [f"MED__{d}" for d in DIST_NAMES]
        kinds += ["timing_K16", "timing_K64"]
        for kind in kinds:
            dist = kind.split("__")[1] if "__" in kind and not kind.startswith(
                ("compile", "timing")) else None
            phase = {8: "A", 12: "A", 16: "A", 32: "A", 64: "B",
                     128: "C", 192: "D", 256: "E"}[w]
            tasks.append({
                "task_id": f"width{w}__{cid}__{kind}",
                "order": order, "width": w, "phase": phase,
                "case_id": cid, "kind": kind,
                "distribution": dist,
            })
            order += 1

    # ---- frozen config + hashes ----
    frozen_config = {
        "timeout_s": TIMEOUT,
        "k_values": [16, 64],
        "distributions": list(DIST_NAMES),
        "random_distributions": list(RANDOM_NAMES),
        "random_seed": RANDOM_SEED,
        "probability_pool": ["1/8", "1/4", "1/2", "3/4", "7/8"],
        "backend": "full-variable/full-Tseitin CNF -> official d4 d-DNNF -> "
                   "exact rational PI reweighting (aux literals neutral)",
        "d4_commit": "333370cc1e843dd0749c1efe88516e72b5239174",
        "ganak": "official v2.7.0 (repo HEAD e8f5184), exact projected WMC",
        "route": "full-variable",
        "med_bit_ordering": "numeric",
        "ranking": "within-width family, Kendall tau-b + strict inversions",
        "timing": ("cold = fresh compile + parse/build + K evals; "
                   "warm = K evals on loaded representation; "
                   "marginal = warm / K; serial latency"),
        "exactness_reference": "Ganak projected exact WMC (GANAK_TIMEOUT "
                               "recorded when > timeout)",
    }
    cfg_hash = hashlib.sha256(
        json.dumps(frozen_config, sort_keys=True).encode()).hexdigest()
    manifest = {
        "campaign": "C7_FORMAL",
        "version": "v1",
        "generated": "2026-10-03",
        "note": ("Frozen before any formal task ran. Selection rules and task "
                 "list must not be modified after the campaign starts."),
        "frozen_config": frozen_config,
        "config_hash": cfg_hash,
        "selection_rules": {
            "eligible_ge_10": "equal-interval deterministic selection of 10 "
                              "(indices floor(i*n/10))",
            "eligible_5_9": "use all",
            "eligible_lt_5": "use all, pool-limited noted",
            "eligibility": ("exclude ONLY designs functionally identical to "
                            "the exact adder (ER miter const0/const1)"),
            "ordering": "stable filename sort",
        },
        "widths": [{"width": w, "family": f, "n_pi": n, "output_bits": o,
                    "exact": e, "phase": ph}
                   for (w, f, n, o, e), ph in zip(
                       [(x[0], x[1], x[2], x[3], x[4]) for x in WIDTHS],
                       ["A", "A", "A", "A", "B", "C", "D", "E"])],
        "excluded_designs": excluded,
        "cases": cases,
        "tasks": tasks,
    }
    _m = {k: v for k, v in manifest.items() if k != "manifest_hash"}
    manifest["manifest_hash"] = hashlib.sha256(
        json.dumps(_m, sort_keys=True, default=str).encode()).hexdigest()

    save_json(FORMAL / "formal_manifest.json", manifest)
    import csv
    with open(FORMAL / "formal_manifest.csv", "w", encoding="utf-8",
              newline="") as f:
        wcsv = csv.writer(f)
        wcsv.writerow(["task_id", "order", "width", "phase", "case_id",
                       "kind", "distribution"])
        for t in tasks:
            wcsv.writerow([t["task_id"], t["order"], t["width"], t["phase"],
                           t["case_id"], t["kind"], t["distribution"]])
    print(f"manifest: {len(cases)} cases, {len(tasks)} tasks, "
          f"excluded {len(excluded)}")
    print("manifest_hash:", manifest["manifest_hash"])


if __name__ == "__main__":
    main()
