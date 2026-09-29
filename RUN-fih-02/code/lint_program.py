"""
Static linter -- catches semantic bug classes found by hand in the
manual review, without needing execution or a task-specific oracle.

Checks:
  1. Declared I/O variables never referenced anywhere in the body
  2. Statically impossible chained comparisons (X > A AND X < B, A >= B)
  3. Assignment directly to a declared FB instance (should be a call)
  4. FB instance declared with a type outside the known standard set
     (TON/TOF/TP/CTU/CTD/CTUD/R_TRIG/F_TRIG/SR/RS)
  5. Identifiers used in the body that were never declared anywhere
"""

import re
import sys
sys.path.insert(0, ".")
from ast_nodes import (
    Identifier, BinaryOp, UnaryOp, MemberAccess, FunctionCallExpr,
    Assignment, FunctionCallStatement, If, Case, For, While, Repeat, Program,
)


def extract_required_io(task_text: str) -> set:
    """Extracts variable names explicitly listed with an address in the
    task text (e.g. 'Low_Level_Sensor: %IX0.0' or 'RPM_Set AI:0.5').
    These are non-negotiable -- the repair loop must never delete them
    to silence UNUSED_IO. Confirmed real exploit: the model was deleting
    spec-required inputs like Speed_Select and RPM_Set entirely rather
    than actually using them, which made UNUSED_IO's absence misleading."""
    names = set()
    for line in task_text.split("\n"):
        m = re.match(r"^\s*([A-Za-z_]\w*)\s*[:\s]\s*(%[IQ]\w*[\d.]*|[AD][IO]:[\d.]+)", line)
        if m:
            names.add(m.group(1))
    return names


def check_missing_required_io(program, required_io: set) -> list:
    issues = []
    declared_casefold = {v.name.casefold() for v in program.variables}
    missing = [n for n in sorted(required_io) if n.casefold() not in declared_casefold]
    for name in missing:
        issues.append(f"MISSING_REQUIRED_IO: '{name}' is explicitly required by the task "
                       f"(with an address) but was not declared at all -- this is worse than "
                       f"UNUSED_IO, it means the requirement was dropped entirely")
    return issues


def check_input_assigned_to(program) -> list:
    """Catches assignment INTO a declared input variable -- a real,
    invalid pattern in IEC 61131-3 (inputs are read-only), and confirmed
    to be a real gaming pattern: the model wrote 'Reset_Button := FALSE;'
    purely to make UNUSED_IO stop complaining, without it meaning
    anything."""
    issues = []
    input_names = {v.name for v in program.variables if v.scope == "input"}
    assigned = set()
    _collect_assignment_targets(program.body, assigned)
    bad = assigned & input_names
    for name in sorted(bad):
        issues.append(f"INPUT_ASSIGNED_TO: '{name}' is a declared INPUT but the program "
                       f"assigns a value to it -- inputs are read-only; this is either invalid "
                       f"ST or a dummy assignment written just to silence an unused-variable warning")
    return issues


def _collect_assignment_targets(stmts, out):
    from ast_nodes import Assignment, If, Case, For, While, Repeat
    for stmt in stmts:
        if isinstance(stmt, Assignment):
            out.add(stmt.target)
        elif isinstance(stmt, If):
            for _, body in stmt.branches:
                _collect_assignment_targets(body, out)
            if stmt.else_body:
                _collect_assignment_targets(stmt.else_body, out)
        elif isinstance(stmt, Case):
            for _, body in stmt.branches:
                _collect_assignment_targets(body, out)
        elif isinstance(stmt, (For, While, Repeat)):
            _collect_assignment_targets(getattr(stmt, "body", []), out)


def _is_constant_expr(node):
    """True if the expression is a bare literal or TRUE/FALSE -- the
    actual DEAD_OVERRIDE bug pattern is a hardcoded constant silencing
    prior conditional logic, not a legitimate expression that still
    depends on inputs (e.g. 'X := X + delta' after an IF, which is fine)."""
    from ast_nodes import Literal
    if isinstance(node, Literal):
        return True
    if isinstance(node, Identifier) and node.name.upper() in ("TRUE", "FALSE"):
        return True
    return False


