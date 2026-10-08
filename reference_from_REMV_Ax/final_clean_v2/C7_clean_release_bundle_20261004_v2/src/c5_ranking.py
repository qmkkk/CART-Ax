"""Exact ranking-shift analysis for C7.

Primary ranking comparisons are performed *within circuit family* (e.g. add8
with add8, mult8 with mult8).  Ranking adders and multipliers together is not
scientifically meaningful because they implement different functions and,
especially for MED, live on different error scales.

Kendall correlation is tau-b, including tie correction.  Historical R5 used
(C-D)/(C+D), which ignores ties and is not Kendall tau-b.
"""
from __future__ import annotations

import json
import math
import sys
from fractions import Fraction
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))

from c5_common import DIST_NAMES, save_json, PARSED  # noqa: E402


def rank(seq):
    """Standard competition ranking (ties share the same rank)."""
    order = sorted(range(len(seq)), key=lambda i: seq[i])
    ranks = [0] * len(seq)
    r = 1
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and seq[order[j + 1]] == seq[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = r
        r += j - i + 1
        i = j + 1
    return ranks


def kendall_tau_b(a, b):
    """Kendall tau-b for two rank vectors, with ties handled correctly."""
    n = len(a)
    conc = disc = tie_a_only = tie_b_only = 0
    for i in range(n):
        for j in range(i + 1, n):
            da = a[i] - a[j]
            db = b[i] - b[j]
            if da == 0 and db == 0:
                continue
            if da == 0:
                tie_a_only += 1
            elif db == 0:
                tie_b_only += 1
            elif da * db > 0:
                conc += 1
            else:
                disc += 1
    den = math.sqrt((conc + disc + tie_a_only) *
                    (conc + disc + tie_b_only))
    return (conc - disc) / den if den else 0.0


def inversions(a, b):
    """Strict pairwise order reversals; ties are not counted as inversions."""
    cnt = 0
    for i in range(len(a)):
        for j in range(i + 1, len(a)):
            da = a[i] - a[j]
            db = b[i] - b[j]
            if da * db < 0:
                cnt += 1
    return cnt


def analyze_family(gt, family, circuits):
    out = {}
    for metric in ("er", "med"):
        values = {
            d: [Fraction(gt["results"][c]["distributions"][d]
                         [f"{metric}_exhaustive"]) for c in circuits]
            for d in DIST_NAMES
        }
        ranks = {d: rank(values[d]) for d in DIST_NAMES}
        r0 = ranks["D0"]
        per_dist = {}
        for d in DIST_NAMES:
            per_dist[d] = {
                "ranks": ranks[d],
                "inversions_vs_D0": inversions(r0, ranks[d]),
                "kendall_tau_b_vs_D0": round(kendall_tau_b(r0, ranks[d]), 6),
                "rank_shift": [ranks[d][i] - r0[i]
                               for i in range(len(circuits))],
            }
        out[metric] = {
            "family": family,
            "circuits": circuits,
            "values": {d: [str(v) for v in values[d]] for d in DIST_NAMES},
            "per_distribution": per_dist,
        }
    return out


def main():
    gt = json.loads((PARSED / "c5_ground_truth.json").read_text(encoding="utf-8"))
    by_family = {}
    for cid, row in gt["results"].items():
        by_family.setdefault(row["family"], []).append(cid)

    out = {
        "note": ("Primary ranking is within family. Kendall correlation is "
                 "tau-b with tie correction. Historical mixed add8+mult8 "
                 "ranking is intentionally not reproduced as a scientific result."),
        "families": {},
    }
    for family, circuits in sorted(by_family.items()):
        out["families"][family] = analyze_family(gt, family, circuits)

    save_json(PARSED / "c5_ranking.json", out)
    for family, fam in out["families"].items():
        for metric in ("er", "med"):
            print(f"== {family} {metric} ==")
            for d in DIST_NAMES:
                p = fam[metric]["per_distribution"][d]
                print(f"  {d}: inv={p['inversions_vs_D0']} "
                      f"tau_b={p['kendall_tau_b_vs_D0']} "
                      f"shift={p['rank_shift']}")


if __name__ == "__main__":
    main()
