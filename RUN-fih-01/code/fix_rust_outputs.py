#!/usr/bin/env python3
"""
Post-hoc checker/fixer for Task B (NL->Rust) outputs.

Run from the directory containing task_NN.rs files and all_results.jsonl:

    python3 fix_rust_outputs.py

What it does, per task_NN.rs:
  1. Injects a self-contained Modbus stub module if the code references
     `use modbus::...` -- this was the DOMINANT systemic failure (81 of
     ~150 total rustc error lines across a 30-task run were
     "unresolved import `modbus`"), since a standalone rustc check has
     no Cargo.toml/dependency resolution for a real external crate.
     The stub is a self-contained in-memory register/coil array,
     appropriate given Task B's stated goal is syntactic correctness +
     logic preservation, not literal hardware I/O.
  2. Injects missing helper-function preludes (e.g. real_to_int) that the
     printer calls but never defines.
  3. Runs `rustc --edition 2021 --emit=metadata` as a real compile gate
     and records the exact error if it fails.
  4. Auto-fixes a trailing "dead override" pattern: an unconditional
     `var = <literal>;` statement sitting immediately after an if/else if
     block that already assigned that same var conditionally.
  5. Flags (does not auto-fix) hardcoded scan-count timer thresholds
     like `>= 400` next to a `_acc` variable.
  6. Writes:
       - fixed_task_NN.rs        (patched file, only if a patch applied)
       - rust_check_report.jsonl (per-task machine-readable results)
       - rust_check_report.txt   (human-readable summary)

This is a static, no-model-call tool -- it does NOT regenerate code from
the LLM. It patches what can be patched mechanically and clearly reports
what still needs a regenerate-with-feedback pass through your existing
repair loop.

Requires: rustc on PATH. If rustc isn't available, the compile-check
step is skipped and reported as SKIPPED, everything else still runs.
"""

import json
import re
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

HERE = Path(".")
RESULTS_FILE = HERE / "all_results.jsonl"

HELPER_PRELUDES = {
    "real_to_int": "fn real_to_int(x: f64) -> i32 { x as i32 }",
    "int_to_real": "fn int_to_real(x: i32) -> f64 { x as f64 }",
    "bool_to_int": "fn bool_to_int(x: bool) -> i32 { if x { 1 } else { 0 } }",
    "clamp_i32": "fn clamp_i32(x: i32, lo: i32, hi: i32) -> i32 { x.max(lo).min(hi) }",
    "clamp_f64": "fn clamp_f64(x: f64, lo: f64, hi: f64) -> f64 { x.max(lo).min(hi) }",
}

MODBUS_STUB = '''
// --- auto-injected self-contained Modbus stub, matching the real
// `modbus` crate's documented API surface (Coil, Config, tcp::Transport)
// so generated code compiles standalone without the actual external
// crate or hardware -- appropriate given Task B's goal is syntactic
// correctness + logic preservation, not literal I/O.
mod modbus {
    #[derive(PartialEq, Clone, Copy)]
    pub enum Coil { On, Off }

    pub trait Client {}

    pub mod tcp {
        use super::Coil;

        #[derive(Default)]
        pub struct Config {
            pub tcp_port: u16,
            pub modbus_uid: u8,
        }

        pub struct Transport {
            registers: [u16; 256],
            coils: [Coil; 256],
        }

        impl Transport {
            pub fn new_with_cfg(_addr: &str, _cfg: Config) -> Result<Self, String> {
                Ok(Transport { registers: [0; 256], coils: [Coil::Off; 256] })
            }
            pub fn read_coils(&mut self, address: u16, count: u16) -> Result<Vec<Coil>, String> {
                let start = address as usize % 256;
                Ok((0..count as usize).map(|i| self.coils[(start + i) % 256]).collect())
            }
            pub fn write_single_coil(&mut self, address: u16, coil: Coil) -> Result<(), String> {
                self.coils[address as usize % 256] = coil;
                Ok(())
            }
            pub fn read_holding_registers(&mut self, address: u16, count: u16) -> Result<Vec<u16>, String> {
                let start = address as usize % 256;
                Ok((0..count as usize).map(|i| self.registers[(start + i) % 256]).collect())
            }
            pub fn write_single_register(&mut self, address: u16, value: u16) -> Result<(), String> {
                self.registers[address as usize % 256] = value;
                Ok(())
            }
        }
    }
}
'''