def check_dead_override(program) -> list:
    """Catches an unconditional CONSTANT assignment to a variable that
    occurs AFTER a conditional (If/Case) assignment to the SAME variable
    at the top level of the program body -- this silently negates
    everything the conditional logic just decided. Confirmed real bug:
    Task 22's trailing 'Conveyor_Run := FALSE;' after a correct IF/ELSIF
    block, and Task 25's trailing 'Acid_Pump := FALSE; Base_Pump :=
    FALSE;' zeroing out both pumps regardless of what the IF/ELSIF just
    set. Deliberately restricted to CONSTANT trailing assignments only --
    an earlier version flagged any trailing assignment regardless of
    value, which false-positived on legitimate patterns like
    'Damper_Position := Damper_Position + (CO2_Sensor - 600) / 400'
    that still genuinely depend on inputs after an IF block (Tasks 3, 16)."""
    from ast_nodes import Assignment, If, Case
    issues = []
    conditionally_set = set()
    for stmt in program.body:
        if isinstance(stmt, (If, Case)):
            branches = stmt.branches if isinstance(stmt, Case) else [b for b in stmt.branches]
            for b in branches:
                body = b[1] if isinstance(stmt, Case) else b[1]
                targets = set()
                _collect_assignment_targets(body, targets)
                conditionally_set |= targets
            if isinstance(stmt, If) and stmt.else_body:
                targets = set()
                _collect_assignment_targets(stmt.else_body, targets)
                conditionally_set |= targets
        elif isinstance(stmt, Assignment):
            if stmt.target in conditionally_set and _is_constant_expr(stmt.value):
                issues.append(f"DEAD_OVERRIDE: '{stmt.target}' is unconditionally assigned a "
                               f"CONSTANT value AFTER a conditional block already set it -- this "
                               f"silently discards whatever the IF/CASE logic just decided")
    return issues


KNOWN_FB_TYPES = {"TON", "TOF", "TP", "CTU", "CTD", "CTUD", "R_TRIG", "F_TRIG", "SR", "RS"}


def _collect_identifiers(node, out):
    """Walks an expression tree collecting every Identifier.name used."""
    if isinstance(node, Identifier):
        name = node.name.split(".")[0]  # strip member access, e.g. "TON0.Q" -> "TON0"
        out.add(name)
    elif isinstance(node, BinaryOp):
        _collect_identifiers(node.left, out)
        _collect_identifiers(node.right, out)
    elif isinstance(node, UnaryOp):
        _collect_identifiers(node.operand, out)
    elif isinstance(node, MemberAccess):
        _collect_identifiers(node.base, out)
    elif isinstance(node, FunctionCallExpr):
        for _, val in node.args:
            _collect_identifiers(val, out)
    elif hasattr(node, "base") and hasattr(node, "index"):  # ArrayIndex
        _collect_identifiers(node.base, out)
        if isinstance(node.index, list):
            for idx in node.index:
                _collect_identifiers(idx, out)
        else:
            _collect_identifiers(node.index, out)


def _walk_statements(stmts, used_names, assigned_targets, fb_direct_assigns, fb_instances):
    for stmt in stmts:
        if isinstance(stmt, Assignment):
            assigned_targets.add(stmt.target)
            if stmt.target in fb_instances:
                fb_direct_assigns.append(stmt.target)
            _collect_identifiers(stmt.value, used_names)
        elif isinstance(stmt, FunctionCallStatement):
            used_names.add(stmt.instance_name)
            for _, val in stmt.named_args:
                _collect_identifiers(val, used_names)
        elif isinstance(stmt, If):
            for cond, body in stmt.branches:
                _collect_identifiers(cond, used_names)
                _walk_statements(body, used_names, assigned_targets, fb_direct_assigns, fb_instances)
            if stmt.else_body:
                _walk_statements(stmt.else_body, used_names, assigned_targets, fb_direct_assigns, fb_instances)
        elif isinstance(stmt, Case):
            _collect_identifiers(stmt.selector, used_names)
            for _, body in stmt.branches:
                _walk_statements(body, used_names, assigned_targets, fb_direct_assigns, fb_instances)
        elif isinstance(stmt, (For, While, Repeat)):
            body = getattr(stmt, "body", [])
            _walk_statements(body, used_names, assigned_targets, fb_direct_assigns, fb_instances)


def _find_impossible_comparisons(stmts, issues):
    """Looks for chained AND'd comparisons on the SAME variable with a
    statically empty range, e.g. 'X > 300 AND X < 280'. Recurses into
    If/Case/For/While/Repeat -- confirmed real gap: originally only
    recursed into If, making impossible conditions inside CASE branches
    (common in sequencing-style tasks) invisible."""
    def check_expr(node):
        if isinstance(node, BinaryOp) and node.op == "AND":
            comparisons = []
            _flatten_and_comparisons(node, comparisons)
            by_var = {}
            for var, op, val in comparisons:
                by_var.setdefault(var, []).append((op, val))
            for var, conds in by_var.items():
                lowers = [v for op, v in conds if op in (">", ">=")]
                uppers = [v for op, v in conds if op in ("<", "<=")]
                if lowers and uppers and max(lowers) >= min(uppers):
                    issues.append(f"IMPOSSIBLE_CONDITION: '{var}' constrained to be both "
                                   f">= {max(lowers)} and <= {min(uppers)} simultaneously -- "
                                   f"this condition can never be true")
        if isinstance(node, BinaryOp):
            check_expr(node.left)
            check_expr(node.right)

    for stmt in stmts:
        if isinstance(stmt, Assignment):
            check_expr(stmt.value)
        elif isinstance(stmt, If):
            for cond, body in stmt.branches:
                check_expr(cond)
                _find_impossible_comparisons(body, issues)
            if stmt.else_body:
                _find_impossible_comparisons(stmt.else_body, issues)
        elif isinstance(stmt, Case):
            check_expr(stmt.selector)
            for _, body in stmt.branches:
                _find_impossible_comparisons(body, issues)
        elif isinstance(stmt, (For, While, Repeat)):
            if hasattr(stmt, "condition") and stmt.condition is not None:
                check_expr(stmt.condition)
            _find_impossible_comparisons(getattr(stmt, "body", []), issues)


