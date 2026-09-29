# NL2PLC: Natural Language to IEC 61131-3 Structured Text and Rust

This is team **fih**'s submission to the FIRE 2026 shared task *AI4Industrial Automation: NL2PLC Code Generation and Understanding*:

- **Task A:** natural language → IEC 61131-3 Structured Text (ST)
- **Task B:** natural language → Rust

The repository holds three things:

- the code and outputs of all three submitted runs
- detailed notes on the method and results
- the LaTeX source of our working note

## How it works

The language model never writes ST or Rust directly:

1. A LoRA fine-tuned **Qwen2.5-Coder-Instruct** model turns the task description into a **compact JSON abstract syntax tree (AST)**.
2. The AST is checked:
   - a **static linter** looks for unused or missing I/O, writes to inputs, dead overrides, impossible conditions and undeclared variables;
   - a **200-cycle scan simulation** flags outputs that never change.
3. Any problems are sent back to the model, which gets **up to 3 attempts**.
4. A **deterministic printer** turns the final AST into ST (Task A) or a Modbus polling-loop Rust program (Task B).
5. For Task B only, a mechanical post-pass adds a self-contained Modbus stub and checks that the file compiles with `rustc`.

```
NL task ─► Qwen2.5-Coder + LoRA ─► JSON AST ─► lint + smoke test ─┬─► ST printer   ─► .st
               ▲                                                    │
               └──────────── feedback (≤ 3 attempts) ◄──────────────┴─► Rust printer ─► .rs ─► Modbus stub + rustc
```

## Official results

The organizers announced these on 4 September 2026.

| Rank | Task A: NL → ST | Score | Task B: NL → Rust | Score |
|---|---|---|---|---|
| 1 | 8 Bit Thugs | 81.78 | Master Mind | 61.55 |
| 2 | team meooo | 79.31 | CSNLP | 60.43 |
| 3 | Treygram | 78.83 | AutoLogic AI | 59.29 |
| 4 | Master Mind | 76.63 | Treygram | 59.22 |
| 5 | CSNLP | 75.11 | TokenX | 56.67 |
| 6 | AutoLogic AI | 73.62 | **fih (us)** | **53.20** |
| 7 | TokenX | 73.50 | team meooo | 44.20 |
| 8 | **fih (us)** | **63.21** | | |

- **How the score is computed:** final score = 25% Cosine Similarity + 25% Structural Match Score + 50% Program Dependence Graph similarity. All three compare our output with the organizers' reference programs.
- **Per-team scores:** there is one score per team per task. The leaderboard does not say which of our runs was scored.

## Our internal verification (30 test tasks)

These numbers come from our own checks, not the official metric.

| Run | Model | Repair loop | Parsed AST | Fully clean (parse + lint + smoke) | Rust compiles (`rustc`) |
|---|---|---|---|---|---|
| RUN-fih-01 (primary) | Qwen2.5-Coder-7B + LoRA | yes | 27/30 | **18/30** | 18/30 |
| RUN-fih-02 | Qwen2.5-Coder-1.5B + LoRA | yes | **30/30** | 12/30 | 18/30 |
| RUN-fih-03 (baseline) | Qwen2.5-Coder-7B + LoRA | no | 26/30 | 15/30 | 0/30 |

## Repository layout

```
.
├── README.md                 this file
├── RUN-fih-01/               primary run: 7B, repair loop, Rust post-pass
│   ├── README.md             run description, pipeline, reproduction steps
│   ├── code/                 all source code used for this run
│   ├── taskA-outputs/        task_01..30.st + all_results.jsonl (per-attempt logs)
│   └── taskB-outputs/        fixed_task_NN.rs, all_results.jsonl, rust_check_report.{jsonl,txt}
├── RUN-fih-02/               1.5B, repair loop, Rust post-pass (same layout)
├── RUN-fih-03/               7B baseline, one attempt, no checks (same layout)
├── docs/
│   └── PAPER_NOTES.md        detailed notes: method, design choices, per-task results, error analysis
└── paper/                    CEUR-format LaTeX source of the working note
```

## Code overview

Each run's `code/` folder holds the following. The shared files are identical across runs.

| File | Purpose |
|---|---|
| `ast_nodes.py` | AST node definitions (the intermediate representation) |
| `ast_compact.py` | compact JSON ⇄ AST, using short type codes and field aliases |
| `st_printer.py` | AST → Structured Text |
| `rust_printer.py` | AST → Rust (Modbus polling loop, 20 ms scan) |
| `lint_program.py` | static linter; some rules read the I/O list from the task text |
| `ast_interpreter.py` | scan-cycle interpreter (TON, TP, CTU, R_TRIG) |
| `smoke_test.py` | 200-cycle simulation that flags outputs which never change |
| `run_real_test_set_with_repair_7b.py` | Task A driver with the repair loop (RUN-01, RUN-02) |
| `run_task_b_rust_repaired.py` | Task B driver with the repair loop (RUN-01, RUN-02) |
| `fix_rust_outputs.py` | Rust post-pass: Modbus stub, helpers, `rustc` compile check |
| `run_real_test_set_7b.py`, `run_task_b_rust.py` | single-attempt drivers (RUN-03) |

## Reproducing

```bash
pip install transformers peft torch json_repair openpyxl
# put Test-Dataset-AI4Industrial-Automation.xlsx and the LoRA adapter next to the scripts
cd RUN-fih-01/code
python3 run_real_test_set_with_repair_7b.py      # Task A
python3 run_task_b_rust_repaired.py              # Task B, step 1
cd submission_output_7b_rust_repaired && python3 ../fix_rust_outputs.py   # Task B, step 2 (needs rustc)
```

Not included here:

- the **LoRA adapter weights**
- the **training script**
- the **test spreadsheet**, which the task organizers distribute

Training used LoRA with rank 16, alpha 32, on q/k/v/o/gate/up/down projections. The data was 744 NL→AST pairs: 349 from the official FIRE training set and 395 from permissively licensed open-source PLC code. Decoding is greedy, with at most 2,560 new tokens.

## Building the paper

```bash
cd paper
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

`ceurart.cls` is the official CEUR-WS template, distributed under the LaTeX Project Public License. See `paper/Copyright*.txt`.

## Notes

- The submitted zips named the code folders `code_files/` (RUN-01) and `code-files/` (RUN-03). They are renamed to `code/` here, to match the run READMEs. The code files themselves are unchanged from the submission.
- The run READMEs gained the official results and our internal verification numbers. The RUN-fih-02 README was also corrected: it previously stated a 7B parameter count and parse failures that belong to the 7B runs.
- `docs/PAPER_NOTES.md` §8–§9 lists known limitations of the code.
