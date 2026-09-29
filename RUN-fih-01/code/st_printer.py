"""
ST pretty printer: AST -> Structured Text source.

Uses a small Emitter (indent/dedent/emit) rather than raw string
concatenation, per the planned architecture -- makes the IF/CASE nesting
logic much easier to get right and to extend to a Rust printer later
without duplicating structure-walking logic.
"""

from ast_nodes import (
    Identifier, Literal, BinaryOp, UnaryOp, FunctionCallExpr, ArrayIndex, MemberAccess,
    Assignment, FunctionCallStatement, If, Case, For, While, Repeat, Return, Exit, VarDecl, Program,
)


class Emitter:
    """Tracks each line's indent level LAZILY -- assigned at the moment
    the first piece of real content is emitted onto that line, not when
    newline() creates it. This matters because the common call pattern is
    newline() -> indent()/dedent() -> emit(...), and baking the indent
    prefix in at newline()-time (the original, buggy version) meant a
    dedent()/indent() call issued between newline() and the next emit()
    never took effect for that line -- confirmed via a real round-trip
    test on GenericBistableDeviceModel, where the first VAR_INPUT
    variable line was missing its indent entirely and END_VAR incorrectly
    kept the inner block's indent level."""

    def __init__(self, indent_str="    "):
        self.raw_lines = [""]
        self.line_indents = [0]
        self.indent_level = 0
        self.indent_str = indent_str
        self._current_line_started = False

    def emit(self, text):
        if not self._current_line_started and text:
            self.line_indents[-1] = self.indent_level
            self._current_line_started = True
        self.raw_lines[-1] += text

    def newline(self):
        self.raw_lines.append("")
        self.line_indents.append(self.indent_level)
        self._current_line_started = False

    def indent(self):
        self.indent_level += 1

    def dedent(self):
        self.indent_level = max(0, self.indent_level - 1)

    def result(self):
        return "\n".join(
            self.indent_str * lvl + content
            for lvl, content in zip(self.line_indents, self.raw_lines)
        )


# Precedence tiers matching expr_parser.py, used to decide when a
# sub-expression needs parentheses to preserve its original grouping.
_PRECEDENCE = {
    "OR": 0, "XOR": 0,
    "AND": 1,
    "=": 2, "<>": 2, "<": 2, ">": 2, "<=": 2, ">=": 2,
    "+": 3, "-": 3,
    "*": 4, "/": 4, "MOD": 4,
    "**": 5,
}


def print_expr(node, parent_precedence=-1):
    if isinstance(node, Identifier):
        return node.name
    if isinstance(node, Literal):
        return node.text
    if isinstance(node, UnaryOp):
        inner = print_expr(node.operand, parent_precedence=100)  # unary binds tight
        if node.op == "NOT":
            return f"NOT {inner}"
        return f"{node.op}{inner}"
    if isinstance(node, BinaryOp):
        my_prec = _PRECEDENCE.get(node.op, 0)
        left = print_expr(node.left, parent_precedence=my_prec)
        right = print_expr(node.right, parent_precedence=my_prec + 1)
        text = f"{left} {node.op} {right}"
        if my_prec < parent_precedence:
            return f"({text})"
        return text
    if isinstance(node, FunctionCallExpr):
        arg_strs = []
        for name, val in node.args:
            val_str = print_expr(val, parent_precedence=-1)
            arg_strs.append(f"{name} := {val_str}" if name is not None else val_str)
        return f"{node.name}({', '.join(arg_strs)})"
    if isinstance(node, ArrayIndex):
        base = print_expr(node.base, parent_precedence=100)
        if isinstance(node.index, list):
            index_str = ", ".join(print_expr(i, parent_precedence=-1) for i in node.index)
        else:
            index_str = print_expr(node.index, parent_precedence=-1)
        return f"{base}[{index_str}]"
    if isinstance(node, MemberAccess):
        base = print_expr(node.base, parent_precedence=100)
        return f"{base}.{node.member}"
    raise TypeError(f"Unknown expression node type: {type(node)}")


