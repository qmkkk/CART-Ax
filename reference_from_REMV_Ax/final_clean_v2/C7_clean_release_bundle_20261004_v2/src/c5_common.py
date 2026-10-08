"""Round-5 (C7 pilot) shared helpers: official tool paths, miter generation,
CNF->WMC conversion, distributions, benchmark manifest.

Tools (official, see run_report_5.md for URLs/commits):
  - VACSEM Circuit2Cnf (built from the official repo source, bundled ABC)
  - Ganak (official repo; counting via the official v2.7.0 release binary)
"""
from __future__ import annotations

import json
import re
import subprocess
from fractions import Fraction
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE = PROJECT_ROOT / "tools" / "cache"
VACSEM = CACHE / "VACSEM"
C2C = VACSEM / "Circuit2Cnf"
C2C_BIN = C2C / "build" / "core" / "Circuit2Cnf.out"
GANAK_BIN = CACHE / "ganak_linux" / "ganak"
RAW = PROJECT_ROOT / "experiments" / "raw" / "c5"
PARSED = PROJECT_ROOT / "experiments" / "parsed"
LOGS = PROJECT_ROOT / "experiments" / "logs"
CFG = PROJECT_ROOT / "experiments" / "configs"

WSL_PREFIX = ["wsl.exe", "-d", "Ubuntu", "--", "bash", "-lc"]


def wsl_path(p) -> str:
    """Convert a Windows path to the WSL /mnt/... form."""
    p = str(Path(p))
    if p.startswith("/mnt/"):
        return p
    drive, rest = p.split(":", 1)
    return "/mnt/" + drive.lower() + rest.replace("\\", "/")

# ---- benchmark manifest (fixed, dict-order selection, NOT result-driven) ----
ADD8_APPROX = sorted(p.name for p in (C2C / "input" / "add8").glob("*.blif")
                     if p.name != "add8.blif")[:5]
MULT8_APPROX = sorted(p.name for p in (C2C / "input" / "mult8").glob("*.blif")
                      if p.name != "mult8.blif")[:5]

SMALL = []   # filled by build_manifest()
SCALABILITY = ["add32", "add64", "mult12", "mult15", "mult16_new", "mac"]


def build_manifest():
    """Small correctness set (dict-order 5+5) and scalability set with their
    exact counterparts; mult14 is absent from the repo -> documented
    substitution mult16-new (see report)."""
    entries = []
    for name in ADD8_APPROX:
        entries.append({
            "id": name.replace(".blif", ""), "family": "add8",
            "approx": str(C2C / "input" / "add8" / name),
            "exact": str(C2C / "input" / "add8" / "add8.blif"),
            "output_bits": 9, "n_pi": 16, "set": "small",
        })
    for name in MULT8_APPROX:
        entries.append({
            "id": name.replace(".blif", ""), "family": "mult8",
            "approx": str(C2C / "input" / "mult8" / name),
            "exact": str(C2C / "input" / "mult8" / "mult8.blif"),
            "output_bits": 16, "n_pi": 16, "set": "small",
        })
    for key, family, out_bits in [
        ("add32", "add32", 33), ("add64", "add64", 65),
        ("mult12", "mult12", 24), ("mult15", "mult15", 30),
        ("mult16_new", "mult16-new", 32), ("mac", "mac", 17)]:
        folder = C2C / "input" / family
        exact = folder / f"{family}.blif"
        entries.append({
            "id": key, "family": family,
            "approx": str(exact), "exact": str(exact),
            "output_bits": out_bits, "n_pi": None, "set": "scalability",
        })
    return entries


# ---- distributions (exact rationals) -------------------------------------
# IMPORTANT: D4/D5 are defined relative to the *current circuit's* PI count.
# Historical R5-R7 code used a fixed length-128 vector and then sliced it,
# which accidentally made D4==D1 and D5==D2 for circuits with <128 PIs.
# Formal experiments must use named_dist()/named_dists() below.
DIST_NAMES = ("D0", "D1", "D2", "D3", "D4", "D5")


