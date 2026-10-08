"""Minimal BLIF simulator for exhaustive ground truth.

Handles the two BLIF dialects used by VACSEM:
  - `.names <inputs...> <output>` truth-table rows ("11 1", "00 1", "-0 1", ...)
  - `.gate <name> a=<in> b=<in> O=<out>` gate lines (inv1, and2, or2, nand2,
    nor2, xor2, xnor2, buf, and3, or3, ...), with negation encoded as
    `a=!<sig>` (used by ABC output).

All values are evaluated in topological order; used only for exhaustive
2^PI enumeration on the small 8-bit benchmark circuits (not a general tool).
"""
from __future__ import annotations

import re
from fractions import Fraction
from typing import Dict, List, Tuple


class Blif:
    def __init__(self, path):
        self.inputs: List[str] = []
        self.outputs: List[str] = []
        self.names: List[Tuple[List[str], str, List[Tuple[str, int]]]] = []
        self.gates: List[Tuple[str, List[Tuple[str, bool]], str]] = []
        self._parse(path)

    def _parse(self, path):
        lines = [l.split("#")[0].strip() for l in open(path, encoding="utf-8", errors="replace")]
        lines = [l for l in lines if l]
        i = 0
        while i < len(lines):
            line = lines[i]
            if line == ".model":
                i += 1
            elif line.startswith(".inputs"):
                toks = line.split()
                name = toks[-1]
                while name.endswith("\\"):
                    i += 1
                    toks = toks[:-1] + lines[i].split()
                    name = toks[-1]
                self.inputs += [t for t in toks[1:] if t]
            elif line.startswith(".outputs"):
                toks = line.split()
                name = toks[-1]
                while name.endswith("\\"):
                    i += 1
                    toks = toks[:-1] + lines[i].split()
                    name = toks[-1]
                self.outputs += [t for t in toks[1:] if t]
            elif line.startswith(".names"):
                toks = line.split()
                ins, outs = toks[1:-1], toks[-1]
                rows = []
                i += 1
                while i < len(lines) and lines[i] and not lines[i].startswith("."):
                    pat, val = lines[i].split()
                    rows.append((pat, int(val)))
                    i += 1
                self.names.append((ins, outs, rows))
                continue
            elif line.startswith(".gate"):
                toks = line.split()
                gname = toks[1]
                args = []
                out = None
                for t in toks[2:]:
                    k, v = t.split("=")
                    neg = v.startswith("!")
                    if k == "O":
                        out = (v[1:] if neg else v, neg)
                    else:
                        args.append((v[1:] if neg else v, neg, k))
                self.gates.append((gname, args, out))
            elif line.startswith("."):
                pass
            i += 1

    def eval(self, assign: Dict[str, int]) -> Dict[str, int]:
        """assign: {input name: 0/1} -> {signal: 0/1} including outputs."""
        vals: Dict[str, int] = dict(assign)
        for ins, outs, rows in self.names:
            if not ins:
                vals[outs] = rows[0][1]
                continue
            a = [vals[x] for x in ins]
            v = 0
            for pat, val in rows:
                ok = True
                for ai, p in zip(a, pat):
                    if p == "-":
                        continue
                    if int(p) != ai:
                        ok = False
                        break
                if ok:
                    v |= val        # BLIF .names = OR of all matching rows
            vals[outs] = v
        for gname, args, out in self.gates:
            a = []
            for name, neg, _k in args:
                v = vals[name]
                a.append(1 - v if neg else v)
            o = self._gate(gname, a)
            if out is not None:
                vals[out[0]] = 1 - o if out[1] else o
        return vals

    @staticmethod
    def _gate(name, a):
        if name in ("zero", "const0"):
            return 0
        if name in ("one", "const1"):
            return 1
        if name == "inv1":
            return 1 - a[0]
        if name == "buf":
            return a[0]
        if name == "and2":
            return a[0] & a[1]
        if name == "or2":
            return a[0] | a[1]
        if name == "nand2":
            return 1 - (a[0] & a[1])
        if name == "nor2":
            return 1 - (a[0] | a[1])
        if name == "xor2":
            return a[0] ^ a[1]
        if name == "xnor2":
            return 1 - (a[0] ^ a[1])
        if name == "and3":
            return a[0] & a[1] & a[2]
        if name == "or3":
            return a[0] | a[1] | a[2]
        if name == "mux21":
            return a[1] if a[2] else a[0]
        raise ValueError(f"unsupported gate {name}")


def evaluate(path, inputs_assign, outputs):
    """Evaluate one assignment; returns list of output values in `outputs` order."""
    b = Blif(path)
    v = b.eval(inputs_assign)
    return [v[o] for o in outputs]


def exhaustive(path, outputs):
    """Enumerate all 2^n input assignments; return (outputs_list_per_assignment,
    total).  Inputs taken from the BLIF in file order."""
    b = Blif(path)
    n = len(b.inputs)
    results = []
    for mask in range(1 << n):
        assign = {b.inputs[i]: (mask >> i) & 1 for i in range(n)}
        v = b.eval(assign)
        results.append([v[o] for o in outputs])
    return results, 1 << n


def er_med(exact_path, approx_path):
    """Exact ER and MED over ALL input assignments (exact circuits first).
    Output vectors are interpreted LSB-first bit arrays."""
    ea = Blif(exact_path)
    ap = Blif(approx_path)
    assert ea.inputs == ap.inputs, "input lists differ"
    n = len(ea.inputs)
    err_sum = 0
    err_count = 0
    for mask in range(1 << n):
        assign = {ea.inputs[i]: (mask >> i) & 1 for i in range(n)}
        ev = ea.eval(assign)
        av = ap.eval(assign)
        e_val = sum(ev[o] << k for k, o in enumerate(ea.outputs))
        a_val = sum(av[o] << k for k, o in enumerate(ap.outputs))
        d = abs(e_val - a_val)
        if d:
            err_count += 1
        err_sum += d
    tot = 1 << n
    return Fraction(err_count, tot), Fraction(err_sum, tot)


if __name__ == "__main__":
    import sys
    ea, ap = sys.argv[1], sys.argv[2]
    er, med = er_med(ea, ap)
    print(f"ER = {er} = {float(er):.10f}")
    print(f"MED = {med} = {float(med):.10f}")
