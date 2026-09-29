"""
Language-independent AST node definitions -- the real compiler target,
per the architecture: Control Logic Graph -> AST -> (ST | Rust).
"""

from dataclasses import dataclass, field
from typing import Optional


# ---- Expressions ----

@dataclass
class Identifier:
    name: str  # may include one dotted member access, e.g. "Timer.Q"


@dataclass
class Literal:
    text: str  # kept as literal source text (e.g. "TRUE", "0.0", "T#5s", "16#FAC0")


@dataclass
class BinaryOp:
    op: str  # "AND" | "OR" | "XOR" | "+" | "-" | "*" | "/" | "MOD" |
             # ">" | "<" | ">=" | "<=" | "=" | "<>" | "**"
    left: "Expr"
    right: "Expr"


@dataclass
class UnaryOp:
    op: str  # "NOT" | "-"
    operand: "Expr"


@dataclass
class FunctionCallExpr:
    """A function CALL used as a value inside an expression. args is a
    list of (name_or_None, Expr) pairs. Default added: a zero-argument
    call (e.g. "MyFunc()") legitimately has an empty args list, and the
    compact serializer omits empty-list fields entirely -- without this
    default, deserializing that omission crashed with a missing-
    positional-argument TypeError (confirmed real bug, 45/747 records
    in the combined training dataset)."""
    name: str
    args: list = field(default_factory=list)  # list[tuple[Optional[str], Expr]]


@dataclass
class ArrayIndex:
    base: object  # Expr
    index: object  # Expr, or list[Expr] for arr[i,j] style


@dataclass
class MemberAccess:
    base: object  # Expr
    member: str  # may be a name (struct field) or a bit index ("0", "1", ...)


Expr = ("Identifier | Literal | BinaryOp | UnaryOp | FunctionCallExpr | "
        "ArrayIndex | MemberAccess")


# ---- Statements ----

@dataclass
class Assignment:
    target: str
    value: object  # Expr


@dataclass
class FunctionCallStatement:
    """A standalone FB invocation statement, e.g. Timer(IN := x, PT := y);
    named_args is a list of (param_name_or_None, Expr) pairs. Default
    added for the same reason as FunctionCallExpr.args above -- a
    zero-argument call's omitted empty list needs a fallback."""
    instance_name: str
    named_args: list = field(default_factory=list)  # list[tuple[Optional[str], Expr]]


@dataclass
class If:
    branches: list  # list of (condition_expr, body_statements)
    else_body: Optional[list] = None


@dataclass
class Case:
    selector: object  # Expr
    branches: list = field(default_factory=list)  # list of (label_text, body_statements)


@dataclass
class For:
    loop_var: str
    start: object  # Expr
    end: object  # Expr
    step: Optional[object] = None  # Expr or None
    body: list = field(default_factory=list)


@dataclass
class While:
    condition: object  # Expr
    body: list = field(default_factory=list)


@dataclass
class Repeat:
    body: list = field(default_factory=list)
    condition: object = None  # Expr, checked at the END (do-while semantics)


@dataclass
class Return:
    pass  # ST's RETURN statement takes no value


@dataclass
class Exit:
    pass  # ST's EXIT statement -- breaks out of the enclosing FOR/WHILE/REPEAT loop


Statement = "Assignment | FunctionCallStatement | If | Case | For | While | Repeat | Return | Exit"


# ---- Program-level ----

@dataclass
class VarDecl:
    name: str
    type: str
    scope: str  # "input" | "output" | "local" | "inout" | "temp" | "memory" | "external" | "global"
    address: Optional[str] = None  # raw hardware address text, e.g. "%IX0.0"


@dataclass
class Program:
    name: str
    kind: str  # "program" | "function_block" | "function"
    return_type: Optional[str] = None
    variables: list = field(default_factory=list)  # list[VarDecl]
    body: list = field(default_factory=list)  # list[Statement]
