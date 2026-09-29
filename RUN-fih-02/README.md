# RUN-fih-02: FIRE 2026 NL2PLC Submission

## 1. What this submission contains

This is one run, covering both Task A (Natural Language -> Structured
Text) and Task B (Natural Language -> Rust), using the same trained
model for both tasks.

```
RUN-fih-02/
├── README.md              <- this file (originally RUN-fih-02-README.md)
├── code/                  <- all source code used to produce the outputs
├── taskA-outputs/          <- Task A: 30 .st files + all_results.jsonl
└── taskB-outputs/          <- Task B: 30 .rs files (already patched by fix_rust_outputs.py)
                               + rust_check_report.{jsonl,txt}
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

## Internal verification results (our own checks, not the official metric)

| | Parsed AST | Fully clean (parse + lint + smoke test) | Rust compiles with `rustc` |
|---|---|---|---|
| First attempt | 30/30 | 9/30 | - |
| **Final, after the repair loop** | **30/30** | **12/30** | **18/30** |

The 1.5B model never broke the AST format (30/30 parsed), but it made about
twice as many logic errors as the 7B model. Under repair pressure it also
deleted required I/O more often: MISSING_REQUIRED_IO went from 3 to 6.

---

## 2. How the model was trained

Model: `Qwen/Qwen2.5-Coder-1.5B-Instruct` (open-source, 1.5B parameters,
under the 8B limit).

Method: LoRA fine-tuning (rank 16, alpha 32). Only a small adapter is
trained on top of the frozen base model. Target modules: q_proj,
k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj.

Training data: 744 examples total. Each example is a pair of
(natural language instruction, compact JSON AST). The 744 examples
come from two sources combined:
- Our own corpus, built from permissively-licensed open-source PLC
  code found on GitHub, plus synthetic/augmented variations.
- FIRE's official training dataset (349 examples), which the
  organizers confirmed is allowed to be combined with external data.

The model is trained to do ONE thing: given a natural language task
description, output a JSON Abstract Syntax Tree (AST) describing the
program. It is never trained to directly output Structured Text or
Rust text. Both output languages are produced afterward by a separate,
non-AI compiler step. This is explained in Section 3 below.

Training script: `code/train_lora_7b.py` is not included in this
package (kept small), but the exact LoRA configuration is documented
above and is fully reproducible against the same base model and the
744-example training set.

---

## 3. The pipeline, step by step (same for both tasks, until the last step)

```
STEP 1: Natural language task description
        (from Test-Dataset-AI4Industrial-Automation.xlsx)
              |
              v
STEP 2: Fine-tuned Qwen2.5-Coder-1.5B-Instruct (+ LoRA adapter)
        generates a JSON Abstract Syntax Tree (AST)
              |
              v
STEP 3: The JSON AST is parsed into Python objects
        (code/ast_compact.py, code/ast_nodes.py)
              |
              v
STEP 4: The AST is checked for problems
        (code/lint_program.py, code/smoke_test.py, code/ast_interpreter.py)
        If a problem is found, the specific problem is sent back to the
        model in Step 2, and the model tries again (up to 3 times total).
              |
              v
STEP 5a: TASK A ONLY -- the AST is converted into                    STEP 5b: TASK B ONLY -- the same AST is converted into
         Structured Text                                                      Rust
         (code/st_printer.py)                                                  (code/rust_printer.py)
              |                                                                     |
              v                                                                     v
    taskA-outputs/task_NN.st                                              taskB-outputs/task_NN.rs
```

Both tasks share Steps 1 through 4 completely. The only difference
between Task A and Task B is the very last step: which printer turns
the AST into final code.

---

## 4. What each file in `code/` does

> **Note on driver scripts.** The `code/` folder contains `run_real_test_set_with_repair_7b.py`
> and `run_task_b_rust_repaired.py`, which are the same files as in RUN-fih-01. For this run they were
> executed with `BASE_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"` and the 1.5B LoRA adapter path.
> Change those two constants at the top of each script to reproduce this run.


