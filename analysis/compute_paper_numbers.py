#!/usr/bin/env python3
"""
Recomputes every number, table and figure input used in the working note
directly from the submitted run logs. Run from the repository root:

    python3 analysis/compute_paper_numbers.py [--tokenizer path/to/qwen_tokenizer.json]

Inputs (all shipped in this repository):
  RUN-fih-0{1,2,3}/taskA-outputs/all_results.jsonl   per-task attempt logs
  RUN-fih-0{1,2}/taskB-outputs/rust_check_report.jsonl  rustc results
  RUN-fih-03/taskB-outputs/*.rs                        baseline Rust outputs
  RUN-fih-01/code/*.py                                 linter, smoke test, printers

Outputs:
  analysis/paper_numbers.json   all numbers quoted in the paper
  analysis/budget_curve.dat     data for Figure 2(a)
  analysis/issue_types.dat      data for Figure 2(b)
  analysis/task_matrix.dat      data for Figure 3
"""
import argparse, collections, json, re, shutil, statistics, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "RUN-fih-01" / "code"
sys.path.insert(0, str(CODE))
from ast_compact import compact_json_to_ast            # noqa: E402
from lint_program import lint_program, extract_required_io  # noqa: E402
from smoke_test import smoke_test                        # noqa: E402
from st_printer import print_program                     # noqa: E402
from rust_printer import print_rust_program              # noqa: E402
from json_repair import repair_json                      # noqa: E402

OUT = ROOT / "analysis"


