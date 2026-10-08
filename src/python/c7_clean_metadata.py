"""Clean-bundle config + metadata generation (writes into the clean bundle)."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))
from c5_common import named_dist, DIST_NAMES  # noqa: E402

CB = PROJECT_ROOT / "deliveries" / "C7_clean_release_bundle_20261004"
F = PROJECT_ROOT / "experiments" / "formal"


def wcsv(path, rows_, cols_):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols_)
        w.writeheader()
        w.writerows(rows_)


def sha(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    m = json.load(open(F / "formal_manifest.json", encoding="utf-8"))

    # ---- configs/frozen_protocol.json ----
    protocol = {
        "campaign": m["campaign"], "version": m["version"],
        "manifest_hash": m["manifest_hash"],
        "config_hash": m["config_hash"],
        "timeout_s": 180,
        "k_values": [16, 64],
        "distributions": list(DIST_NAMES),
        "random_distributions": [f"R{i}" for i in range(10)],
        "random_seed": 42,
        "probability_pool": ["1/8", "1/4", "1/2", "3/4", "7/8"],
        "backend": ("full-variable/full-Tseitin CNF -> official d4 d-DNNF -> "
                    "exact rational PI reweighting (aux literals neutral)"),
        "semantic_reference": ("Ganak exact projected weighted model counting "
                               "(v2.7.0); GANAK_TIMEOUT recorded when > timeout"),
        "med_bit_ordering": "numeric",
        "ranking": "within-width family, Kendall tau-b + strict inversions",
        "timing": {
            "cold": "fresh compile + one-time parse/build + K evaluations",
            "warm": "K evaluations on the loaded representation",
            "marginal": "warm / K",
            "serial_latency": True,
            "no_cache_as_fresh": True,
            "no_concurrent_ganak_for_latency": True,
        },
        "checkpoint_resume": ("atomic per-task writes; max loss one atomic "
                              "task; resume never re-runs terminal tasks"),
    }
    (CB / "configs" / "frozen_protocol.json").write_text(
        json.dumps(protocol, indent=2), encoding="utf-8")

    # ---- configs/distribution_config.json ----
    dist_cfg = {
        "note": ("Corrected circuit-relative product distributions. D4/D5 are "
                 "generated per circuit total PI count (NOT by slicing a "
                 "fixed 128-vector)."),
        "formulas": {
            "D0": "all p = 1/2",
            "D1": "all p = 1/4",
            "D2": "all p = 3/4",
            "D3": "alternating p = 1/4 (even idx), 3/4 (odd idx)",
            "D4": "first n//2 PIs p=1/4, second half p=3/4",
            "D5": "first n//2 PIs p=3/4, second half p=1/4",
            "R0-R9": ("10 random factorized product distributions, one frozen "
                      "seed-42 stream per PI width, p in {1/8,1/4,1/2,3/4,7/8}"),
        },
        "generator": "c5_common.named_dist / c5_common.random_dists",
        "d4_ne_d1_guard": [str(named_dist("D4", n) != named_dist("D1", n))
                           for n in (16, 24, 32, 64, 128, 192, 256)],
        "d5_ne_d2_guard": [str(named_dist("D5", n) != named_dist("D2", n))
                           for n in (16, 24, 32, 64, 128, 192, 256)],
        "legacy_bug": ("historical DISTS[128]-slicing made D4==D1/D5==D2 for "
                       "n<128 PIs; fixed before freeze; never used in the "
                       "formal results"),
    }
    (CB / "configs" / "distribution_config.json").write_text(
        json.dumps(dist_cfg, indent=2), encoding="utf-8")

    # ---- configs/benchmark_manifest.csv (+ benchmarks/) ----
    excl = [(e["case_id"], e["width"], e["reason"]) for e in m["excluded_designs"]]
    bm = [{"width": c["width"], "case_id": c["case_id"], "family": c["family"],
           "n_pi": c["n_pi"], "output_bits": c["output_bits"],
           "selection_rule": c["selection_rule"],
           "eligible_pool_size": c["eligible_pool_size"],
           "phase": next(t["phase"] for t in m["tasks"]
                         if t["case_id"] == c["case_id"])}
          for c in m["cases"]]
    cols = list(bm[0].keys())
    wcsv(CB / "configs" / "benchmark_manifest.csv", bm, cols)
    wcsv(CB / "benchmarks" / "benchmark_manifest.csv", bm, cols)
    # excluded designs note appended to source_pointers via doc file below

    # ---- benchmarks/source_pointers.md ----
    sp = """# Benchmark Source Pointers

All benchmark designs are public. Per frozen rule, eligibility = the ER miter
is not a constant (functionally identical designs are excluded with reason).

