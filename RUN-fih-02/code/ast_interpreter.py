"""
Direct AST interpreter -- executes your AST scan-cycle by scan-cycle,
maintaining real program state across cycles (timers, counters, edge
detectors), rather than just compiling to text and checking structure.

WHAT THIS CATCHES that the compiler round-trip check cannot: bugs where
the AST is perfectly valid and round-trips correctly, but the LOGIC
itself is wrong over time -- e.g. a timer that never resets, a sequence
with no wraparound, a counter that free-runs instead of latching. This
is exactly the class of bug found by hand in the LightChase scenario
earlier this session (compiled cleanly, was still wrong).

WHAT THIS DOES NOT DO: it is not a formal verifier and has no built-in
notion of "correct" behavior for any given task. You provide input
sequences and either eyeball the output trace or write your own
assertions per scenario. This is closer to writing unit tests by hand
than to automatic verification -- an honest limitation, not a
technicality.

Usage:
    from ast_interpreter import Interpreter
    interp = Interpreter(program)
    interp.set_input("sensor", True)
    interp.step()  # one scan cycle
    print(interp.get_output("motor"))
"""

import sys
sys.path.insert(0, ".")
from ast_nodes import (
    Identifier, Literal, BinaryOp, UnaryOp, FunctionCallExpr, ArrayIndex, MemberAccess,
    Assignment, FunctionCallStatement, If, Case, For, While, Repeat, Return, Exit, Program,
)

SCAN_INTERVAL_MS = 20  # matches the Rust backend's assumption, for consistency


def _parse_time_literal_ms(text: str) -> int:
    import re
    text = text.strip("'\"")
    m = re.match(r"T#(\d+)(ms|s|m|h)?", text, re.IGNORECASE)
    if not m:
        return 1000
    value, unit = int(m.group(1)), (m.group(2) or "ms").lower()
    return {"ms": 1, "s": 1000, "m": 60000, "h": 3600000}[unit] * value


