"""
st_sim.py -- a small, time-accurate interpreter for the Structured Text
subset that our ST printer emits (code/st_printer.py).

It is used only for post-hoc analysis of the submitted Task A files
(analysis/analyze_outputs.py). It is NOT part of the submission pipeline.

Supported:
  PROGRAM ... END_PROGRAM with VAR_INPUT / VAR_OUTPUT / VAR / VAR_IN_OUT
  declarations (optional ':= init'), assignments (incl. inst.member := e),
  FB calls with named arguments, IF/ELSIF/ELSE, CASE (int labels, lists,
  ranges, ELSE), FOR, WHILE, REPEAT (bounded), RETURN.
  Expressions follow IEC 61131-3 precedence. Functions: ABS, MIN, MAX,
  LIMIT, SEL, MOD, TRUNC, *_TO_* conversions.
  Function blocks: TON, TOF, TP, CTU, CTD, R_TRIG, F_TRIG, SR, RS, with
  IEC semantics driven by an absolute clock (ms). An FB instance only
  updates when it is called, as on a real PLC.

Identifiers are case-insensitive, as in IEC 61131-3.
"""
import re

KEYWORDS = {
    "PROGRAM", "END_PROGRAM", "VAR", "VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT",
    "END_VAR", "IF", "THEN", "ELSIF", "ELSE", "END_IF", "CASE", "OF",
    "END_CASE", "FOR", "TO", "BY", "DO", "END_FOR", "WHILE", "END_WHILE",
    "REPEAT", "UNTIL", "END_REPEAT", "RETURN", "EXIT", "AND", "OR", "XOR",
    "NOT", "MOD", "TRUE", "FALSE", "AT", "CONSTANT", "RETAIN",
}

_TOKEN_RE = re.compile(r"""
    (?P<ws>\s+|//[^\n]*|\(\*.*?\*\))
  | (?P<time>(?:T|TIME)\#[0-9A-Za-z_.]+)
  | (?P<based>\d+\#[0-9A-Fa-f_]+)
  | (?P<num>\d+\.\d+(?:[eE][-+]?\d+)?|\d+)
  | (?P<addr>%[IQM][XBWD]?[0-9.]+)
  | (?P<id>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>:=|<>|<=|>=|\*\*|\.\.|[-+*/<>=():;,.&\[\]])
""", re.X | re.S)


class STError(Exception):
    pass


def parse_time_ms(text):
    body = text.split("#", 1)[1].replace("_", "").lower()
    total = 0.0
    for val, unit in re.findall(r"(\d+(?:\.\d+)?)(ms|d|h|m|s)", body):
        v = float(val)
        total += v * {"d": 86400000, "h": 3600000, "m": 60000, "s": 1000, "ms": 1}[unit]
    if not re.fullmatch(r"(?:\d+(?:\.\d+)?(?:ms|d|h|m|s))+", body):
        raise STError(f"bad time literal {text}")
    return int(round(total))


