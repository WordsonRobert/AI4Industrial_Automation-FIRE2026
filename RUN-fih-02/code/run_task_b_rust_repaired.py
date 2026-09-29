"""
Task B (NL -> Rust) WITH the same generate -> lint -> smoke -> repair
loop used for Task A. The lint and smoke checks operate on the shared
AST, not the target language, so they apply identically here -- only
the final compilation step (print_rust_program instead of print_program)
differs from the Task A repair script.

After this, run fix_rust_outputs.py against the output directory for
the Rust-specific pass (missing helper functions, statement ordering,
hardcoded scan-count timers, and a real rustc compile gate) that the
shared AST-level lint can't see.

Usage:
    python3 run_task_b_rust_repaired.py
"""

import re
import sys
import json
import pathlib
import torch
import openpyxl
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from json_repair import repair_json

sys.path.insert(0, ".")
from ast_compact import compact_json_to_ast
from rust_printer import print_rust_program
from lint_program import lint_program
from smoke_test import smoke_test

BASE_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
ADAPTER_PATH = "./lora_nl2ast_adapter_7b"
RUN_NAME = "7b_rust_repaired"
MAX_ATTEMPTS = 3

XLSX_PATH = "Test-Dataset-AI4Industrial-Automation.xlsx"
OUT_DIR = pathlib.Path(f"submission_output_{RUN_NAME}")
OUT_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT = """You are an expert industrial automation programmer. Given a natural language description of a PLC control task, output ONLY a JSON object representing the program as a compact Abstract Syntax Tree (AST). Do not output any explanation, markdown formatting, or IEC 61131-3 Structured Text -- only the raw JSON AST.

The AST uses a "t" field to identify each node's type, and short field names to keep output compact:

Program: {"t":"Prg", "name": str, "kind": "program"|"function_block"|"function", "rt": str (optional, return type), "vars": [VarDecl], "b": [Statement]}
VarDecl: {"t":"Vd", "n": str, "ty": str, "sc": "input"|"output"|"local"|"inout"|"temp"}

Statements:
Assignment: {"t":"Asn", "tg": str (target), "v": Expr (value)}
FunctionCallStatement: {"t":"FnS", "in": str (instance_name), "na": [[param_name_or_null, Expr]]}
If: {"t":"If", "br": [[condition_Expr, [Statement]]], "eb": [Statement] (optional, else body)}
Case: {"t":"Cs", "sel": Expr (selector), "br": [[label_str, [Statement]]]}
For: {"t":"For", "lv": str (loop_var), "st": Expr (start), "e": Expr (end), "sp": Expr (optional, step), "b": [Statement]}
While: {"t":"Wh", "c": Expr (condition), "b": [Statement]}
Repeat: {"t":"Rp", "b": [Statement], "c": Expr (condition, checked at end)}
Return: {"t":"Ret"}
Exit: {"t":"Ex"}

Expressions:
Identifier: {"t":"Id", "n": str (name)}
Literal: {"t":"Lit", "tx": str (text)}
BinaryOp: {"t":"Bin", "o": str (op), "l": Expr (left), "r": Expr (right)}
UnaryOp: {"t":"Un", "o": "NOT"|"-", "opd": Expr (operand)}
FunctionCallExpr: {"t":"FnE", "n": str (name), "a": [[param_name_or_null, Expr]]}
ArrayIndex: {"t":"Arr", "ba": Expr (base), "ix": Expr (index)}
MemberAccess: {"t":"Mem", "ba": Expr (base), "m": str (member)}

Omit any field that would be null or an empty list -- do not write "field": null.
"""


def strip_code_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def generate(model, tokenizer, messages):
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    output = model.generate(**inputs, max_new_tokens=2560, do_sample=False)
    return tokenizer.decode(output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)