| File | Job |
|---|---|
| `ast_nodes.py` | Defines the AST data structures (Program, Assignment, If, BinaryOp, etc.) as Python classes. This is the shared "language" that both Task A and Task B are built from. |
| `ast_compact.py` | Converts the raw JSON that the model outputs into the Python AST objects defined in `ast_nodes.py`, and back again. |
| `st_printer.py` | Takes a Python AST object and writes it out as IEC 61131-3 Structured Text. Used for Task A only. |
| `rust_printer.py` | Takes the SAME Python AST object and writes it out as Rust code. Used for Task B only. |
| `lint_program.py` | Checks an AST for specific, rule-based problems: inputs/outputs listed in the task that were never used, inputs/outputs required by the task that are missing entirely, assigning a value to something that should only be read, a constant value written after a decision block that already set it, and comparisons that can mathematically never be true. Returns a list of problems found, if any. |
| `ast_interpreter.py` | Runs an AST as if it were a real PLC program, one scan cycle at a time, so its behavior can be tested without needing real hardware. |
| `smoke_test.py` | Uses `ast_interpreter.py` to run a program for 200 simulated scan cycles with changing inputs, and checks whether every declared output actually changes value at some point. If an output never changes, that is flagged as suspicious. |
| `run_real_test_set_with_repair_7b.py` | The Task A driver script. Loads the model, generates an AST per task, runs `lint_program.py` and `smoke_test.py`, sends any problems found back to the model for correction (up to 3 tries), and writes the final Structured Text with `st_printer.py`. |
| `run_task_b_rust_repaired.py` | The Task B driver script. Identical to the Task A script in every way (same model, same lint/smoke checks, same repair loop), except at the final step it calls `rust_printer.py` instead of `st_printer.py`. |
| `fix_rust_outputs.py` | A separate, second-pass tool that runs only on the Rust output, after `run_task_b_rust_repaired.py` has already finished. Explained in Section 5. |

---

## 5. What `run_task_b_rust_repaired.py` actually does, and why a second tool was needed afterward

`run_task_b_rust_repaired.py` does the full job described in Section 3:
generate an AST, lint it, smoke-test it, repair it up to 3 times if
needed, then print it as Rust.

However, `lint_program.py` and `smoke_test.py` only understand the AST
-- they have no knowledge of Rust-specific requirements. The generated
Rust code assumes a real external `modbus` crate (a real, published
Rust library for industrial communication) is available. When actually
compiled with `rustc` on its own, this fails, because there is no
`Cargo.toml` declaring that dependency in this test setup.

`fix_rust_outputs.py` is run AFTER `run_task_b_rust_repaired.py`, directly
on the `.rs` files it produced. It does the following, per file:
1. If the file uses the `modbus` crate, it inserts a small,
   self-contained stand-in module (same name, same functions/types)
   directly into the file, so the file can compile on its own without
   needing the real external crate or real hardware.
2. It checks for a small number of missing helper functions the
   printer sometimes calls but never defines, and adds them if needed.
3. It removes a specific known bug pattern: a constant value written
   to an output immediately after a decision block that already set
   that same output, which silently cancels the decision.
4. It actually runs `rustc` on the result and records whether it
   compiles or not.

Final result after both tools ran: 18 out of 30 Rust files compile
successfully with `rustc`. The `taskB-outputs/` folder contains the
result of running both tools, in that order.

---

## 6. Parse failures in this run

The 1.5B model produced a JSON AST that could be parsed for **all 30 tasks**,
on both Task A and Task B. There are no "GENERATION FAILED" files in this run.
The 7B runs (RUN-fih-01 and RUN-fih-03) did have parse failures, on tasks 8, 24
and 30.

All 30 files in `taskB-outputs/` are real generated Rust code. They went through
the repair loop and then the `fix_rust_outputs.py` pass described in Section 5,
and 18 of 30 compile with `rustc`. The 12 that fail are listed in
`rust_check_report.txt`. Most of them fail because of gaps in our Rust printer,
not model mistakes: the TP timer and counter/timer outputs like `.CV` and `.ET`
are not supported, and mixing integers with decimals causes type errors.

This run has no Task B `all_results.jsonl`. With greedy decoding, the Task B
generation gives the same ASTs as Task A, so `taskA-outputs/all_results.jsonl`
holds the attempt log for both tasks.

---

## 7. Reproduction instructions

Requires: Python 3.12, transformers, peft, trl, torch (bf16-capable
GPU recommended), json_repair, openpyxl, rustc (for the Task B compile
check only).

```bash
pip install transformers peft trl torch json_repair openpyxl --break-system-packages

# place the released test-set xlsx in the same directory as the scripts

# Task A:
python3 code/run_real_test_set_with_repair_7b.py

# Task B, step 1 (generate + repair loop):
python3 code/run_task_b_rust_repaired.py

# Task B, step 2 (Rust-specific fixes + real compile check), run
# from inside the folder that step 1 wrote its .rs files to:
python3 code/fix_rust_outputs.py
```

LoRA adapter weights are not included in this package to keep its size
small. They can be reproduced by fine-tuning
`Qwen/Qwen2.5-Coder-1.5B-Instruct` with the LoRA configuration described
in Section 2, on the 744-example training set, or provided on request.