def uses_modbus_import(rust_code: str) -> bool:
    return bool(re.search(r"^\s*use\s+modbus::", rust_code, re.MULTILINE))


def inject_modbus_stub(rust_code: str) -> str:
    # Don't strip the original 'use modbus::...' lines -- they resolve
    # correctly to the injected stub module below since it's also named
    # `modbus` and lives in the same crate. Stripping them (an earlier,
    # wrong version of this function) broke unqualified references like
    # `tcp::Transport`, `Config`, `Coil` that depended on those imports
    # actually being present.
    return MODBUS_STUB + "\n" + rust_code


def load_task_texts():
    texts = {}
    if RESULTS_FILE.exists():
        for line in RESULTS_FILE.read_text().splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                texts[r["task_number"]] = r.get("task_text", "")
            except Exception:
                pass
    return texts


def find_task_number(path: Path):
    m = re.search(r"(\d+)", path.stem)
    return int(m.group(1)) if m else None


def check_rustc_compiles(rust_code: str, edition="2021"):
    if shutil.which("rustc") is None:
        return "SKIPPED_NO_RUSTC"
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "check.rs"
        src.write_text(rust_code)
        try:
            r = subprocess.run(
                ["rustc", "--edition", edition, "--emit=metadata",
                 "--crate-type", "bin", "-o", str(Path(td) / "out"), str(src)],
                capture_output=True, text=True, timeout=60,
            )
        except subprocess.TimeoutExpired:
            return "COMPILE_TIMEOUT"
        if r.returncode == 0:
            return None
        return r.stderr.strip()[:4000]


def missing_helpers(rust_code: str):
    missing = []
    for name, definition in HELPER_PRELUDES.items():
        called = re.search(rf"\b{name}\s*\(", rust_code) is not None
        defined = re.search(rf"\bfn\s+{name}\s*\(", rust_code) is not None
        if called and not defined:
            missing.append(name)
    return missing


def inject_prelude(rust_code: str, helper_names: list) -> str:
    if not helper_names:
        return rust_code
    prelude = "\n".join(HELPER_PRELUDES[n] for n in helper_names)
    lines = rust_code.split("\n")
    insert_at = 0
    for i, ln in enumerate(lines):
        if ln.strip().startswith("use "):
            insert_at = i + 1
    lines.insert(insert_at, f"\n// --- auto-injected helper prelude ---\n{prelude}\n")
    return "\n".join(lines)


def find_dead_overrides(rust_code: str):
    lines = rust_code.split("\n")
    findings = []
    assigned_in_branch = set()
    in_branch_depth = 0
    for i, raw in enumerate(lines):
        line = raw.strip()
        if re.match(r"^(if|}\s*else\s*(if)?)\b.*\{?\s*$", line) or line.startswith("if ") or "else" in line:
            in_branch_depth += line.count("{")
            in_branch_depth -= line.count("}")
            continue
        m_assign = re.match(r"^(\w+)\s*=\s*[^=].*;$", line)
        if m_assign and in_branch_depth > 0:
            assigned_in_branch.add(m_assign.group(1))
        in_branch_depth += line.count("{") - line.count("}")
        if in_branch_depth <= 0 and m_assign is None:
            pass
        m_dead = re.match(r"^(\w+)\s*=\s*(true|false|-?\d+(\.\d+)?)\s*;$", line)
        if m_dead and in_branch_depth <= 0 and m_dead.group(1) in assigned_in_branch:
            findings.append((m_dead.group(1), i))
    return findings


def strip_dead_overrides(rust_code: str, findings):
    if not findings:
        return rust_code
    dead_lines = {i for _, i in findings}
    lines = rust_code.split("\n")
    kept = [ln for i, ln in enumerate(lines) if i not in dead_lines]
    return "\n".join(kept)


def find_hardcoded_scan_counts(rust_code: str):
    findings = []
    for m in re.finditer(r"(\w*_acc)\s*>=\s*(\d+)", rust_code):
        findings.append(f"'{m.group(1)} >= {m.group(2)}' looks like a hardcoded scan-count "
                         f"timer threshold (implicit 20ms/cycle assumption) rather than "
                         f"wall-clock Duration/Instant comparison")
    return findings


