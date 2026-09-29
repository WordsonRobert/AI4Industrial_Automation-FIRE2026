# RUN-fih-03 — 7B single pass (baseline)

| | |
|---|---|
| Model | Qwen2.5-Coder-7B-Instruct + LoRA (same adapter as RUN-fih-01) |
| Decoding | greedy, ≤ 2,560 new tokens |
| Verification | none; one attempt |
| Rust post-pass | none |

With greedy decoding, this run matches the first attempt of RUN-fih-01, so the two runs together isolate the effect of repair.

## Files

```
code/
  run_real_test_set_7b.py    Task A driver (single attempt)
  run_task_b_rust.py         Task B driver (single attempt)
  ast_nodes.py, ast_compact.py, st_printer.py, rust_printer.py
taskA-outputs/   task_NN.st, all_results.jsonl (includes the raw model output, generated_raw)
taskB-outputs/   task_NN.rs (unpatched), all_results.jsonl
```

## Summary (30 tasks)

- 26 parseable trees; tasks 8, 23, 24 and 30 failed to parse.
- None of the Rust files compiles as submitted, because they import the external `modbus` crate.
- Applying the RUN-fih-01 stub post hoc gives 18 compiling files (see `analysis/`).