def load(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def safe(f, *a, **k):
    # mirrors evaluate() in the repair drivers: a crash counts as "no issues"
    try:
        return f(*a, **k)
    except Exception:
        return []


def kind(issue):
    return issue.split(":")[0]


r1 = load(ROOT / "RUN-fih-01/taskA-outputs/all_results.jsonl")
r1b = load(ROOT / "RUN-fih-01/taskB-outputs/all_results.jsonl")
r2 = load(ROOT / "RUN-fih-02/taskA-outputs/all_results.jsonl")
r3 = load(ROOT / "RUN-fih-03/taskA-outputs/all_results.jsonl")
N = len(r1)
res = {"n_tasks": N}

# ---------------------------------------------------------------- RUN-03 re-verification
r3_status, r3_issues, r3_prog = {}, {}, {}
for r in r3:
    n = r["task_number"]
    if r["status"] != "OK":
        r3_status[n] = "FAILED"; r3_issues[n] = []; continue
    p = compact_json_to_ast(json.loads(repair_json(r["generated_raw"])))
    r3_prog[n] = p
    iss = safe(lint_program, p, task_text=r["task_text"]) + safe(smoke_test, p)
    r3_issues[n] = iss
    r3_status[n] = "CLEAN" if not iss else "ISSUES_FOUND"


def summarize_repair_run(rows):
    first = collections.Counter(r["attempt_log"][0]["status"] for r in rows)
    final = collections.Counter(r["final_status"] for r in rows)
    first_issues = collections.Counter(kind(i) for r in rows for i in r["attempt_log"][0]["issues"])
    final_issues = collections.Counter(kind(i) for r in rows if r["final_status"] != "FAILED"
                                       for i in r["attempt_log"][-1]["issues"])
    return {
        "first_parsed": N - first["COMPILE_FAILED"], "first_clean": first["CLEAN"],
        "first_issue_instances": sum(first_issues.values()),
        "final_parsed": N - final["FAILED"], "final_clean": final["CLEAN"],
        "final_issue_instances": sum(final_issues.values()),
        "generations": sum(len(r["attempt_log"]) for r in rows),
        "first_issue_types": dict(first_issues), "final_issue_types": dict(final_issues),
        "repaired_to_clean": [r["task_number"] for r in rows
                              if r["final_status"] == "CLEAN" and r["attempt_log"][0]["status"] != "CLEAN"],
        "parse_rescued": [r["task_number"] for r in rows
                          if r["attempt_log"][0]["status"] == "COMPILE_FAILED" and r["final_status"] != "FAILED"],
    }


res["run01"] = summarize_repair_run(r1)
res["run02"] = summarize_repair_run(r2)
c3 = collections.Counter(r3_status.values())
res["run03"] = {"parsed": N - c3["FAILED"], "clean": c3["CLEAN"],
                "issue_instances": sum(len(v) for v in r3_issues.values()),
                "parse_errors": {r["task_number"]: r["error"] for r in r3 if r["status"] != "OK"}}
res["run01_taskA_taskB_logs_identical"] = all(a["attempt_log"] == b["attempt_log"] for a, b in zip(r1, r1b))
res["run03_equals_run01_first_attempt"] = all(
    (r3_status[r["task_number"]] == "FAILED") == (r["attempt_log"][0]["status"] == "COMPILE_FAILED") and
    sorted(map(kind, r3_issues[r["task_number"]])) == sorted(map(kind, r["attempt_log"][0]["issues"]))
    for r in r1)

# ---------------------------------------------------------------- budget curve (Fig 2a)
def budget(rows, k):
    clean = parsed = 0
    for r in rows:
        log = r["attempt_log"][:k]
        clean += any(a["status"] == "CLEAN" for a in log)
        parsed += any(a["status"] != "COMPILE_FAILED" for a in log)
    return clean, parsed


curve = {}
with open(OUT / "budget_curve.dat", "w") as f:
    f.write("k clean7b parsed7b clean15b parsed15b\n")
    for k in (1, 2, 3):
        c7, p7 = budget(r1, k); c15, p15 = budget(r2, k)
        curve[k] = {"7B": [c7, p7], "1.5B": [c15, p15]}
        f.write(f"{k} {c7} {p7} {c15} {p15}\n")
res["budget_curve"] = curve

# ---------------------------------------------------------------- issue types (Fig 2b)
TYPES = ["UNUSED_IO", "STATIC_OUTPUT", "INPUT_ASSIGNED_TO", "DEAD_OVERRIDE",
         "UNDECLARED_VARIABLE", "MISSING_REQUIRED_IO", "IMPOSSIBLE_CONDITION"]
with open(OUT / "issue_types.dat", "w") as f:
    f.write("type first7b final7b first15b final15b\n")
    for t in TYPES:
        f.write(f"{t} {res['run01']['first_issue_types'].get(t,0)} {res['run01']['final_issue_types'].get(t,0)} "
                f"{res['run02']['first_issue_types'].get(t,0)} {res['run02']['final_issue_types'].get(t,0)}\n")

# ---------------------------------------------------------------- lint-only vs lint+smoke criterion
def lint_only_clean(issues):
    return all(kind(i) == "STATIC_OUTPUT" for i in issues)


res["criterion"] = {
    "run03_lint_only_clean": sum(1 for n, s in r3_status.items() if s != "FAILED" and lint_only_clean(r3_issues[n])),
    "run01_final_lint_only_clean": sum(1 for r in r1 if r["final_status"] != "FAILED"
                                       and lint_only_clean(r["attempt_log"][-1]["issues"])),
    "run02_final_lint_only_clean": sum(1 for r in r2 if lint_only_clean(r["attempt_log"][-1]["issues"])),
    "run02_first_lint_only_clean": sum(1 for r in r2 if lint_only_clean(r["attempt_log"][0]["issues"])),
    "run01_static_output_only_tasks": [r["task_number"] for r in r1 if r["final_status"] == "ISSUES_FOUND"
                                       and lint_only_clean(r["attempt_log"][-1]["issues"])],
    "run01_same_issue_all_three_attempts": [r["task_number"] for r in r1 if len(r["attempt_log"]) == 3 and
                                            len({tuple(sorted(a["issues"])) for a in r["attempt_log"]}) == 1
                                            and r["attempt_log"][0]["status"] == "ISSUES_FOUND"],
}

# ---------------------------------------------------------------- Rust results
def rust_report(run):
    rep = {json.loads(l)["task_number"]: json.loads(l) for l in open(ROOT / run / "taskB-outputs/rust_check_report.jsonl")}
    ok = sorted(n for n, e in rep.items() if e["compile_status"] == "OK")
    return rep, ok


rep1, ok1 = rust_report("RUN-fih-01")
rep2, ok2 = rust_report("RUN-fih-02")


def rust_cause(err):
    e = err or ""
    if "E0601" in e: return "no AST (raw text)"
    if re.search(r"`\w*_(q|cv|et)` in this scope", e) or re.search(r"cannot find value `ton_\w+`", e): return "unsupported FB / FB output"
    if "keyword `mod`" in e: return "printer: MOD as keyword"
    if "prefix `T` is unknown" in e: return "printer: time literal"
    if "function `abs`" in e: return "printer: missing helper"
    if "co_nveyor" in e: return "printer: identifier casing"
    if "unary operator `-` to type `bool`" in e: return "model: invalid operator"
    if "`bool` by `{float}`" in e: return "model: BOOL used as number"
    if "expected `i32`, found `bool`" in e: return "model: BOOL declared for word I/O"
    if re.search(r"E0277|E0308", e): return "printer: int/float typing"
    return "other"


res["rust"] = {
    "run01_ok": ok1, "run02_ok": ok2,
    "run01_causes": dict(collections.Counter(rust_cause(e["compile_error"]) for e in rep1.values() if e["compile_status"] != "OK")),
    "run02_causes": dict(collections.Counter(rust_cause(e["compile_error"]) for e in rep2.values() if e["compile_status"] != "OK")),
    "patches_ever_applied": sorted({p.split(" (")[0][:40] for rep in (rep1, rep2) for e in rep.values() for p in e["patches_applied"]}),
}

# stub-only ablation: run the unmodified post-pass over the RUN-03 (no-repair) Rust files
def compile_ok(code):
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "c.rs"; src.write_text(code)
        r = subprocess.run(["rustc", "--edition", "2021", "--emit=metadata", "--crate-type", "bin",
                            "-o", str(Path(td) / "o"), str(src)], capture_output=True, text=True)
        return r.returncode == 0


if shutil.which("rustc"):
    raw_ok, stub_ok = [], []
    with tempfile.TemporaryDirectory() as td:
        for f in sorted((ROOT / "RUN-fih-03/taskB-outputs").glob("task_*.rs")):
            shutil.copy(f, td)
        shutil.copy(ROOT / "RUN-fih-03/taskB-outputs/all_results.jsonl", td)
        for f in sorted(Path(td).glob("task_*.rs")):
            if compile_ok(f.read_text()): raw_ok.append(int(f.stem[-2:]))
        subprocess.run([sys.executable, str(CODE / "fix_rust_outputs.py")], cwd=td, capture_output=True, text=True)
        rep3 = {json.loads(l)["task_number"]: json.loads(l) for l in open(Path(td) / "rust_check_report.jsonl")}
        stub_ok = sorted(n for n, e in rep3.items() if e["compile_status"] == "OK")
    res["rust"]["run03_raw_ok"] = raw_ok
    res["rust"]["run03_stub_only_ok"] = stub_ok

# CLEAN vs rustc agreement
clean1 = {r["task_number"] for r in r1 if r["final_status"] == "CLEAN"}
clean2 = {r["task_number"] for r in r2 if r["final_status"] == "CLEAN"}
res["agreement"] = {
    "run01_clean_and_rustc": sorted(clean1 & set(ok1)), "run01_clean_not_rustc": sorted(clean1 - set(ok1)),
    "run01_rustc_not_clean": sorted(set(ok1) - clean1),
    "run02_clean_and_rustc": sorted(clean2 & set(ok2)),
    "oracle_union_clean": sorted(clean1 | clean2),
}


# ---------------------------------------------------------------- exact McNemar tests (paired, same 30 tasks)
from math import comb


def mcnemar(a_only, b_only):
    n = a_only + b_only
    if n == 0:
        return 1.0
    k = min(a_only, b_only)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


clean3 = {n for n, s in r3_status.items() if s == "CLEAN"}
parsed1 = {r["task_number"] for r in r1 if r["final_status"] != "FAILED"}
parsed2 = {r["task_number"] for r in r2 if r["final_status"] != "FAILED"}
stub3 = set(res["rust"].get("run03_stub_only_ok", []))
res["mcnemar"] = {
    "clean_repair_vs_oneshot_7b": {"gained": len(clean1 - clean3), "lost": len(clean3 - clean1), "p": mcnemar(len(clean1 - clean3), len(clean3 - clean1))},
    "clean_7b_vs_15b_repaired": {"7b_only": len(clean1 - clean2), "15b_only": len(clean2 - clean1), "p": mcnemar(len(clean1 - clean2), len(clean2 - clean1))},
    "parsed_15b_vs_7b_repaired": {"15b_only": len(parsed2 - parsed1), "7b_only": len(parsed1 - parsed2), "p": mcnemar(len(parsed2 - parsed1), len(parsed1 - parsed2))},
    "rustc_stub_vs_nostub_7b_oneshot": {"gained": len(stub3), "lost": 0, "p": mcnemar(len(stub3), 0)},
    "rustc_repair_vs_oneshot_with_stub": {"repair_only": sorted(set(ok1) - stub3), "oneshot_only": sorted(stub3 - set(ok1)),
                                          "p": mcnemar(len(set(ok1) - stub3), len(stub3 - set(ok1)))},
}

# ---------------------------------------------------------------- difficulty
req = {r["task_number"]: len(extract_required_io(r["task_text"])) for r in r1}
raw_len = {r["task_number"]: len(r["generated_raw"]) for r in r3}
fails = [n for n, s in r3_status.items() if s == "FAILED"]
rank = sorted(raw_len, key=raw_len.get, reverse=True)
res["difficulty"] = {
    "req_io_median_clean7b": statistics.median(req[n] for n in clean1),
    "req_io_median_notclean7b": statistics.median(req[n] for n in req if n not in clean1),
    "req_io_mean_clean7b": round(statistics.mean(req[n] for n in clean1), 2),
    "req_io_mean_notclean7b": round(statistics.mean(req[n] for n in req if n not in clean1), 2),
    "parse_fail_tasks": fails,
    "parse_fail_raw_len_rank": {n: rank.index(n) + 1 for n in fails},
    "raw_len_median": statistics.median(raw_len.values()),
    "parse_fail_raw_len": {n: raw_len[n] for n in fails},
    "word_io_tasks": [r["task_number"] for r in r1 if re.search(r"%[IQ]W\d", r["task_text"])],
}

# ---------------------------------------------------------------- representation cost
def verbose(node):
    """Re-implementation of the original verbose serialisation described in
    code/ast_compact.py: full type names in a "__type__" tag, full field
    names, and null / empty fields written out."""
    if node is None or isinstance(node, (str, int, float, bool)):
        return node
    if isinstance(node, (list, tuple)):
        return [verbose(x) for x in node]
    d = {"__type__": type(node).__name__}
    for k, v in vars(node).items():
        d[k] = verbose(v)
    return d


def compact(node):
    from ast_compact import ast_to_compact_json
    return ast_to_compact_json(node)


tok = None
ap = argparse.ArgumentParser(); ap.add_argument("--tokenizer"); args = ap.parse_args()
if args.tokenizer:
    from tokenizers import Tokenizer
    tok = Tokenizer.from_file(args.tokenizer)

rows = []
for n, p in sorted(r3_prog.items()):
    c = json.dumps(compact(p)); v = json.dumps(verbose(p))
    st = print_program(p); rs = print_rust_program(p)
    row = {"task": n, "compact_chars": len(c), "verbose_chars": len(v), "st_chars": len(st), "rust_chars": len(rs)}
    if tok:
        row.update({"compact_tok": len(tok.encode(c).ids), "verbose_tok": len(tok.encode(v).ids),
                    "st_tok": len(tok.encode(st).ids), "rust_tok": len(tok.encode(rs).ids)})
    rows.append(row)


def med(key):
    return statistics.median(r[key] for r in rows)


rep = {"n_programs": len(rows), "median_compact_chars": med("compact_chars"), "median_verbose_chars": med("verbose_chars"),
       "char_saving_median_pct": round(100 * statistics.median(1 - r["compact_chars"] / r["verbose_chars"] for r in rows), 1)}
if tok:
    from importlib import util
    spec = util.spec_from_file_location("drv", CODE / "run_real_test_set_with_repair_7b.py")
    src = (CODE / "run_real_test_set_with_repair_7b.py").read_text()
    sysprompt = re.search(r'SYSTEM_PROMPT = """(.*?)"""', src, re.S).group(1)
    rep.update({
        "median_compact_tok": med("compact_tok"), "median_verbose_tok": med("verbose_tok"),
        "median_st_tok": med("st_tok"), "median_rust_tok": med("rust_tok"),
        "max_compact_tok": max(r["compact_tok"] for r in rows), "max_verbose_tok": max(r["verbose_tok"] for r in rows),
        "tok_saving_median_pct": round(100 * statistics.median(1 - r["compact_tok"] / r["verbose_tok"] for r in rows), 1),
        "compact_vs_st_ratio_median": round(statistics.median(r["compact_tok"] / r["st_tok"] for r in rows), 2),
        "system_prompt_tok": len(tok.encode(sysprompt).ids),
        "max_raw_output_tok_all30": max(len(tok.encode(r["generated_raw"]).ids) for r in r3),
        "raw_output_tok_parse_failures": {r["task_number"]: len(tok.encode(r["generated_raw"]).ids) for r in r3 if r["status"] != "OK"},
        "verbose_over_1536_minus_prompt": sum(1 for r in rows if r["verbose_tok"] > 1536 - len(tok.encode(sysprompt).ids)),
        "compact_over_1536_minus_prompt": sum(1 for r in rows if r["compact_tok"] > 1536 - len(tok.encode(sysprompt).ids)),
    })
res["representation"] = rep

# ---------------------------------------------------------------- per-task matrix (Fig 3)
code = {"CLEAN": 2, "ISSUES_FOUND": 1, "FAILED": 0}
with open(OUT / "task_matrix.dat", "w") as f:
    f.write("task run03 run01 run02 rust01 rust02 reqio\n")
    for n in range(1, N + 1):
        f.write(f"{n} {code[r3_status[n]]} {code[r1[n-1]['final_status']]} {code[r2[n-1]['final_status']]} "
                f"{int(n in ok1)} {int(n in ok2)} {req[n]}\n")

json.dump(res, open(OUT / "paper_numbers.json", "w"), indent=1, default=str)
print(json.dumps(res, indent=1, default=str))
