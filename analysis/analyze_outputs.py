"""
analyze_outputs.py -- output-level analysis of the submitted files.

Reads only the files under RUN-fih-0{1,2,3}/taskA-outputs and taskB-outputs
and writes analysis/output_numbers.json. Configurations:
    oneshot7  = RUN-fih-03  (7B, one greedy attempt; = first attempt of RUN-01)
    repair7   = RUN-fih-01  (7B, verify-and-repair, <= 3 attempts)
    repair15  = RUN-fih-02  (1.5B, verify-and-repair, <= 3 attempts)

Analyses
  1. front-end check of each ST file (parse + name resolution, st_sim.py)
  2. behavioural probes (probes.py; validated on probe_reference/)
  3. interface fidelity against the task's address list
  4. timing fidelity: durations in the task text vs T# literals
  5. repair edit rate and cross-model agreement
  6. Rust: Modbus address fidelity and input/output address sharing

usage: python3 analysis/analyze_outputs.py
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import st_sim   # noqa: E402
import probes   # noqa: E402
import categories  # noqa: E402

CONFIGS = {"oneshot7": "RUN-fih-03", "repair7": "RUN-fih-01", "repair15": "RUN-fih-02"}
N = 30


def load_tasks():
    rows = [json.loads(x) for x in open(os.path.join(ROOT, "RUN-fih-01/taskA-outputs/all_results.jsonl"))]
    return {r["task_number"]: r["task_text"] for r in rows}


def load_status():
    """Lint+sim verdict per task and config, from the logs."""
    out = {}
    for cfg, run in CONFIGS.items():
        rows = [json.loads(x) for x in open(os.path.join(ROOT, run, "taskA-outputs/all_results.jsonl"))]
        out[cfg] = {r["task_number"]: r.get("final_status") for r in rows}
    # the one-shot run was not linted by its own driver; it is byte-identical to the
    # first attempt of RUN-fih-01 (checked in compute_paper_numbers.py), so use that verdict
    rows = [json.loads(x) for x in open(os.path.join(ROOT, "RUN-fih-01/taskA-outputs/all_results.jsonl"))]
    out["oneshot7"] = {r["task_number"]: r["attempt_log"][0]["status"] for r in rows}
    return out


IO_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:?\s*(%[IQ][XW][0-9.]+|[AD][IO]:[0-9.]+)\s*$")


def required_io(text):
    io = []
    for line in text.splitlines():
        m = IO_RE.match(line)
        if m:
            name, addr = m.groups()
            if addr.startswith("%"):
                direction = "in" if addr[1] == "I" else "out"
                kind = "bit" if addr[2] == "X" else "word"
            else:
                direction = "in" if addr[1] == "I" else "out"
                kind = "bit" if addr[0] == "D" else "word"
            io.append({"name": name, "addr": addr, "dir": direction, "kind": kind})
    return io


DUR_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|s\b|seconds?|minutes?|min\b)", re.I)


def required_durations(text):
    body = "\n".join(l for l in text.splitlines() if not IO_RE.match(l))
    out = set()
    for val, unit in DUR_RE.findall(body):
        u = unit.lower()
        mult = 1 if u == "ms" else 60000 if u.startswith("min") else 1000
        out.add(int(round(float(val) * mult)))
    return sorted(out)


def st_files(run):
    out = {}
    for i in range(1, N + 1):
        src = open(os.path.join(ROOT, run, "taskA-outputs", f"task_{i:02d}.st")).read()
        out[i] = None if src.lstrip().startswith("// GENERATION FAILED") else src
    return out


def front_end(src):
    try:
        p = st_sim.Program(src)
    except st_sim.STError as e:
        return None, [str(e)]
    return p, p.static_errors()


def run_probe(i, src):
    """Runs the probe of task i; a program that fails the front-end fails every check."""
    p, errs = front_end(src) if src else (None, ["no program"])
    ref = _probe_checks(i)
    fail_all = [(l, False, o) for l, _, o in ref]
    if p is None or errs:
        checks, err = fail_all, (errs or ["?"])[0]
    else:
        h = probes.Harness(p)
        try:
            probes.PROBES[i](h)
            checks, err = h.checks, None
        except st_sim.STError as e:
            checks, err = fail_all, f"runtime: {e}"
    passed = sum(ok for _, ok, _ in checks)
    return {"passed": passed, "total": len(checks), "all": passed == len(checks), "error": err,
            "failed": [l for l, ok, _ in checks if not ok], "checks": checks}


_REF = {}


def _probe_checks(i):
    if i not in _REF:
        p = st_sim.Program(open(os.path.join(HERE, "probe_reference", f"task_{i:02d}.st")).read())
        h = probes.Harness(p)
        probes.PROBES[i](h)
        _REF[i] = h.checks
    return _REF[i]


def _probe_labels(i):
    return [l for l, _, _ in _probe_checks(i)]


def earned(result, active):
    """Active checks passed whose outputs also pass every passive check of the task,
    so an output that is on where the task requires it off earns nothing."""
    bad = set()
    for l, ok, outs in result["checks"]:
        if l not in active and not ok:
            bad.update(outs)
    return [l for l, ok, outs in result["checks"] if l in active and ok and not (set(outs) & bad)]


def always_on_program(io):
    """Declares the required I/O and drives every BOOL output TRUE on every scan."""
    s = null_program(io).replace("END_PROGRAM\n", "")
    for d in io:
        if d["dir"] == "out" and d["kind"] == "bit":
            s += f"{d['name']} := TRUE;\n"
    return s + "END_PROGRAM\n"


def null_program(io):
    """Declares every required I/O with the right direction/type, writes nothing."""
    ins = [d for d in io if d["dir"] == "in"]
    outs = [d for d in io if d["dir"] == "out"]

    def decl(d):
        return f"    {d['name']} : {'BOOL' if d['kind'] == 'bit' else 'INT'};\n"
    s = "PROGRAM Null\n"
    if ins:
        s += "VAR_INPUT\n" + "".join(decl(d) for d in ins) + "END_VAR\n"
    if outs:
        s += "VAR_OUTPUT\n" + "".join(decl(d) for d in outs) + "END_VAR\n"
    return s + "END_PROGRAM\n"


INT_LIKE = st_sim.INT_TYPES | st_sim.REAL_TYPES


def interface(p, io):
    decl = {k: (p.section[k], p.types[k], p.display[k]) for k in p.section}
    body_ids = set()

    def walk(x):
        if isinstance(x, tuple):
            if len(x) >= 2 and x[0] in ("id",) and isinstance(x[1], str):
                body_ids.add(x[1].lower())
            if x and x[0] == "assign":
                body_ids.add(x[1].lower())
            for y in x:
                walk(y)
        elif isinstance(x, list):
            for y in x:
                walk(y)
    walk(p.ast["body"])
    r = {"required": len(io), "declared": 0, "direction_ok": 0, "type_ok": 0, "used": 0,
         "exact_case": 0, "real_on_word": 0}
    for d in io:
        k = d["name"].lower()
        if k not in decl:
            continue
        sec, ty, disp = decl[k]
        r["declared"] += 1
        r["exact_case"] += disp == d["name"]
        want = "VAR_INPUT" if d["dir"] == "in" else "VAR_OUTPUT"
        r["direction_ok"] += sec == want
        if d["kind"] == "bit":
            r["type_ok"] += ty == "BOOL"
        else:
            r["type_ok"] += ty in INT_LIKE
            r["real_on_word"] += ty in st_sim.REAL_TYPES
        r["used"] += k in body_ids
    req = {d["name"].lower() for d in io}
    r["extra_io"] = sum(1 for k, (sec, _, _) in decl.items()
                        if sec in ("VAR_INPUT", "VAR_OUTPUT") and k not in req)
    return r


def time_literals(src):
    return sorted({st_sim.parse_time_ms(m) for m in re.findall(r"\b(?:T|TIME)#[0-9A-Za-z_.]+", src)})


def norm(src):
    body = re.sub(r"^PROGRAM\s+\w+", "PROGRAM X", src.strip(), flags=re.M)
    return re.sub(r"\s+", " ", body).lower()


# ------------------------------------------------------------------ Rust
RUST_DIRS = {"oneshot7": ("RUN-fih-03", "task_{:02d}.rs"),
             "repair7": ("RUN-fih-01", "fixed_task_{:02d}.rs"),
             "repair15": ("RUN-fih-02", "task_{:02d}.rs")}


def rust_file(cfg, i):
    run, pat = RUST_DIRS[cfg]
    p = os.path.join(ROOT, run, "taskB-outputs", pat.format(i))
    if not os.path.exists(p):
        p = os.path.join(ROOT, run, "taskB-outputs", f"task_{i:02d}.rs")
    return open(p).read() if os.path.exists(p) else None


def expected_modbus(d):
    a = d["addr"]
    m = re.fullmatch(r"%[IQ]X(\d+)\.(\d+)", a)
    if m:
        return ("coil", int(m.group(1)) * 8 + int(m.group(2)))
    m = re.fullmatch(r"%[IQ]W(\d+)", a)
    if m:
        return ("reg", int(m.group(1)))
    return None


def rust_io(src):
    """name -> (table, address, 'in'/'out') from the scan-loop reads/writes."""
    out = {}
    for name, fn, addr in re.findall(r"(\w+)\s*=\s*self\.client\.(read_coils|read_holding_register)\((\d+)", src):
        out.setdefault(name.lower(), []).append(("coil" if fn == "read_coils" else "reg", int(addr), "in"))
    for fn, addr, name in re.findall(r"self\.client\.(write_coil|write_register)\((\d+),\s*(\w+)\)", src):
        out.setdefault(name.lower(), []).append(("coil" if fn == "write_coil" else "reg", int(addr), "out"))
    return out


def snake(name):
    """Same conversion as code/rust_printer.py::_to_snake."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", s)
    return s.lower().replace("__", "_")


