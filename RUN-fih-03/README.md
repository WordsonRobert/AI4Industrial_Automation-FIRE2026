# RUN-fih-03: FIRE 2026 NL2PLC Submission (baseline, no repair loop)

## 1. What this submission contains

This run is a deliberate baseline: the same fine-tuned model as
RUN-fih-01, but WITHOUT the lint/smoke-test/repair loop and WITHOUT the
Rust-specific `fix_rust_outputs.py` pass used in RUN-fih-01 and
RUN-fih-02. Each task is generated in a single pass, with no
verification and no retry. This run exists to show what the model
produces on its own, as a genuine point of comparison against our
repaired submissions.

```
RUN-fih-03/
├── README.md       <- this file (originally RUN-fih-03-README.md)
├── code/
├── taskA-outputs/    <- Task A: 30 .st files + all_results.jsonl
└── taskB-outputs/    <- Task B: 30 .rs files + all_results.jsonl
```


---

## Official results (FIRE 2026 leaderboard)

The organizers announced the final results on 4 September 2026. They
published **one score per team per task**, and the leaderboard does not
say which of our three runs (RUN-fih-01/02/03) the score came from.

| Task | Our score (team fih) | Rank | Best score | Median of all teams |
|---|---|---|---|---|
| Task A: NL -> Structured Text | 63.21 | 8 of 8 | 81.78 (8 Bit Thugs) | 75.9 |
| Task B: NL -> Rust | 53.20 | 6 of 7 | 61.55 (Master Mind) | 59.2 |

Final score = 25% Cosine Similarity (CS) + 25% Structural Match Score (SMS)
+ 50% Program Dependence Graph Similarity (PDG). All three measure similarity
to the organizers' reference programs. None of them checks whether the code
compiles or runs. The full leaderboard is in the top-level `README.md`.
---

## Internal verification results (our own checks, re-run after submission)

This run did no checking of its own. For comparison, we later ran the same
linter and smoke test as RUN-fih-01 on its outputs, and compiled its `.rs`
files with `rustc`:

| Parsed AST | Fully clean (parse + lint + smoke test) | Rust compiles with `rustc` |
|---|---|---|
| 26/30 | 15/30 | 0/30 (every file fails on the missing `modbus` crate) |

Parse failures: task 8 (`'FALSE'` used as a node type), task 23 (invented a
`'Mod'` node), task 24 (used the long field name `name` inside an assignment)
and task 30 (lowercase `'id'`). Decoding is greedy, so this run is identical to
the first attempt of RUN-fih-01.

---

## 2. How the model was trained

Identical to RUN-fih-01: `Qwen/Qwen2.5-Coder-7B-Instruct`, LoRA fine-
tuned (rank 16, alpha 32), on the same 744-example NL -> JSON-AST
training set (our own corpus + FIRE's official training set, combined
per organizer confirmation). Same model, same training run, same
adapter as RUN-fih-01 -- the only difference between the two runs is
what happens AFTER generation.

---

## 3. The pipeline, step by step

```
STEP 1: Natural language task description
        (from Test-Dataset-AI4Industrial-Automation.xlsx)
              |
              v
STEP 2: Fine-tuned Qwen2.5-Coder-7B-Instruct (+ LoRA adapter)
        generates a JSON Abstract Syntax Tree (AST)
        -- ONE ATTEMPT ONLY. No lint check, no smoke test, no retry.
              |
              v
STEP 3: The JSON AST is parsed into Python objects
        (code/ast_compact.py, code/ast_nodes.py)
              |
              v
STEP 4a: TASK A ONLY -- the AST is converted into           STEP 4b: TASK B ONLY -- the same AST is converted into
         Structured Text                                             Rust
         (code/st_printer.py)                                         (code/rust_printer.py)
              |                                                            |
              v                                                            v
    taskA-outputs/task_NN.st                                    taskB-outputs/task_NN.rs
```

This is the SAME shared-AST architecture as RUN-fih-01 (Steps 1-3 are
identical), but Step 2 here has no feedback loop: whatever the model
outputs on its first attempt is what gets compiled, with no chance to
correct itself if something is wrong.

---

## 4. What each file in `code/` does

| File | Job |
|---|---|
| `ast_nodes.py` | Defines the AST data structures (Program, Assignment, If, BinaryOp, etc.) as Python classes. |
| `ast_compact.py` | Converts the raw JSON the model outputs into the Python AST objects, and back again. |
| `st_printer.py` | Takes a Python AST object and writes it out as IEC 61131-3 Structured Text. Used for Task A. |
| `rust_printer.py` | Takes the SAME Python AST object and writes it out as Rust code. Used for Task B. |
| `run_real_test_set_7b.py` | The Task A driver script for this baseline run. Loads the model, generates one AST per task, and writes it out with `st_printer.py`. No lint, no smoke test, no retry. |
| `run_task_b_rust.py` | The Task B driver script for this baseline run. Identical process to the Task A script, except it calls `rust_printer.py` instead of `st_printer.py` at the final step. |

---

## 5. Why this run has no `fix_rust_outputs.py` pass

In our other two submissions (RUN-fih-01, RUN-fih-02), a separate tool
called `fix_rust_outputs.py` runs after Rust generation to resolve a
known, shared issue: the generated Rust code assumes a real external
`modbus` crate is available, which fails to compile standalone without
a `Cargo.toml` declaring that dependency. That tool is deliberately NOT
used here, so that this run remains a true, unmodified baseline of what
the model produces with no post-processing of any kind, on either task.

---

## 6. Why some tasks fail

For every task, the model gets exactly one attempt to produce a JSON
AST that can be parsed. For a small number of tasks (the same task
numbers on both Task A and Task B, since both start from the same
generation step), the model's raw output could not be parsed into a
valid AST at all. For those specific tasks, the output file contains a
comment stating that generation failed, along with the model's raw
output, instead of working code. This is expected and unavoidable in a
single-attempt, no-repair run -- it is the exact reason RUN-fih-01 and
RUN-fih-02 add a repair loop that retries with specific feedback when
this happens.

---

## 7. Reproduction instructions

```bash
pip install transformers peft torch json_repair openpyxl --break-system-packages

# place the released test-set xlsx in the same directory as the scripts

# Task A:
python3 code/run_real_test_set_7b.py

# Task B:
python3 code/run_task_b_rust.py
```

LoRA adapter weights are not included in this package to keep its size
small. They are the same adapter as RUN-fih-01, reproducible by fine-
tuning `Qwen/Qwen2.5-Coder-7B-Instruct` with the configuration
described in Section 2, or provided on request.
