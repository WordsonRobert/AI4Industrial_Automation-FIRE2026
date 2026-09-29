# Pipeline notes

These notes cover each stage of the system in the order used by the paper. Where a stage is implemented in this repository, the file is named. Paths refer to `RUN-fih-01/code/` unless stated otherwise. The shared files are identical across runs.

---

## 1. Data

**Official data.** The FIRE training set supplies 349 (NL, ST) pairs.

**External data.** Public GitHub repositories containing PLCopen XML (TC6) projects were collected, with these filters:

- Licence: only MIT, Apache-2.0, BSD-2/3-Clause, ISC, Unlicense and CC0-1.0 were kept.
- Authenticity: a file was kept only if it contained real project markers (the `TC6_XML` namespace, `pou name=` and `bodyType`). This excludes schemas and parser test files.

**Conversion.** Each program unit was parsed into the tree format below and serialised as compact JSON. DeepSeek-V3 wrote an NL description for each unit. Augmentation renamed I/O, tags and literals, and near-duplicates were removed.

**Result.** The corpus has 744 NL–tree pairs (349 official, 395 external or augmented). Quality checks kept 396 of them, split 356 train / 40 held-out (seed 42).

Implemented here:

- the tree format (`ast_nodes.py`, `ast_compact.py`)
- a loader fix: records with argument-less function calls previously crashed because the compact form drops empty lists; argument lists now default to empty (`ast_nodes.py`)

Not included: the scraper, converter and merge scripts.

## 2. Fine-tuning

| | |
|---|---|
| Base models | Qwen2.5-Coder-7B-Instruct (RUN-01, RUN-03), Qwen2.5-Coder-1.5B-Instruct (RUN-02) |
| Method | LoRA on q, k, v, o, gate, up, down projections; base weights frozen |
| LoRA | r = 16, α = 32, dropout 0.05 |
| Optimisation | 3 epochs, per-device batch 1 × 16 accumulation, lr 2e-4, bf16, gradient checkpointing |
| Max length | 1536 tokens |
| Target | compact JSON tree only; the model never sees ST or Rust as output |

The training script and adapters are not included.

## 3. Generation

- **System prompt:** asks for a single JSON object (no Markdown, no prose, no ST) and lists the schema, one line per node type.
- **User turn:** `Task: {task}\n\nOutput the AST as JSON:`
- **Decoding:** greedy (`do_sample=False`), at most 2,560 new tokens, bf16, adapter loaded with PEFT.

Because decoding is greedy, RUN-fih-03 (single attempt) matches the first attempt of RUN-fih-01, and Task A and Task B receive identical trees.

Code: `run_real_test_set_with_repair_7b.py` (`SYSTEM_PROMPT`, `generate`)

### Tree format

The tree has 18 node types:

- program and variable declarations (each declaration keeps its IEC address, e.g. `%IX0.0`)
- statements: assignment, FB call, IF, CASE, FOR, WHILE, REPEAT, RETURN, EXIT
- expressions: identifier, literal, binary op, unary op, function call, array index, member access

In the compact form:

- node types are 1–3 letter codes (`Prg`, `Vd`, `Asn`, `FnS`, `If`, `Id`, `Lit`, `Bin`, …)
- 28 field names have short aliases (`name→n`, `target→tg`, `value→v`, …)
- empty fields are omitted

Example (task 2, first statement):

```json
{"t":"FnS","in":"TP_Red","na":[["IN",{"t":"Id","n":"TRUE"}],["PT",{"t":"Lit","tx":"T#5s"}]]}
```

Code: `ast_nodes.py`, `ast_compact.py` (`_TYPE_CODES`, `_FIELD_ALIASES`)

## 4. Parsing