def named_dist(name: str, n_pi: int):
    """Return one exact product distribution for exactly ``n_pi`` PIs.

    D0: all 1/2; D1: all 1/4; D2: all 3/4; D3: alternating 1/4,3/4;
    D4: first half 1/4, second half 3/4; D5: reverse D4.
    """
    if n_pi <= 0:
        raise ValueError("n_pi must be positive")
    if name == "D0":
        return [Fraction(1, 2)] * n_pi
    if name == "D1":
        return [Fraction(1, 4)] * n_pi
    if name == "D2":
        return [Fraction(3, 4)] * n_pi
    if name == "D3":
        return [Fraction(1, 4) if i % 2 == 0 else Fraction(3, 4)
                for i in range(n_pi)]
    half = n_pi // 2
    if name == "D4":
        return [Fraction(1, 4) if i < half else Fraction(3, 4)
                for i in range(n_pi)]
    if name == "D5":
        return [Fraction(3, 4) if i < half else Fraction(1, 4)
                for i in range(n_pi)]
    raise KeyError(f"unknown distribution: {name}")


def named_dists(n_pi: int):
    return {name: named_dist(name, n_pi) for name in DIST_NAMES}


# Legacy compatibility only.  Do NOT slice this mapping for formal results.
# Kept so historical scripts/artifacts remain readable.
DISTS = named_dists(128)

RANDOM_POOL = [Fraction(1, 8), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4), Fraction(7, 8)]


def random_dists(seed=42, count=16, n=128):
    import random
    rng = random.Random(seed)
    out = {}
    for k in range(count):
        out[f"R{k}"] = [rng.choice(RANDOM_POOL) for _ in range(n)]
    return out


def pi_probs(dist, n_pi):
    """First n_pi probabilities of a distribution (PIs are in BLIF order)."""
    return [Fraction(p) for p in dist[:n_pi]]


# ---- miter generation via official Circuit2Cnf ---------------------------
def gen_er_cnf(entry, outdir: Path):
    """ER miter CNF for a circuit pair; returns the CNF path."""
    outdir.mkdir(parents=True, exist_ok=True)
    cnf = outdir / f"{entry['id']}_er.cnf"
    if cnf.exists():
        return cnf
    cmd = (f"cd {wsl_path(VACSEM)} && ./Circuit2Cnf/build/core/Circuit2Cnf.out -t ER "
           f"-e {wsl_path(entry['exact'])} -a {wsl_path(entry['approx'])} "
           f"-o {wsl_path(outdir)}/{entry['id']}_er.cnf")
    r = subprocess.run(WSL_PREFIX + [cmd], capture_output=True, text=True, timeout=600)
    if r.returncode != 0 or not cnf.exists():
        raise RuntimeError(f"ER miter failed for {entry['id']}: {r.stderr[-500:]}")
    return cnf




def med_bit_index(path) -> int:
    """Extract numeric MED bit index from names like *_med_12.cnf_const0."""
    m = re.search(r"_med_(\d+)", Path(path).name)
    if not m:
        raise ValueError(f"not a MED-bit artifact: {path}")
    return int(m.group(1))


def sort_med_artifacts(paths):
    """Numeric, not lexicographic, MED-bit order (0,1,2,...,10,...)."""
    return sorted(paths, key=med_bit_index)

def gen_med_cnfs(entry, width, outdir: Path):
    """MED miter CNFs (one per error bit) using the width-W absolute-error
    deviation function; returns sorted list of CNF paths."""
    outdir.mkdir(parents=True, exist_ok=True)
    dev = C2C / "input" / "deviation-function" / f"width_{width}_absolute_error.blif"
    if not dev.exists():
        raise RuntimeError(f"deviation function width {width} missing")
    cmd = (f"cd {wsl_path(VACSEM)} && ./Circuit2Cnf/build/core/Circuit2Cnf.out -t MED "
           f"-e {wsl_path(entry['exact'])} -a {wsl_path(entry['approx'])} "
           f"-d {wsl_path(dev)} "
           f"-o {wsl_path(outdir)}/{entry['id']}_med.cnf")
    r = subprocess.run(WSL_PREFIX + [cmd], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"MED miter failed for {entry['id']}: {r.stderr[-500:]}")
    cnfs = sort_med_artifacts(outdir.glob(f"{entry['id']}_med_*.cnf*"))
    if not cnfs:
        raise RuntimeError(f"no MED CNFs for {entry['id']}")
    return cnfs


