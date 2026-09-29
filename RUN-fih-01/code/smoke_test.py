"""
Generic, task-independent execution smoke test: runs a program through
the AST interpreter with varying/toggling inputs over many scan cycles,
and flags any declared OUTPUT that never changes value. This catches a
real, distinct bug class the linter can't: outputs that are declared
and even referenced, but whose assigned logic never actually responds
to any input combination (e.g. Task 6's Motor_Run staying frozen, or
logic that's always vacuously false/true for structural reasons the
linter's simple interval check doesn't cover).

This does NOT know what the "correct" output behavior should be -- it
only flags outputs that are completely static across a real variety of
inputs, which is inherently suspicious for almost any real control
task (a genuinely constant output is rare and usually not what's
being asked for).
"""

import sys
sys.path.insert(0, ".")
from ast_interpreter import Interpreter
from ast_nodes import Identifier, FunctionCallStatement, If, Case, For, While, Repeat


def _collect_identifiers_in_expr(node, input_names, out):
    """Recurses through an expression tree collecting any raw input
    variable referenced anywhere in it -- not just bare Identifier args,
    since real trigger conditions are often computed expressions like
    'High_Level_Sensor AND NOT Low_Level_Sensor', not a single passthrough."""
    from ast_nodes import Identifier, BinaryOp, UnaryOp, MemberAccess, FunctionCallExpr
    if isinstance(node, Identifier):
        base_name = node.name.split(".")[0]
        if base_name in input_names:
            out.add(base_name)
    elif isinstance(node, BinaryOp):
        _collect_identifiers_in_expr(node.left, input_names, out)
        _collect_identifiers_in_expr(node.right, input_names, out)
    elif isinstance(node, UnaryOp):
        _collect_identifiers_in_expr(node.operand, input_names, out)
    elif isinstance(node, MemberAccess):
        _collect_identifiers_in_expr(node.base, input_names, out)
    elif isinstance(node, FunctionCallExpr):
        for _, val in node.args:
            _collect_identifiers_in_expr(val, input_names, out)


def _find_fb_trigger_inputs(program):
    """Finds input variable names that feed into any FB call's trigger
    condition (TON/CTU/R_TRIG/etc), directly OR via a computed
    expression -- these need SUSTAINED/REPEATED stimulus, not just
    generic rotation, or the FB never actually fires."""
    trigger_inputs = set()
    input_names = {v.name for v in program.variables if v.scope == "input"}

    def walk(stmts):
        for stmt in stmts:
            if isinstance(stmt, FunctionCallStatement):
                for _, val in stmt.named_args:
                    _collect_identifiers_in_expr(val, input_names, trigger_inputs)
            elif isinstance(stmt, If):
                for _, body in stmt.branches:
                    walk(body)
                if stmt.else_body:
                    walk(stmt.else_body)
            elif isinstance(stmt, Case):
                for _, body in stmt.branches:
                    walk(body)
            elif isinstance(stmt, (For, While, Repeat)):
                walk(getattr(stmt, "body", []))

    walk(program.body)
    return trigger_inputs


def smoke_test(program, cycles=200):
    """Returns a list of issue strings. Uses TARGETED stimulus for
    inputs that feed timers/counters/edge-detectors (sustained holds +
    real repeated rising edges), and generic rotation for everything
    else, then checks which declared outputs ever changed."""
    issues = []

    input_vars = [v for v in program.variables if v.scope == "input"]
    output_vars = [v for v in program.variables if v.scope == "output"]

    if not output_vars:
        return issues

    trigger_inputs = _find_fb_trigger_inputs(program)

    interp = Interpreter(program, max_pt_scans=10)  # cap every timer at 10 scans (200ms) for
                                                       # smoke-testing purposes only -- real PT
                                                       # values (8s, 10s, 20s, 30s, 10min in this
                                                       # task set) can't fire within a short test
                                                       # window otherwise, causing false
                                                       # STATIC_OUTPUT flags on correct programs
    output_history = {v.name: set() for v in output_vars}

    for cycle in range(1, cycles + 1):
        for i, v in enumerate(input_vars):
            if v.name in trigger_inputs and v.type == "BOOL":
                if cycle <= cycles // 3:
                    # phase 1: fast-edge toggling -- gives ~1 rising edge
                    # per 4 cycles, enough for counters needing several
                    # PV counts within the test window
                    interp.set_input(v.name, (cycle % 4) < 2)
                elif cycle <= 2 * cycles // 3:
                    # phase 2: sustained hold, staggered by index parity
                    interp.set_input(v.name, (i % 2) == 0)
                else:
                    # phase 3: sustained hold, FLIPPED parity -- tries the
                    # opposite combination, since a single fixed
                    # staggering only has a 50% chance of matching what a
                    # given AND-with-negation condition actually needs
                    interp.set_input(v.name, (i % 2) == 1)
            elif v.type == "BOOL":
                interp.set_input(v.name, bool((cycle + i * 3) % (4 + i) < 2))
            elif v.type in ("INT", "REAL", "LREAL"):
                interp.set_input(v.name, (cycle * (i + 1) * 17) % 1000)
        interp.step()
        for v in output_vars:
            val = interp.get_output(v.name)
            output_history[v.name].add(val)

    for v in output_vars:
        distinct_values = output_history[v.name]
        if len(distinct_values) <= 1:
            issues.append(f"STATIC_OUTPUT: '{v.name}' never changed value across {cycles} scan cycles "
                           f"with varying/targeted inputs (stuck at {distinct_values}) -- "
                           f"suspicious for almost any real control task")

    return issues


if __name__ == "__main__":
    # self-test against a known-frozen example (Task 6/21 pattern:
    # declared output never assigned anywhere)
    from ast_nodes import Program, VarDecl, Assignment, Identifier

    program = Program(
        name="Test", kind="program", return_type=None,
        variables=[
            VarDecl(name="Start_Button", type="BOOL", scope="input"),
            VarDecl(name="EStop_Lamp", type="BOOL", scope="output"),
            VarDecl(name="Motor_Run", type="BOOL", scope="output"),  # never assigned -- should be flagged
        ],
        body=[
            Assignment(target="EStop_Lamp", value=Identifier(name="Start_Button")),
        ],
    )
    issues = smoke_test(program)
    print(f"Found {len(issues)} issues:")
    for issue in issues:
        print(f"  - {issue}")
