# RUN-fih-01 — 7B with verification and repair (primary)

| | |
|---|---|
| Model | Qwen2.5-Coder-7B-Instruct + LoRA |
| Decoding | greedy, ≤ 2,560 new tokens |
| Verification | linter + 200-scan simulation, ≤ 3 attempts |
| Rust post-pass | Modbus stub + `rustc` check |

## Files

```
code/
  run_real_test_set_with_repair_7b.py   Task A driver (generation, parsing, checks, repair)
  run_task_b_rust_repaired.py           Task B driver (same loop, Rust printer)
  fix_rust_outputs.py                   Rust post-pass
  ast_nodes.py, ast_compact.py          tree format
  lint_program.py, smoke_test.py,
  ast_interpreter.py                    verification
  st_printer.py, rust_printer.py        printers
taskA-outputs/   task_NN.st, all_results.jsonl
taskB-outputs/   fixed_task_NN.rs (patched), task_08/24/30.rs (no tree), rust_check_report.{jsonl,txt}
```

## Run

```bash
cd code
python3 run_real_test_set_with_repair_7b.py
python3 run_task_b_rust_repaired.py
cd submission_output_7b_rust_repaired && python3 ../fix_rust_outputs.py
```

The drivers expect the organisers' test spreadsheet and the LoRA adapter next to the scripts. Set `BASE_MODEL` and `ADAPTER_PATH` at the top of each driver.

## Summary (30 tasks)

- 58 generations; 27 parseable trees; 18 clean.
- Tasks 8, 24 and 30 never produced a tree.
- 18 Rust files compile after the post-pass.
- Task A and Task B share each tree.