def tokenize(src):
    toks, pos = [], 0
    while pos < len(src):
        m = _TOKEN_RE.match(src, pos)
        if not m:
            raise STError(f"cannot tokenize at {src[pos:pos+20]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind == "ws":
            continue
        text = m.group(kind)
        if kind == "id" and text.upper() in KEYWORDS:
            toks.append(("kw", text.upper()))
        elif kind == "time":
            toks.append(("time", parse_time_ms(text)))
        elif kind == "based":
            b, v = text.split("#")
            toks.append(("num", int(v.replace("_", ""), int(b))))
        elif kind == "num":
            toks.append(("num", float(text) if "." in text or "e" in text.lower() else int(text)))
        else:
            toks.append((kind, text))
    toks.append(("eof", None))
    return toks


# ----------------------------------------------------------------- parser
class Parser:
    def __init__(self, src):
        self.t = tokenize(src)
        self.i = 0

    def peek(self, k=0):
        return self.t[self.i + k]

    def next(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def accept(self, kind, val=None):
        tok = self.peek()
        if tok[0] == kind and (val is None or tok[1] == val):
            self.i += 1
            return tok
        return None

    def expect(self, kind, val=None):
        tok = self.accept(kind, val)
        if tok is None:
            raise STError(f"expected {kind} {val}, got {self.peek()}")
        return tok

    def program(self):
        self.expect("kw", "PROGRAM")
        name = self.expect("id")[1]
        decls = []
        while self.peek()[0] == "kw" and self.peek()[1] in ("VAR", "VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT"):
            section = self.next()[1]
            while self.accept("kw", "CONSTANT") or self.accept("kw", "RETAIN"):
                pass
            while not self.accept("kw", "END_VAR"):
                names = [self.expect("id")[1]]
                while self.accept("op", ","):
                    names.append(self.expect("id")[1])
                addr = None
                if self.accept("kw", "AT"):
                    addr = self.expect("addr")[1]
                self.expect("op", ":")
                ty = self.expect("id")[1].upper()
                init = None
                if self.accept("op", ":="):
                    init = self.expr()
                self.expect("op", ";")
                for n in names:
                    decls.append({"name": n, "type": ty, "section": section, "init": init, "addr": addr})
        body = self.stmts({"END_PROGRAM"})
        self.expect("kw", "END_PROGRAM")
        return {"name": name, "decls": decls, "body": body}

    def stmts(self, stop):
        out = []
        while not (self.peek()[0] == "kw" and self.peek()[1] in stop) and self.peek()[0] != "eof":
            if self.accept("op", ";"):
                continue
            out.append(self.stmt())
        return out

    def stmt(self):
        tok = self.peek()
        if tok == ("kw", "IF"):
            self.next()
            branches = []
            cond = self.expr()
            self.expect("kw", "THEN")
            body = self.stmts({"ELSIF", "ELSE", "END_IF"})
            branches.append((cond, body))
            else_body = None
            while True:
                if self.accept("kw", "ELSIF"):
                    c = self.expr()
                    self.expect("kw", "THEN")
                    branches.append((c, self.stmts({"ELSIF", "ELSE", "END_IF"})))
                elif self.accept("kw", "ELSE"):
                    else_body = self.stmts({"END_IF"})
                else:
                    break
            self.expect("kw", "END_IF")
            self.accept("op", ";")
            return ("if", branches, else_body)
        if tok == ("kw", "CASE"):
            self.next()
            sel = self.expr()
            self.expect("kw", "OF")
            branches, else_body = [], None
            while True:
                if self.accept("kw", "END_CASE"):
                    break
                if self.accept("kw", "ELSE"):
                    else_body = self.stmts({"END_CASE"})
                    continue
                labels = [self.case_label()]
                while self.accept("op", ","):
                    labels.append(self.case_label())
                self.expect("op", ":")
                body = self.case_body()
                branches.append((labels, body))
            self.accept("op", ";")
            return ("case", sel, branches, else_body)
        if tok == ("kw", "FOR"):
            self.next()
            var = self.expect("id")[1]
            self.expect("op", ":=")
            a = self.expr()
            self.expect("kw", "TO")
            b = self.expr()
            step = None
            if self.accept("kw", "BY"):
                step = self.expr()
            self.expect("kw", "DO")
            body = self.stmts({"END_FOR"})
            self.expect("kw", "END_FOR")
            self.accept("op", ";")
            return ("for", var, a, b, step, body)
        if tok == ("kw", "WHILE"):
            self.next()
            c = self.expr()
            self.expect("kw", "DO")
            body = self.stmts({"END_WHILE"})
            self.expect("kw", "END_WHILE")
            self.accept("op", ";")
            return ("while", c, body)
        if tok == ("kw", "REPEAT"):
            self.next()
            body = self.stmts({"UNTIL"})
            self.expect("kw", "UNTIL")
            c = self.expr()
            self.expect("kw", "END_REPEAT")
            self.accept("op", ";")
            return ("repeat", body, c)
        if tok == ("kw", "RETURN"):
            self.next()
            self.accept("op", ";")
            return ("return",)
        if tok == ("kw", "EXIT"):
            self.next()
            self.accept("op", ";")
            return ("exit",)
        # assignment or FB call
        name = self.expect("id")[1]
        member = None
        if self.accept("op", "."):
            member = self.expect("id")[1]
        if self.accept("op", "("):
            args = []
            if not self.accept("op", ")"):
                while True:
                    if self.peek()[0] == "id" and self.peek(1) == ("op", ":="):
                        pname = self.next()[1]
                        self.next()
                        args.append((pname, self.expr()))
                    else:
                        args.append((None, self.expr()))
                    if self.accept("op", ")"):
                        break
                    self.expect("op", ",")
            self.expect("op", ";")
            return ("call", name, args)
        self.expect("op", ":=")
        val = self.expr()
        self.expect("op", ";")
        return ("assign", name, member, val)

    def case_label(self):
        neg = bool(self.accept("op", "-"))
        tok = self.next()
        if tok[0] == "num":
            lo = -tok[1] if neg else tok[1]
            if self.accept("op", ".."):
                neg2 = bool(self.accept("op", "-"))
                hi = self.expect("num")[1]
                return ("range", lo, -hi if neg2 else hi)
            return ("val", lo)
        if tok[0] == "id":
            return ("id", tok[1])
        raise STError(f"bad CASE label {tok}")

    def case_body(self):
        out = []
        while True:
            tok = self.peek()
            if tok[0] == "eof" or tok in (("kw", "END_CASE"), ("kw", "ELSE")):
                break
            # next label: num [.. num] (, ...)* ':'
            j = self.i
            if self.t[j] == ("op", "-"):
                j += 1
            if self.t[j][0] == "num":
                k = j + 1
                while self.t[k] in (("op", ","), ("op", ".."), ("op", "-")) or self.t[k][0] == "num":
                    k += 1
                if self.t[k] == ("op", ":"):
                    break
            if self.accept("op", ";"):
                continue
            out.append(self.stmt())
        return out

    # IEC precedence: OR < XOR < AND < (= <>) < (< > <= >=) < (+ -) < (* / MOD) < ** < unary
    def expr(self):
        return self.binop_level(0)

    LEVELS = [
        [("kw", "OR")],
        [("kw", "XOR")],
        [("kw", "AND"), ("op", "&")],
        [("op", "="), ("op", "<>")],
        [("op", "<"), ("op", ">"), ("op", "<="), ("op", ">=")],
        [("op", "+"), ("op", "-")],
        [("op", "*"), ("op", "/"), ("kw", "MOD")],
        [("op", "**")],
    ]

    def binop_level(self, lvl):
        if lvl == len(self.LEVELS):
            return self.unary()
        left = self.binop_level(lvl + 1)
        while self.peek() in self.LEVELS[lvl]:
            op = self.next()[1]
            if op == "&":
                op = "AND"
            right = self.binop_level(lvl + 1)
            left = ("bin", op, left, right)
        return left

    def unary(self):
        if self.accept("kw", "NOT"):
            return ("not", self.unary())
        if self.accept("op", "-"):
            return ("neg", self.unary())
        if self.accept("op", "+"):
            return self.unary()
        return self.primary()

    def primary(self):
        tok = self.next()
        if tok[0] == "num":
            return ("lit", tok[1])
        if tok[0] == "time":
            return ("lit", tok[1])
        if tok == ("kw", "TRUE"):
            return ("lit", True)
        if tok == ("kw", "FALSE"):
            return ("lit", False)
        if tok == ("op", "("):
            e = self.expr()
            self.expect("op", ")")
            return e
        if tok[0] == "id" or tok == ("kw", "MOD"):
            name = tok[1]
            if self.accept("op", "("):
                args = []
                if not self.accept("op", ")"):
                    while True:
                        if self.peek()[0] == "id" and self.peek(1) == ("op", ":="):
                            self.next(); self.next()
                        args.append(self.expr())
                        if self.accept("op", ")"):
                            break
                        self.expect("op", ",")
                return ("fn", name.upper(), args)
            if self.accept("op", "."):
                member = self.expect("id")[1]
                return ("member", name, member)
            return ("id", name)
        raise STError(f"unexpected token {tok}")


# ------------------------------------------------------------ function blocks
class FB:
    INPUTS = {}
    OUTPUTS = {}

    def __init__(self):
        self.p = dict(self.INPUTS)
        self.o = dict(self.OUTPUTS)


class TON(FB):
    INPUTS = {"IN": False, "PT": 0}
    OUTPUTS = {"Q": False, "ET": 0}

    def __init__(self):
        super().__init__()
        self.prev = False
        self.start = 0

    def step(self, now):
        IN, PT = bool(self.p["IN"]), self.p["PT"]
        if IN and not self.prev:
            self.start = now
        if IN:
            el = now - self.start
            self.o["Q"] = el >= PT
            self.o["ET"] = min(el, PT)
        else:
            self.o["Q"], self.o["ET"] = False, 0
        self.prev = IN


class TOF(FB):
    INPUTS = {"IN": False, "PT": 0}
    OUTPUTS = {"Q": False, "ET": 0}

    def __init__(self):
        super().__init__()
        self.prev = False
        self.start = 0

    def step(self, now):
        IN, PT = bool(self.p["IN"]), self.p["PT"]
        if not IN and self.prev:
            self.start = now
        if IN:
            self.o["Q"], self.o["ET"] = True, 0
        elif self.o["Q"]:
            el = now - self.start
            self.o["ET"] = min(el, PT)
            self.o["Q"] = el < PT
        self.prev = IN


class TP(FB):
    INPUTS = {"IN": False, "PT": 0}
    OUTPUTS = {"Q": False, "ET": 0}

    def __init__(self):
        super().__init__()
        self.prev = False
        self.start = 0
        self.running = False

    def step(self, now):
        IN, PT = bool(self.p["IN"]), self.p["PT"]
        if IN and not self.prev and not self.running:
            self.running, self.start = True, now
        if self.running:
            el = now - self.start
            if el >= PT:
                self.running = False
                self.o["ET"] = PT
            else:
                self.o["ET"] = el
        elif not IN:
            self.o["ET"] = 0
        self.o["Q"] = self.running
        self.prev = IN


class CTU(FB):
    INPUTS = {"CU": False, "R": False, "PV": 0}
    OUTPUTS = {"Q": False, "CV": 0}

    def __init__(self):
        super().__init__()
        self.prev = False

    def step(self, now):
        cu = bool(self.p["CU"])
        if self.p["R"]:
            self.o["CV"] = 0
        elif cu and not self.prev:
            self.o["CV"] += 1
        self.prev = cu
        self.o["Q"] = self.o["CV"] >= self.p["PV"]


class CTD(FB):
    INPUTS = {"CD": False, "LD": False, "PV": 0}
    OUTPUTS = {"Q": False, "CV": 0}

    def __init__(self):
        super().__init__()
        self.prev = False

    def step(self, now):
        cd = bool(self.p["CD"])
        if self.p["LD"]:
            self.o["CV"] = self.p["PV"]
        elif cd and not self.prev:
            self.o["CV"] -= 1
        self.prev = cd
        self.o["Q"] = self.o["CV"] <= 0


class R_TRIG(FB):
    INPUTS = {"CLK": False}
    OUTPUTS = {"Q": False}

    def __init__(self):
        super().__init__()
        self.m = False

    def step(self, now):
        clk = bool(self.p["CLK"])
        self.o["Q"] = clk and not self.m
        self.m = clk


class F_TRIG(FB):
    INPUTS = {"CLK": False}
    OUTPUTS = {"Q": False}

    def __init__(self):
        super().__init__()
        self.m = False

    def step(self, now):
        clk = bool(self.p["CLK"])
        self.o["Q"] = (not clk) and self.m
        self.m = clk


class SR(FB):
    INPUTS = {"S1": False, "R": False}
    OUTPUTS = {"Q1": False}

    def step(self, now):
        self.o["Q1"] = bool(self.p["S1"]) or (bool(self.o["Q1"]) and not self.p["R"])


class RS(FB):
    INPUTS = {"S": False, "R1": False}
    OUTPUTS = {"Q1": False}

    def step(self, now):
        self.o["Q1"] = (not self.p["R1"]) and (bool(self.p["S"]) or bool(self.o["Q1"]))


FB_TYPES = {c.__name__: c for c in (TON, TOF, TP, CTU, CTD, R_TRIG, F_TRIG, SR, RS)}
INT_TYPES = {"INT", "DINT", "SINT", "LINT", "UINT", "UDINT", "USINT", "ULINT", "WORD", "DWORD", "BYTE", "LWORD"}
REAL_TYPES = {"REAL", "LREAL"}


class ReturnSignal(Exception):
    pass


class ExitSignal(Exception):
    pass


# ---------------------------------------------------------------- program
class Program:
    """Loads one ST program and runs scan cycles against an absolute clock."""

    def __init__(self, src):
        self.ast = Parser(src).program()
        self.vars = {}      # lower-name -> value
        self.types = {}     # lower-name -> type
        self.section = {}   # lower-name -> section
        self.display = {}   # lower-name -> declared spelling
        self.fbs = {}       # lower-name -> FB instance
        for d in self.ast["decls"]:
            k = d["name"].lower()
            self.display[k] = d["name"]
            self.types[k] = d["type"]
            self.section[k] = d["section"]
            if d["type"] in FB_TYPES:
                self.fbs[k] = FB_TYPES[d["type"]]()
            elif d["type"] in REAL_TYPES:
                self.vars[k] = 0.0
            elif d["type"] in INT_TYPES or d["type"] == "TIME":
                self.vars[k] = 0
            elif d["type"] == "BOOL":
                self.vars[k] = False
            else:
                raise STError(f"unsupported type {d['type']} for {d['name']}")
        self.now = 0
        for d in self.ast["decls"]:
            if d["init"] is not None and d["name"].lower() in self.vars:
                self.vars[d["name"].lower()] = self.coerce(d["name"].lower(), self.eval(d["init"]))

    # -- helpers
    def coerce(self, k, v):
        ty = self.types.get(k)
        if ty == "BOOL":
            return bool(v)
        if ty in INT_TYPES or ty == "TIME":
            return int(v) if not isinstance(v, bool) else int(v)
        if ty in REAL_TYPES:
            return float(v)
        return v

    def lookup(self, name):
        k = name.lower()
        if k in self.vars:
            return self.vars[k]
        raise STError(f"undeclared identifier {name}")

    def eval(self, e):
        tag = e[0]
        if tag == "lit":
            return e[1]
        if tag == "id":
            return self.lookup(e[1])
        if tag == "member":
            inst = self.fbs.get(e[1].lower())
            if inst is None:
                raise STError(f"{e[1]} is not an FB instance")
            m = e[2].upper()
            if m in inst.o:
                return inst.o[m]
            if m in inst.p:
                return inst.p[m]
            raise STError(f"{e[1]} has no member {e[2]}")
        if tag == "not":
            v = self.eval(e[1])
            return (not v) if isinstance(v, bool) else ~int(v)
        if tag == "neg":
            return -self.eval(e[1])
        if tag == "bin":
            op = e[1]
            a = self.eval(e[2])
            if op == "AND" and isinstance(a, bool) and not a:
                self.eval(e[3])  # evaluate for errors, no short-circuit semantics needed
                return False
            b = self.eval(e[3])
            if op == "AND":
                return (a and b) if isinstance(a, bool) or isinstance(b, bool) else (int(a) & int(b))
            if op == "OR":
                return bool(a or b) if isinstance(a, bool) or isinstance(b, bool) else (int(a) | int(b))
            if op == "XOR":
                return bool(a) != bool(b)
            if op == "=":
                return a == b
            if op == "<>":
                return a != b
            if op == "<":
                return a < b
            if op == ">":
                return a > b
            if op == "<=":
                return a <= b
            if op == ">=":
                return a >= b
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                if b == 0:
                    return 0
                if isinstance(a, float) or isinstance(b, float):
                    return a / b
                q = abs(int(a)) // abs(int(b))
                return q if (a >= 0) == (b >= 0) else -q
            if op == "MOD":
                if b == 0:
                    return 0
                return int(a) - int(b) * int(int(a) / int(b))
            if op == "**":
                return float(a) ** float(b)
            raise STError(f"unknown operator {op}")
        if tag == "fn":
            name, args = e[1], [self.eval(a) for a in e[2]]
            if name == "ABS":
                return abs(args[0])
            if name == "MIN":
                return min(args)
            if name == "MAX":
                return max(args)
            if name == "LIMIT":
                return max(args[0], min(args[1], args[2]))
            if name == "SEL":
                return args[2] if args[0] else args[1]
            if name == "MOD":
                return self.eval(("bin", "MOD", ("lit", args[0]), ("lit", args[1])))
            if name in ("TRUNC",):
                return int(args[0])
            m = re.fullmatch(r"(\w+)_TO_(\w+)", name)
            if m:
                src, dst = m.groups()
                v = args[0]
                if dst in INT_TYPES:
                    return int(round(v)) if src in REAL_TYPES else int(v)
                if dst in REAL_TYPES:
                    return float(v)
                if dst == "BOOL":
                    return bool(v)
                if dst == "TIME":
                    return int(v)
            raise STError(f"unsupported function {name}")
        raise STError(f"bad expression node {tag}")

    def exec_block(self, stmts, depth=0):
        for s in stmts:
            self.exec(s, depth)

    def exec(self, s, depth=0):
        tag = s[0]
        if tag == "assign":
            _, name, member, val = s
            v = self.eval(val)
            if member is not None:
                inst = self.fbs.get(name.lower())
                if inst is None:
                    raise STError(f"{name} is not an FB instance")
                m = member.upper()
                if m in inst.p:
                    inst.p[m] = v
                elif m in inst.o:
                    inst.o[m] = v   # writing an FB output: legal in some IDEs, no effect on next call
                else:
                    raise STError(f"{name} has no member {member}")
                return
            k = name.lower()
            if k not in self.vars:
                raise STError(f"assignment to undeclared {name}")
            self.vars[k] = self.coerce(k, v)
        elif tag == "call":
            _, name, args = s
            inst = self.fbs.get(name.lower())
            if inst is None:
                raise STError(f"call to unknown FB instance {name}")
            for pname, pexpr in args:
                if pname is None:
                    raise STError("positional FB argument")
                if pname.upper() not in inst.p:
                    raise STError(f"{name} has no input {pname}")
                inst.p[pname.upper()] = self.eval(pexpr)
            inst.step(self.now)
        elif tag == "if":
            _, branches, else_body = s
            for cond, body in branches:
                if self.eval(cond):
                    self.exec_block(body, depth)
                    return
            if else_body is not None:
                self.exec_block(else_body, depth)
        elif tag == "case":
            _, sel, branches, else_body = s
            v = self.eval(sel)
            for labels, body in branches:
                for lab in labels:
                    if (lab[0] == "val" and v == lab[1]) or \
                       (lab[0] == "range" and lab[1] <= v <= lab[2]) or \
                       (lab[0] == "id" and v == self.lookup(lab[1])):
                        self.exec_block(body, depth)
                        return
            if else_body is not None:
                self.exec_block(else_body, depth)
        elif tag == "for":
            _, var, a, b, step, body = s
            k = var.lower()
            self.vars[k] = int(self.eval(a))
            end = int(self.eval(b))
            st = int(self.eval(step)) if step is not None else 1
            n = 0
            try:
                while (self.vars[k] <= end) if st > 0 else (self.vars[k] >= end):
                    self.exec_block(body, depth)
                    self.vars[k] += st
                    n += 1
                    if n > 10000:
                        raise STError("runaway FOR loop")
            except ExitSignal:
                pass
        elif tag == "while":
            n = 0
            try:
                while self.eval(s[1]):
                    self.exec_block(s[2], depth)
                    n += 1
                    if n > 10000:
                        raise STError("runaway WHILE loop (would trip the PLC watchdog)")
            except ExitSignal:
                pass
        elif tag == "repeat":
            n = 0
            try:
                while True:
                    self.exec_block(s[1], depth)
                    n += 1
                    if self.eval(s[2]):
                        break
                    if n > 10000:
                        raise STError("runaway REPEAT loop")
            except ExitSignal:
                pass
        elif tag == "return":
            raise ReturnSignal()
        elif tag == "exit":
            raise ExitSignal()
        else:
            raise STError(f"bad statement {tag}")

    # -- static name resolution (what a compiler front-end would reject)
    KNOWN_FUNCS = {"ABS", "MIN", "MAX", "LIMIT", "SEL", "MOD", "TRUNC"}

    def static_errors(self):
        errs = []

        def ex(e):
            tag = e[0]
            if tag == "id" and e[1].lower() not in self.vars:
                errs.append(f"undeclared identifier {e[1]}")
            elif tag == "member":
                inst = self.fbs.get(e[1].lower())
                if inst is None:
                    errs.append(f"{e[1]} is not an FB instance")
                elif e[2].upper() not in inst.o and e[2].upper() not in inst.p:
                    errs.append(f"{e[1]} has no member {e[2]}")
            elif tag in ("not", "neg"):
                ex(e[1])
            elif tag == "bin":
                ex(e[2]); ex(e[3])
            elif tag == "fn":
                if e[1] not in self.KNOWN_FUNCS and not re.fullmatch(r"\w+_TO_\w+", e[1]):
                    errs.append(f"unknown function {e[1]}")
                for a in e[2]:
                    ex(a)

        def st(s):
            tag = s[0]
            if tag == "assign":
                if s[2] is None and s[1].lower() not in self.vars:
                    errs.append(f"assignment to undeclared {s[1]}")
                if s[2] is not None and s[1].lower() not in self.fbs:
                    errs.append(f"{s[1]} is not an FB instance")
                ex(s[3])
            elif tag == "call":
                inst = self.fbs.get(s[1].lower())
                if inst is None:
                    errs.append(f"call to unknown FB instance {s[1]}")
                for pn, pe in s[2]:
                    if inst is not None and (pn is None or pn.upper() not in inst.p):
                        errs.append(f"{s[1]} has no input {pn}")
                    ex(pe)
            elif tag == "if":
                for c, b in s[1]:
                    ex(c); [st(x) for x in b]
                if s[2]:
                    [st(x) for x in s[2]]
            elif tag == "case":
                ex(s[1])
                for _, b in s[2]:
                    [st(x) for x in b]
                if s[3]:
                    [st(x) for x in s[3]]
            elif tag == "for":
                ex(s[2]); ex(s[3]); [st(x) for x in s[5]]
            elif tag == "while":
                ex(s[1]); [st(x) for x in s[2]]
            elif tag == "repeat":
                [st(x) for x in s[1]]; ex(s[2])

        for s in self.ast["body"]:
            st(s)
        return errs

    def scan(self, inputs, now):
        """One PLC scan: latch inputs into the image, run the body."""
        self.now = now
        for k, v in inputs.items():
            if k in self.vars:
                self.vars[k] = self.coerce(k, v)
        try:
            self.exec_block(self.ast["body"])
        except ReturnSignal:
            pass