def main():
    rs_files = sorted(HERE.glob("task_*.rs"), key=lambda p: find_task_number(p) or 0)
    if not rs_files:
        print("No task_*.rs files found in the current directory.")
        sys.exit(1)

    task_texts = load_task_texts()
    report = []
    rustc_available = shutil.which("rustc") is not None
    if not rustc_available:
        print("NOTE: rustc not found on PATH -- compile checks will be skipped.\n")

    for path in rs_files:
        n = find_task_number(path)
        original = path.read_text()
        code = original
        patches_applied = []

        # 1. Modbus stub (dominant systemic fix)
        if uses_modbus_import(code):
            code = inject_modbus_stub(code)
            patches_applied.append("injected self-contained Modbus stub module (replaces 'use modbus::...')")

        # 2. missing helper preludes
        missing = missing_helpers(code)
        if missing:
            code = inject_prelude(code, missing)
            patches_applied.append(f"injected prelude for: {', '.join(missing)}")

        # 3. dead overrides
        dead = find_dead_overrides(code)
        if dead:
            code = strip_dead_overrides(code, dead)
            patches_applied.append(
                "removed dead override(s): " +
                ", ".join(f"'{v}' (line {i+1})" for v, i in dead)
            )

        # 4. hardcoded scan-count timers (report only)
        scan_count_flags = find_hardcoded_scan_counts(code)

        # 5. compile check (on the PATCHED code)
        compile_error = check_rustc_compiles(code) if rustc_available else "SKIPPED_NO_RUSTC"

        fixed_path = None
        if code != original:
            fixed_path = HERE / f"fixed_{path.name}"
            fixed_path.write_text(code)

        entry = {
            "task_number": n,
            "file": str(path),
            "patched_file": str(fixed_path) if fixed_path else None,
            "patches_applied": patches_applied,
            "scan_count_flags": scan_count_flags,
            "compile_status": (
                "SKIPPED" if compile_error == "SKIPPED_NO_RUSTC"
                else "OK" if compile_error is None
                else "TIMEOUT" if compile_error == "COMPILE_TIMEOUT"
                else "FAILED"
            ),
            "compile_error": compile_error if compile_error not in (None, "SKIPPED_NO_RUSTC") else None,
        }
        report.append(entry)

        status_str = entry["compile_status"]
        print(f"task {n:>2}: compile={status_str:8}  patches={len(patches_applied)}  "
              f"scan_count_flags={len(scan_count_flags)}")

    with open(HERE / "rust_check_report.jsonl", "w") as f:
        for e in report:
            f.write(json.dumps(e) + "\n")

    with open(HERE / "rust_check_report.txt", "w") as f:
        n_ok = sum(1 for e in report if e["compile_status"] == "OK")
        n_failed = sum(1 for e in report if e["compile_status"] == "FAILED")
        n_skipped = sum(1 for e in report if e["compile_status"] == "SKIPPED")
        f.write(f"Rust compile check summary\n")
        f.write(f"  OK:      {n_ok}/{len(report)}\n")
        f.write(f"  FAILED:  {n_failed}/{len(report)}\n")
        f.write(f"  SKIPPED: {n_skipped}/{len(report)}\n\n")
        for e in report:
            f.write(f"{'='*70}\nTask {e['task_number']}  ({e['file']})\n")
            f.write(f"  compile_status: {e['compile_status']}\n")
            if e["patches_applied"]:
                f.write("  patches_applied:\n")
                for p in e["patches_applied"]:
                    f.write(f"    - {p}\n")
            if e["scan_count_flags"]:
                f.write("  scan_count_flags (not auto-fixed, needs manual review):\n")
                for s in e["scan_count_flags"]:
                    f.write(f"    - {s}\n")
            if e["compile_error"]:
                f.write("  compile_error:\n")
                for ln in e["compile_error"].split("\n"):
                    f.write(f"    {ln}\n")
            task_text = task_texts.get(e["task_number"])
            if task_text:
                f.write(f"  task_text: {task_text[:150].strip()}...\n")

    print(f"\nWrote rust_check_report.jsonl and rust_check_report.txt")
    print(f"Patched files (where applicable) written as fixed_task_NN.rs")


if __name__ == "__main__":
    main()
