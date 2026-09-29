"""Asserts every number quoted in Section 4-5 of the paper against the analysis outputs."""
import json, os
from math import comb
H = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(H, "paper_numbers.json")))
O = json.load(open(os.path.join(H, "output_numbers.json")))
C = O["configs"]
def sign_p(u, d):
    n = u + d; k = min(u, d)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)
ok = []
def chk(name, cond):
    ok.append(cond); print(("PASS " if cond else "FAIL ") + name)
chk("gen calls 30/58/69", (30, P["run01"]["generations"], P["run02"]["generations"]) == (30, 58, 69))
chk("parsed 26/27/30", (C["oneshot7"]["parsed"], C["repair7"]["parsed"], C["repair15"]["parsed"]) == (26, 27, 30))
chk("clean 15/18/12", tuple(len(C[c]["clean"]) for c in ("oneshot7", "repair7", "repair15")) == (15, 18, 12))
chk("front-end 24/25/26", tuple(len(C[c]["front_end_ok"]) for c in ("oneshot7", "repair7", "repair15")) == (24, 25, 26))
I = {c: C[c]["interface_parsed_programs"] for c in C}
chk("I/O declared 120/121 125/126 140/151", [(I[c]["declared"], I[c]["required"]) for c in ("oneshot7", "repair7", "repair15")] == [(120, 121), (125, 126), (140, 151)])
chk("dir/type/used", [(I[c]["direction_ok"], I[c]["type_ok"], I[c]["used"]) for c in ("oneshot7", "repair7", "repair15")] == [(120, 116, 113), (125, 121, 119), (137, 133, 129)])
chk("durations 10/12 10/12 12/14", [(C[c]["durations_matched"], C[c]["durations_required"]) for c in ("oneshot7", "repair7", "repair15")] == [(10, 12), (10, 12), (12, 14)])
chk("earned active 18/20/4 of 91", [C[c]["active_checks_passed"] for c in ("oneshot7", "repair7", "repair15")] == [18, 20, 4] and O["n_active_checks"] == 91)
chk("1.5B raw active 14", C["repair15"]["active_raw_passed"] == 14)
chk("categories 26/34/31", O["active_by_category"] == {"memory": 26, "timing": 34, "direct": 31})
chk("per-category", [tuple(C[c]["active_passed_by_category"][k] for k in ("memory", "timing", "direct")) for c in ("oneshot7", "repair7", "repair15")] == [(3, 3, 12), (3, 3, 14), (0, 1, 3)])
chk("all-check totals 77/78/67 vs do-nothing 78", [C[c]["probe_checks_passed"] for c in ("oneshot7", "repair7", "repair15")] == [77, 78, 67])
chk("always-on: 50 active passed, 2 earned", O["always_on_baseline"]["active_passed"] == 50 and O["always_on_baseline"]["active_earned"] == 2)
chk("tasks all 2/2/0 (5 and 9)", [C[c]["probe_tasks_all"] for c in ("oneshot7", "repair7", "repair15")] == [[5, 9], [5, 9], []])
chk("169 checks, null 78, ref 169", O["n_probe_checks"] == 169 and O["null_baseline"]["checks_passed"] == 78 and O["reference_check"]["checks_passed"] == 169)
R = O["rust"]
chk("rust addr 113/116 118/121 137/146", [(R[c]["addr_matched"], R[c]["addr_checked"]) for c in ("oneshot7", "repair7", "repair15")] == [(113, 116), (118, 121), (137, 146)])
chk("7B addr slip only task 26", list(R["repair7"]["addr_wrong"]) == ["26"])
chk("spec shared numbers 24", len(R["spec_tasks_with_shared_numbers"]) == 24)
chk("rustc 18/18/18 incl stub-only", (len(P["rust"]["run03_stub_only_ok"]), len(P["rust"]["run01_ok"]), len(P["rust"]["run02_ok"])) == (18, 18, 18))
chk("stub p<1e-5", P["mcnemar"]["rustc_stub_vs_nostub_7b_oneshot"]["p"] < 1e-5)
chk("repair swapped 14 in, 21 out", P["mcnemar"]["rustc_repair_vs_oneshot_with_stub"] == {"repair_only": [14], "oneshot_only": [21], "p": 1.0})
chk("12 failures: 3 no AST, 6 printer, 3 model", P["rust"]["run01_causes"] == {"unsupported FB / FB output": 3, "no AST (raw text)": 3, "printer: int/float typing": 3, "model: invalid operator": 1, "model: BOOL declared for word I/O": 2})
chk("clean rate 33%", C["repair7"]["active_rate_clean"] == 0.333)
fl = [i for i in range(1, 31) if C["repair7"]["probe_errors"].get(str(i)) != "no program" and i not in C["repair7"]["clean"]]
ap = C["repair7"]["active_per_task"]
chk("flagged 0%", sum(ap[str(i)][0] for i in fl) == 0)
chk("clean McNemar 3/0 p=.25", P["mcnemar"]["clean_repair_vs_oneshot_7b"] == {"gained": 3, "lost": 0, "p": 0.25})
chk("clean 7B vs 1.5B p=.15", round(P["mcnemar"]["clean_7b_vs_15b_repaired"]["p"], 2) == 0.15)
chg = O["repair7_changed_files"]
ea = {i: (C["oneshot7"]["active_per_task"][str(i)][0], C["repair7"]["active_per_task"][str(i)][0]) for i in range(1, 31)}
chk("repair changed 8; earned up only 14, down only 21", len(chg) == 8 and [i for i, (a, b) in ea.items() if b > a] == [14] and [i for i, (a, b) in ea.items() if b < a] == [21])
u = sum(C["repair7"]["active_per_task"][str(i)][0] > C["repair15"]["active_per_task"][str(i)][0] for i in range(1, 31))
d = sum(C["repair7"]["active_per_task"][str(i)][0] < C["repair15"]["active_per_task"][str(i)][0] for i in range(1, 31))
chk("7B vs 1.5B 9 vs 0 p=.004", (u, d) == (9, 0) and round(sign_p(u, d), 3) == 0.004)
chk("union clean 21", len(P["agreement"]["oracle_union_clean"]) == 21)
chk("budget +2 +1 / +3 +0", [P["budget_curve"][k]["7B"][0] for k in "123"] == [15, 17, 18] and [P["budget_curve"][k]["1.5B"][0] for k in "123"] == [9, 12, 12])
chk("static 9->9, missing 3->6", P["run01"]["first_issue_types"]["STATIC_OUTPUT"] == 9 and P["run01"]["final_issue_types"]["STATIC_OUTPUT"] == 9 and P["run02"]["first_issue_types"]["MISSING_REQUIRED_IO"] == 3 and P["run02"]["final_issue_types"]["MISSING_REQUIRED_IO"] == 6)
chk("1.5B lacks 11/151, 3 wrong dir, 9/146", I["repair15"]["required"] - I["repair15"]["declared"] == 11 and I["repair15"]["declared"] - I["repair15"]["direction_ok"] == 3 and R["repair15"]["addr_checked"] - R["repair15"]["addr_matched"] == 9)
chk("front-end fails of clean 7B+repair are 4 and 21", sorted(int(k) for k in C["repair7"]["front_end_errors"]) == [4, 21] and {4, 21} <= set(C["repair7"]["clean"]))
chk("1.5B front-end fails 4,7,28,30", sorted(int(k) for k in C["repair15"]["front_end_errors"]) == [4, 7, 28, 30])
chk("representation 4.2x, 10%", round(P["representation"]["compact_vs_st_ratio_median"], 1) == 4.2 and round(P["representation"]["tok_saving_median_pct"]) == 10)
chk("task 17 T#10s in all three", all(C[c]["duration_detail"]["17"]["have"] == [10000] for c in C))
# 1.5B missing required I/O: dropped by the ST printer (present in the Rust) vs omitted by the model
import re, sys
sys.path.insert(0, H)
import analyze_outputs as A, st_sim
tasks = A.load_tasks(); files = A.st_files("RUN-fih-02"); prn = mdl = 0
for i in range(1, 31):
    p = st_sim.Program(files[i]); rs = A.rust_file("repair15", i) or ""
    for d in A.required_io(tasks[i]):
        if d["name"].lower() not in p.section:
            if re.search(r"let mut %s\b" % A.snake(d["name"]), rs): prn += 1
            else: mdl += 1
chk("1.5B missing I/O: 5 printer-dropped, 6 model-omitted", (prn, mdl) == (5, 6))
print(f"{sum(ok)}/{len(ok)} claims verified")
