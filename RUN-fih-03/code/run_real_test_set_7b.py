"""
Runs the 1.5B LoRA adapter on FIRE's real 30 test-set tasks and
produces ST code for each -- the actual submission deliverable.

Usage:
    python3 run_real_test_set_1_5b.py

Requires Test-Dataset-AI4Industrial-Automation.xlsx present in this
folder.
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
from st_printer import print_program

BASE_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
ADAPTER_PATH = "./lora_nl2ast_adapter_7b"
RUN_NAME = "7b"

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


if __name__ == "__main__":
    if not pathlib.Path(XLSX_PATH).exists():
        print(f"{XLSX_PATH} not found -- place it in this folder.")
        raise SystemExit(1)

    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
    ws = wb.active
    tasks = [row[0] for row in ws.iter_rows(min_row=2, values_only=True) if row[0]]
    print(f"[{RUN_NAME}] Loaded {len(tasks)} real test tasks")

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, device_map="auto", dtype=torch.bfloat16,
    )
    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    model.eval()

    results = []
    for i, task in enumerate(tasks):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Task: {task}\n\nOutput the AST as JSON:"},
        ]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        output = model.generate(**inputs, max_new_tokens=2560, do_sample=False)
        generated_raw = tokenizer.decode(output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        generated = strip_code_fence(generated_raw)

        status, st_code, error = "FAILED", None, None
        try:
            try:
                ast_data = json.loads(generated)
            except json.JSONDecodeError:
                ast_data = json.loads(repair_json(generated))
            program = compact_json_to_ast(ast_data)
            st_code = print_program(program)
            status = "OK"
        except Exception as e:
            error = f"{type(e).__name__}: {e}"

        print(f"[{RUN_NAME}] [{i+1}/{len(tasks)}] Task {i+1}: {status}" + (f" -- {error}" if error else ""))

        out_file = OUT_DIR / f"task_{i+1:02d}.st"
        out_file.write_text(st_code if st_code else f"// GENERATION FAILED: {error}\n// Raw output:\n// {generated_raw}")

        results.append({
            "task_number": i + 1, "task_text": task, "status": status,
            "error": error, "generated_raw": generated_raw, "st_code": st_code,
        })

    with open(OUT_DIR / "all_results.jsonl", "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    ok_count = sum(1 for r in results if r["status"] == "OK")
    print(f"\n[{RUN_NAME}] {ok_count}/{len(results)} real test tasks produced valid ST")
    print(f"[{RUN_NAME}] Individual .st files + full results written to {OUT_DIR}/")
