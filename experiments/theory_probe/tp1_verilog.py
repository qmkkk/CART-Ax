"""tp1_verilog.py — minimal gate-level Verilog simulator for EvoApproxLib add12 designs.

Parses `assign LHS = expr;` statements (operators: & | ^ ! ~, bit-select A[i], constants 1'b0/1'b1)
into a topological order and compiles a single Python function f(x:int)->O:int via exec.
24-bit packed input: A = x[11:0], B = x[23:12]; output O is 13 bits.

This is a probe-side simulator (NOT a compiler rewrite); correctness is validated against the
authoritative v2 MED/ER values at distribution endpoints (D0/D1/D2...).
"""
from __future__ import annotations

import re
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from tp_paths import add12_dir  # noqa: E402

ADD12_DIR = add12_dir()
N_BITS = 12


def parse_module(text: str):
    """Return list of (lhs, expr_str) in file order for `assign` lines."""
    assigns = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"assign\s+(.+?)\s*=\s*(.+?);$", line)
        if m:
            assigns.append((m.group(1).strip(), m.group(2).strip()))
    return assigns


def lhs_name(lhs: str) -> str:
    """Normalize LHS to a Python identifier: sig_25 -> sig_25, O[4] -> O4, n_0 -> n_0."""
    if lhs.startswith("O["):
        return "O" + lhs[2:-1]
    return lhs


def to_py_expr(e: str) -> str:
    """Translate a Verilog boolean expression to Python bit-expr over names."""
    e = e.strip()
    # constants
    e = e.replace("1'b0", "0").replace("1'b1", "1")
    # bit selects
    e = re.sub(r"\bA\[(\d+)\]", r"(A>>\1)&1", e)
    e = re.sub(r"\bB\[(\d+)\]", r"(B>>\1)&1", e)
    e = re.sub(r"\bO\[(\d+)\]", r"O\1", e)  # only if used inside expr (should not happen)
    # unary ! and ~ -> not_
    e = re.sub(r"!\(([^()]*(?:\([^()]*\)[^()]*)*)\)", r"(1-(\1))", e)
    e = re.sub(r"~(\w+)", r"(1-(\1))", e)
    e = re.sub(r"~\(([^()]*)\)", r"(1-(\1))", e)
    return e


def topo_sort(assigns):
    """Order assigns so every RHS name is defined earlier. Names = LHS of any assign."""
    defined = set()
    order = []
    remaining = list(assigns)
    while remaining:
        progress = False
        for a in list(remaining):
            lhs, rhs = a
            names = set(re.findall(r"\b(sig_\d+|n_\d+|O\d+)\b", to_py_expr(rhs)))
            # O names never appear in RHS for these designs; only sig_/n_ matter
            need = {x for x in names if x.startswith(("sig_", "n_"))}
            if need <= defined:
                order.append(a)
                defined.add(lhs_name(lhs))
                remaining.remove(a)
                progress = True
        if not progress:
            raise RuntimeError(f"cycle or unresolved assigns: {remaining[:5]}")
    return order


def build_func(text: str):
    """Compile the module into f(x:int)->O:int."""
    assigns = parse_module(text)
    order = topo_sort(assigns)
    lines = ["def f(x):", "    A = x & 0xFFF", "    B = (x >> 12) & 0xFFF"]
    for lhs, rhs in order:
        name = lhs_name(lhs)
        expr = to_py_expr(rhs)
        if name.startswith("O"):
            lines.append(f"    {name} = {expr}")
        else:
            lines.append(f"    {name} = {expr}")
    outs = [n for n, _ in [(lhs_name(l), r) for l, r in order] if n.startswith("O")]
    # ensure all outputs present (some may be assigned)
    odefs = sorted({int(o[1:]) for o in outs})
    lines.append("    O = 0")
    for b in range(N_BITS + 1):
        nm = f"O{b}"
        if nm in {o for o in outs}:
            lines.append(f"    O |= {nm} << {b}")
        else:
            lines.append(f"    # O[{b}] unassigned (treated as 0)")
    lines.append("    return O")
    code = "\n".join(lines)
    ns = {}
    exec(code, ns)
    return ns["f"], code


def load_design(name: str):
    """name without .v, e.g. 'add12u_054'."""
    text = (ADD12_DIR / f"{name}.v").read_text(encoding="utf-8", errors="replace")
    return build_func(text)


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "add12u_054"
    f, code = load_design(name)
    print(f"[{name}] compiled. sample f(0x000):", f(0))
    print(f"[{name}] sample f(0x001):", f(0x001))
    print(f"[{name}] sample f(0x000123):", f(0x000123))
    # quick exhaustive on low 12 bits only (A varies, B=0) for a smoke test
    from fractions import Fraction
    tot = Fraction(0)
    cnt = 0
    for x in range(1 << 12):
        o = f(x)
        exact = x + 0
        e = abs(exact - o)
        tot += e
        if e != 0:
            cnt += 1
    print(f"[{name}] B=0 sweep: sumE={tot}, errcnt={cnt} (D0 full sweep not done here)")