def cnf_meta(cnf: Path):
    """(n_pi_max, n_vars, n_clauses, const0/const1 flag)."""
    text = cnf.read_text(errors="replace").splitlines()
    maxpi = 0
    nvars = ncls = 0
    const = None
    for l in text:
        if l.startswith("c maxPI"):
            maxpi = int(l.split()[-1])
        elif l.startswith("p cnf"):
            nvars, ncls = int(l.split()[2]), int(l.split()[3])
        elif l.startswith("c nIsolatedPIs"):
            pass
    if cnf.name.endswith("_const0"):
        const = 0
    elif cnf.name.endswith("_const1"):
        const = 1
    return maxpi, nvars, ncls, const


def active_pi_indices(blif_path) -> list:
    """Original PI indices (0-based, BLIF .inputs order) that have fanout in
    the miter network.  The CNF enumerates exactly these PIs as variables
    1..maxPI in this order, so weights must be assigned by PI index, not by
    CNF position (isolated PIs are dropped from the CNF)."""
    from blif_sim import Blif
    b = Blif(str(blif_path))
    used = set()
    for ins, _outs, _rows in b.names:
        used.update(ins)
    for _g, args, _o in b.gates:
        used.update(a for a, _, _ in args)
    return [i for i, p in enumerate(b.inputs) if p in used]


def to_wmc(cnf: Path, probs, outdir: Path, pi_indices=None):
    """Convert a VACSEM CNF to a Ganak projected-weighted CNF (.wmc).
    Projection = the CNF's primary inputs (1..maxPI); PI literal weights =
    p and 1-p (exact rationals).  Internal-variable weights are set to 1/1
    only because Ganak is explicitly projected onto the PI set; they are not
    probability-normalized (1+1 != 1).  Do not generalize this comment to
    full-variable d-DNNF evaluation, where auxiliary-variable semantics must
    be validated separately."""
    maxpi, nvars, ncls, const = cnf_meta(cnf)
    clauses = [l for l in cnf.read_text(errors="replace").splitlines()
               if l and (l[0].isdigit() or l[0] == "-")]
    out = ["c t pwmc", f"p cnf {nvars} {len(clauses)}",
           f"c p show {' '.join(str(v) for v in range(1, maxpi + 1))} 0"]
    for v in range(1, maxpi + 1):
        idx = pi_indices[v - 1] if pi_indices is not None else (v - 1)
        p = Fraction(probs[idx])
        out.append(f"c p weight {v} {p.numerator}/{p.denominator} 0")
        out.append(f"c p weight -{v} {(1 - p).numerator}/{(1 - p).denominator} 0")
    for v in range(maxpi + 1, nvars + 1):
        out.append(f"c p weight {v} 1/1 0")
        out.append(f"c p weight -{v} 1/1 0")
    out += clauses
    outdir.mkdir(parents=True, exist_ok=True)
    wmc = outdir / (cnf.stem + ".wmc")
    wmc.write_text("\n".join(out) + "\n", encoding="utf-8")
    return wmc


def run_ganak(wmc: Path, timeout=180):
    """Run official Ganak (exact, non-probabilistic, rational); returns
    (fraction_result_or_None, runtime_s, peak_rss_kb, timed_out, error)."""
    import time
    cmd = f"cd {wsl_path(CACHE)} && ./ganak_linux/ganak --mode 1 --prob 0 {wsl_path(wmc)}"
    t0 = time.time()
    try:
        r = subprocess.run(WSL_PREFIX + [cmd], capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, timeout, None, True, "timeout"
    dt = time.time() - t0
    if r.returncode != 0:
        return None, dt, None, False, (r.stdout + r.stderr)[-500:]
    m = re.search(r"c s exact arb frac (\d+)/(\d+)", r.stdout)
    if m:
        return Fraction(int(m.group(1)), int(m.group(2))), dt, None, False, ""
    m = re.search(r"c s exact arb frac (\d+)", r.stdout)
    if m:
        return Fraction(int(m.group(1)), 1), dt, None, False, ""
    m = re.search(r"c s exact arb (\S+)", r.stdout)
    if m:
        try:
            return Fraction(m.group(1)), dt, None, False, ""
        except ValueError:
            return None, dt, None, False, f"parse: {r.stdout[-200:]}"
    return None, dt, None, False, (r.stdout + r.stderr)[-300:]


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