def evaluate(generated_raw, task_text):
    """Same evaluate() as the Task A repair script, except the final
    compile step calls print_rust_program instead of print_program."""
    generated = strip_code_fence(generated_raw)
    try:
        try:
            ast_data = json.loads(generated)
        except json.JSONDecodeError:
            ast_data = json.loads(repair_json(generated))
        program = compact_json_to_ast(ast_data)
        rust_code = print_rust_program(program)
    except Exception as e:
        return "COMPILE_FAILED", None, None, [], f"{type(e).__name__}: {e}"

    try:
        lint_issues = lint_program(program, task_text=task_text)
    except Exception:
        lint_issues = []
    try:
        smoke_issues = smoke_test(program)
    except Exception:
        smoke_issues = []

    all_issues = lint_issues + smoke_issues
    if all_issues:
        return "ISSUES_FOUND", rust_code, program, all_issues, None
    return "CLEAN", rust_code, program, [], None


if __name__ == "__main__":
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
    ws = wb.active
    tasks = [row[0] for row in ws.iter_rows(min_row=2, values_only=True) if row[0]]
    print(f"[{RUN_NAME}] Loaded {len(tasks)} real test tasks")

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    base_model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, device_map="auto", dtype=torch.bfloat16)
    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    model.eval()

    results = []
    for i, task in enumerate(tasks):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Task: {task}\n\nOutput the AST as JSON:"},
        ]

        attempt_log = []
        final_status, final_rust, final_raw = "FAILED", None, None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            generated_raw = generate(model, tokenizer, messages)
            final_raw = generated_raw
            status, rust_code, program, issues, compile_error = evaluate(generated_raw, task)
            attempt_log.append({"attempt": attempt, "status": status,
                                 "issues": issues, "compile_error": compile_error})

            if status == "CLEAN":
                final_status, final_rust = "CLEAN", rust_code
                break
            if status == "ISSUES_FOUND":
                final_status, final_rust = "ISSUES_FOUND", rust_code

            if compile_error:
                feedback = f"That output failed to compile with this error: {compile_error}\n\nPlease provide a corrected JSON AST that fixes this specific problem."
            else:
                issue_text = "\n".join(f"- {iss}" for iss in issues)
                feedback = (f"That output compiled, but automated review found these problems:\n{issue_text}\n\n"
                            f"Please provide a corrected JSON AST that fixes these specific problems. "
                            f"IMPORTANT: never fix an unused-variable warning by deleting the variable "
                            f"or removing it from the task -- every input/output listed in the task with "
                            f"an address must remain declared AND be genuinely used in real logic. "
                            f"Never assign a value to a declared INPUT variable. Never write a constant "
                            f"assignment to an output after conditional logic has already set it.")

            messages = messages + [
                {"role": "assistant", "content": generated_raw},
                {"role": "user", "content": feedback},
            ]

        print(f"[{RUN_NAME}] [{i+1}/{len(tasks)}] Task {i+1}: {final_status} "
              f"(after {len(attempt_log)} attempt(s))")

        out_file = OUT_DIR / f"task_{i+1:02d}.rs"
        out_file.write_text(final_rust if final_rust else f"// GENERATION FAILED\n// Raw: {final_raw}")

        results.append({
            "task_number": i + 1, "task_text": task, "final_status": final_status,
            "attempt_log": attempt_log, "rust_code": final_rust,
        })

    with open(OUT_DIR / "all_results.jsonl", "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    clean_count = sum(1 for r in results if r["final_status"] == "CLEAN")
    issues_count = sum(1 for r in results if r["final_status"] == "ISSUES_FOUND")
    failed_count = sum(1 for r in results if r["final_status"] == "FAILED")
    print(f"\n[{RUN_NAME}] {clean_count}/{len(results)} fully clean (compile + lint + smoke)")
    print(f"[{RUN_NAME}] {issues_count}/{len(results)} compiled but still have flagged issues")
    print(f"[{RUN_NAME}] {failed_count}/{len(results)} never compiled")
    print(f"[{RUN_NAME}] Output written to {OUT_DIR}/")