def print_statement(stmt, emitter: Emitter):
    if isinstance(stmt, Return):
        emitter.emit("RETURN;")
        emitter.newline()
    elif isinstance(stmt, Exit):
        emitter.emit("EXIT;")
        emitter.newline()
    elif isinstance(stmt, Assignment):
        emitter.emit(f"{stmt.target} := {print_expr(stmt.value)};")
        emitter.newline()
    elif isinstance(stmt, FunctionCallStatement):
        arg_strs = []
        for name, val in stmt.named_args:
            if name is None:
                arg_strs.append(print_expr(val))  # positional argument, no label
            else:
                arg_strs.append(f"{name} := {print_expr(val)}")
        emitter.emit(f"{stmt.instance_name}({', '.join(arg_strs)});")
        emitter.newline()
    elif isinstance(stmt, If):
        for i, (condition, body) in enumerate(stmt.branches):
            keyword = "IF" if i == 0 else "ELSIF"
            emitter.emit(f"{keyword} {print_expr(condition)} THEN")
            emitter.newline()
            emitter.indent()
            for s in body:
                print_statement(s, emitter)
            emitter.dedent()
        if stmt.else_body is not None:
            emitter.emit("ELSE")
            emitter.newline()
            emitter.indent()
            for s in stmt.else_body:
                print_statement(s, emitter)
            emitter.dedent()
        emitter.emit("END_IF;")
        emitter.newline()
    elif isinstance(stmt, Case):
        emitter.emit(f"CASE {print_expr(stmt.selector)} OF")
        emitter.newline()
        emitter.indent()
        for label, body in stmt.branches:
            emitter.emit(f"{label}:")
            emitter.newline()
            emitter.indent()
            for s in body:
                print_statement(s, emitter)
            emitter.dedent()
        emitter.dedent()
        emitter.emit("END_CASE;")
        emitter.newline()
    elif isinstance(stmt, For):
        header = f"FOR {stmt.loop_var} := {print_expr(stmt.start)} TO {print_expr(stmt.end)}"
        if stmt.step is not None:
            header += f" BY {print_expr(stmt.step)}"
        header += " DO"
        emitter.emit(header)
        emitter.newline()
        emitter.indent()
        for s in stmt.body:
            print_statement(s, emitter)
        emitter.dedent()
        emitter.emit("END_FOR;")
        emitter.newline()
    elif isinstance(stmt, While):
        emitter.emit(f"WHILE {print_expr(stmt.condition)} DO")
        emitter.newline()
        emitter.indent()
        for s in stmt.body:
            print_statement(s, emitter)
        emitter.dedent()
        emitter.emit("END_WHILE;")
        emitter.newline()
    elif isinstance(stmt, Repeat):
        emitter.emit("REPEAT")
        emitter.newline()
        emitter.indent()
        for s in stmt.body:
            print_statement(s, emitter)
        emitter.dedent()
        emitter.emit(f"UNTIL {print_expr(stmt.condition)}")
        emitter.newline()
        emitter.emit("END_REPEAT;")
        emitter.newline()
    else:
        raise TypeError(f"Unknown statement node type: {type(stmt)}")


def print_program(program: Program) -> str:
    emitter = Emitter()

    header_kind = {"program": "PROGRAM", "function_block": "FUNCTION_BLOCK",
                   "function": "FUNCTION"}.get(program.kind, "PROGRAM")
    header = f"{header_kind} {program.name}"
    if program.kind == "function" and program.return_type:
        header += f" : {program.return_type}"
    emitter.emit(header)
    emitter.newline()

    by_scope = {}
    for v in program.variables:
        by_scope.setdefault(v.scope, []).append(v)

    scope_to_block = {
        "input": "VAR_INPUT", "output": "VAR_OUTPUT",
        "inout": "VAR_IN_OUT", "temp": "VAR_TEMP", "local": "VAR",
    }
    for scope, block_kw in scope_to_block.items():
        vars_in_scope = by_scope.get(scope, [])
        if not vars_in_scope:
            continue
        emitter.emit(block_kw)
        emitter.newline()
        emitter.indent()
        for v in vars_in_scope:
            emitter.emit(f"{v.name} : {v.type};")
            emitter.newline()
        emitter.dedent()
        emitter.emit("END_VAR")
        emitter.newline()

    for stmt in program.body:
        print_statement(stmt, emitter)

    footer_kind = {"program": "END_PROGRAM", "function_block": "END_FUNCTION_BLOCK",
                   "function": "END_FUNCTION"}.get(program.kind, "END_PROGRAM")
    emitter.emit(footer_kind)

    return emitter.result()