class Interpreter:
    def __init__(self, program: Program, max_pt_scans: int = None):
        """max_pt_scans: if set, caps every timer's effective threshold
        at this many scan cycles, regardless of its real PT value. Used
        ONLY for smoke testing -- real timer durations (8s, 10s, 20s,
        30s, 10min in this task set) can't fire within a short test
        window otherwise, causing false STATIC_OUTPUT flags on
        genuinely correct programs. Leave None for real/full-duration
        simulation."""
        self.program = program
        self.max_pt_scans = max_pt_scans
        self.state = {}       # variable name -> value
        self.fb_state = {}    # fb instance name -> {"acc"/"count"/"prev"/"q": ...}
        self.fb_types = {v.name: v.type for v in program.variables
                          if v.type in ("TON", "TOF", "TP", "CTU", "CTD", "R_TRIG", "F_TRIG")}
        self.cycle_count = 0
        self.trace = []  # list of {cycle, state snapshot} after each step

        for v in program.variables:
            if v.type == "BOOL":
                self.state[v.name] = False
            elif v.type in ("REAL", "LREAL"):
                self.state[v.name] = 0.0
            elif v.type in self.fb_types.values() or v.name in self.fb_types:
                pass  # FB instances aren't plain variables, handled via fb_state
            else:
                self.state[v.name] = 0

    def set_input(self, name: str, value):
        """Manually set an input variable's value before the next step()."""
        self.state[name] = value

    def get_output(self, name: str):
        return self.state.get(name)

    def _eval_expr(self, node):
        if isinstance(node, Identifier):
            name = node.name
            if name.upper() == "TRUE":
                return True
            if name.upper() == "FALSE":
                return False
            if "." in name:
                base, _, member = name.partition(".")
                if base in self.fb_state:
                    return self.fb_state[base].get(member.lower(), False)
                return self.state.get(name, False)
            return self.state.get(name, 0)
        if isinstance(node, Literal):
            text = node.text.strip("'\"")
            try:
                if "." in text:
                    return float(text)
                return int(text)
            except ValueError:
                return text
        if isinstance(node, UnaryOp):
            val = self._eval_expr(node.operand)
            return not val if node.op == "NOT" else -val
        if isinstance(node, BinaryOp):
            left = self._eval_expr(node.left)
            right = self._eval_expr(node.right)
            ops = {
                "AND": lambda a, b: a and b, "OR": lambda a, b: a or b,
                "XOR": lambda a, b: bool(a) != bool(b),
                "=": lambda a, b: a == b, "<>": lambda a, b: a != b,
                "<": lambda a, b: a < b, ">": lambda a, b: a > b,
                "<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b,
                "+": lambda a, b: a + b, "-": lambda a, b: a - b,
                "*": lambda a, b: a * b, "/": lambda a, b: a / b if b else 0,
                "MOD": lambda a, b: a % b if b else 0,
            }
            return ops.get(node.op, lambda a, b: 0)(left, right)
        if isinstance(node, MemberAccess):
            base_name = node.base.name if isinstance(node.base, Identifier) else None
            if base_name in self.fb_state:
                return self.fb_state[base_name].get(node.member.lower(), False)
            return False
        return None

    def _exec_fb_call(self, stmt: FunctionCallStatement):
        instance = stmt.instance_name
        fb_type = self.fb_types.get(instance)
        named = {name: self._eval_expr(val) for name, val in stmt.named_args if name}

        if instance not in self.fb_state:
            self.fb_state[instance] = {"acc": 0, "count": 0, "prev": False, "q": False}
        s = self.fb_state[instance]

        if fb_type == "TON":
            in_val = named.get("IN", False)
            pt_literal = next((v.text for n, v in stmt.named_args if n == "PT" and hasattr(v, "text")), "T#1000ms")
            threshold = _parse_time_literal_ms(pt_literal) // SCAN_INTERVAL_MS
            if self.max_pt_scans is not None:
                threshold = min(threshold, self.max_pt_scans)
            s["acc"] = s["acc"] + 1 if in_val else 0
            s["q"] = s["acc"] >= threshold
        elif fb_type == "CTU":
            cu, r = named.get("CU", False), named.get("R", False)
            pv = named.get("PV", 0)
            if r:
                s["count"] = 0
            elif cu:
                s["count"] += 1
            s["q"] = s["count"] >= pv
            s["cv"] = s["count"]  # standard CTU output: current count value
        elif fb_type == "R_TRIG":
            clk = named.get("CLK", False)
            s["q"] = clk and not s["prev"]
            s["prev"] = clk
        elif fb_type == "TP":
            in_val = named.get("IN", False)
            pt_literal = next(
                (v.text for n, v in stmt.named_args if n == "PT" and hasattr(v, "text")),
                "T#1000ms",
            )
            threshold = _parse_time_literal_ms(pt_literal) // SCAN_INTERVAL_MS
            if self.max_pt_scans is not None:
                threshold = min(threshold, self.max_pt_scans)
            if in_val and not s.get("prev", False) and not s.get("q", False):
                s["acc"] = 0
                s["q"] = True
            if s.get("q", False):
                s["acc"] = s.get("acc", 0) + 1
                if s["acc"] >= threshold:
                    s["q"] = False
                    s["acc"] = 0
            s["prev"] = in_val

    def _exec_statement(self, stmt):
        if isinstance(stmt, Assignment):
            self.state[stmt.target] = self._eval_expr(stmt.value)
        elif isinstance(stmt, FunctionCallStatement):
            self._exec_fb_call(stmt)
        elif isinstance(stmt, If):
            executed = False
            for condition, body in stmt.branches:
                if self._eval_expr(condition):
                    for s in body:
                        self._exec_statement(s)
                    executed = True
                    break
            if not executed and stmt.else_body is not None:
                for s in stmt.else_body:
                    self._exec_statement(s)
        elif isinstance(stmt, Case):
            selector_val = self._eval_expr(stmt.selector)
            for label, body in stmt.branches:
                label_val = int(label) if label.lstrip("-").isdigit() else label
                if selector_val == label_val:
                    for s in body:
                        self._exec_statement(s)
                    break
        # For/While/Repeat intentionally not executed -- not yet in the
        # Rust backend either, consistent scope limit stated up front

    def step(self):
        """Runs exactly one scan cycle: executes the full program body
        once, using whatever inputs are currently set via set_input()."""
        for stmt in self.program.body:
            self._exec_statement(stmt)
        self.cycle_count += 1
        self.trace.append({
            "cycle": self.cycle_count,
            "state": dict(self.state),
            "fb_state": {k: dict(v) for k, v in self.fb_state.items()},
        })

    def run(self, cycles: int, input_schedule: dict = None):
        """Runs multiple cycles. input_schedule: {cycle_number:
        {var_name: value}} -- inputs to set BEFORE that cycle runs."""
        input_schedule = input_schedule or {}
        for i in range(1, cycles + 1):
            if i in input_schedule:
                for name, value in input_schedule[i].items():
                    self.set_input(name, value)
            self.step()
        return self.trace
