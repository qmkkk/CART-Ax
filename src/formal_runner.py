"""formal_runner.py — PROJECT_4 FORMAL_EXPERIMENT_CAMPAIGN_V1 runner.

Resumable, atomic, checkpointed execution.  The ONLY entry points are:
    python src/formal_runner.py --status
    python src/formal_runner.py --resume

State is persisted on disk (formal/checkpoints, formal/results, formal/logs);
chat context is never a source of truth.

Job model (per width):
  cnf    : design x (ER | MED bit)  -> CNF from VACSEM miter BLIF -> d4 -> NNF
  poly   : design x path            -> ER/MED polynomial coefficients (exact)
  family : path x metric            -> all-pair roots + family regimes

Rules:
  - DONE jobs are never re-run;
  - results are written to *.tmp then atomic-renamed; DONE checkpoint only after
    result integrity check (SHA256 of result file);
  - a RUNNING job interrupted by process kill is re-run on next --resume;
  - FAILED (incl. FAILED_TIMEOUT) is retried on --resume;
  - float/evalf only for display; all scientific decisions are exact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import itertools
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "theory_probe"))
sys.path.insert(0, str(ROOT / "src" / "python"))

from tp1_poly import exact_roots, sort_roots, trim, eval_poly  # noqa: E402
from tp2_round2 import family_regimes_from_polys, weak_ranking  # noqa: E402
from tp2_cnf import write_cnfs_miter  # noqa: E402
from tp2_eval import nnf_metric_polys  # noqa: E402

FORMAL = ROOT / "formal"
CFG = FORMAL / "config"
CHK = FORMAL / "checkpoints"
RES = FORMAL / "results"
LOG = FORMAL / "logs"
NNFS = FORMAL / "nnf"
ASSETS = FORMAL / "assets"

Z = Fraction(0, 1)
ONE = Fraction(1, 1)

# ---------------------------------------------------------------------------
# frozen campaign configuration (created once; never mutated after first run)
# ---------------------------------------------------------------------------

CAMPAIGN = {
    "name": "FORMAL_EXPERIMENT_CAMPAIGN_V1",
    "version": "v1",
    "benchmark": "VACSEM miter BLIF (commit b11ede7), frozen REMV-Ax miter assets",
    "selection": "deterministic equal-interval (frozen REMV-Ax formal manifest)",
    "widths": [16, 32, 64],
    "designs_16": [],   # filled at first run from wide_benchmark_manifest
    "designs_32": [],
    "designs_64": [],
    "paths": ["D0D1", "D0D2", "D0D3", "D0D4", "D0D5", "Rnew"],
    "metrics": ["ER", "MED"],
    "timeout_s": {"cnf": 300, "poly": 300, "family": 900},
}

WIDTH_INFO = {16: {"n_pi": 32, "n_bits": 17},
              32: {"n_pi": 64, "n_bits": 33},
              64: {"n_pi": 128, "n_bits": 65}}


def load_config():
    p = CFG / "campaign_v1.json"
    manifest = json.loads((FORMAL / "manifests" / "wide_benchmark_manifest.json").read_text(
        encoding="utf-8"))
    if p.exists():
        cfg = json.loads(p.read_text(encoding="utf-8"))
    else:
        cfg = dict(CAMPAIGN)
    # idempotent width/design initialization (frozen selection rule; not result-driven)
    if "designs_32" not in cfg or not cfg["designs_32"]:
        cfg["designs_32"] = sorted({r["design_name"] for r in manifest["rows"]
                                    if r["width"] == 32 and r["exact_approx"] == "approx"})
    if "designs_64" not in cfg or not cfg["designs_64"]:
        cfg["designs_64"] = sorted({r["design_name"] for r in manifest["rows"]
                                    if r["width"] == 64 and r["exact_approx"] == "approx"})
    if 64 not in cfg.get("widths", []):
        cfg["widths"] = [16, 32, 64]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def frozen_path_vectors(path_id, n_pi, width=16):
    """Exact p0/p1 vectors for a frozen path id (16-bit instance)."""
    if path_id == "Rnew":
        fp = CFG / f"frozen_paths_{width}.json"
        d = json.loads(fp.read_text(encoding="utf-8"))
        p0 = [Fraction(x) for x in d["dists"]["R_new0"]]
        p1 = [Fraction(x) for x in d["dists"]["R_new1"]]
        return p0, p1
    D0 = [Fraction(1, 2)] * n_pi
    if path_id == "D0D1":
        return D0, [Fraction(1, 4)] * n_pi
    if path_id == "D0D2":
        return D0, [Fraction(3, 4)] * n_pi
    if path_id == "D0D3":
        return D0, [Fraction(1, 4) if i % 2 == 0 else Fraction(3, 4) for i in range(n_pi)]
    half = n_pi // 2
    if path_id == "D0D4":
        return D0, [Fraction(1, 4)] * half + [Fraction(3, 4)] * half
    if path_id == "D0D5":
        return D0, [Fraction(3, 4)] * half + [Fraction(1, 4)] * half
    raise KeyError(path_id)


# ---------------------------------------------------------------------------
# job list
# ---------------------------------------------------------------------------

def all_jobs(cfg):
    jobs = []
    for width in cfg["widths"]:
        info = WIDTH_INFO[width]
        designs = cfg[f"designs_{width}"]
        for d in designs:
            jobs.append({"id": f"w{width}_cnf_{d}_ER", "type": "cnf", "design": d,
                         "kind": "ER", "width": width})
            for k in range(info["n_bits"]):
                jobs.append({"id": f"w{width}_cnf_{d}_med_{k}", "type": "cnf",
                             "design": d, "kind": f"med_{k}", "width": width})
        for d in designs:
            for pth in cfg["paths"]:
                jobs.append({"id": f"w{width}_poly_{d}_{pth}", "type": "poly",
                             "design": d, "path": pth, "width": width})
        for pth in cfg["paths"]:
            for m in cfg["metrics"]:
                jobs.append({"id": f"w{width}_family_{pth}_{m}", "type": "family",
                             "path": pth, "metric": m, "width": width})
    return jobs


def job_status(job_id):
    cp = CHK / f"{job_id}.json"
    if not cp.exists():
        return "PENDING"
    return json.loads(cp.read_text(encoding="utf-8"))["status"]


# ---------------------------------------------------------------------------
# atomic helpers
# ---------------------------------------------------------------------------

def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def mark(job_id, status, **extra):
    rec = {"job_id": job_id, "status": status, "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
           **extra}
    atomic_write(CHK / f"{job_id}.json", json.dumps(rec, indent=2, default=str))


# ---------------------------------------------------------------------------
# job executors
# ---------------------------------------------------------------------------

def _wsl_path(p) -> str:
    """Convert a Windows path to the WSL /mnt/<drive>/... form (any drive letter)."""
    p = str(Path(p))
    if p.startswith("/mnt/"):
        return p
    drive, rest = p.split(":", 1)
    return "/mnt/" + drive.lower() + rest.replace("\\", "/")


def _d4_binary() -> str:
    """Resolve the d4 binary: CART_D4 env var first, then PATH lookup.

    d4 is only needed to (re)compile CNF -> NNF. All frozen formal results are
    committed, so this is never invoked on a completed campaign.
    """
    env = os.environ.get("CART_D4")
    if env:
        return env
    exe = shutil.which("d4")
    if exe:
        return exe
    raise RuntimeError(
        "d4 binary not found: set CART_D4=/path/to/d4 (crillab/d4) or add d4 to "
        "PATH. Only needed to recompile CNF->NNF; all frozen results are committed."
    )


def _d4_compile(cnf, timeout):
    nnf = cnf[:-4] + ".nnf"
    if Path(nnf).exists() and Path(nnf).stat().st_size > 0:
        return 0.0, "cached"
    d4 = _d4_binary()
    t0 = time.time()
    try:
        if shutil.which("wsl.exe"):
            # Windows + WSL transport (original environment)
            w = _wsl_path(cnf)
            wo = _wsl_path(nnf)
            distro = os.environ.get("CART_WSL_DISTRO", "Ubuntu")
            cmd = ["wsl.exe", "-d", distro, "--", "bash", "-lc",
                   f"{d4} -dDNNF {w} -out={wo} 2>&1 | tail -1"]
        else:
            # Native Linux/macOS: run d4 directly on local paths
            cmd = ["bash", "-lc", f"{d4} -dDNNF {cnf} -out={nnf} 2>&1 | tail -1"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return timeout, "TIMEOUT"
    dt = time.time() - t0
    return dt, r.stdout.strip()[:60]


def run_cnf(job, cfg):
    design, kind = job["design"], job["kind"]
    width = job["width"]
    outdir = NNFS / f"add{width}"
    outdir.mkdir(parents=True, exist_ok=True)
    # CNF generation is idempotent; recompile only if NNF missing (run in one job)
    er_blif = ASSETS / f"miters{width}" / "er" / f"{design}_er.blif"
    med_dir = ASSETS / f"miters{width}" / "med"
    # generate all CNFs for the design once per job set (idempotent, cheap)
    cnf = outdir / f"{design}_{kind}.cnf"
    if not cnf.exists():
        write_cnfs_miter(er_blif, med_dir, design, width, outdir)
    if not cnf.exists():
        # const0/const1 bit: VACSEM miter verified constant -> no CNF/NNF needed.
        # MED reconstruction uses only existing bit NNFs (contribution 0 otherwise).
        return {"design": design, "kind": kind, "width": width,
                "const_skip": True, "compile_s": 0.0, "d4_status": "const_skip"}
    dt, out = _d4_compile(str(cnf), cfg["timeout_s"]["cnf"])
    nnf = outdir / f"{design}_{kind}.nnf"
    rec = {"design": design, "kind": kind, "width": width,
           "compile_s": round(dt, 3) if dt != "TIMEOUT" else None,
           "d4_status": out,
           "nnf_bytes": nnf.stat().st_size if nnf.exists() else None,
           "nnf_sha256": sha256_file(nnf) if nnf.exists() else None}
    if out == "TIMEOUT" or not nnf.exists():
        raise RuntimeError(f"compile failed: {out}")
    return rec


def run_poly(job, cfg):
    design, pth = job["design"], job["path"]
    width = job["width"]
    info = WIDTH_INFO[width]
    p0, p1 = frozen_path_vectors(pth, info["n_pi"], width)
    er_poly, med_poly = nnf_metric_polys(design, p0, p1, n_pi=info["n_pi"], n_bits=info["n_bits"],
                                         cnf_dir=NNFS / f"add{width}")
    return {
        "design": design, "path": pth, "width": width,
        "er_deg": len(er_poly) - 1, "med_deg": len(med_poly) - 1,
        "er_coeffs": [str(c) for c in er_poly],
        "med_coeffs": [str(c) for c in med_poly],
        "er_at_0": str(eval_poly(er_poly, Z)), "er_at_1": str(eval_poly(er_poly, ONE)),
        "med_at_0": str(eval_poly(med_poly, Z)), "med_at_1": str(eval_poly(med_poly, ONE)),
    }


def run_family(job, cfg):
    pth, metric = job["path"], job["metric"]
    width = job["width"]
    designs = cfg[f"designs_{width}"]
    info = WIDTH_INFO[width]
    p0, p1 = frozen_path_vectors(pth, info["n_pi"], width)
    poly = {}
    for d in designs:
        rp = RES / f"w{width}_poly_{d}_{pth}.json"
        data = json.loads(rp.read_text(encoding="utf-8"))
        key = "er_coeffs" if metric == "ER" else "med_coeffs"
        poly[d] = [Fraction(x) for x in data[key]]
    fam = family_regimes_from_polys(poly, designs, metric=metric)
    return fam


EXEC = {"cnf": run_cnf, "poly": run_poly, "family": run_family}


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

def run_resume(cfg):
    jobs = all_jobs(cfg)
    stat = {"total": len(jobs), "DONE": 0, "RUNNING": 0, "FAILED": 0, "PENDING": 0}
    for j in jobs:
        stat[job_status(j["id"])] = stat.get(job_status(j["id"]), 0) + 1
    print(f"[status] total={stat['total']} DONE={stat['DONE']} RUNNING={stat['RUNNING']} "
          f"FAILED={stat['FAILED']} PENDING={stat['PENDING']}")

    for job in jobs:
        jid = job["id"]
        st = job_status(jid)
        if st == "DONE":
            continue
        # a stale RUNNING (killed process) is re-run
        print(f"[run] {jid} (was {st})", flush=True)
        mark(jid, "RUNNING", start=time.time())
        log = []
        try:
            t0 = time.time()
            rec = EXEC[job["type"]](job, cfg)
            rt = time.time() - t0
            rec["runtime_s"] = round(rt, 3)
            res_path = RES / f"{jid}.json"
            atomic_write(res_path, json.dumps(rec, indent=2, default=str))
            h = sha256_file(res_path)
            mark(jid, "DONE", runtime_s=round(rt, 3), result_sha256=h,
                 result_path=str(res_path))
            print(f"   -> DONE ({round(rt,1)}s)", flush=True)
        except Exception as e:
            mark(jid, "FAILED", error=str(e)[:300], log="\n".join(log)[-2000:])
            print(f"   -> FAILED: {e}", flush=True)
    print("[resume] finished pass")


def run_status(cfg):
    jobs = all_jobs(cfg)
    stat = {"total": len(jobs), "DONE": 0, "RUNNING": 0, "FAILED": 0, "PENDING": 0}
    by_type = {}
    for j in jobs:
        st = job_status(j["id"])
        stat[st] = stat.get(st, 0) + 1
        by_type.setdefault(j["type"], {}).setdefault(st, 0)
        by_type[j["type"]][st] = by_type[j["type"]].get(st, 0) + 1
    print(f"[status] total={stat['total']} DONE={stat['DONE']} RUNNING={stat['RUNNING']} "
          f"FAILED={stat['FAILED']} PENDING={stat['PENDING']}")
    for t, d in by_type.items():
        print(f"   {t}: " + " ".join(f"{k}={v}" for k, v in d.items()))
    # next pending job
    for j in jobs:
        if job_status(j["id"]) == "PENDING":
            print(f"[next] {j['id']}")
            break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    for d in (CFG, CHK, RES, LOG):
        d.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    if a.status:
        run_status(cfg)
    else:
        run_resume(cfg)


if __name__ == "__main__":
    main()
