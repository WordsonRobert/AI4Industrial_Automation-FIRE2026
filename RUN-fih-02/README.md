# RUN-fih-02 — 1.5B with verification and repair

| | |
|---|---|
| Model | Qwen2.5-Coder-1.5B-Instruct + LoRA |
| Decoding | greedy, ≤ 2,560 new tokens |
| Verification | linter + 200-scan simulation, ≤ 3 attempts |
| Rust post-pass | Modbus stub + `rustc` check |

## Files

The code is the same as in RUN-fih-01; the drivers keep their 7B file names, with `BASE_MODEL` and `ADAPTER_PATH` set to the 1.5B model.

```
code/            same files as RUN-fih-01
taskA-outputs/   task_NN.st, all_results.jsonl
taskB-outputs/   task_NN.rs (already patched), rust_check_report.{jsonl,txt}
```

## Summary (30 tasks)

- 69 generations; 30 parseable trees; 12 clean.
- 18 Rust files compile after the post-pass.
