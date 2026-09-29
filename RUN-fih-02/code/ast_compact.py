"""
Compact AST JSON serialization -- same information as ast_serialize.py,
but using short single/double-letter type codes instead of full type
names, and omitting null-valued optional fields entirely (rather than
writing "field": null).

Built specifically because verbose "__type__": "FunctionCallExpr"-style
tags were confirmed to be causing real generation truncation on large
real corpus programs (FB_BeltConveyor, TrafficController, BOILER, etc)
even at max_new_tokens=2560 -- these are genuinely large ASTs (150-250+
nodes), and the verbose tags alone were estimated to cost roughly
40-50% of the total serialized size for programs this size.

Usage:
    from ast_compact import ast_to_compact_json, compact_json_to_ast
    data = ast_to_compact_json(program)
    program2 = compact_json_to_ast(data)
"""

import ast_nodes as N

# short codes -- kept to 1-2 characters, chosen to be visually distinct
# enough for manual debugging while minimizing token cost
_TYPE_CODES = {
    N.Identifier: "Id",
    N.Literal: "Lit",
    N.BinaryOp: "Bin",
    N.UnaryOp: "Un",
    N.FunctionCallExpr: "FnE",
    N.ArrayIndex: "Arr",
    N.MemberAccess: "Mem",
    N.Assignment: "Asn",
    N.FunctionCallStatement: "FnS",
    N.If: "If",
    N.Case: "Cs",
    N.For: "For",
    N.While: "Wh",
    N.Repeat: "Rp",
    N.Return: "Ret",
    N.Exit: "Ex",
    N.VarDecl: "Vd",
    N.Program: "Prg",
}
_CODE_TO_TYPE = {v: k for k, v in _TYPE_CODES.items()}

# short field-name aliases for the highest-frequency fields, applied only
# where unambiguous per node type (kept as a flat global map since no
# field name collides across node types with a different meaning)
_FIELD_ALIASES = {
    "name": "n", "type": "ty", "scope": "sc", "kind": "k",
    "return_type": "rt", "variables": "vars", "body": "b",
    "target": "tg", "value": "v", "op": "o", "left": "l", "right": "r",
    "operand": "opd", "args": "a", "base": "ba", "index": "ix",
    "member": "m", "instance_name": "in", "named_args": "na",
    "branches": "br", "else_body": "eb", "selector": "sel",
    "loop_var": "lv", "start": "st", "end": "e", "step": "sp",
    "condition": "c", "text": "tx",
}
_ALIAS_TO_FIELD = {v: k for k, v in _FIELD_ALIASES.items()}


def ast_to_compact_json(node):
    if node is None:
        return None
    if isinstance(node, (str, int, float, bool)):
        return node
    if isinstance(node, list):
        return [ast_to_compact_json(item) for item in node]
    if isinstance(node, tuple):
        # (name_or_None, Expr) pairs -- represented as a plain 2-element
        # list rather than a tagged tuple wrapper, since the position
        # alone is unambiguous for these specific pair usages
        return [ast_to_compact_json(item) for item in node]

    node_type = type(node)
    if node_type not in _TYPE_CODES:
        raise TypeError(f"Don't know how to serialize {node_type}")

    result = {"t": _TYPE_CODES[node_type]}
    for field_name, value in vars(node).items():
        if value is None:
            continue  # omit null fields entirely rather than writing "field": null
        if isinstance(value, list) and not value:
            continue  # omit empty lists too -- e.g. an If with no else_body items
        alias = _FIELD_ALIASES.get(field_name, field_name)
        result[alias] = ast_to_compact_json(value)
    return result


def compact_json_to_ast(data, _expected_tuple_fields=("na", "a", "br")):
    """Reconstructs AST nodes from compact JSON. Note: since tuples were
    flattened to plain 2-element lists during serialization, this
    function re-wraps them into tuples for the specific fields that are
    supposed to hold (name_or_None, Expr) or (condition, body) pairs --
    see _expected_tuple_fields handling below."""
    if data is None:
        return None
    if isinstance(data, (str, int, float, bool)):
        return data
    if isinstance(data, list):
        return [compact_json_to_ast(item) for item in data]

    if not isinstance(data, dict):
        raise TypeError(f"Unexpected JSON value for AST node: {data!r}")

    code = data.get("t")
    if code not in _CODE_TO_TYPE:
        raise ValueError(f"Unknown or missing type code: {code!r}")

    node_cls = _CODE_TO_TYPE[code]
    kwargs = {}
    for key, value in data.items():
        if key == "t":
            continue
        field_name = _ALIAS_TO_FIELD.get(key, key)
        parsed_value = compact_json_to_ast(value)

        # re-wrap flattened 2-element lists into tuples for fields that
        # are supposed to hold pair-lists (named_args, args, branches)
        if field_name in ("named_args", "args", "branches") and isinstance(parsed_value, list):
            parsed_value = [
                tuple(item) if isinstance(item, list) and len(item) == 2 else item
                for item in parsed_value
            ]
        kwargs[field_name] = parsed_value

    return node_cls(**kwargs)


if __name__ == "__main__":
    # self-test + real size comparison against the verbose format
    import sys
    import pathlib
    import json as json_module

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from build_ast import build_program_ast
    from st_printer import print_program
    from ast_serialize import ast_to_json, json_to_ast

    with open(pathlib.Path(__file__).resolve().parents[1] / "data" / "processed" / "plcopen_ir.jsonl") as f:
        units = [json_module.loads(l) for l in f]
    unit = next(u for u in units if u["name"] == "GenericBistableDeviceModel")

    program, skipped = build_program_ast(unit)

    verbose_json = json_module.dumps(ast_to_json(program))
    compact_json = json_module.dumps(ast_to_compact_json(program))

    print(f"Verbose format: {len(verbose_json)} chars")
    print(f"Compact format: {len(compact_json)} chars")
    print(f"Reduction: {100*(1 - len(compact_json)/len(verbose_json)):.1f}%")
    print()

    # round-trip check: compact JSON -> AST -> print -> should match
    # what the verbose-format round-trip already produces
    reconstructed = compact_json_to_ast(ast_to_compact_json(program))
    original_printed = print_program(program)
    reconstructed_printed = print_program(reconstructed)
    print("Round-trip match (compact JSON -> AST -> print == original print):",
          original_printed == reconstructed_printed)
