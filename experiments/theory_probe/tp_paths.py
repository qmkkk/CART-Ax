"""tp_paths.py — unified path resolution for PROJECT_4 probes.

Supports BOTH layouts:
  (a) in-project layout:  <root>/workloads/imported/add12, <root>/experiments/theory_probe/cnf,
                          <root>/experiments/results
  (b) clean-bundle layout: <root>/workloads/add12, <root>/nnfs/cnf, <root>/data

Resolution order (first hit wins):
  1. environment variable PROJECT4_ROOT (explicit override);
  2. automatic detection from the module location (parents[2] must be the root in
     both layouts: src/... and experiments/theory_probe/... are both two levels deep).

No hard-coded legacy directory names in probe code beyond the candidates listed here.
"""
from __future__ import annotations

import os
from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parent

def project_root() -> Path:
    env = os.environ.get("PROJECT4_ROOT")
    if env:
        return Path(env)
    if _MODULE_DIR.name == "theory_probe":
        # project layout: <root>/experiments/theory_probe -> parents[1] = project root
        return _MODULE_DIR.parents[1]
    # bundle layout: <root>/src -> parents[0] = bundle root
    return _MODULE_DIR.parents[0]

ROOT = project_root()

def _first(*cands) -> Path:
    for c in cands:
        p = Path(c)
        if p.exists():
            return p
    return Path(cands[0])  # fall back to the bundle layout candidate

def add12_dir() -> Path:
    return _first(ROOT / "workloads" / "add12",          # bundle layout
                  ROOT / "workloads" / "imported" / "add12")  # project layout

def cnf_dir() -> Path:
    return _first(ROOT / "nnfs" / "cnf",                 # bundle layout
                  ROOT / "experiments" / "theory_probe" / "cnf")  # project layout

def data_dir() -> Path:
    return _first(ROOT / "data",                         # bundle layout
                  ROOT / "experiments" / "theory_probe")  # project layout

def results_dir() -> Path:
    return _first(ROOT / "data",                         # bundle layout (authoritative CSVs)
                  ROOT / "experiments" / "results")      # project layout

def out_dir() -> Path:
    """Where probe outputs are written (project layout; bundle layout keeps ./data read-only)."""
    return ROOT / "experiments" / "theory_probe" if (ROOT / "experiments").exists() else ROOT / "data"
