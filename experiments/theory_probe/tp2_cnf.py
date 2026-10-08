"""tp2_cnf.py — Tseitin CNF construction for the (Ce,Ca) ER / MED-bit predicates.

Gate network built from:
  - approximate adder O  : parsed EvoApproxLib Verilog (tp1_verilog.to_py_expr AST)
  - exact adder ye       : A+B (13-bit ripple carry)
  - abs error E = |ye-ya|: comparator gt=(ye>ya), two 13-bit subtractors, per-bit mux
  - ER root              : OR over E bits (E != 0)
  - MED-bit root b       : E_b

PI variable order: A[0..11] -> 1..12, B[0..11] -> 13..24 (matches Round-1 exhaustive
bucket grouping order 'contig'). All gates -> Tseitin aux variables.
Standard d4 -dDNNF consumes the output CNF.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
import tp_paths  # noqa: E402
PROJECT_ROOT = tp_paths.ROOT
sys.path.insert(0, str(PROJECT_ROOT / "experiments" / "theory_probe"))
from tp1_verilog import parse_module, to_py_expr, topo_sort  # noqa: E402

CNFDIR = tp_paths.cnf_dir()


class Net:
    """Gate DAG with Tseitin variable allocation."""

    def __init__(self, n_pi=24):
        self.n_pi = n_pi
        self.var = list(range(1, n_pi + 1))          # var[i] = literal-var of PI i
        self.const0 = n_pi + 1                       # dedicated constant-0 variable
        self.const1 = n_pi + 2                       # dedicated constant-1 variable
        self.next_var = n_pi + 3
        self.gates = {}                              # node -> (op, args)
        self.clauses = []

    def alloc(self):
        v = self.next_var
        self.next_var += 1
        return v

    def mk(self, op, *args):
        """Tseitin-encode a gate and return its output variable (node)."""
        # full constant folding: constants are ints 0/1, but PI vars occupy 1..24,
        # so no gate may keep a bare 0/1 argument (avoids PI/const ambiguity)
        c0, c1 = self.const0, self.const1
        if op == "not":
            a = args[0]
            if a == c0:
                return c1
            if a == c1:
                return c0
        else:
            a, b = args
            if op == "and":
                if a == c0 or b == c0:
                    return c0
                if a == c1:
                    return b
                if b == c1:
                    return a
            elif op == "or":
                if a == c1 or b == c1:
                    return c1
                if a == c0:
                    return b
                if b == c0:
                    return a
            elif op == "xor":
                if a == c0:
                    return b
                if b == c0:
                    return a
                if a == c1:
                    return self.mk("not", b)
                if b == c1:
                    return self.mk("not", a)
            elif op == "xnor":
                if a == c1:
                    return b
                if b == c1:
                    return a
                if a == c0:
                    return self.mk("not", b)
                if b == c0:
                    return self.mk("not", a)
        v = self.alloc()
        if op == "not":
            a = args[0]
            self.clauses.append([v, a])
            self.clauses.append([-v, -a])
        elif op == "and":
            a, b = args
            self.clauses.append([-v, a])
            self.clauses.append([-v, b])
            self.clauses.append([v, -a, -b])
        elif op == "or":
            a, b = args
            self.clauses.append([v, -a])
            self.clauses.append([v, -b])
            self.clauses.append([-v, a, b])
        elif op == "xor":
            a, b = args
            self.clauses.append([-v, a, b])
            self.clauses.append([-v, -a, -b])
            self.clauses.append([v, -a, b])
            self.clauses.append([v, a, -b])
        elif op == "xnor":
            a, b = args
            self.clauses.append([v, a, b])
            self.clauses.append([v, -a, -b])
            self.clauses.append([-v, -a, b])
            self.clauses.append([-v, a, -b])
        elif op == "const":
            pass
        else:
            raise ValueError(op)
        self.gates[v] = (op, args)
        return v

    def const(self, val):
        if val == 0:
            return self.mk("const") if False else None
        return None

    def lit(self, pi_idx):
        """var of PI pi_idx (0-based) -> var number."""
        return self.var[pi_idx]

    def write(self, path, root):
        clauses = [c for c in self.clauses if c]
        # unit clamps: const0 = 0, const1 = 1, root = 1
        out = [f"p cnf {self.next_var - 1} {len(clauses) + 3}"]
        for c in clauses:
            out.append(" ".join(str(x) for x in c) + " 0")
        out.append(f"-{self.const0} 0")
        out.append(f"{self.const1} 0")
        out.append(f"{root} 0")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(out) + "\n", encoding="utf-8")


# ---- expression -> gate (via Python AST of to_py_expr output) ----------

class GateBuilder:
    def __init__(self, net: Net, a_lo, a_hi, b_lo, b_hi):
        self.net = net
        self.a_lo, self.a_hi = a_lo, a_hi
        self.b_lo, self.b_hi = b_lo, b_hi
        self.cache = {}

    def node(self, e):
        if isinstance(e, ast.BinOp):
            op = type(e.op)
            l = self.node(e.left)
            r = self.node(e.right)
            if op is ast.BitAnd:
                return self.net.mk("and", l, r)
            if op is ast.BitOr:
                return self.net.mk("or", l, r)
            if op is ast.BitXor:
                return self.net.mk("xor", l, r)
            if op is ast.Sub:
                # only for constants 1 - x handled below; bitwise sub not used
                raise ValueError(f"Sub not supported: {ast.dump(e)}")
            raise ValueError(f"op {op}")
        if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.USub):
            # -(x) never appears
            raise ValueError("USub")
        if isinstance(e, ast.Constant):
            return 0 if e.value == 0 else 1
        if isinstance(e, ast.Name):
            if e.id in self.cache:
                return self.cache[e.id]
            raise ValueError(f"unknown name {e.id}")
        if isinstance(e, ast.BinOp):
            pass
        raise ValueError(f"unsupported node {ast.dump(e)}")

    def build_expr(self, expr):
        """expr is a Python-expression string from to_py_expr (over A>>i / B>>i / names)."""
        t = ast.parse(expr, mode="eval")
        return self._build(t.body)

    def _build(self, e):
        if isinstance(e, ast.Constant):
            return 0 if e.value == 0 else 1
        if isinstance(e, ast.BinOp):
            if isinstance(e.op, ast.BitAnd):
                return self.net.mk("and", self._build(e.left), self._build(e.right))
            if isinstance(e.op, ast.BitOr):
                return self.net.mk("or", self._build(e.left), self._build(e.right))
            if isinstance(e.op, ast.BitXor):
                return self.net.mk("xor", self._build(e.left), self._build(e.right))
            if isinstance(e.op, ast.Sub):
                return self._sub(self._build(e.left), self._build(e.right))
            raise ValueError(f"BinOp {type(e.op)}")
        if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.Not):
            return self.net.mk("not", self._build(e.operand))
        if isinstance(e, ast.BinOp):
            pass
        raise ValueError(f"unsupported {ast.dump(e)}")

    def _sub(self, a, b):
        return self.net.mk("and", self.net.mk("not", b), a) if False else self.net.mk("xor", a, b)

    def bit_of(self, name, i, side):
        # handled by converting expr to explicit (A>>i)&1 earlier; here we intercept
        # names A[i]/B[i] already converted to ((A>>i)&1) by to_py_expr -> treat as PI
        return None


def _pi_var(expr_str, net: Net, gb):
    """to_py_expr produced '((A>>i)&1)' or '((B>>i)&1)' or '1'/'0' or wire names."""
    e = ast.parse(expr_str, mode="eval").body
    if isinstance(e, ast.Constant):
        return 0 if e.value == 0 else 1
    # pattern: ((A>>k)&1)
    if isinstance(e, ast.BinOp) and isinstance(e.op, ast.BitAnd):
        l = e.left
        if isinstance(l, ast.BinOp) and isinstance(l.op, ast.RShift):
            base = l.left
            if isinstance(base, ast.Name) and base.id in ("A", "B"):
                k = l.right.value
                idx = k if base.id == "A" else 12 + k
                return net.lit(idx)
    raise ValueError(f"cannot map PI expr: {expr_str}")


def approx_network(net: Net, assigns_topo):
    """Encode the Verilog assign statements; returns {wire_name: var}."""
    wires = {}
    for lhs, rhs in assigns_topo:
        # rhs already translated to Python expr string
        name = lhs if lhs.startswith("sig_") or lhs.startswith("n_") else None
        pexpr = to_py_expr(rhs)
        e = ast.parse(pexpr, mode="eval").body
        if isinstance(e, ast.Constant):
            var = 0 if e.value == 0 else 1
        else:
            var = _build_gate(e, net)
        if lhs.startswith("O["):
            wires[lhs] = var
        else:
            wires[lhs] = var
    return wires


def _build_gate(e, net, wires=None):
    """Recursive gate builder over Python AST of a translated expr."""
    if isinstance(e, ast.Constant):
        return net.const0 if e.value == 0 else net.const1
    if isinstance(e, ast.Name):
        if wires is not None and e.id in wires:
            return wires[e.id]
        raise ValueError(f"unresolved wire name {e.id} (topo order bug)")
    # PI bit-select pattern: ((A|B) >> k) possibly masked with &1
    if isinstance(e, ast.BinOp) and isinstance(e.op, ast.RShift):
        base = e.left
        if isinstance(base, ast.Name) and base.id in ("A", "B"):
            k = e.right.value
            return net.lit(k if base.id == "A" else 12 + k)
    if isinstance(e, ast.BinOp):
        op = type(e.op)
        l = _build_gate(e.left, net, wires)
        r = _build_gate(e.right, net, wires)
        if op is ast.BitAnd:
            if l == net.const1:
                return r
            if r == net.const1:
                return l
            if l == net.const0 or r == net.const0:
                return net.const0
            return net.mk("and", l, r)
        if op is ast.BitOr:
            if l == net.const0:
                return r
            if r == net.const0:
                return l
            if l == net.const1 or r == net.const1:
                return net.const1
            return net.mk("or", l, r)
        if op is ast.BitXor:
            if l == net.const0:
                return r
            if r == net.const0:
                return l
            return net.mk("xor", l, r)
        if op is ast.Sub:
            # only '1 - expr' (from Verilog ! translation); 1 - x == not x
            if isinstance(e.left, ast.Constant) and e.left.value == 1:
                if r == net.const0:
                    return net.const1
                if r == net.const1:
                    return net.const0
                return net.mk("not", r)
            raise ValueError(f"Sub with non-1 minuend: {ast.dump(e)}")
    if isinstance(e, ast.UnaryOp) and isinstance(e.op, ast.Not):
        x = _build_gate(e.operand, net, wires)
        if x == net.const0:
            return net.const1
        if x == net.const1:
            return net.const0
        return net.mk("not", x)
    raise ValueError(f"gate ast {ast.dump(e)}")


# ---- exact adder / subtractor / comparator / mux -------------------------

def exact_adder(net, a_vars, b_vars, n=12):
    """ye = A + B, returns list of n+1 output vars (bit 0..n)."""
    s = []
    c = net.const0
    for i in range(n):
        t = net.mk("xor", a_vars[i], b_vars[i])
        s_i = net.mk("xor", t, c)
        # carry: (a&b) | (c & t)
        ab = net.mk("and", a_vars[i], b_vars[i])
        ct = net.mk("and", c, t)
        c = net.mk("or", ab, ct)
        s.append(s_i)
    s.append(c)
    return s


def subtractor(net, x_vars, y_vars, n=13):
    """d = x - y (ripple borrow), returns (d[0..n-1], borrow_out)."""
    d = []
    b = net.const0
    for i in range(n):
        t = net.mk("xor", x_vars[i], y_vars[i])       # x^y
        d_i = net.mk("xor", t, b)                     # d = t ^ borrow
        nx = net.mk("not", x_vars[i])
        nxa = net.mk("and", nx, y_vars[i])            # (not x) & y
        nt = net.mk("not", t)
        btb = net.mk("and", nt, b)                    # (not t) & borrow
        b = net.mk("or", nxa, btb)
        d.append(d_i)
    return d, b


def comparator_gt(net, x_vars, y_vars, n=13):
    """gt = (x > y) over n-bit vectors (MSB first comparison)."""
    gt = net.const0
    eq = net.const1
    for i in range(n - 1, -1, -1):
        xi, yi = x_vars[i], y_vars[i]
        gt_i = net.mk("and", xi, net.mk("not", yi))
        gteq = net.mk("and", gt_i, eq)
        gt = net.mk("or", gt, gteq)
        eq_i = net.mk("xnor", xi, yi)
        eq = net.mk("and", eq, eq_i)
    return gt


def build_circuit(design_name):
    """Full gate net for one approx design; returns net + e_bits (13 vars) + er_root."""
    from tp1_verilog import ADD12_DIR
    text = (ADD12_DIR / f"{design_name}.v").read_text(encoding="utf-8", errors="replace")
    assigns = parse_module(text)
    assigns_topo = topo_sort(assigns)

    net = Net(n_pi=24)
    a_vars = [net.lit(i) for i in range(12)]
    b_vars = [net.lit(12 + i) for i in range(12)]

    # approximate adder outputs O[0..12]
    o_vars = [None] * 13
    wires = {}
    # build in topological order; O[i] assigned to wires
    # but to_py_expr names O[..] -> we need the wire var; process assigns with name resolution
    # simple approach: two passes (wires may be referenced before definition handled by topo_sort)
    for lhs, rhs in assigns_topo:
        pexpr = to_py_expr(rhs)
        e = ast.parse(pexpr, mode="eval").body
        var = _build_gate(e, net, wires)
        wires[lhs] = var
    for lhs, var in wires.items():
        if lhs.startswith("O["):
            b = int(lhs[2:-1])
            o_vars[b] = var
    for b in range(13):
        if o_vars[b] is None:
            o_vars[b] = net.const0

    # exact adder
    ye = exact_adder(net, a_vars, b_vars, n=12)      # 13 bits

    # subtractors (13-bit) and comparator
    d1, _ = subtractor(net, ye, o_vars, 13)          # ye - O
    d2, _ = subtractor(net, o_vars, ye, 13)          # O - ye
    gt = comparator_gt(net, ye, o_vars, 13)
    e_bits = []
    for b in range(13):
        gt_d1 = net.mk("and", gt, d1[b])
        ngt = net.mk("not", gt)
        ngt_d2 = net.mk("and", ngt, d2[b])
        e_bits.append(net.mk("or", gt_d1, ngt_d2))

    er_root = e_bits[0]
    for b in range(1, 13):
        er_root = net.mk("or", er_root, e_bits[b])
    return net, e_bits, er_root


def write_cnfs(design_name, outdir=CNFDIR):
    net, e_bits, er_root = build_circuit(design_name)
    n_const = 0
    if er_root == net.const0:
        print(f"[{design_name}] ER identically 0 (skip)")
    elif er_root == net.const1:
        print(f"[{design_name}] ER identically 1 (skip)")
        n_const += 1
    else:
        net.write(outdir / f"{design_name}_er.cnf", er_root)
    n_skipped = 0
    for b in range(13):
        if e_bits[b] == net.const0:
            n_skipped += 1
        elif e_bits[b] == net.const1:
            n_skipped += 1
        else:
            net.write(outdir / f"{design_name}_med_{b}.cnf", e_bits[b])
    return net.next_var - 1, len(net.clauses), n_skipped


# ---------------------------------------------------------------------------
# BLIF input support (VACSEM official BLIF, arbitrary width) — FORMAL CAMPAIGN
# Semantics: .names <ins> <out> rows  =  out = OR of matching rows (val=1).
# A 2-input single-row table encodes one AND-of-literals (match pattern).
# ---------------------------------------------------------------------------

def _blif_names_table(blif_path):
    """Parse VACSEM BLIF: returns (input_order, outputs_order, tables) where
    tables = list of (ins, outs, rows) with ins/outs as signal-name lists."""
    text = Path(blif_path).read_text(encoding="utf-8", errors="replace")
    inputs, outputs, tables = [], [], []
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(".inputs"):
            inputs = [t for t in line.split()[1:] if t and t != "\\"]
            while lines[i].endswith("\\"):
                i += 1
                inputs += [t for t in lines[i].split() if t and t != "\\"]
        elif line.startswith(".outputs"):
            outputs = [t for t in line.split()[1:] if t and t != "\\"]
            while lines[i].endswith("\\"):
                i += 1
                outputs += [t for t in lines[i].split() if t and t != "\\"]
        elif line.startswith(".names"):
            toks = line.split()
            ins = toks[1:-1]
            outs = [toks[-1]]
            rows = []
            i += 1
            while i < len(lines) and lines[i] and not lines[i].startswith("."):
                parts = lines[i].split()
                if len(parts) == 2:
                    rows.append((parts[0], int(parts[1])))
                i += 1
            tables.append((ins, outs, rows))
            continue
        elif line.startswith(".model") or line.startswith(".end") or line.startswith("."):
            pass
        i += 1
    return inputs, outputs, tables


def _and_all(net, lits):
    if not lits:
        return net.const1
    acc = lits[0]
    for x in lits[1:]:
        acc = net.mk("and", acc, x)
    return acc


def _or_all(net, lits):
    acc = net.const0
    for x in lits:
        acc = net.mk("or", acc, x)
    return acc


def _blif_gate(net, ins, rows, defined):
    """Encode one .names table as a gate variable (OR of matching val=1 rows)."""
    if not ins:
        return net.const1 if rows and rows[0][1] == 1 else net.const0
    lits = []
    for pat, val in rows:
        if val == 0:
            continue
        terms = []
        for name, ch in zip(ins, pat):
            if ch == "-":
                continue
            var = defined[name]
            terms.append(var if ch == "1" else net.mk("not", var))
        lits.append(_and_all(net, terms))
    return _or_all(net, lits)


def _blif_signal_var(net, name, width):
    """a[k] -> var k+1, b[k] -> var width+k+1; wires handled by caller via defined map."""
    import re
    m = re.match(r"a\[(\d+)\]", name)
    if m:
        return net.lit(int(m.group(1)))
    m = re.match(r"b\[(\d+)\]", name)
    if m:
        return net.lit(width + int(m.group(1)))
    raise ValueError(f"unexpected input signal: {name}")


def build_circuit_blif(blif_path, width):
    """Gate network for a VACSEM BLIF approximate adder (arbitrary width).
    PI order: a[0..w-1] -> var 1..w, b[0..w-1] -> var w+1..2w (matches 12-bit map).
    Returns (net, e_bits(width+1), er_root)."""
    inputs, outputs, tables = _blif_names_table(blif_path)
    n_pi = 2 * width
    net = Net(n_pi=n_pi)
    a_vars = [net.lit(i) for i in range(width)]
    b_vars = [net.lit(width + i) for i in range(width)]
    # exact adder
    ye = exact_adder(net, a_vars, b_vars, n=width)
    # approximate adder outputs o[000]..o[width] via topological table processing
    defined = {}
    for i, name in enumerate(inputs):
        defined[name] = net.lit(i)
    remaining = list(tables)
    while remaining:
        progress = False
        for t in list(remaining):
            ins, outs, rows = t
            if all(x in defined for x in ins):
                var = _blif_gate(net, ins, rows, defined)
                for o in outs:
                    defined[o] = var
                remaining.remove(t)
                progress = True
        if not progress:
            raise RuntimeError(f"BLIF cycle/unresolved tables: {remaining[:3]}")
    o_vars = [defined.get(f"o[{k:03d}]") for k in range(width + 1)]
    for k in range(width + 1):
        if o_vars[k] is None:
            o_vars[k] = net.const0
    # abs error |ye - O| (width+1 bits)
    nb = width + 1
    d1, _ = subtractor(net, ye, o_vars, nb)
    d2, _ = subtractor(net, o_vars, ye, nb)
    gt = comparator_gt(net, ye, o_vars, nb)
    e_bits = []
    for k in range(nb):
        gt_d1 = net.mk("and", gt, d1[k])
        ngt = net.mk("not", gt)
        ngt_d2 = net.mk("and", ngt, d2[k])
        e_bits.append(net.mk("or", gt_d1, ngt_d2))
    er_root = e_bits[0]
    for k in range(1, nb):
        er_root = net.mk("or", er_root, e_bits[k])
    return net, e_bits, er_root


def write_cnfs_blif(blif_path, width, outdir):
    """Write ER + (width+1) MED-bit CNFs for a BLIF design into outdir."""
    net, e_bits, er_root = build_circuit_blif(blif_path, width)
    stem = Path(blif_path).stem
    n_skip = 0
    if er_root not in (net.const0, net.const1):
        net.write(outdir / f"{stem}_er.cnf", er_root)
    else:
        n_skip += 1
    for k in range(width + 1):
        if e_bits[k] in (net.const0, net.const1):
            n_skip += 1
        else:
            net.write(outdir / f"{stem}_med_{k}.cnf", e_bits[k])
    return net.next_var - 1, len(net.clauses), n_skip


# ---------------------------------------------------------------------------
# VACSEM miter BLIF support (.gate format) — authoritative 16/32/64-bit source
# ---------------------------------------------------------------------------

def _gate_to_net(net, gname, vals):
    """Map a blif_sim gate name to Net gates (multi-input via chains)."""
    if gname in ("zero", "const0"):
        return net.const0
    if gname in ("one", "const1"):
        return net.const1
    if gname == "inv1":
        return net.mk("not", vals[0])
    if gname == "buf":
        return vals[0]
    if gname == "and2":
        return net.mk("and", vals[0], vals[1])
    if gname == "or2":
        return net.mk("or", vals[0], vals[1])
    if gname == "nand2":
        return net.mk("not", net.mk("and", vals[0], vals[1]))
    if gname == "nor2":
        return net.mk("not", net.mk("or", vals[0], vals[1]))
    if gname == "xor2":
        return net.mk("xor", vals[0], vals[1])
    if gname == "xnor2":
        return net.mk("xnor", vals[0], vals[1])
    if gname == "and3":
        return net.mk("and", net.mk("and", vals[0], vals[1]), vals[2])
    if gname == "or3":
        return net.mk("or", net.mk("or", vals[0], vals[1]), vals[2])
    if gname == "mux21":
        # ports: a=sel0-value, b=sel1-value, s=select (blif_sim: a[1] if a[2] else a[0])
        return net.mk("or", net.mk("and", vals[0], net.mk("not", vals[2])),
                      net.mk("and", vals[1], vals[2]))
    raise ValueError(f"unsupported gate {gname}")


def build_miter_net(blif_path, n_pi, output_names):
    """Build a Net from a VACSEM .gate miter BLIF.
    output_names: list of output signal names to return (each mapped to its var).
    Returns (net, {output_name: var})."""
    import sys as _sys
    from pathlib import Path as _P
    import tp_paths as _tp
    _src_py = _tp.ROOT / "src" / "python"
    if str(_src_py) not in _sys.path:
        _sys.path.insert(0, str(_src_py))
    from blif_sim import Blif  # frozen REMV-Ax parser (src/python)
    b = Blif(str(blif_path))
    net = Net(n_pi=n_pi)
    defined = {}
    for i, inp in enumerate(b.inputs):
        defined[inp] = net.lit(i)
    # .names tables first (if any)
    for ins, outs, rows in b.names:
        if all(x in defined for x in ins):
            var = _blif_gate(net, ins, rows, defined)
            for o in outs:
                defined[o] = var
    # .gate elements, topological
    remaining = list(b.gates)
    while remaining:
        progress = False
        for g in list(remaining):
            gname, args, out = g
            ins = [a[0] for a in args]
            if all(x in defined for x in ins):
                vals = []
                for (name, neg, _port) in args:
                    v = defined[name]
                    vals.append(net.mk("not", v) if neg else v)
                var = _gate_to_net(net, gname, vals)
                out_name, out_neg = out
                defined[out_name] = net.mk("not", var) if out_neg else var
                remaining.remove(g)
                progress = True
        if not progress:
            raise RuntimeError(f"miter cycle/unresolved gates: {remaining[:3]}")
    return net, {o: defined.get(o) for o in output_names}


def write_cnfs_miter(er_blif, med_blif_dir, design, width, outdir):
    """Write ER + (width+1) MED-bit CNFs from VACSEM miter BLIFs.
    er_blif: ER miter path; med_blif_dir: directory with {design}_med_{k}.blif."""
    from pathlib import Path as _P
    outdir = _P(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    n_pi = 2 * width
    stats = {}
    # ER
    net, outs = build_miter_net(er_blif, n_pi, ["miter"])
    root = outs["miter"]
    if root in (net.const0, net.const1):
        stats["er_skip"] = 1
    else:
        net.write(outdir / f"{design}_er.cnf", root)
    n_skip = 0
    for k in range(width + 1):
        med_blif = _P(med_blif_dir) / f"{design}_med_{k}.blif"
        if not med_blif.exists():
            n_skip += 1
            continue
        net2, outs2 = build_miter_net(med_blif, n_pi, [f"abs_err[{k:03d}]"])
        root2 = outs2[f"abs_err[{k:03d}]"]
        if root2 in (net2.const0, net2.const1):
            n_skip += 1
            continue
        net2.write(outdir / f"{design}_med_{k}.cnf", root2)
    return n_skip


if __name__ == "__main__":
    for name in sys.argv[1:] or ["add12u_4R6"]:
        nv, nc, nskip = write_cnfs(name)
        print(f"[{name}] vars={nv} clauses={nc}")
