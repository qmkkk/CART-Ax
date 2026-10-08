"""tp_freeze_dists.py — EXPLICIT standalone command to (re)generate the frozen
semantic random distributions. Main probe flows must NOT regenerate or overwrite
frozen_random_dists.json; they only load it.

Usage:
    python tp_freeze_dists.py            # generate into the probe out dir
    python tp_freeze_dists.py --check    # verify existing file matches a fresh generation
"""
from __future__ import annotations

import json
import random
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tp_paths  # noqa: E402

N = 24
POOL = [Fraction(1, 8), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4), Fraction(7, 8)]


def generate(seed=42, n=N, count=10):
    rng = random.Random(seed)
    return {f"R_new{k}": [rng.choice(POOL) for _ in range(n)] for k in range(count)}


def freeze_payload():
    return {
        "seed": 42,
        "pool": [str(x) for x in POOL],
        "n_pi": N,
        "pi_map_ref": "pi_map.json",
        "note": "NEW semantic frozen random distributions (independent of legacy v2 "
                "R0-R9 tables; legacy ordering UNRECOVERED). Indexed by semantic PI "
                "per pi_map.json (var order 1..24 = A[0..11], B[0..11]). "
                "READ-ONLY: probes only load this file; regenerate only via this "
                "standalone command.",
        "dists": {k: [str(x) for x in v] for k, v in generate().items()},
    }


def main():
    out = tp_paths.out_dir() / "frozen_random_dists.json"
    if "--check" in sys.argv:
        if not out.exists():
            print("MISSING:", out)
            sys.exit(1)
        old = json.loads(out.read_text(encoding="utf-8"))
        new = freeze_payload()
        same = old["dists"] == new["dists"] and old["seed"] == new["seed"]
        print("CHECK:", "MATCH" if same else "MISMATCH")
        sys.exit(0 if same else 1)
    out.write_text(json.dumps(freeze_payload(), indent=2), encoding="utf-8")
    print("frozen:", out)


if __name__ == "__main__":
    main()