## VACSEM adder input sets (add8/16/32/64/128/192/256 + deviation functions)
- repo: https://github.com/ehw-fit/vacsem
- commit: b11ede7 (as recorded in run_report_5)
- local path on the original machine: tools/cache/VACSEM/Circuit2Cnf/input/
- used files: addW/*.blif (approx + exact), deviation-function/width_*_absolute_error.blif
- selection rule per width (frozen): stable filename sort; eligible >= 10 ->
  deterministic equal-interval 10 (indices floor(i*n/10)); 5-9 -> all; < 5 ->
  all (pool-limited noted). VACSEM BLIFs are NOT redistributed in this bundle;
  regenerate via the repo at the pinned commit.
- deviation functions width_13/193/257 are MISSING upstream; instantiated
  mechanically from the official parametric template
  (`abs_err = (a>b)?(a-b):(b-a)` over `_bit` bits) and synthesized with the
  frozen yosys 0.52 flow (tool-input gap, not a method change).

## EvoApproxLib add12 (only_required_local_sources/add12/)
- repo: https://github.com/ehw-fit/evoapproxlib
- commit: ec28be83bfce1b8e8b92bd456be520d323a568b5
- path: adders/12_unsigned/pareto_pwr_ep/*.v  (MIT license, redistributed with
  attribution; see each file header)
- exact counterpart add12exact.v = `assign O = A + B` (project-generated,
  same yosys flow)
- add12u_19A is EXCLUDED by the frozen eligibility rule (functionally equal to
  the exact adder, ER=0, miter const0) - recorded in the manifest
  `excluded_designs`.

## Excluded designs (frozen eligibility rule)
"""
    for cid, w, reason in excl:
        sp += f"- {cid} (width {w}): {reason}\n"
    (CB / "benchmarks" / "source_pointers.md").write_text(sp, encoding="utf-8")

    # ---- metadata/tool_versions.txt ----
    tv = """TOOL VERSIONS (final frozen set)
- Python: 3.14.5 (Windows, project .venv; no numpy required)
- WSL: Ubuntu 26.04.1 (WSL2), user k, 32 cores, 7.6 GiB RAM
- GCC/G++: 15.2.0 (WSL)
- Ganak: official v2.7.0 release binary (repo HEAD e8f5184)
- d4: official crillab/d4 commit 333370cc1e843dd0749c1efe88516e72b5239174
- Yosys: 0.52 (git sha1 fee39a3284c90249e1d9684cf6944ffbbcbb8f90)
- VACSEM Circuit2Cnf: commit b11ede7 (built R5)
- EvoApproxLib: commit ec28be83bfce1b8e8b92bd456be520d323a568b5
- ddnnf-cleanup (audit phase C): built from ganak repo source
- Boost 1.85 headers; GMP/zlib from official Ubuntu 26.04 debs (local, no sudo)
- OS: Windows 11
- timeout: 180 s (single compile / exact probe)
- K values: 16, 64
- random seed: 42 (one frozen stream per PI width; pool {1/8,1/4,1/2,3/4,7/8})
- experiment date: 2026-10-03/04
"""
    (CB / "metadata" / "tool_versions.txt").write_text(tv, encoding="utf-8")

    # ---- metadata/git_commits.txt ----
    gc = """REPO COMMITS (none of these repositories were modified locally)
- VACSEM: b11ede7
- Ganak: e8f5184 (repo HEAD at acquisition; v2.7.0 binary)
- d4: 333370cc1e843dd0749c1efe88516e72b5239174
- EvoApproxLib: ec28be83bfce1b8e8b92bd456be520d323a568b5
- (project itself is not a git repository)
Third-party source modifications: NONE (see audit_metadata/third_party_patches).
"""
    (CB / "metadata" / "git_commits.txt").write_text(gc, encoding="utf-8")

    # ---- metadata/commands_used.txt ----
    cu = """COMMANDS USED (final frozen flow)
Formal run:       .venv\\Scripts\\python.exe src\\python\\c7_formal_campaign.py
Resume:           .venv\\Scripts\\python.exe src\\python\\c7_formal_campaign.py --resume
Rollup:           .venv\\Scripts\\python.exe src\\python\\c7_formal_campaign.py --rollup
Manifest:         .venv\\Scripts\\python.exe src\\python\\c7_formal_manifest.py
Tables:           .venv\\Scripts\\python.exe src\\python\\c7_clean_tables.py
Ground truth:     .venv\\Scripts\\python.exe src\\python\\c5_ground_truth.py
Ranking:          .venv\\Scripts\\python.exe src\\python\\c5_ranking.py
d4 compile:       ./d4 -dDNNF <cnf> -out=<nnf>   (WSL, from tools/cache/d4)
Ganak reference:  ./ganak_linux/ganak --mode 1 --prob 0 <file>.wmc
Yosys (add12):    yosys -p "read_verilog f.v; synth -top t; write_blif f.blif"
Plotting:         .venv\\Scripts\\python.exe figures\\plotting_scripts\\make_plots.py
"""
    (CB / "metadata" / "commands_used.txt").write_text(cu, encoding="utf-8")

    # ---- metadata/provenance_map.csv ----
    prov = []
    cfg_hash = m["config_hash"]
    mhash = m["manifest_hash"]
    rows = {}
    with open(F / "formal_ledger.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rows[r["task_id"]] = r
    for c in m["cases"]:
        prov.append({"paper_claim_id": f"ER_{c['case_id']}",
                     "metric": "ER", "case_id": c["case_id"],
                     "distribution_id": "D0-D5,R0-R9",
                     "source_file": "results/formal_er_results.csv",
                     "source_row": f"case_id={c['case_id']}",
                     "generating_script": "c7_formal_campaign.py",
                     "config_hash": cfg_hash, "manifest_hash": mhash})
        prov.append({"paper_claim_id": f"MED_{c['case_id']}",
                     "metric": "MED", "case_id": c["case_id"],
                     "distribution_id": "D0-D5",
                     "source_file": "results/formal_med_results.csv",
                     "source_row": f"case_id={c['case_id']}",
                     "generating_script": "c7_formal_campaign.py",
                     "config_hash": cfg_hash, "manifest_hash": mhash})
        prov.append({"paper_claim_id": f"CASE_{c['case_id']}",
                     "metric": "case_summary", "case_id": c["case_id"],
                     "distribution_id": "",
                     "source_file": "results/case_level_summary.csv",
                     "source_row": f"case_id={c['case_id']}",
                     "generating_script": "c7_clean_tables.py",
                     "config_hash": cfg_hash, "manifest_hash": mhash})
    for tbl, metric in [("formal_ranking.csv", "ranking"),
                        ("formal_timing.csv", "timing"),
                        ("formal_break_even.csv", "break_even"),
                        ("formal_scalability.csv", "scalability")]:
        prov.append({"paper_claim_id": f"TABLE_{tbl}", "metric": metric,
                     "case_id": "all", "distribution_id": "",
                     "source_file": f"results/{tbl}", "source_row": "all",
                     "generating_script": "c7_formal_campaign.py --rollup",
                     "config_hash": cfg_hash, "manifest_hash": mhash})
    wcsv(CB / "metadata" / "provenance_map.csv", prov, list(prov[0].keys()))

    # ---- metadata/file_manifest.csv + sha256sums.txt ----
    fm = []
    hashes = []
    for p in sorted(CB.rglob("*")):
        if p.is_dir():
            continue
        rel = str(p.relative_to(CB)).replace("\\", "/")
        if rel in ("metadata/sha256sums.txt", "metadata/file_manifest.csv"):
            continue
        h = sha(p)
        hashes.append((h, rel))
        if rel.startswith("src/"):
            cat, src = "source", "frozen final code"
        elif rel.startswith(("configs/", "benchmarks/")):
            cat, src = "config", "frozen manifest/protocol"
        elif rel.startswith("results/"):
            cat, src = "result", "formal campaign rollup"
        elif rel.startswith("evidence/"):
            cat, src = "evidence", "audit reports + representative evidence"
        elif rel.startswith("supplementary/"):
            cat, src = "supplementary", "derived tables (from results only)"
        elif rel.startswith("figures/"):
            cat, src = "figures", "plotting data + scripts"
        elif rel.startswith("metadata/"):
            cat, src = "metadata", "bundle inventory/provenance"
        else:
            cat, src = "doc", "bundle documentation"
        fm.append({"relative_path": rel, "size_bytes": p.stat().st_size,
                   "category": cat, "source": src,
                   "reason_included": cat, "sha256": h})
    wcsv(CB / "metadata" / "file_manifest.csv", fm, list(fm[0].keys()))
    # hash the just-written manifest (it is both input and output)
    hashes.append((sha(CB / "metadata" / "file_manifest.csv"),
                   "metadata/file_manifest.csv"))
    with open(CB / "metadata" / "sha256sums.txt", "w", encoding="utf-8") as f:
        for h, rel in sorted(hashes, key=lambda x: x[1]):
            f.write(f"{h}  {rel}\n")
    print("config + metadata done; files in bundle:", len(fm))


if __name__ == "__main__":
    main()