def _flatten_and_comparisons(node, out):
    """Extracts (variable, op, numeric_value) triples from a chain of
    AND'd comparisons."""
    if isinstance(node, BinaryOp) and node.op == "AND":
        _flatten_and_comparisons(node.left, out)
        _flatten_and_comparisons(node.right, out)
    elif isinstance(node, BinaryOp) and node.op in (">", ">=", "<", "<="):
        var, val = None, None
        if isinstance(node.left, Identifier):
            var = node.left.name
        if hasattr(node.right, "text"):
            try:
                val = float(node.right.text.strip("'\""))
            except ValueError:
                pass
        if var is not None and val is not None:
            out.append((var, node.op, val))


def lint_program(program: Program, task_text: str = None) -> list:
    """Returns a list of human-readable issue strings, empty if clean.
    If task_text is provided, also checks for required I/O that was
    deleted entirely rather than used (the confirmed repair-loop
    exploit) -- pass it whenever available."""
    issues = []

    io_vars = {v.name for v in program.variables if v.scope in ("input", "output")}
    fb_instances = {v.name for v in program.variables
                     if v.type in KNOWN_FB_TYPES or v.name.upper().startswith(("TON", "TOF", "TP", "CTU", "CTD", "R_TRIG", "F_TRIG"))}
    declared_names = {v.name for v in program.variables}

    used_names = set()
    assigned_targets = set()
    fb_direct_assigns = []
    _walk_statements(program.body, used_names, assigned_targets, fb_direct_assigns, fb_instances)

    # 1. unused declared I/O
    unused_io = io_vars - used_names - assigned_targets
    for name in sorted(unused_io):
        issues.append(f"UNUSED_IO: '{name}' is declared as input/output but never referenced anywhere in the program body")

    # 2. impossible conditions
    _find_impossible_comparisons(program.body, issues)

    # 3. FB direct assignment
    for name in fb_direct_assigns:
        issues.append(f"FB_DIRECT_ASSIGN: '{name}' is a function block instance but is assigned to directly "
                       f"with ':=' instead of being called with named parameters")

    # 4. invented FB types
    for v in program.variables:
        if v.name in fb_instances and v.type not in KNOWN_FB_TYPES:
            issues.append(f"UNKNOWN_FB_TYPE: '{v.name}' is declared with type '{v.type}', "
                           f"which is not a standard IEC 61131-3 function block")

    # 5. undeclared identifiers used
    all_referenced = used_names | assigned_targets
    undeclared = all_referenced - declared_names - {"TRUE", "FALSE"}
    for name in sorted(undeclared):
        issues.append(f"UNDECLARED_VARIABLE: '{name}' is used but never declared in any VAR block")

    # 6. required I/O deleted entirely (worse than unused -- confirmed
    # real gaming pattern, must be checked and reported ahead of anything else)
    if task_text:
        required_io = extract_required_io(task_text)
        issues = check_missing_required_io(program, required_io) + issues

    # 7. assignment into a declared input (confirmed dummy-assignment gaming pattern)
    issues.extend(check_input_assigned_to(program))

    # 8. dead override after conditional logic
    issues.extend(check_dead_override(program))

    return issues


if __name__ == "__main__":
    # self-test against a known-buggy example (Task 14 pattern: impossible condition)
    from ast_nodes import VarDecl, BinaryOp, Literal

    program = Program(
        name="Test", kind="program", return_type=None,
        variables=[
            VarDecl(name="Temp_Sensor", type="INT", scope="input"),
            VarDecl(name="Fan1", type="BOOL", scope="output"),
            VarDecl(name="Unused_Input", type="BOOL", scope="input"),
        ],
        body=[
            Assignment(target="Fan1", value=BinaryOp(
                op="AND",
                left=BinaryOp(op=">", left=Identifier(name="Temp_Sensor"), right=Literal(text="300")),
                right=BinaryOp(op="<", left=Identifier(name="Temp_Sensor"), right=Literal(text="280")),
            )),
        ],
    )
    issues = lint_program(program)
    print(f"Found {len(issues)} issues:")
    for issue in issues:
        print(f"  - {issue}")
