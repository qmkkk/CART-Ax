"""C7 FORMAL EXPERIMENT CAMPAIGN RUNNER (frozen method, checkpoint/resume).

Run:
  python src/python/c7_formal_campaign.py            # start (or auto-resume)
  python src/python/c7_formal_campaign.py --resume   # explicit resume
  python src/python/c7_formal_campaign.py --selftest # resume self-test only

Guarantees (frozen protocol):
  - manifest/config/backend hashes validated before any task runs; mixed
    protocol data is impossible.
  - each atomic task is ledger-marked RUNNING before execution and PASS/
    TIMEOUT/ERROR/SKIPPED_DEPENDENCY only after its result JSON exists,
    was verified (parse + task_id + sha256), and was atomically renamed.
  - resume never re-runs PASS/TIMEOUT tasks; interrupted RUNNING tasks are
    re-run only when their result file is missing or corrupt.
  - every measurement is written immediately (max loss = one atomic task).
  - latency timing is serial; fresh output directories; cache hits never
    count as fresh compiles.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))

from c5_common import (DIST_NAMES, named_dist, random_dists, to_wmc,  # noqa: E402
                       run_ganak, active_pi_indices, cnf_meta, wsl_path,
                       WSL_PREFIX, CACHE, VACSEM, save_json, RAW)
from c5_r7_phase0 import (parse_nnf_fast, eval_nnf_fast, make_order,  # noqa: E402
                          build_litw)

TIMEOUT = 180
KS = (16, 64)
FORMAL = PROJECT_ROOT / "experiments" / "formal"
RESULTS = FORMAL / "results"
ARTIFACTS = RESULTS / "artifacts"
LOGS = FORMAL / "logs"
WMC = FORMAL / "wmc"
TIMING_DIR = RESULTS / "timing"
MED_MITERS = FORMAL / "med_miters"
CASE_SUMMARIES = RESULTS / "case_summaries"
SELFTEST_DIR = FORMAL / "_selftest"

CAMPAIGN_VERSION = "C7_FORMAL_v1"

ACTIVE = {"formal_dir": FORMAL}


def _dir(name: str):
    return ACTIVE["formal_dir"] / name

# ---------------- atomic io helpers ---------------------------------------


def _fsync_file(path: Path):
    with open(path, "rb") as f:
        os.fsync(f.fileno())


def write_atomic(path: Path, text: str):
    """Write text to path via tmp + flush + fsync + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    last_err = None
    for attempt in range(6):
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
            return
        except OSError as e:
            # Windows transient lock (AV/scan/fs race): retry with backoff
            last_err = e
            time.sleep(0.25 * (attempt + 1))
    raise last_err


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def sha256_file(path: Path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------- frozen-config validation --------------------------------


def code_hashes():
    h = {}
    for f in ("c5_common.py", "c5_r7_phase0.py", "c5_r7_phaseB.py",
              "c7_formal_campaign.py"):
        p = PROJECT_ROOT / "src" / "python" / f
        h[f] = sha256_text(p.read_text(encoding="utf-8")) if p.exists() else "MISSING"
    return h


def manifest_digest(manifest: dict):
    m = {k: v for k, v in manifest.items() if k != "manifest_hash"}
    return sha256_text(json.dumps(m, sort_keys=True, default=str))


def config_digest(manifest: dict):
    return manifest["config_hash"]


def write_checkpoint(cp: dict, formal_dir=None):
    write_atomic((formal_dir or ACTIVE["formal_dir"]) / "checkpoint.json",
                 json.dumps(cp, indent=2, default=str))


def read_checkpoint(formal_dir=None):
    return read_json((formal_dir or ACTIVE["formal_dir"]) / "checkpoint.json") or {}


# ---------------- ledger --------------------------------------------------


LEDGER_COLS = ["task_id", "width", "case_id", "metric", "distribution_id",
               "phase", "status", "attempt", "start_time", "end_time",
               "elapsed_s", "result_path", "sha256", "return_code",
               "error_type", "error_message"]


def ledger_path(formal_dir: Path):
    return formal_dir / "formal_ledger.csv"


def load_ledger(formal_dir: Path):
    rows = {}
    p = ledger_path(formal_dir)
    if not p.exists():
        return rows
    with open(p, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rows[r["task_id"]] = r
    return rows


def save_ledger(formal_dir: Path, rows: dict):
    write_atomic(ledger_path(formal_dir),
                 _ledger_text(rows))


def _ledger_text(rows: dict):
    buf = [",".join(LEDGER_COLS)]
    for tid in sorted(rows):
        r = rows[tid]
        buf.append(",".join(str(r.get(c, "")) for c in LEDGER_COLS))
    return "\n".join(buf) + "\n"


def update_ledger_row(formal_dir: Path, rows: dict, task: dict, status: str,
                      attempt: int, start: float, end: float, result_path="",
                      sha="", rc="", etype="", emsg=""):
    rows[task["task_id"]] = {
        "task_id": task["task_id"], "width": task.get("width", ""),
        "case_id": task.get("case_id", ""),
        "metric": task.get("kind", ""),
        "distribution_id": task.get("distribution", ""),
        "phase": task.get("phase", ""),
        "status": status, "attempt": attempt,
        "start_time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start)),
        "end_time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(end)),
        "elapsed_s": round(end - start, 3) if end else "",
        "result_path": result_path, "sha256": sha, "return_code": rc,
        "error_type": etype, "error_message": str(emsg)[:400],
    }
    save_ledger(formal_dir, rows)


# ---------------- task result files --------------------------------------


def result_path_of(task_id: str):
    return _dir("results") / f"{task_id}.json"


def write_task_result(task_id: str, data: dict):
    """Atomic result write: tmp -> flush/fsync -> verify -> sha -> replace."""
    path = result_path_of(task_id)
    tmp = path.with_suffix(".json.tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=2, default=str))
        f.flush()
        os.fsync(f.fileno())
    # verify before replace
    check = read_json(tmp)
    assert check is not None, "result tmp unparseable"
    assert str(check.get("task_id")) == str(task_id), "task_id mismatch"
    sha = sha256_file(tmp)
    os.replace(tmp, path)
    return sha


def read_task_result(task_id: str):
    p = result_path_of(task_id)
    if not p.exists():
        return None
    return read_json(p)


def task_result_valid(task_id: str):
    d = read_task_result(task_id)
    if d is None or str(d.get("task_id")) != str(task_id):
        return None
    if d.get("status") not in ("PASS", "TIMEOUT", "ERROR",
                               "SKIPPED_DEPENDENCY"):
        return None
    return d


# ---------------- solver helpers -----------------------------------------


def kill_stray(tag: str):
    try:
        subprocess.run(WSL_PREFIX + [f"pkill -f '{tag}' || true"],
                       capture_output=True, timeout=30)
    except Exception:
        pass


def run_d4_compile(cnf: Path, out_nnf: Path, timeout=TIMEOUT):
    """Fresh official d4 -dDNNF compile; returns (status, wall, count, note,
    stdout+stderr tail).  status: 'ok' | 'timeout' | 'error'."""
    out_nnf.parent.mkdir(parents=True, exist_ok=True)
    if out_nnf.exists():
        out_nnf.unlink()  # freshness: never reuse a partial/previous file
    for suf in (".decl", ".arc"):
        for p in out_nnf.parent.glob(out_nnf.name + suf + "*"):
            try:
                p.unlink()
            except OSError:
                pass
    d4 = PROJECT_ROOT / "tools" / "cache" / "d4" / "d4"
    cmd = f"cd {wsl_path(d4.parent)} && ./d4 -dDNNF {wsl_path(cnf)} -out={wsl_path(out_nnf)}"
    t0 = time.time()
    try:
        r = subprocess.run(WSL_PREFIX + [cmd], capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8",
                           errors="replace")
    except subprocess.TimeoutExpired:
        kill_stray("d4 -dDNNF")
        time.sleep(1)
        return "timeout", timeout, None, "", ""
    dt = time.time() - t0
    m = re.search(r"^s (\d+)", r.stdout, re.M)
    count = int(m.group(1)) if m else None
    if r.returncode != 0 or not out_nnf.exists() or out_nnf.stat().st_size == 0:
        return "error", dt, count, "", (r.stdout + r.stderr)[-400:]
    nodes = sum(1 for ln in out_nnf.read_text(errors="replace").splitlines()
                if ln[:1] in ("a", "o", "t", "f"))
    return "ok", dt, count, nodes, ""


def run_ganak_capture(wmc: Path, timeout=TIMEOUT):
    """(value, wall, timed_out, internal_s, error_tail)"""
    cmd = f"cd {wsl_path(CACHE)} && ./ganak_linux/ganak --mode 1 --prob 0 {wsl_path(wmc)}"
    t0 = time.time()
    try:
        r = subprocess.run(WSL_PREFIX + [cmd], capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8",
                           errors="replace")
    except subprocess.TimeoutExpired:
        kill_stray("ganak_linux/ganak")
        return None, timeout, True, None, "timeout"
    dt = time.time() - t0
    intern = None
    m = re.search(r"Total time \[Arjun\+GANAK\]:\s*([\d.]+)", r.stdout)
    if m:
        intern = float(m.group(1))
    if r.returncode != 0:
        return None, dt, False, intern, (r.stdout + r.stderr)[-300:]
    m = re.search(r"c s exact arb frac (\d+)/(\d+)", r.stdout)
    if m:
        return Fraction(int(m.group(1)), int(m.group(2))), dt, False, intern, ""
    m = re.search(r"c s exact arb frac (\d+)", r.stdout)
    if m:
        return Fraction(int(m.group(1)), 1), dt, False, intern, ""
    return None, dt, False, intern, (r.stdout + r.stderr)[-300:]


def gen_er_cnf(entry, outdir: Path):
    """Official Circuit2Cnf ER miter (cached artifact, not a measurement)."""
    outdir.mkdir(parents=True, exist_ok=True)
    cnf = outdir / f"{entry['id']}_er.cnf"
    if cnf.exists():
        return cnf
    cmd = (f"cd {wsl_path(VACSEM)} && ./Circuit2Cnf/build/core/Circuit2Cnf.out "
           f"-t ER -e {wsl_path(entry['exact'])} -a {wsl_path(entry['approx'])} "
           f"-o {wsl_path(outdir)}/{entry['id']}_er.cnf")
    r = subprocess.run(WSL_PREFIX + [cmd], capture_output=True, text=True,
                       timeout=600, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"ER miter failed: {r.stderr[-300:]}")
    for suf in ("_const0", "_const1"):
        p = outdir / f"{entry['id']}_er.cnf{suf}"
        if p.exists():
            return p
    if not cnf.exists():
        raise RuntimeError("ER miter produced no CNF")
    return cnf


def gen_med_cnf(entry, width, bit, outdir: Path):
    """Circuit2Cnf MED miter for one error bit (cached artifact)."""
    outdir.mkdir(parents=True, exist_ok=True)
    dev = (PROJECT_ROOT / "tools" / "cache" / "VACSEM" / "Circuit2Cnf"
           / "input" / "deviation-function"
           / f"width_{width}_absolute_error.blif")
    for suf in (".cnf", ".cnf_const0", ".cnf_const1"):
        p = outdir / f"{entry['id']}_med_{bit}{suf}"
        if p.exists():
            return p
    # Circuit2Cnf generates the full per-bit set from a BASE name
    # (…/med.cnf -> …_med_0.cnf …_med_{width-1}.cnf), as in the R5 flow.
    cmd = (f"cd {wsl_path(VACSEM)} && ./Circuit2Cnf/build/core/Circuit2Cnf.out "
           f"-t MED -e {wsl_path(entry['exact'])} -a {wsl_path(entry['approx'])} "
           f"-d {wsl_path(dev)} -o {wsl_path(outdir)}/{entry['id']}_med.cnf")
    r = subprocess.run(WSL_PREFIX + [cmd], capture_output=True, text=True,
                       timeout=600, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"MED miter bit{bit} failed: {r.stderr[-300:]}")
    for suf in (".cnf", ".cnf_const0", ".cnf_const1"):
        p = outdir / f"{entry['id']}_med_{bit}{suf}"
        if p.exists():
            return p
    raise RuntimeError(f"MED miter bit{bit} produced no CNF")


def blif_of_cnf(cnf: Path):
    return cnf.parent / (re.sub(r"\.cnf(_const[01])?$", "", cnf.name) + ".blif")


# ---------------- task executors -----------------------------------------


def case_entry(manifest, case_id):
    return next(c for c in manifest["cases"] if c["case_id"] == case_id)


def artifact_er_nnf(case_id):
    return _dir("results") / "artifacts" / case_id / "er.nnf"


def artifact_er_meta(case_id):
    return _dir("results") / "artifacts" / case_id / "er_compile.json"


def artifact_med_nnf(case_id, bit):
    return _dir("results") / "artifacts" / case_id / f"med_bit{bit}.nnf"


def artifact_med_meta(case_id, bit):
    return _dir("results") / "artifacts" / case_id / f"med_bit{bit}.json"


def execute_compile_er(task, manifest, log):
    case = case_entry(manifest, task["case_id"])
    entry = {"id": case["case_id"], "approx": case["approx_blif"],
             "exact": case["exact_blif"]}
    cnf = gen_er_cnf(entry, _dir("miters"))
    log(f"ER miter: {cnf.name}")
    if cnf.name.endswith("_const0") or cnf.name.endswith("_const1"):
        return {"task_id": task["task_id"], "status": "PASS",
                "degenerate": True, "cnf": cnf.name}
    nnf = artifact_er_nnf(task["case_id"])
    status, wall, count, nodes, err = run_d4_compile(cnf, nnf)
    res = {"task_id": task["task_id"], "status": "TIMEOUT" if status == "timeout"
           else "PASS", "compile_wall_s": round(wall, 3),
           "d4_count": count, "error": err, "nnf": str(nnf),
           "cnf": str(cnf)}
    if status == "ok":
        res.update({
            "nnf_mb": round(nnf.stat().st_size / 1e6, 4),
            "nnf_nodes": nodes,
            "nnf_bytes": nnf.stat().st_size,
            "nnf_sha256": sha256_file(nnf),
        })
        write_atomic(artifact_er_meta(task["case_id"]),
                     json.dumps(res, indent=2, default=str))
    else:
        res["nnf"] = None
    return res


def load_er_nnf(case_id):
    nnf = artifact_er_nnf(case_id)
    meta = read_json(artifact_er_meta(case_id))
    if meta is None or meta.get("status") != "PASS" or not nnf.exists():
        return None, None
    return nnf, meta


def execute_er_eval(task, manifest, log):
    case = case_entry(manifest, task["case_id"])
    dist_name = task["distribution"]
    n_total = case["n_pi"]
    dist = (named_dist(dist_name, n_total) if dist_name in DIST_NAMES
            else random_dists(seed=42, count=10, n=n_total)[dist_name])
    cnf = _dir("miters") / f"{case['case_id']}_er.cnf"
    if not cnf.exists():
        return {"task_id": task["task_id"], "status": "ERROR",
                "error_type": "missing_miter", "error_message": str(cnf)}
    idx = active_pi_indices(_dir("miters") / f"{case['case_id']}_er.blif")
    wmc = to_wmc(cnf, dist, WMC, pi_indices=idx)
    gv, gt, gto, gint, gerr = run_ganak_capture(wmc)
    row = {"task_id": task["task_id"], "status": "PASS",
           "distribution": dist_name, "ganak_value": str(gv) if gv else None,
           "ganak_runtime_s": round(gt, 3) if gt is not None else None,
           "ganak_timeout": gto, "ganak_internal_s": gint,
           "ganak_error": gerr}
    nnf, meta = load_er_nnf(task["case_id"])
    if nnf is None:
        row["d4_value"] = None
        row["d4_nnf_missing"] = True
        row["match"] = None
        return row
    types, arcs, root, _, _, mode = parse_nnf_fast(nnf)
    order = make_order(types, arcs, root, mode)
    t0 = time.time()
    rv = eval_nnf_fast(types, arcs, order, build_litw(dist, idx), root)
    row["d4_value"] = str(rv)
    row["d4_eval_s"] = round(time.time() - t0, 4)
    row["d4_nnf_missing"] = False
    row["match"] = (not gto and gv is not None and rv == gv)
    return row


def execute_compile_med(task, manifest, log):
    """Per-bit MED d4 compiles with atomic per-bit sub-saves; continues past
    per-bit timeouts (each timeout is a recorded result)."""
    case = case_entry(manifest, task["case_id"])
    width = case["output_bits"]  # number of MED bits
    entry = {"id": case["case_id"], "approx": case["approx_blif"],
             "exact": case["exact_blif"]}
    per_bit = {}
    ok = True
    for bit in range(width):
        meta = read_json(artifact_med_meta(case["case_id"], bit))
        if meta is not None and meta.get("terminal") is True:
            per_bit[bit] = meta
            log(f"bit {bit}: cached {meta.get('kind', meta.get('status'))}")
            continue
        try:
            cnf = gen_med_cnf(entry, width, bit,
                              _dir("med_miters") / case["case_id"])
        except RuntimeError as e:
            sub = {"bit": bit, "status": "ERROR", "terminal": True,
                   "error": str(e)[:300]}
            write_atomic(artifact_med_meta(case["case_id"], bit),
                         json.dumps(sub, indent=2))
            per_bit[bit] = sub
            ok = False
            continue
        if cnf.name.endswith("_const0"):
            sub = {"bit": bit, "status": "PASS", "terminal": True,
                   "kind": "const0", "value": "0"}
        elif cnf.name.endswith("_const1"):
            sub = {"bit": bit, "status": "PASS", "terminal": True,
                   "kind": "const1", "value": "1"}
        else:
            nnf = artifact_med_nnf(case["case_id"], bit)
            status, wall, count, nodes, err = run_d4_compile(cnf, nnf)
            if status == "ok":
                sub = {"bit": bit, "status": "PASS", "terminal": True,
                       "kind": "compiled", "compile_wall_s": round(wall, 3),
                       "nnf_bytes": nnf.stat().st_size,
                       "nnf_mb": round(nnf.stat().st_size / 1e6, 4),
                       "nnf_nodes": nodes, "nnf_sha256": sha256_file(nnf)}
            elif status == "timeout":
                sub = {"bit": bit, "status": "TIMEOUT", "terminal": True,
                       "compile_wall_s": round(wall, 3), "kind": "timeout"}
                ok = False
            else:
                sub = {"bit": bit, "status": "ERROR", "terminal": True,
                       "kind": "error", "error": err[:300]}
                ok = False
        write_atomic(artifact_med_meta(case["case_id"], bit),
                     json.dumps(sub, indent=2, default=str))
        per_bit[bit] = sub
        log(f"bit {bit}: {sub['status']} ({sub.get('kind','')})")
    return {"task_id": task["task_id"],
            "status": "PASS" if ok else "TIMEOUT",
            "bits": {str(k): v for k, v in per_bit.items()},
            "all_bits_terminal": True}


def execute_med_eval(task, manifest, log):
    case = case_entry(manifest, task["case_id"])
    dist_name = task["distribution"]
    n_total = case["n_pi"]
    dist = named_dist(dist_name, n_total)
    width = case["output_bits"]
    bits = []
    d4_total = Fraction(0, 1)
    g_total = Fraction(0, 1)
    d4_complete = True
    g_complete = True
    for bit in range(width):
        meta = read_json(artifact_med_meta(case["case_id"], bit))
        b = {"bit": bit}
        if meta is None:
            b["status"] = "no_compile_record"
            d4_complete = False
            bits.append(b)
            continue
        kind = meta.get("kind")
        if kind in ("const0", "const1"):
            val = Fraction(int(meta.get("value", "0")))
            b["d4_value"] = str(val)
            b["ganak_value"] = str(val)
            b["match"] = True
            b["kind"] = kind
            d4_total += (1 << bit) * val
            g_total += (1 << bit) * val
            bits.append(b)
            continue
        if meta.get("status") != "PASS":
            b["status"] = meta.get("status", "no_compile")
            b["kind"] = kind
            d4_complete = False
            bits.append(b)
            continue
        # compiled bit: d4 eval + ganak reference
        nnf = artifact_med_nnf(case["case_id"], bit)
        idx = active_pi_indices(
            blif_of_cnf(_dir("med_miters") / case["case_id"]
                        / f"{case['case_id']}_med_{bit}.cnf"))
        wmc = to_wmc(_dir("med_miters") / case["case_id"]
                     / f"{case['case_id']}_med_{bit}.cnf", dist, WMC,
                     pi_indices=idx)
        gv, gt, gto, gint, gerr = run_ganak_capture(wmc)
        types, arcs, root, _, _, mode = parse_nnf_fast(nnf)
        order = make_order(types, arcs, root, mode)
        t0 = time.time()
        rv = eval_nnf_fast(types, arcs, order, build_litw(dist, idx), root)
        b.update({
            "d4_value": str(rv), "d4_eval_s": round(time.time() - t0, 4),
            "ganak_value": str(gv) if gv else None,
            "ganak_runtime_s": round(gt, 3) if gt is not None else None,
            "ganak_timeout": gto,
            "match": (not gto and gv is not None and rv == gv),
        })
        if gv is not None:
            g_total += (1 << bit) * gv
        else:
            g_complete = False
        d4_total += (1 << bit) * rv
        bits.append(b)
        log(f"bit {bit}: match={b['match']}")
    res = {
        "task_id": task["task_id"], "status": "PASS",
        "distribution": dist_name,
        "med_d4_total": str(d4_total) if d4_complete else None,
        "med_ganak_total": str(g_total) if g_complete else None,
        "d4_total_complete": d4_complete,
        "ganak_total_complete": g_complete,
        "total_match": (d4_complete and g_complete and d4_total == g_total),
        "bits": bits,
    }
    return res


def execute_timing(task, manifest, log, K):
    case = case_entry(manifest, task["case_id"])
    n_total = case["n_pi"]
    cnf = _dir("miters") / f"{case['case_id']}_er.cnf"
    if not cnf.exists():
        return {"task_id": task["task_id"], "status": "ERROR",
                "error_type": "missing_miter", "error_message": str(cnf)}
    idx = active_pi_indices(_dir("miters") / f"{case['case_id']}_er.blif")
    # FRESH compile into a fresh per-task directory
    fresh_dir = _dir("results") / "timing" / task["task_id"]
    fresh_dir.mkdir(parents=True, exist_ok=True)
    nnf = fresh_dir / "er.nnf"
    status, wall, count, nodes, err = run_d4_compile(cnf, nnf)
    row = {"task_id": task["task_id"], "K": K,
           "fresh_compile_s": round(wall, 3), "d4_count": count,
           "nnf_mb": None}
    if status != "ok":
        return {**row, "status": "TIMEOUT" if status == "timeout" else "ERROR",
                "error": err[:300]}
    row["nnf_mb"] = round(nnf.stat().st_size / 1e6, 4)
    row["nnf_nodes"] = nodes
    t0 = time.time()
    types, arcs, root, n, na, mode = parse_nnf_fast(nnf)
    order = make_order(types, arcs, root, mode)
    row["parse_build_s"] = round(time.time() - t0, 4)
    dists = {"D0": named_dist("D0", n_total)}
    dists.update(random_dists(seed=42, count=K - 1, n=n_total))
    t0 = time.time()
    for dname, dist in dists.items():
        eval_nnf_fast(types, arcs, order, build_litw(dist, idx), root)
    warm = time.time() - t0
    cold = wall + row["parse_build_s"] + warm
    t0 = time.time()
    g_total = 0.0
    g_intern = 0.0
    g_intern_ok = True
    for dname, dist in dists.items():
        wmc = to_wmc(cnf, dist, _dir("wmc"), pi_indices=idx)
        gv, gt, gto, gint, gerr = run_ganak_capture(wmc)
        if gint is None:
            g_intern_ok = False
        else:
            g_intern += gint
        g_total += gt
        if gto:
            row["ganak_timeout_any"] = True
    ganak_e2e = time.time() - t0
    row.update({
        "status": "PASS",
        "warm_s": round(warm, 4), "cold_s": round(cold, 4),
        "marginal_per_eval_s": round(warm / K, 6),
        "ganak_e2e_s": round(ganak_e2e, 3),
        "ganak_internal_sum_s": round(g_intern, 4) if g_intern_ok else None,
        "amortized_warm": bool(warm < ganak_e2e),
        "amortized_cold": bool(cold < ganak_e2e),
    })
    return row


# ---------------- runner core ---------------------------------------------


def load_manifest(formal_dir: Path):
    p = formal_dir / "formal_manifest.json"
    if not p.exists():
        raise SystemExit(f"manifest missing: {p}")
    m = read_json(p)
    if m is None or "tasks" not in m:
        raise SystemExit("manifest corrupt")
    return m


def validate_environment(manifest, formal_dir):
    """Frozen-hash validation before any task runs."""
    mh = manifest["manifest_hash"]
    if mh != manifest_digest(manifest):
        raise SystemExit("MANIFEST HASH MISMATCH - refusing to run")
    ch = code_hashes()
    cp = read_checkpoint(formal_dir) if formal_dir == FORMAL else {}
    if cp.get("manifest_hash") and cp["manifest_hash"] != mh:
        raise SystemExit("checkpoint manifest_hash != manifest - "
                         "mixed protocol detected, refusing to run")
    if cp.get("campaign_version") and cp["campaign_version"] != CAMPAIGN_VERSION:
        raise SystemExit("checkpoint campaign_version mismatch")
    return mh, ch


def run_campaign(formal_dir: Path, selftest: bool, kill_after: str = None,
                 task_budget: int = None, time_budget: float = None):
    if selftest:
        formal_dir = SELFTEST_DIR
    formal_dir.mkdir(parents=True, exist_ok=True)
    ACTIVE["formal_dir"] = formal_dir
    for d in (RESULTS, LOGS, WMC, TIMING_DIR, ARTIFACTS, MED_MITERS,
              CASE_SUMMARIES):
        formal_dir.joinpath(d.relative_to(FORMAL)).mkdir(
            parents=True, exist_ok=True)
    manifest = load_manifest(formal_dir)
    mh, ch = validate_environment(manifest, formal_dir)
    tasks = sorted(manifest["tasks"], key=lambda t: t["order"])
    rows = load_ledger(formal_dir)
    cp = read_checkpoint() if formal_dir == FORMAL else {}
    cp.setdefault("completed_task_ids", [])
    cp.setdefault("timeout_task_ids", [])
    started = time.time()
    done_in_run = 0
    budget_reason = None

    def logfile(task_id):
        return (formal_dir / "logs" / f"{task_id}.log")

    for task in tasks:
        tid = task["task_id"]
        if (time_budget and (time.time() - started) > time_budget) or (
                task_budget and done_in_run >= task_budget):
            budget_reason = "time" if time_budget and (
                time.time() - started) > time_budget else "task"
            break
        state = rows.get(tid, {}).get("status")
        if state in ("PASS", "TIMEOUT", "SKIPPED_DEPENDENCY"):
            continue
        if state == "ERROR":
            # terminal after retry budget; re-check result file
            res = task_result_valid(tid)
            if res is not None:
                continue
        if state == "RUNNING":
            res = task_result_valid(tid)
            if res is not None:
                # interrupted after completion but before ledger update
                update_ledger_row(formal_dir, rows, task, res["status"],
                                  int(rows[tid].get("attempt", 1)),
                                  time.time(), time.time(),
                                  str(result_path_of(tid)),
                                  sha256_file(result_path_of(tid)))
                cp["completed_task_ids"].append(tid)
                write_checkpoint(cp)
                continue
            # corrupt/missing -> rerun
            rows[tid]["status"] = "PENDING"
            save_ledger(formal_dir, rows)
        attempt = int(rows.get(tid, {}).get("attempt") or 0) + 1
        start = time.time()
        update_ledger_row(formal_dir, rows, task, "RUNNING", attempt, start,
                          start)
        cp["current_task"] = tid
        cp["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        write_checkpoint(cp)
        lf = logfile(tid)
        lf.parent.mkdir(parents=True, exist_ok=True)
        with open(lf, "w", encoding="utf-8") as flog:
            def log(msg):
                flog.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
                flog.flush()
            # selftest kill simulation: die DURING execution of this task
            if kill_after is not None and tid == kill_after:
                partial = result_path_of(tid)
                partial.parent.mkdir(parents=True, exist_ok=True)
                partial.write_text("{broken partial json", encoding="utf-8")
                log("SELFTEST KILL SIMULATION")
                os._exit(77)
            log(f"task {tid} start (attempt {attempt})")
            try:
                kind = task["kind"]
                if kind == "compile_ER":
                    data = execute_compile_er(task, manifest, log)
                elif kind.startswith("ER__"):
                    data = execute_er_eval(task, manifest, log)
                elif kind == "compile_MED":
                    data = execute_compile_med(task, manifest, log)
                elif kind.startswith("MED__"):
                    data = execute_med_eval(task, manifest, log)
                elif kind == "timing_K16":
                    data = execute_timing(task, manifest, log, 16)
                elif kind == "timing_K64":
                    data = execute_timing(task, manifest, log, 64)
                else:
                    raise RuntimeError(f"unknown kind {kind}")
            except Exception as e:  # noqa: BLE001
                data = {"task_id": tid, "status": "ERROR",
                        "error_type": type(e).__name__,
                        "error_message": str(e)[:400]}
                log(f"ERROR {type(e).__name__}: {e}")
        end = time.time()
        st = data.get("status", "ERROR")
        if st == "ERROR" and attempt < 2:
            # one retry for transient/system-interrupt class failures
            log("transient error -> retry once (attempt 2)")
            rows[tid] = {**rows.get(tid, {}), "status": "PENDING",
                         "attempt": 2}
            save_ledger(formal_dir, rows)
            continue
        if st not in ("PASS", "TIMEOUT", "ERROR", "SKIPPED_DEPENDENCY"):
            st = "ERROR"
            data["status"] = st
        sha = write_task_result(tid, data)
        rp = str(result_path_of(tid))
        update_ledger_row(formal_dir, rows, task, st, attempt, start, end,
                          rp, sha)
        if st == "PASS":
            cp["completed_task_ids"].append(tid)
        elif st == "TIMEOUT":
            cp["timeout_task_ids"].append(tid)
        cp["last_completed_task"] = tid
        cp["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        write_checkpoint(cp, formal_dir)
        update_case_summary(formal_dir, task["case_id"], manifest)
        if task["order"] % 25 == 0:
            rollup(formal_dir, manifest, cp)
        done_in_run += 1
        if done_in_run % 10 == 0:
            print(f"PROGRESS {done_in_run} tasks done this run, "
                  f"last={tid}", flush=True)
    # final rollup
    cp["current_task"] = None
    cp["campaign_version"] = CAMPAIGN_VERSION
    cp["manifest_hash"] = mh
    cp["finished"] = True
    write_checkpoint(cp, formal_dir)
    rollup(formal_dir, manifest, cp)
    print("CAMPAIGN_RUNNER_DONE")
    if budget_reason:
        print(f"CHUNK_STOPPED budget={budget_reason}")


# ---------------- summaries / rollups -------------------------------------


def update_case_summary(formal_dir, case_id, manifest):
    rows = load_ledger(formal_dir)
    rel = [r for r in rows.values() if r["case_id"] == case_id]
    case = next((c for c in manifest["cases"] if c["case_id"] == case_id), None)
    if case is None:
        return
    summary = {
        "case_id": case_id, "width": case["width"],
        "tasks_total": len(rel),
        "tasks_terminal": sum(1 for r in rel if r["status"] in
                              ("PASS", "TIMEOUT", "ERROR",
                               "SKIPPED_DEPENDENCY")),
        "by_status": {s: sum(1 for r in rel if r["status"] == s)
                      for s in ("PASS", "TIMEOUT", "ERROR", "RUNNING",
                                "PENDING", "SKIPPED_DEPENDENCY")},
    }
    write_atomic(formal_dir / "results" / "case_summaries"
                 / f"case_{case_id}_summary.json",
                 json.dumps(summary, indent=2, default=str))


def rollup(formal_dir, manifest, cp):
    """Regenerate the formal CSV/JSON rollups from task results."""
    rows = load_ledger(formal_dir)
    er = []
    med = []
    timing = []
    failures = []
    for tid, r in rows.items():
        res = read_json(RESULTS / f"{tid}.json") if formal_dir == FORMAL \
            else read_json(formal_dir / "results" / f"{tid}.json")
        if res is None:
            continue
        kind = r.get("metric", "")
        if kind.startswith("ER__"):
            er.append({
                "task_id": tid, "width": r["width"], "case_id": r["case_id"],
                "distribution": r["distribution_id"],
                "d4_value": res.get("d4_value"),
                "ganak_value": res.get("ganak_value"),
                "ganak_timeout": res.get("ganak_timeout"),
                "match": res.get("match"),
                "d4_nnf_missing": res.get("d4_nnf_missing"),
            })
        elif kind.startswith("MED__"):
            med.append({
                "task_id": tid, "width": r["width"], "case_id": r["case_id"],
                "distribution": r["distribution_id"],
                "med_d4_total": res.get("med_d4_total"),
                "med_ganak_total": res.get("med_ganak_total"),
                "total_match": res.get("total_match"),
                "d4_total_complete": res.get("d4_total_complete"),
                "ganak_total_complete": res.get("ganak_total_complete"),
            })
        elif kind.startswith("timing_"):
            timing.append({
                "task_id": tid, "width": r["width"], "case_id": r["case_id"],
                "K": res.get("K"), "fresh_compile_s": res.get("fresh_compile_s"),
                "parse_build_s": res.get("parse_build_s"),
                "warm_s": res.get("warm_s"), "cold_s": res.get("cold_s"),
                "marginal_per_eval_s": res.get("marginal_per_eval_s"),
                "ganak_e2e_s": res.get("ganak_e2e_s"),
                "ganak_internal_sum_s": res.get("ganak_internal_sum_s"),
                "amortized_warm": res.get("amortized_warm"),
                "amortized_cold": res.get("amortized_cold"),
            })
        if r.get("status") in ("TIMEOUT", "ERROR"):
            failures.append({
                "task_id": tid, "width": r["width"], "case_id": r["case_id"],
                "status": r["status"], "error_type": r.get("error_type"),
                "error_message": r.get("error_message"),
                "elapsed_s": r.get("elapsed_s"),
            })
    def write_csv(name, rows_, cols):
        with open(formal_dir / name, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r_ in rows_:
                w.writerow(r_)
    if er:
        write_csv("formal_er_results.csv", er,
                  ["task_id", "width", "case_id", "distribution", "d4_value",
                   "ganak_value", "ganak_timeout", "match", "d4_nnf_missing"])
    if med:
        write_csv("formal_med_results.csv", med,
                  ["task_id", "width", "case_id", "distribution",
                   "med_d4_total", "med_ganak_total", "total_match",
                   "d4_total_complete", "ganak_total_complete"])
    if timing:
        write_csv("formal_timing.csv", timing,
                  ["task_id", "width", "case_id", "K", "fresh_compile_s",
                   "parse_build_s", "warm_s", "cold_s", "marginal_per_eval_s",
                   "ganak_e2e_s", "ganak_internal_sum_s", "amortized_warm",
                   "amortized_cold"])
    if failures:
        write_csv("formal_failures.csv", failures,
                  ["task_id", "width", "case_id", "status", "error_type",
                   "error_message", "elapsed_s"])
    # break-even + ranking + scalability + summary
    # Break-even rollup must be independent of timing-row order.  Only cases
    # with a completed K64 cold comparison receive a by-K64 bucket.
    timing_by_case = defaultdict(dict)
    for t in timing:
        timing_by_case[(int(t["width"]), t["case_id"])][int(t["K"])] = t
    break_even_rows = []
    for (width, case_id), kd in sorted(timing_by_case.items()):
        k64 = kd.get(64)
        if not k64 or k64.get("amortized_cold") is None:
            continue
        k16 = kd.get(16)
        a16 = bool(k16 and k16.get("amortized_cold"))
        a64 = bool(k64.get("amortized_cold"))
        bucket = "K<=16" if a16 else ("16<K<=64" if a64 else ">64")
        break_even_rows.append({
            "case_id": case_id, "width": width,
            "break_even_bucket": bucket,
            "cold_K16": k16.get("cold_s") if k16 else None,
            "cold_K64": k64.get("cold_s"),
        })
    write_csv("formal_break_even.csv", break_even_rows,
              ["case_id", "width", "break_even_bucket", "cold_K16", "cold_K64"])
    ranking_rows = compute_ranking(er, med, manifest)
    if ranking_rows:
        write_csv("formal_ranking.csv", ranking_rows,
                  ["width", "metric", "distribution", "n_designs",
                   "kendall_tau_b_vs_D0", "strict_inversions", "rank_shift"])
    scal = []
    for c in manifest["cases"]:
        compile_rows = [r for r in rows.values()
                        if r["case_id"] == c["case_id"]
                        and r["metric"] == "compile_ER"]
        if not compile_rows:
            continue
        r = compile_rows[0]
        res = read_json(RESULTS / f"{r['task_id']}.json") if formal_dir == FORMAL \
            else read_json(formal_dir / "results" / f"{r['task_id']}.json")
        if res is None:
            continue
        scal.append({
            "width": c["width"], "case_id": c["case_id"],
            "status": r["status"], "compile_wall_s": res.get("compile_wall_s"),
            "nnf_mb": res.get("nnf_mb"), "nnf_nodes": res.get("nnf_nodes"),
            "d4_count": res.get("d4_count"),
        })
    write_csv("formal_scalability.csv", scal,
              ["width", "case_id", "status", "compile_wall_s", "nnf_mb",
               "nnf_nodes", "d4_count"])
    nterm = sum(1 for r in rows.values() if r["status"] in
                ("PASS", "TIMEOUT", "ERROR", "SKIPPED_DEPENDENCY",
                 "NOT_RUN_RESOURCE_LIMIT"))
    summary = {
        "campaign_version": CAMPAIGN_VERSION,
        "tasks_total": len(rows),
        "tasks_terminal": nterm,
        "by_status": {s: sum(1 for r in rows.values() if r["status"] == s)
                      for s in ("PASS", "TIMEOUT", "ERROR", "RUNNING",
                                "PENDING", "SKIPPED_DEPENDENCY",
                                "NOT_RUN_RESOURCE_LIMIT")},
        "note": ("256-bit NOT_RUN_RESOURCE_LIMIT tasks were stopped by the "
                 "global wall-clock budget (see formal_experiment_report.md); "
                 "8-192 is the complete formal campaign"),
        "manifest_hash": manifest.get("manifest_hash"),
    }
    write_atomic(formal_dir / "formal_summary.json",
                 json.dumps(summary, indent=2, default=str))


def compute_ranking(er_rows, med_rows, manifest):
    """Within-width family ranking: Kendall tau-b + strict inversions vs D0."""
    out = []
    widths = sorted({c["width"] for c in manifest["cases"]})
    for width in widths:
        for metric, rows in (("ER", er_rows), ("MED", med_rows)):
            if metric == "ER":
                rows_w = [r for r in rows if int(r["width"]) == width
                          and r.get("match") is True and r.get("d4_value")]
            else:
                rows_w = [r for r in rows if int(r["width"]) == width
                          and r.get("total_match") is True
                          and r.get("med_d4_total")]
            if not rows_w:
                continue
            cases_w = sorted({r["case_id"] for r in rows_w})
            vals = {}
            for r in rows_w:
                v = r["d4_value"] if metric == "ER" else r["med_d4_total"]
                vals.setdefault(r["case_id"], {})[r["distribution"]] = \
                    Fraction(v)
            if len(cases_w) < 2:
                continue
            def ranks(dist):
                seq = [vals[c][dist] for c in cases_w
                       if dist in vals[c]]
                order = sorted(range(len(seq)), key=lambda i: seq[i])
                rr = [0] * len(seq)
                rk = 1
                i = 0
                while i < len(order):
                    j = i
                    while j + 1 < len(order) and seq[order[j + 1]] == seq[order[i]]:
                        j += 1
                    for k in range(i, j + 1):
                        rr[order[k]] = rk
                    rk += j - i + 1
                    i = j + 1
                return rr
            def tau_b(a, b):
                n = len(a)
                conc = disc = ta = tb = 0
                for i in range(n):
                    for j in range(i + 1, n):
                        da, db = a[i] - a[j], b[i] - b[j]
                        if da == 0 and db == 0:
                            continue
                        if da == 0:
                            ta += 1
                        elif db == 0:
                            tb += 1
                        elif da * db > 0:
                            conc += 1
                        else:
                            disc += 1
                den = ((conc + disc + ta) * (conc + disc + tb)) ** 0.5
                return (conc - disc) / den if den else 0.0
            def inversions(a, b):
                return sum(1 for i in range(len(a)) for j in range(i + 1, len(a))
                           if (a[i] - a[j]) * (b[i] - b[j]) < 0)
            r0 = ranks("D0")
            for dist in list(DIST_NAMES):
                if not all(dist in vals[c] for c in cases_w):
                    continue
                rd = ranks(dist)
                out.append({
                    "width": width, "metric": metric,
                    "distribution": dist, "n_designs": len(cases_w),
                    "kendall_tau_b_vs_D0": round(tau_b(r0, rd), 6),
                    "strict_inversions": inversions(r0, rd),
                    "rank_shift": [rd[i] - r0[i] for i in range(len(cases_w))],
                })
    return out


# ---------------- selftest -------------------------------------------------


def selftest_init():
    """Create the tiny self-test manifest (1_add8 only, 4 tasks)."""
    d = SELFTEST_DIR
    d.mkdir(parents=True, exist_ok=True)
    cases = [{
        "case_id": "1_add8_err_0.0299377_size_63_depth_12",
        "width": 8, "family": "add8", "n_pi": 16, "output_bits": 9,
        "approx_blif": str(PROJECT_ROOT / "tools" / "cache" / "VACSEM"
                           / "Circuit2Cnf" / "input" / "add8"
                           / "1_add8_err_0.0299377_size_63_depth_12.blif"),
        "exact_blif": str(PROJECT_ROOT / "tools" / "cache" / "VACSEM"
                          / "Circuit2Cnf" / "input" / "add8" / "add8.blif"),
        "selection_rule": "selftest", "eligible_pool_size": 1,
    }]
    kinds = ["compile_ER", "ER__D0", "ER__D1", "ER__D2"]
    tasks = []
    for o, kind in enumerate(kinds):
        tasks.append({
            "task_id": f"width8__{cases[0]['case_id']}__{kind}",
            "order": o, "width": 8, "phase": "S",
            "case_id": cases[0]["case_id"], "kind": kind,
            "distribution": kind.split("__")[1] if "__" in kind else None,
        })
    m = {
        "campaign": "C7_FORMAL_SELFTEST", "version": "v1",
        "generated": "2026-10-03",
        "frozen_config": {"timeout_s": 180, "k_values": [16, 64],
                          "distributions": ["D0", "D1", "D2", "D3", "D4", "D5"],
                          "random_seed": 42,
                          "probability_pool": ["1/8", "1/4", "1/2", "3/4", "7/8"],
                          "backend": "d4 full-variable + neutral aux",
                          "note": "selftest only; data never enters formal results"},
        "config_hash": "SELFTEST",
        "excluded_designs": [], "cases": cases, "tasks": tasks,
    }
    m["manifest_hash"] = manifest_digest(m)
    write_atomic(d / "formal_manifest.json", json.dumps(m, indent=2, default=str))
    return m


def run_selftest(clean=True):
    m = selftest_init()
    d = SELFTEST_DIR
    for sub in ("results", "logs", "wmc", "timing", "artifacts",
                "med_miters", "case_summaries", "miters"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    # cleanup previous selftest state
    if clean and (d / "formal_ledger.csv").exists():
        (d / "formal_ledger.csv").unlink()
    if clean:
        import shutil
        shutil.rmtree(d / "results", ignore_errors=True)
        shutil.rmtree(d / "logs", ignore_errors=True)
    kill_after = os.environ.get("C7_SELFTEST_KILL_AFTER")
    if kill_after:
        print(f"SELFTEST kill simulation enabled at {kill_after}")
    run_campaign(d, selftest=False, kill_after=kill_after)
    return m


def verify_selftest():
    """A-H verification of the resume self-test (see campaign prompt)."""
    d = SELFTEST_DIR
    rows = load_ledger(d)
    checks = {}
    # A: first task (compile_ER) completed on attempt 1 and was NOT re-run
    er_task = [tid for tid in rows
               if rows[tid]["metric"] == "compile_ER"]
    checks["A_first_task_attempt1"] = bool(
        er_task and rows[er_task[0]]["attempt"] == "1"
        and rows[er_task[0]]["status"] == "PASS")
    # B: killed task re-run on attempt 2
    killed = [tid for tid in rows if rows[tid]["metric"] == "ER__D0"]
    checks["B_killed_task_attempt2"] = bool(
        killed and rows[killed[0]]["attempt"] == "2"
        and rows[killed[0]]["status"] == "PASS")
    # C: later tasks completed
    later = [tid for tid in rows if rows[tid]["metric"] in ("ER__D1", "ER__D2")]
    checks["C_later_tasks_pass"] = bool(
        later and all(rows[t]["status"] == "PASS" for t in later))
    # D/E: ledger + checkpoint parseable
    checks["D_ledger_intact"] = len(rows) == 4
    cp = read_checkpoint(d)
    checks["E_checkpoint_intact"] = cp is not None and isinstance(
        cp.get("completed_task_ids"), list)
    # F/G: result JSONs valid + task_id matches; manifest hash matches
    all_json_ok = True
    for tid in rows:
        res = read_json(d / "results" / f"{tid}.json")
        if res is None or res.get("task_id") != tid:
            all_json_ok = False
    checks["F_results_json_ok"] = all_json_ok
    m = load_manifest(d)
    checks["G_manifest_hash_ok"] = (
        m["manifest_hash"] == manifest_digest(m))
    # H: ledger sha256 matches result files
    sha_ok = True
    for tid, r in rows.items():
        if r.get("sha256"):
            p = d / "results" / f"{tid}.json"
            if not p.exists() or sha256_file(p) != r["sha256"]:
                sha_ok = False
    checks["H_result_sha256_ok"] = sha_ok
    for k, v in checks.items():
        print(f"  {k}: {'OK' if v else 'FAIL'}")
    return all(checks.values())


# ---------------- main -----------------------------------------------------


def main():
    args = sys.argv[1:]
    selftest = "--selftest" in args
    if selftest:
        if "--resume" in args:
            run_selftest(clean=False)  # recovery run
            ok = verify_selftest()
            print("RESUME_SELFTEST_PASS" if ok else "RESUME_SELFTEST_FAIL")
        else:
            run_selftest(clean=True)  # initial run (may be killed)
        return
    if "--rollup" in args:
        formal_dir = FORMAL
        manifest = load_manifest(formal_dir)
        cp = read_checkpoint(formal_dir) or {}
        rollup(formal_dir, manifest, cp)
        print("ROLLUP_DONE")
        return
    task_budget = None
    time_budget = None
    if "--task-budget" in args:
        task_budget = int(args[args.index("--task-budget") + 1])
    if "--time-budget" in args:
        time_budget = float(args[args.index("--time-budget") + 1])
    formal_dir = FORMAL
    manifest = load_manifest(formal_dir)
    run_campaign(formal_dir, selftest=False, task_budget=task_budget,
                 time_budget=time_budget)


if __name__ == "__main__":
    main()