def main():
    tasks = load_tasks()
    status = load_status()
    io = {i: required_io(tasks[i]) for i in tasks}
    durs = {i: required_durations(tasks[i]) for i in tasks}
    res = {"n_tasks": N, "n_probe_checks": sum(len(_probe_labels(i)) for i in range(1, N + 1)),
           "probe_checks_per_task": {i: len(_probe_labels(i)) for i in range(1, N + 1)},
           "required_io_total": sum(len(v) for v in io.values()),
           "required_durations": {i: v for i, v in durs.items() if v}}

    # null baseline
    nb = [run_probe(i, null_program(io[i])) for i in range(1, N + 1)]
    res["null_baseline"] = {"checks_passed": sum(r["passed"] for r in nb), "tasks_all": sum(r["all"] for r in nb)}
    # "active" checks = the ones a do-nothing program fails (they need the program to act)
    active = {i + 1: set(nb[i]["failed"]) for i in range(N)}
    res["n_active_checks"] = sum(len(v) for v in active.values())
    res["active_by_category"] = {}
    for i in active:
        for l in active[i]:
            c = categories.category(i, l)
            res["active_by_category"][c] = res["active_by_category"].get(c, 0) + 1
    ao = {i: run_probe(i, always_on_program(io[i])) for i in range(1, N + 1)}
    res["always_on_baseline"] = {
        "checks_passed": sum(r["passed"] for r in ao.values()),
        "active_passed": sum(len(set(active[i]) - set(ao[i]["failed"])) for i in ao),
        "active_earned": sum(len(earned(ao[i], active[i])) for i in ao)}
    res["null_baseline"]["active_earned"] = sum(len(earned(nb[i - 1], active[i])) for i in active)
    ref = [run_probe(i, open(os.path.join(HERE, "probe_reference", f"task_{i:02d}.st")).read()) for i in range(1, N + 1)]
    res["reference_check"] = {"checks_passed": sum(r["passed"] for r in ref), "tasks_all": sum(r["all"] for r in ref)}

    files = {cfg: st_files(run) for cfg, run in CONFIGS.items()}
    per = {}
    for cfg in CONFIGS:
        fe_ok, fe_err = [], {}
        pr = {}
        itf = {"required": 0, "declared": 0, "direction_ok": 0, "type_ok": 0, "used": 0,
               "exact_case": 0, "real_on_word": 0, "extra_io": 0}
        itf_tasks_complete = []
        dur_hit, dur_tot, dur_detail = 0, 0, {}
        clean = [i for i in range(1, N + 1) if status[cfg][i] == "CLEAN"]
        itf_detail = {}
        for i in range(1, N + 1):
            src = files[cfg][i]
            pr[i] = run_probe(i, src)
            if src is None:
                continue
            p, errs = front_end(src)
            if p is not None and not errs:
                fe_ok.append(i)
            else:
                fe_err[i] = errs[0]
            if p is not None:
                r = interface(p, io[i])
                for k in itf:
                    itf[k] += r[k]
                if r["declared"] != r["required"] or r["type_ok"] != r["declared"] or r["used"] != r["declared"] \
                        or r["direction_ok"] != r["declared"]:
                    itf_detail[i] = r
                if r["declared"] == r["direction_ok"] == r["type_ok"] == r["used"] == r["required"]:
                    itf_tasks_complete.append(i)
            if durs[i]:
                lits = time_literals(src)
                hit = [d for d in durs[i] if d in lits]
                dur_hit += len(hit)
                dur_tot += len(durs[i])
                dur_detail[i] = {"want": durs[i], "have": lits}
        clean = [i for i in range(1, N + 1) if status[cfg][i] == "CLEAN"]
        act_raw = {i: len(active[i]) - len(set(pr[i]["failed"]) & active[i]) for i in pr}
        earn = {i: earned(pr[i], active[i]) for i in pr}
        act_pass = {i: len(earn[i]) for i in pr}
        per[cfg] = {
            "parsed": sum(1 for v in files[cfg].values() if v is not None),
            "active_raw_passed": sum(act_raw.values()),
            "active_checks_passed": sum(act_pass.values()),
            "active_per_task": {i: [act_pass[i], len(active[i])] for i in pr},
            "active_earned_labels": {i: earn[i] for i in pr if earn[i]},
            "active_passed_by_category": {c: sum(1 for i in pr for l in earn[i] if categories.category(i, l) == c)
                                          for c in ("memory", "timing", "direct")},
            "active_rate_clean": round(sum(act_pass[i] for i in clean) / max(1, sum(len(active[i]) for i in clean)), 3),
            "active_rate_not_clean": round(sum(act_pass[i] for i in pr if i not in clean) /
                                           max(1, sum(len(active[i]) for i in pr if i not in clean)), 3),
            "front_end_ok": fe_ok, "front_end_errors": fe_err,
            "probe_checks_passed": sum(r["passed"] for r in pr.values()),
            "probe_tasks_all": [i for i in pr if pr[i]["all"]],
            "probe_tasks_ge80": [i for i in pr if pr[i]["passed"] >= 0.8 * pr[i]["total"]],
            "probe_per_task": {i: [pr[i]["passed"], pr[i]["total"]] for i in pr},
            "probe_failed_labels": {i: pr[i]["failed"] for i in pr if pr[i]["failed"]},
            "probe_errors": {i: pr[i]["error"] for i in pr if pr[i]["error"]},
            "clean": clean,
            "clean_and_probe_all": [i for i in clean if pr[i]["all"]],
            "probe_all_not_clean": [i for i in pr if pr[i]["all"] and i not in clean],
            "probe_rate_clean": round(sum(pr[i]["passed"] for i in clean) / max(1, sum(pr[i]["total"] for i in clean)), 3),
            "probe_rate_not_clean": round(sum(pr[i]["passed"] for i in pr if i not in clean) /
                                          max(1, sum(pr[i]["total"] for i in pr if i not in clean)), 3),
            "interface_parsed_programs": itf, "interface_complete_tasks": itf_tasks_complete,
            "interface_detail": itf_detail,
            "durations_matched": dur_hit, "durations_required": dur_tot, "duration_detail": dur_detail,
        }
    res["configs"] = per

    # repair edit rate (7B): which final files differ from the one-shot file
    changed = [i for i in range(1, N + 1) if files["repair7"][i] != files["oneshot7"][i]]
    res["repair7_changed_files"] = changed
    res["repair7_probe_delta"] = {i: [per["oneshot7"]["probe_per_task"][i][0], per["repair7"]["probe_per_task"][i][0]]
                                  for i in changed}
    both = [i for i in range(1, N + 1) if files["repair7"][i] and files["repair15"][i]]
    res["same_program_7b_15b"] = [i for i in both if norm(files["repair7"][i]) == norm(files["repair15"][i])]
    res["probe_all_union"] = sorted(set().union(*[set(per[c]["probe_tasks_all"]) for c in per]))

    # ---- Rust
    rust = {}
    for cfg in CONFIGS:
        hit = tot = 0
        wrong = {}
        shared = []
        for i in range(1, N + 1):
            src = rust_file(cfg, i)
            if src is None:
                continue
            got = rust_io(src)
            if not got:
                continue
            for d in io[i]:
                exp = expected_modbus(d)
                if exp is None:
                    continue
                cand = got.get(snake(d["name"])) or got.get(d["name"].lower())
                tot += 1
                want = (exp[0], exp[1], d["dir"])
                if cand and want in cand:
                    hit += 1
                else:
                    wrong.setdefault(i, []).append(d["name"])
            ins = {(t, a) for v in got.values() for (t, a, dr) in v if dr == "in"}
            outs = {(t, a) for v in got.values() for (t, a, dr) in v if dr == "out"}
            if ins & outs:
                shared.append(i)
        rust[cfg] = {"addr_matched": hit, "addr_checked": tot, "addr_wrong": wrong,
                     "tasks_in_out_share_address": shared}
    spec_shared = []
    for i in range(1, N + 1):
        a = [expected_modbus(d) + (d["dir"],) for d in io[i] if expected_modbus(d)]
        if {(t, x) for t, x, dr in a if dr == "in"} & {(t, x) for t, x, dr in a if dr == "out"}:
            spec_shared.append(i)
    rust["spec_tasks_with_shared_numbers"] = spec_shared
    res["rust"] = rust

    out = os.path.join(HERE, "output_numbers.json")
    with open(out, "w") as f:
        json.dump(res, f, indent=1)
    print(f"wrote {out}")
    for cfg in CONFIGS:
        c = per[cfg]
        print(f"{cfg:9s} parsed={c['parsed']} fe_ok={len(c['front_end_ok'])} probe={c['probe_checks_passed']}/{res['n_probe_checks']} "
              f"all={len(c['probe_tasks_all'])} ge80={len(c['probe_tasks_ge80'])} clean={len(c['clean'])} clean&all={len(c['clean_and_probe_all'])} "
              f"rate clean/not={c['probe_rate_clean']}/{c['probe_rate_not_clean']} dur={c['durations_matched']}/{c['durations_required']} "
              f"active={c['active_checks_passed']}(raw {c['active_raw_passed']})/{res['n_active_checks']} arate={c['active_rate_clean']}/{c['active_rate_not_clean']} "
              f"itf={c['interface_parsed_programs']} complete={len(c['interface_complete_tasks'])}")
    print("null", res["null_baseline"], "always-on", res["always_on_baseline"], "ref", res["reference_check"],
          "active by cat", res["active_by_category"])
    for cfg in CONFIGS:
        print("  ", cfg, per[cfg]["active_passed_by_category"])
    print("changed", changed, res["repair7_probe_delta"])
    print("same 7b/1.5b", res["same_program_7b_15b"])
    print("rust", json.dumps(rust))


if __name__ == "__main__":
    main()