1. Strip a leading `` ```json `` fence and the trailing fence.
2. Run `json.loads`; if it fails, run `json_repair` and try again.
3. Run `compact_json_to_ast`, which raises on an unknown type code or field name.

A failure at any step is logged as `COMPILE_FAILED`, meaning no tree could be built.

Code: `run_real_test_set_with_repair_7b.py` (`strip_code_fence`, `evaluate`), `ast_compact.py`

## 5. Verification and repair

### Linter (`lint_program.py`)

| Rule | Catches |
|---|---|
| `MISSING_REQUIRED_IO` | an I/O point listed with an address in the task text but not declared |
| `UNUSED_IO` | declared I/O that is never used |
| `INPUT_ASSIGNED_TO` | writes to an input |
| `DEAD_OVERRIDE` | a constant written after conditional logic already set the variable |
| `IMPOSSIBLE_CONDITION` | contradictory comparisons, e.g. `X > 300 AND X < 280` |
| `UNDECLARED_VARIABLE` | names used but never declared |
| `FB_DIRECT_ASSIGN`, `UNKNOWN_FB_TYPE` | `TON0 := …`, or invented function-block types |

Required I/O is read from the task text, one regex per line (`%I…`/`%Q…` or `AI:`/`DI:`).

### Scan-cycle simulation (`ast_interpreter.py`, `smoke_test.py`)

- The tree runs for 200 scans of 20 ms, keeping TON/TP/CTU/R_TRIG state between scans.
- Any output that never changes is flagged `STATIC_OUTPUT`.
- Timer presets are capped at 10 scans, so that long presets do not raise false alarms.
- Inputs feeding timers or counters get a three-phase pattern (toggling, hold, inverted hold); other inputs get staggered periodic patterns.

The simulation checks that outputs respond at all, not that they respond correctly.

### Repair loop (`run_real_test_set_with_repair_7b.py`)

- **Attempts:** at most 3 in total. Each is generate → parse → lint → simulate.
- **Feedback:** the previous answer and a new user message holding the parse error or the list of findings. The message also carries a fixed instruction not to delete flagged variables, assign to inputs, or append constant overrides.
- **Stopping:** a clean attempt ends the loop. Otherwise the last parseable tree is kept. If nothing parsed, the output is `// GENERATION FAILED` followed by the raw text.

## 6. Structured Text (Task A)

`st_printer.py` writes:

- a `PROGRAM` header
- `VAR_INPUT` / `VAR_OUTPUT` / `VAR` blocks
- statements, with parentheses only where precedence requires them

Indentation is assigned per line.

Known gaps:

- `AT %…` address bindings are not printed, although the tree holds them.
- Declarations whose scope label is outside `input`/`output`/`inout`/`temp`/`local` (e.g. `memory`) are silently dropped.

## 7. Rust (Task B)

`run_task_b_rust_repaired.py` is the Task A driver with the Rust printer swapped in.

`rust_printer.py` follows the organisers' template: a Modbus client, a loop that reads inputs, computes and writes outputs, and a 20 ms sleep.

- `%IXb.i` → coil `8b + i`; `%IWn` → holding register `n`; `AI:`/`DI:` addresses are skipped.
- TON becomes a scan counter; CTU and R_TRIG are translated; other FBs (TP, TOF, …) are emitted as comments.
- Inputs are read from the coil and holding-register tables, so an input and an output with the same number share one Modbus address.

`fix_rust_outputs.py` makes every file compile with plain `rustc --edition 2021`:

1. It prepends a self-contained 48-line `mod modbus` (256 coils, 256 registers), replacing the external crate import.
2. It adds missing helpers, removes Rust-level dead overrides and flags hard-coded scan counts. In the submitted runs, only step 1 changed any file.
3. It compiles each file and writes `rust_check_report.{jsonl,txt}`.

## 8. Post-hoc analysis (`analysis/`)

The analysis scripts read only the submitted files:

| Script | Measures |
|---|---|
| `compute_paper_numbers.py` | repair budget curves, issue types, McNemar tests, Rust failure causes, stub-only ablation, token cost of the tree format |
| `st_sim.py` | parses, name-resolves and executes the printed ST (IEC timer/counter semantics) |
| `probes.py` | 169 behavioural checks written from the task texts; `probe_reference/` shows each is satisfiable |
| `analyze_outputs.py` | front-end validity, interface and timing fidelity, probe scores against do-nothing and always-on baselines, Rust address checks |
| `check_paper_claims.py` | asserts every number quoted in the paper |

## 9. Output files

| Run | Task A | Task B |
|---|---|---|
| RUN-fih-01 | `taskA-outputs/task_NN.st`, `all_results.jsonl` | `fixed_task_NN.rs` (patched), raw `task_08/24/30.rs`, `rust_check_report.*` |
| RUN-fih-02 | same | `task_NN.rs` (patched), `rust_check_report.*` |
| RUN-fih-03 | same, `all_results.jsonl` includes `generated_raw` | raw `task_NN.rs`, `all_results.jsonl` |

`all_results.jsonl` records, per task, the task text, the final status, and per-attempt findings and parse errors.
