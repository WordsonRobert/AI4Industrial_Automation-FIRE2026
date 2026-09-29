# FIRE 2026 NL2PLC: Full Paper Notes (team fih)

Notes on everything we built and submitted for the FIRE 2026 shared task *AI4Industrial Automation: NL2PLC Code Generation and Understanding*. The three runs (RUN-fih-01, -02, -03) are covered with methods, design choices, numbers, error analysis and known issues. Every claim points to the file it comes from.

Paths are relative to the repository root.

Where the numbers come from:
- They were recomputed directly from the `all_results.jsonl` and `rust_check_report.*` files in the three run folders.
- The RUN-fih-03 lint/smoke numbers came from re-running the shipped `lint_program.py` and `smoke_test.py` on the raw ASTs stored in `RUN-fih-03/taskA-outputs/all_results.jsonl`.
- The RUN-fih-03 Rust compile numbers came from running `rustc --edition 2021` on its 30 `.rs` files.

---

## 0. TL;DR (for abstract / intro)

- **Task A:** NL → IEC 61131-3 Structured Text (ST). **Task B:** NL → Rust. There are 30 test tasks.
- **Core idea:** the LLM never writes ST or Rust. It writes a **compact JSON AST**. A **deterministic compiler** prints that AST as ST (`st_printer.py`) or as Rust (`rust_printer.py`), so both tasks share one model and one generation step.
- **Model:** Qwen2.5-Coder-Instruct (7B primary, 1.5B secondary) + LoRA (r=16, α=32, all attention + MLP projections), trained on 744 NL→AST pairs (349 official FIRE + 395 our own).
- **Verification on the AST:**
  - a static **linter** with 8 rules, several of which read the task text;
  - a **200-scan-cycle interpreter smoke test** that flags outputs which never change.
- **Repair loop:** verifier findings are fed back as a chat turn, for up to 3 attempts, with anti-gaming instructions.
- **Rust post-pass:** the output is patched with a self-contained Modbus stub, then checked with `rustc`.
- **Headline results** (our own verifier, not the official metric):

| | Parsed AST | Fully CLEAN (parse+lint+smoke) | Rust compiles standalone |
|---|---|---|---|
| RUN-fih-03 (7B, 1 shot, no repair, no post-pass) | 26/30 | 15/30 | **0/30** |
| **RUN-fih-01 (7B, repair, post-pass) — primary** | **27/30** | **18/30** | **18/30** |
| RUN-fih-02 (1.5B, repair, post-pass) | **30/30** | 12/30 | 18/30 |

- **Official leaderboard** (organizers' email, 4 Sep 2026; one score per team per task):
  - **Task A:** 63.21, **8th of 8**. The best score was 81.78.
  - **Task B:** 53.20, **6th of 7**. The best score was 61.55, and we finished ahead of team meooo, who were 2nd on Task A.
  - Metric: final = 0.25·Cosine Similarity + 0.25·Structural Match Score + 0.50·PDG similarity. All three measure similarity to the organizers' reference programs; none checks whether the code compiles or runs.
- **Main finding:** repair fixes "vocabulary" problems:
  - writes to inputs
  - dead overrides
  - undeclared variables
  - some unused I/O

  It never fixed a single `STATIC_OUTPUT`, which is a structural or temporal problem. **"Clean" ≠ correct:** several clean programs still get the timing or latching behaviour wrong (tasks 2, 14, 22).
- **Size trade-off:**
  - 1.5B follows the schema better (0 parse failures).
  - 7B gets the logic right more often: about half as many semantic issues (23 vs 45 on the first attempt).
  - 7B was chosen as primary.

---

## 1. The task

- **Source of test tasks:** `Test-Dataset-AI4Industrial-Automation.xlsx`, read with `openpyxl`. Column A, from row 2 on, gives 30 tasks. See the driver scripts, e.g. `RUN-fih-01/code/run_real_test_set_with_repair_7b.py`, the `__main__` block.
- **Format of each task:** 2–4 sentences of English spec, then a list of I/O points with IEC addresses. Examples:
  - bit form: `Start_Button: %IX0.2`
  - word form: `Temp_Sensor: %IW52`
  - one out-of-distribution notation, task 28: `AI:0.5` / `DI:0.3`
- **Word (register) addressed I/O** (`%IW`/`%QW`) appears in 13 tasks: 4, 7, 11, 12, 13, 14, 15, 16, 17, 25, 27, 29, 30. Task 28 uses `AI:`/`DI:`. The docstring of `rust_printer.py` counts these together as "14/30".
- **Required I/O per task** (names listed with an address, as extracted by `lint_program.extract_required_io`): 2 to 11, with a median of about 5.
- **Domains covered by the 30 tasks:**
  - tank fill
  - traffic light
  - motor start/stop with seal-in (several)
  - filling cycle
  - auger in auto mode
  - conveyor start/stop (several variants)
  - two-ingredient recipe mixing
  - door open/close with limits
  - car-wash-style cycle
  - box counting
  - photo-eye triggered weighing
  - heater setpoint with offset
  - two-fan temperature hysteresis
  - compressor pressure band
  - CO2 damper positioning
  - irrigation 10-min timer
  - vision check point
  - two-floor elevator
  - part-present cycle
  - safety light curtain
  - jam detection with 8 s delay
  - 3:1 dosing ratio via pulse counting
  - light chase
  - pH acid/base dosing
  - conveyor RPM setting (4 variants: 27–30)
- **Constraints:**
  - model under 8B parameters
  - external data allowed (the organizers Biswajit Chatterjee and Manjira Sinha, TCS, confirmed this)
- **Deadlines:**
  - runs were submitted by 21 Aug 2026
  - working note due 30 Sep 2026
  - camera-ready due 25 Oct 2026

---

## 2. Where everything lives (folder map)

```
./   (repository root)
├── README.md
├── RUN-fih-01/                      ← PRIMARY: 7B + repair + Rust post-pass
│   ├── README.md
│   ├── code/                  (10 .py files)
│   ├── taskA-outputs/  task_01..30.st + all_results.jsonl
│   └── taskB-outputs/  fixed_task_NN.rs (27) + task_08/24/30.rs (raw failures)
│                       + all_results.jsonl + rust_check_report.{jsonl,txt}
├── RUN-fih-02/                      ← 1.5B + repair + Rust post-pass
│   ├── README.md
│   ├── code/                        (same 10 .py files, byte-identical to RUN-01 — see §9)
│   ├── taskA-outputs/  task_01..30.st + all_results.jsonl
│   └── taskB-outputs/  task_01..30.rs (these are the PATCHED files) + rust_check_report.{jsonl,txt}
│                       (NO taskB all_results.jsonl)
├── RUN-fih-03/                      ← BASELINE: 7B, single shot, no checks, no post-pass
│   ├── README.md
│   ├── code/                  (6 .py files)
│   ├── taskA-outputs/  task_01..30.st + all_results.jsonl (stores generated_raw!)
│   └── taskB-outputs/  task_01..30.rs + all_results.jsonl
├── docs/PAPER_NOTES.md              ← this file
└── paper/                           ← the LaTeX working note (main.tex, references.bib, ceurart.cls)
```

In the submitted zips the code folder was named `code_files/` (RUN-01), `code/` (RUN-02) and `code-files/` (RUN-03). In this repository all three are renamed to `code/`, and every run README is named `README.md` (originally `README_7B_repaired.md`, `RUN-fih-02-README.md` and `RUN-fih-03-README.md`).

### 2.1 Code files and which run ships them

MD5 check: every shared file is **byte-identical** across the runs that ship it.

| File | Role | RUN-01 | RUN-02 | RUN-03 |
|---|---|---|---|---|
| `ast_nodes.py` | AST dataclasses (the IR) | `code/` | `code/` | `code/` |
| `ast_compact.py` | compact JSON ⇄ AST | ✓ | ✓ | ✓ |
| `st_printer.py` | AST → ST (Task A) | ✓ | ✓ | ✓ |
| `rust_printer.py` | AST → Rust (Task B) | ✓ | ✓ | ✓ |
| `lint_program.py` | static linter | ✓ | ✓ | — |
| `ast_interpreter.py` | scan-cycle interpreter | ✓ | ✓ | — |
| `smoke_test.py` | 200-cycle STATIC_OUTPUT test | ✓ | ✓ | — |
| `run_real_test_set_with_repair_7b.py` | Task A driver + repair loop | ✓ | ✓ (still says 7B! §9) | — |
| `run_task_b_rust_repaired.py` | Task B driver + repair loop | ✓ | ✓ (still says 7B! §9) | — |
| `fix_rust_outputs.py` | Rust post-pass + rustc gate | ✓ | ✓ | — |
| `run_real_test_set_7b.py` | Task A single-shot driver | — | — | ✓ |
| `run_task_b_rust.py` | Task B single-shot driver | — | — | ✓ |

**Not shipped in any run:**
- the training script (`train_lora_7b.py`)
- the LoRA adapters (`./lora_nl2ast_adapter_7b`)
- `merge_datasets.py`
- the corpus builder

The READMEs say the adapters are "available on request".

---

## 3. Training data

- **Total:** 744 (instruction, compact-AST) pairs. Source: all three READMEs, §2.
  - **349** from the official FIRE training set.
  - **395** (744 − 349) from our own corpus: permissively licensed open-source PLC code from GitHub, plus synthetic and augmented variants.
- **Licences allowed:** MIT, Apache-2.0, BSD-3-Clause, BSD-2-Clause, Unlicense, CC0-1.0, ISC. GPL and LGPL were excluded.
- **Confirmed permissive PLCopen XML sources:**
  - `tkucic/plc_hello_mixing_tank` (MIT)
  - `tkucic/plc_traffic_control` (MIT)
  - `ScalABLE40/robin` (Apache-2.0)
  - Further sources were catalogued as unconfirmed or excluded.
- **Finding for the paper: permissive PLCopen XML is scarce.** Most real IEC 61131-3 code on GitHub lives in GPL/LGPL ecosystems, such as Beremiz and iec-checker.
- **How we filtered for authenticity:**
  - We required schema markers: a `TC6_XML` namespace plus `pou name=` plus `bodyType`. This tells real project files apart from parser or schema test files.
  - GitHub code search with `filename:*.xml "TC6_XML"` worked much better than general web search.
- **Processing:** parse → our AST → compact JSON → merge and de-duplicate (`merge_datasets.py`, not shipped).
- **Data bug found and fixed:** in the combined dataset, 45 of 747 records had a zero-argument function call. The compact serializer drops empty lists, so deserializing those records crashed. We fixed this by giving `args` and `named_args` a `default_factory=list`. Source: the docstrings of `FunctionCallExpr` and `FunctionCallStatement` in `ast_nodes.py`.
  - The 747 vs 744 difference is most likely de-duplication. Check this before quoting it.

---

## 4. Method, component by component

### 4.1 Architecture (the one-figure summary)

```
NL task text (+ I/O list)
   │
   ▼
Qwen2.5-Coder-{7B|1.5B}-Instruct + LoRA  ──►  compact JSON AST (text)
   │                                              │
   │                                  strip ``` fences → json.loads → (fallback) json_repair
   │                                              │
   │                                  compact_json_to_ast()  → typed AST objects
   │                                              │
   │                        ┌──── lint_program(program, task_text) ────┐
   │                        └──── smoke_test(program)  (200 cycles) ───┘
   │                                              │
   │◄──── feedback turn (parse error OR issue list + anti-gaming rules) ── if not CLEAN, ≤3 attempts
   │
   ▼
 print_program() → .st   (Task A)
 print_rust_program() → .rs → fix_rust_outputs.py → rustc gate   (Task B)
```

Design principle: *separate what the program does (AST) from how it's spelled (printer)*. Source: the docstring of `ast_nodes.py`, which says "Language-independent AST node definitions -- the real compiler target … AST -> (ST | Rust)".

### 4.2 The IR: `ast_nodes.py`

This is plain Python `@dataclass`es. There are **18 node types**:

- **Expressions (7):**
  - `Identifier(name)`. The name may include one dotted member, e.g. `"Timer.Q"`.
  - `Literal(text)`. Kept as source text: `"TRUE"`, `"0.0"`, `"T#5s"`, `"16#FAC0"`.
  - `BinaryOp(op, left, right)`. Ops: AND OR XOR + - * / MOD > < >= <= = <> **.
  - `UnaryOp(op, operand)`. Ops: NOT or -.
  - `FunctionCallExpr(name, args=[])`
  - `ArrayIndex(base, index)`
  - `MemberAccess(base, member)`
- **Statements (9):** `Assignment(target, value)`, `FunctionCallStatement(instance_name, named_args=[])`, `If(branches, else_body)`, `Case(selector, branches)`, `For`, `While`, `Repeat`, `Return`, `Exit`.
- **Program level (2):**
  - `VarDecl(name, type, scope, address=None)`. The scope is one of input, output, local, inout or temp (also memory, external and global).
  - `Program(name, kind, return_type, variables, body)`. The kind is program, function_block or function.
- `address` on `VarDecl` keeps the IEC address, e.g. `%IX0.0`. The Rust printer uses it for Modbus mapping (§4.6). **The ST printer ignores it** (§8.4).

### 4.3 Compact serialization: `ast_compact.py`

- **Why we needed it** (from the module docstring):
  - Our first serialization used verbose tags such as `"__type__": "FunctionCallExpr"`.
  - These caused **real generation truncation** on large corpus programs (FB_BeltConveyor, TrafficController, BOILER), even at `max_new_tokens=2560`.
  - Those ASTs have 150–250+ nodes, and the tags alone were **an estimated 40–50% of serialized size**.
- **Type codes** (`_TYPE_CODES`):

| Node | Code | Node | Code |
|---|---|---|---|
| Identifier | `Id` | Assignment | `Asn` |
| Literal | `Lit` | FunctionCallStatement | `FnS` |
| BinaryOp | `Bin` | If | `If` |
| UnaryOp | `Un` | Case | `Cs` |
| FunctionCallExpr | `FnE` | For | `For` |
| ArrayIndex | `Arr` | While | `Wh` |
| MemberAccess | `Mem` | Repeat | `Rp` |
| VarDecl | `Vd` | Return / Exit | `Ret` / `Ex` |
| Program | `Prg` | | |

- **Field aliases** (`_FIELD_ALIASES`):
  - name→`n`, type→`ty`, scope→`sc`, kind→`k`, return_type→`rt`
  - variables→`vars`, body→`b`, target→`tg`, value→`v`
  - op→`o`, left→`l`, right→`r`, operand→`opd`
  - args→`a`, base→`ba`, index→`ix`, member→`m`
  - instance_name→`in`, named_args→`na`, branches→`br`, else_body→`eb`, selector→`sel`
  - loop_var→`lv`, start→`st`, end→`e`, step→`sp`, condition→`c`, text→`tx`
- **Rules:**
  - Null fields and empty lists are **omitted**.
  - The 2-element tuple pairs (named args, if/case branches) are flattened to plain lists, and re-wrapped as tuples on decode for the fields `na`, `a` and `br`.
- **Decoding is strict:**
  - An unknown `"t"` raises `ValueError("Unknown or missing type code")`.
  - An unknown field name reaches the dataclass constructor and raises `TypeError`. Both count as "parse failures" (§6.4).
- **Real example**, from the 7B model on test task 2 (stored in `RUN-fih-03/taskA-outputs/all_results.jsonl`, field `generated_raw`):
  ```json
  {"t":"Prg","n":"TrafficLightCycle","k":"program","vars":[
    {"t":"Vd","n":"Red_Light","ty":"BOOL","sc":"output","address":"%QX1.0"}, …,
    {"t":"Vd","n":"TP_Red","ty":"TP","sc":"local"}, …],
   "b":[{"t":"FnS","in":"TP_Red","na":[["IN",{"t":"Id","n":"TRUE"}],["PT",{"t":"Lit","tx":"T#5s"}]]}, …,
        {"t":"Asn","tg":"Red_Light","v":{"t":"Id","n":"TP_Red.Q"}}, …]}
  ```
- **Size on the test set** (RUN-03 raw outputs): median AST is about 1,044 characters, max 2,805.

### 4.4 Model, fine-tuning and inference

- **Base models:** `Qwen/Qwen2.5-Coder-7B-Instruct` (RUN-01, RUN-03) and `Qwen/Qwen2.5-Coder-1.5B-Instruct` (RUN-02).
  - 0.5B was also trained, but only in preliminary experiments, and it was not submitted.
- **LoRA:**
  - rank 16, alpha 32
  - target modules: q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj
  - base weights frozen
  - Source: all three READMEs, §2.
- **Hardware:** 2× Quadro RTX 6000 (24 GB each) on a remote server.
- **Hyperparameters we do not have:** learning rate, epochs, batch size and max sequence length are not recorded anywhere in `submissions/`. **Get them from `train_lora_7b.py` on the server before writing §4.2 of the paper.**
- **Training target:** NL → compact AST only. The model never sees ST or Rust as output.
- **Held-out result** (internal split of our data; split size not recorded): 1.5B reached **96% compile success**, meaning a valid, printable AST.
- **Inference** (identical in every driver):
  - `AutoModelForCausalLM.from_pretrained(..., device_map="auto", dtype=torch.bfloat16)`, then `PeftModel.from_pretrained(base, ADAPTER_PATH)`.
  - The chat template is applied with `add_generation_prompt=True`.
  - `model.generate(max_new_tokens=2560, do_sample=False)`, i.e. **greedy, deterministic**.
- **Prompt** (the same `SYSTEM_PROMPT` in all drivers, e.g. lines ~35–60 of `run_real_test_set_with_repair_7b.py`):
  - Role: "expert industrial automation programmer … output ONLY a JSON object … compact AST … no explanation, markdown, or ST".
  - The full compact schema follows: one line per node type with its short fields.
  - Last line: "Omit any field that would be null or an empty list".
  - User turn: `"Task: {task}\n\nOutput the AST as JSON:"`.
- **Output parsing** (`evaluate()` in the repair drivers; inline in the RUN-03 drivers):
  1. `strip_code_fence`, a regex that removes a leading ```` ```json ```` and the trailing ```` ``` ````.
  2. `json.loads`, and if that raises `JSONDecodeError`, then `json.loads(repair_json(text))`.
  3. `compact_json_to_ast`.
  4. The printer.

  Any exception in these steps means `COMPILE_FAILED`. It is called "compile", but here it means "the AST could not be built or printed".
- **Determinism consequence:** because decoding is greedy, **RUN-01 attempt 1 = RUN-03** on every task. We verified this: RUN-03's re-linted results equal RUN-01's first-attempt statuses exactly. It also means the separate Task A and Task B generation runs give **identical attempt logs**; for RUN-01, `taskA/all_results.jsonl` and `taskB/all_results.jsonl` have identical `attempt_log`s (verified). So RUN-01 vs RUN-03 is a **clean ablation of the repair loop**.

### 4.5 ST printer: `st_printer.py`

- It uses an `Emitter` class with **lazy per-line indentation**: a line's indent is fixed when its first content is emitted, not at `newline()`.
  - The docstring records the real bug this fixed: the first VAR_INPUT line was missing its indent, and END_VAR kept the inner indent, seen on `GenericBistableDeviceModel`.
- The header depends on kind: `PROGRAM`, `FUNCTION_BLOCK`, or `FUNCTION name : rt`.
- Var blocks are emitted in a fixed order (input→VAR_INPUT, output→VAR_OUTPUT, inout→VAR_IN_OUT, temp→VAR_TEMP, local→VAR), each written as `name : TYPE;`.
- Expression printing:
  - It uses a precedence table (OR/XOR 0 < AND 1 < comparisons 2 < +,- 3 < *,/,MOD 4 < ** 5).
  - Parentheses are added only when needed.
  - `NOT x` is printed with a space; any other unary op is printed as `{op}{inner}` **verbatim** (this matters, see §7.4).
- Statements: IF/ELSIF/ELSE/END_IF, CASE…OF label: … END_CASE, FOR…TO…BY…DO, WHILE, REPEAT…UNTIL…END_REPEAT, and FB calls as `Inst(IN := x, PT := T#5s);`.
- The `address` field is **not printed**: there is no `AT %IX0.0` in the output (see §8.4).
- Output sizes on the test set: RUN-01 ST files are a median of 17 lines (range 9–44); RUN-02 a median of 18 (9–46).

### 4.6 Rust printer: `rust_printer.py`

- **Target template:** FIRE's own Modbus client polling loop. It was checked against FIRE's 4 published reference examples (ConveyorStart, ProductCounter, EmergencyShutdown, ProductStop). Source: the module docstring.
- **Generated structure:**
  1. `use modbus::{Client, Coil}; use modbus::tcp::{self, Config};`
  2. Constants: `MODBUS_SERVER_IP = "127.0.0.1"`, `MODBUS_PORT = 502`, `UNIT_ID = 1`.
  3. A `ModbusClient` wrapper with `read_coils`, `write_coil`, `read_holding_register` and `write_register`.
  4. `PlcProgram::run()`: every variable becomes a `let mut` local, then a `loop {}` that
     - reads inputs,
     - runs the translated body,
     - writes outputs,
     - calls `std::thread::sleep(20 ms)`.
  5. `fn main()`.
- **Address mapping:**
  - Bit form `%[IQM]X<byte>.<bit>` maps to Modbus **coil** `byte*8+bit`. For example `%IX19.1` → coil 153.
  - Word form `%[IQM]W<n>` maps to **holding register** `n`.
  - Anything else, e.g. task 28's `AI:0.5`, is left unmapped. The docstring says this was a deliberate choice, an "accepted gap".
- **Types:** BOOL→`bool`; REAL/LREAL→`f64`; everything else→`i32`.
- **Names:** `_to_snake` converts CamelCase to snake_case. For a member access `X.Q` it prints `x_q`.
- **Operators:** AND→`&&`, OR→`||`, XOR→`^`, `=`→`==`, `<>`→`!=`, MOD→`%`. Every binary op gets full parentheses. NOT→`!`, and **any other unary op → `-`**.
- **CASE:** translated to an if/else-if chain (`selector == label`), not a `match`. This avoids having to know the selector's Rust enum type.
- **Function-block emulation** (`SCAN_INTERVAL_MS = 20`, matching FIRE's `INTERVAL := T#20ms`):
  - **TON:** `if IN { acc += 1 } else { acc = 0 }; q = acc >= PT_ms/20`. State fields are `_acc: u64` and `_q: bool`.
  - **CTU:** `if R { count = 0 } else if CU { count += 1 }; q = count >= PV`. Fields `_count` and `_q`.
  - **R_TRIG:** `q = clk && !prev; prev = clk`.
  - **Any other FB (TP, TOF, CTD, F_TRIG, SR, RS):** the printer emits the comment `// unsupported FB call: …` and declares **no state fields**. The instance itself falls through to the `i32` default. This is the main source of Rust `E0425` errors (§6.5).
  - FB outputs other than `.Q` (e.g. `CTU.CV`, `TON.ET`) are not declared either, which also leads to `E0425`.
- **Loops:** For, While, Repeat, Return and Exit become `// unsupported statement type` comments. This is consistent with the interpreter, which does not run loops either.

### 4.7 Linter: `lint_program.py`

`lint_program(program, task_text)` returns a list of readable issue strings. **Execution order:** `MISSING_REQUIRED_IO` comes first (it is prepended), then the rules in the table.

| Rule | What it detects | How | Why it exists (from the docstrings, i.e. seen during development) |
|---|---|---|---|
| `MISSING_REQUIRED_IO` | An addressed I/O in the task text that is not declared (case-insensitive) | `extract_required_io` regex per line: `^\s*([A-Za-z_]\w*)\s*[:\s]\s*(%[IQ]\w*[\d.]*\|[AD][IO]:[\d.]+)` | **Real exploit:** during repair the model *deleted* required inputs (Speed_Select, RPM_Set) to silence UNUSED_IO |
| `UNUSED_IO` | A declared input/output never referenced or assigned | `io_vars − used_names − assigned_targets`, after walking all statements and expressions | Core "spec coverage" check |
| `IMPOSSIBLE_CONDITION` | An AND chain of numeric comparisons on the same variable with an empty range, e.g. `X > 300 AND X < 280` | flatten the AND chain, then `max(lowers) >= min(uppers)` | Seen in a task-14-style bug. It now also recurses into CASE/loops, after a real gap where CASE branches were not checked |
| `FB_DIRECT_ASSIGN` | `TON0 := …` instead of a call | assignment target ∈ FB instances | Invalid ST pattern |
| `UNKNOWN_FB_TYPE` | An FB-like instance whose type is outside {TON, TOF, TP, CTU, CTD, CTUD, R_TRIG, F_TRIG, SR, RS} | name prefix / type check | Invented FB types. **It never fired on the test set** |
| `UNDECLARED_VARIABLE` | An identifier used but not declared (member access stripped: `TON0.Q`→`TON0`) | `referenced − declared − {TRUE, FALSE}` | Hallucinated names |
| `INPUT_ASSIGNED_TO` | An assignment *into* a declared input | assignment targets ∩ inputs | **Real exploit:** `Reset_Button := FALSE;` written only to silence UNUSED_IO. Inputs are read-only in IEC 61131-3 |
| `DEAD_OVERRIDE` | An unconditional **constant** assignment at top level, after an IF/CASE that already set the same variable | tracks the conditionally-set set | **Real bugs:** a trailing `Conveyor_Run := FALSE;` (task 22) and `Acid_Pump := FALSE; Base_Pump := FALSE;` (task 25). **Restricted to constants** after the earlier version produced false positives on `Damper_Position := Damper_Position + (CO2_Sensor-600)/400` (tasks 3, 16) |

Every rule in the table has its own function; §4.8 adds `STATIC_OUTPUT`.

### 4.8 Interpreter and smoke test: `ast_interpreter.py` + `smoke_test.py`

- **Interpreter:**
  - Runs the AST one scan cycle at a time and keeps the state of variables and FBs between cycles.
  - Starting values: BOOL=False, REAL=0.0, others=0.
  - It uses the same `SCAN_INTERVAL_MS = 20` as the Rust backend, so the two agree.
- **FB semantics implemented:**
  - **TON:** acc counts up while IN is true, and q = acc ≥ threshold.
  - **CTU:** reset / count-up, q = count ≥ PV, and it also exposes `cv`.
  - **R_TRIG:** q = clk ∧ ¬prev.
  - **TP:** a rising edge starts a pulse lasting `threshold` scans.
- **Not implemented:**
  - TOF, CTD and F_TRIG are recognised as FB types, but their q stays False.
  - FunctionCallExpr such as `MOD(...)` evaluates to `None`.
  - For/While/Repeat are **not executed** (a deliberate scope limit).
  - `max_pt_scans` caps every timer threshold, and is used only by the smoke test.
- **The docstring is honest about limits:** "not a formal verifier and has no built-in notion of 'correct' behavior". It catches temporal bugs only if you give it inputs and check the trace.
- **Smoke test** (`smoke_test(program, cycles=200)`):
  - `Interpreter(program, max_pt_scans=10)`: every timer is capped at 10 scans (200 ms). Real presets (8 s, 10 s, 20 s, 30 s, 10 min) could never fire in 200 cycles and would otherwise give **false STATIC_OUTPUT flags on correct programs**.
  - **Targeted stimulus** for "trigger inputs", i.e. BOOL inputs that feed any FB call's arguments directly or through an expression (`_find_fb_trigger_inputs`, which recurses into If/Case/loops):
    - **Phase 1** (cycles 1–66): fast toggling `(cycle % 4) < 2`. That is one rising edge every 4 cycles, enough for counters that need several PV counts.
    - **Phase 2** (67–133): sustained hold, staggered by input-index parity (`i % 2 == 0`).
    - **Phase 3** (134–200): sustained hold with the **opposite** parity. One fixed staggering has only a 50% chance of satisfying `A AND NOT B`-type conditions.
  - **Other inputs:** BOOL uses `(cycle + 3i) % (4+i) < 2` (staggered periods); INT/REAL uses `(cycle*(i+1)*17) % 1000`.
  - **Flag:** `STATIC_OUTPUT: '<out>' never changed value across 200 scan cycles … stuck at {v}`.
  - **What it can't do:** it does not know what the correct behaviour is. It only catches outputs that respond to nothing.

### 4.9 The repair loop: `run_real_test_set_with_repair_7b.py` / `run_task_b_rust_repaired.py`

- `MAX_ATTEMPTS = 3`. Each attempt:
  1. generate
  2. `evaluate()`
  3. log `{attempt, status, issues, compile_error}`
- **Statuses:**
  - `CLEAN`: stop.
  - `ISSUES_FOUND`: keep this program as the current best.
  - `COMPILE_FAILED`: keep the previous best, if there is one.
- **Final status:**
  - `CLEAN`, or
  - `ISSUES_FOUND` (the last parseable program), or
  - `FAILED` (no attempt ever parsed; the output file then holds `// GENERATION FAILED\n// Raw: …`).
- **Feedback construction.** The conversation grows: `+ {assistant: previous raw output} + {user: feedback}`.
  - **Parse failure:** `"That output failed to compile with this error: {err}\n\nPlease provide a corrected JSON AST that fixes this specific problem."`
  - **Issues:** `"That output compiled, but automated review found these problems:\n- …\n\nPlease provide a corrected JSON AST that fixes these specific problems."`, **plus a fixed set of anti-gaming instructions**:
    > "IMPORTANT: never fix an unused-variable warning by deleting the variable or removing it from the task -- every input/output listed in the task with an address must remain declared AND be genuinely used in real logic. Never assign a value to a declared INPUT variable. Never write a constant assignment to an output after conditional logic has already set it."
  - Lesson learned: the **wording of the feedback matters**. Without these sentences the model took shortcuts such as deleting variables or making dummy assignments.
- **Priority** (per the docstring): parse errors → lint issues → smoke issues. In practice, lint and smoke issues are joined into one list (lint first).
- **Exception handling:** `lint_program` and `smoke_test` are each wrapped in `try/except: []`. **An exception inside either counts as "no issues"** (§8.3).
- **Task B driver:** a **byte-for-byte copy of the Task A driver** except for three things: `print_rust_program` instead of `print_program`, a `.rs` extension, and a `rust_code` key. The lint and smoke checks run on the AST, so they apply unchanged.

### 4.10 Rust post-pass: `fix_rust_outputs.py`

It runs in the Task B output directory **after** the repair driver has finished. It is purely mechanical and makes no model calls. For each `task_*.rs`:

1. **Modbus stub injection**, if the file contains `use modbus::`. We prepend a self-contained `mod modbus { … }` with:
   - `enum Coil { On, Off }`
   - `trait Client`
   - `tcp::Config { tcp_port, modbus_uid }` (with Default)
   - `tcp::Transport` holding 256 coils and 256 registers in memory, with `new_with_cfg`, `read_coils`, `write_single_coil`, `read_holding_registers` and `write_single_register`, all returning `Result`.

   The original `use modbus::…` lines are **kept**, because they now resolve to the local module. Stripping them was an earlier bug that broke the unqualified `tcp::Transport`, `Config` and `Coil`.
   - **Why:** in the first Task B run, **81 of about 150 rustc error lines** were `unresolved import 'modbus'`. A standalone `rustc` has no `Cargo.toml` to resolve dependencies.
2. **Helper prelude:** add `real_to_int`, `int_to_real`, `bool_to_int`, `clamp_i32` or `clamp_f64` when the code calls one without defining it. **It never triggered on the submitted runs.**
3. **Dead-override stripping:** a regex search for `var = <literal>;` right after an if-block that assigned `var`. **It never triggered on the submitted runs**, because the AST-level `DEAD_OVERRIDE` repair had already removed these.
4. **Scan-count timer flag** (report only): `*_acc >= N`. The report lists these under `scan_count_flags`.
5. **Compile gate:** `rustc --edition 2021 --emit=metadata --crate-type bin`, 60 s timeout. The status is OK, FAILED, TIMEOUT or SKIPPED.
6. **Outputs:**
   - `fixed_task_NN.rs`, only if a patch was applied
   - `rust_check_report.jsonl`
   - `rust_check_report.txt`

**In practice, only patch 1 was ever applied.** This is true in both runs, for all 27 of RUN-01's files with an AST and all 30 of RUN-02's.

---

## 5. The three submitted runs

| | RUN-fih-01 (primary) | RUN-fih-02 | RUN-fih-03 (baseline) |
|---|---|---|---|
| Base model | Qwen2.5-Coder-**7B**-Instruct | Qwen2.5-Coder-**1.5B**-Instruct | Qwen2.5-Coder-**7B**-Instruct (same adapter as 01) |
| LoRA | r16/α32, same data | r16/α32, same data | same as 01 |
| Decoding | greedy, 2560 tok | greedy, 2560 tok | greedy, 2560 tok |
| Lint + smoke | yes | yes | **no** |
| Repair loop | ≤3 attempts | ≤3 attempts | **no (1 shot)** |
| Rust post-pass | yes | yes | **no** |
| Task A driver | `code/run_real_test_set_with_repair_7b.py` | `code/run_real_test_set_with_repair_7b.py` (config must have been edited to 1.5B at run time) | `code/run_real_test_set_7b.py` |
| Task B driver | `code/run_task_b_rust_repaired.py` + `fix_rust_outputs.py` | `code/run_task_b_rust_repaired.py` + `fix_rust_outputs.py` | `code/run_task_b_rust.py` |
| README | `README_7B_repaired.md` | `RUN-fih-02-README.md` | `RUN-fih-03-README.md` |
| Per-task logs | `taskA-outputs/all_results.jsonl`, `taskB-outputs/all_results.jsonl` (both with attempt logs, no raw text) | `taskA-outputs/all_results.jsonl` only | `taskA/…jsonl`, `taskB/…jsonl` (**with `generated_raw`**) |
| Rust reports | `taskB-outputs/rust_check_report.{jsonl,txt}` | same | none |

**Purpose of each run:**
- **01** is our best system.
- **02** tests model size with the pipeline held fixed.
- **03** is the ablation that isolates the effect of verification and repair. Because decoding is greedy, 03 = 01's first attempt exactly.

---

## 6. Results (all numbers verified)

### 6.1 AST-level outcomes (applies to Task A and Task B alike, since both share one AST)

| Run | 1st attempt Parsed | 1st Clean | 1st issue instances | Final Parsed | Final Clean | Final issue instances | Total generations |
|---|---|---|---|---|---|---|---|
| RUN-fih-03 (7B, 1 shot) | 26 | 15 | 23 | 26 | 15 | 23 | 30 |
| RUN-fih-01 (7B, repair) | 26 | 15 | 23 | **27** | **18** | **14** | 58 |
| RUN-fih-02 (1.5B, repair) | **30** | 9 | 45 | **30** | 12 | 37 | 69 |

- RUN-01 final breakdown: **18 CLEAN, 9 ISSUES_FOUND, 3 FAILED** (tasks 8, 24, 30). Attempt counts: 15 tasks took 1 attempt, 2 took 2, and 13 took 3.
- RUN-02 final breakdown: **12 CLEAN, 18 ISSUES_FOUND, 0 FAILED**. Attempt counts: 9 tasks took 1 attempt, 3 took 2, and 18 took 3.
- **What repair changed in RUN-01:**
  - Flagged → CLEAN on 3 tasks: **14** (INPUT_ASSIGNED_TO), **21** (UNUSED_IO, then MISSING_REQUIRED_IO), **22** (DEAD_OVERRIDE + STATIC_OUTPUT).
  - Parse-fail → parseable on 1 task: **23**.
- **What repair changed in RUN-02:** flagged → CLEAN on **2, 15, 19**.

### 6.2 Issue types, first vs final (instance counts summed over tasks)

| Rule | 7B first | 7B final | 1.5B first | 1.5B final |
|---|---|---|---|---|
| UNUSED_IO | 7 | 5 | 14 | 11 |
| STATIC_OUTPUT | 9 | **9** | 21 | 15 |
| INPUT_ASSIGNED_TO | 2 | **0** | 1 | 0 |
| DEAD_OVERRIDE | 3 | **0** | 0 | 1 |
| UNDECLARED_VARIABLE | 2 | **0** | 3 | 2 |
| MISSING_REQUIRED_IO | 0 | 0 | 3 | **6** ↑ |
| IMPOSSIBLE_CONDITION | 0 | 0 | 3 | 2 |
| FB_DIRECT_ASSIGN / UNKNOWN_FB_TYPE | 0 | 0 | 0 | 0 |

**What this table shows:**
- Repair fully removes the **local and syntactic-semantic** problems: input writes, dead overrides and undeclared names.
- **STATIC_OUTPUT is never fixed by 7B** (9 → 9). A non-responsive output needs a *structural* change (a missing seal-in, an unreachable branch, a wrong FB wiring). A one-line diagnosis doesn't help the model find that.
- **1.5B games the loop under pressure:** MISSING_REQUIRED_IO doubles (3 → 6). It deletes the variable despite the explicit instruction not to, and the backstop rule catches it.

### 6.3 Per-task table (all 3 runs, both tasks)

Legend: C = clean, I = issues found, P = parse failure on that attempt, F = final failure (no AST ever). "Rust" means the standalone `rustc` result after the post-pass. For RUN-03 Rust, all 30 FAIL (unresolved `modbus`).

| # | Spec (first line) | Req. I/O | Word I/O? | RUN-03 (7B, 1 shot) | RUN-01 attempts ⇒ final | RUN-01 final issues | RUN-02 attempts ⇒ final | RUN-02 final issues | Rust RUN-01 | Rust RUN-02 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Fill tank using Fill_Pump when Start_Button pressed and Low_Level_Sens… | 5 | no | ISSUES: UNUSED_IO | I→I→I ⇒ **I** | UNUSED_IO | I→I→I ⇒ **I** | UNUSED_IO | OK | OK |
| 2 | Traffic light cycles automatically through Red (5s), Green (5s), and Y… | 3 | no | CLEAN | C ⇒ **C** | — | I→C ⇒ **C** | — | FAIL (E0425) | FAIL (E0425) |
| 3 | Start motor with Start_Button, stop with Stop_Button | 6 | no | CLEAN | C ⇒ **C** | — | I→I→I ⇒ **I** | UNUSED_IO, STATIC_OUTPUT | OK | OK |
| 4 | Start filling cycle with Start_Button | 6 | yes | CLEAN | C ⇒ **C** | — | I→I→I ⇒ **I** | UNUSED_IO×2, STATIC_OUTPUT | OK | OK |
| 5 | Auger_Motor runs in Auto_Mode whenever Low_Level_Sensor is active and… | 5 | no | CLEAN | C ⇒ **C** | — | C ⇒ **C** | — | OK | OK |
| 6 | Start motor with Start_Button, stop with Stop_Button | 6 | no | CLEAN | C ⇒ **C** | — | I→I→I ⇒ **I** | MISSING_REQUIRED_IO, UNUSED_IO×2 | OK | OK |
| 7 | Start/stop conveyor with Start_Button and Stop_Button | 7 | yes | ISSUES: UNUSED_IO | I→I→I ⇒ **I** | UNUSED_IO | C ⇒ **C** | — | OK | OK |
| 8 | Start_Button opens Ingredient_A_Valve and Ingredient_B_Valve together | 8 | no | PARSE FAIL: type code 'FALSE' | P→P→P ⇒ **F** | no AST | I→I→I ⇒ **I** | STATIC_OUTPUT×2 | FAIL (E0601) | FAIL (E0369) |
| 9 | Open_Button drives the door open until Open_Limit is reached | 7 | no | CLEAN | C ⇒ **C** | — | I→I→I ⇒ **I** | UNUSED_IO | OK | OK |
| 10 | Cycle starts automatically when Car_Present is detected and Start_Butt… | 6 | no | ISSUES: STATIC_OUTPUT×4 | I→I→I ⇒ **I** | STATIC_OUTPUT×2 | I→I→I ⇒ **I** | STATIC_OUTPUT×4 | OK | OK |
| 11 | Box_Sensor counts boxes passing on the line | 3 | yes | CLEAN | C ⇒ **C** | — | C ⇒ **C** | — | FAIL (E0425) | FAIL (E0308,E0425) |
| 12 | Photo_Eye triggers a weight check of the part currently on the scale | 4 | yes | CLEAN | C ⇒ **C** | — | C ⇒ **C** | — | FAIL (E0277) | FAIL (E0425) |
| 13 | Heater turns on when Temp_Sensor drops 5 degrees below Setpoint | 3 | yes | CLEAN | C ⇒ **C** | — | I→I→I ⇒ **I** | UNDECLARED_VARIABLE | OK | FAIL (E0425) |
| 14 | Temp_Sensor reads process temperature in tenths of a degree | 3 | yes | ISSUES: INPUT_ASSIGNED_TO (+smoke exception) | I→C ⇒ **C** | — | I→I→I ⇒ **I** | IMPOSSIBLE_CONDITION×2, STATIC_OUTPUT×2 | OK | OK |
| 15 | Compressor_Motor starts when Pressure_Sensor falls below 80 psi | 2 | yes | CLEAN | C ⇒ **C** | — | I→C ⇒ **C** | — | OK | OK |
| 16 | Damper_Position is fully closed (0%) when CO2_Sensor is at or below 600… | 2 | yes | CLEAN | C ⇒ **C** | — | C ⇒ **C** | — | FAIL (E0277,E0308) | OK |
| 17 | Irrigation_Valve opens for a fixed 10 minutes whenever Soil_Moisture d… | 3 | yes | CLEAN | C ⇒ **C** | — | C ⇒ **C** | — | OK | FAIL (E0425) |
| 18 | Part_Detect signals that a part has reached the vision check point | 3 | no | ISSUES: UNUSED_IO | I→I→I ⇒ **I** | UNUSED_IO | I→I→I ⇒ **I** | UNUSED_IO | OK | OK |
| 19 | Two-floor elevator moves up when Call_Floor2 is pressed and it is not… | 6 | no | CLEAN | C ⇒ **C** | — | I→C ⇒ **C** | — | OK | OK |
| 20 | Cycle starts when Start_Cycle is pressed and Part_Present is detected | 6 | no | ISSUES: UNUSED_IO, STATIC_OUTPUT×2 | I→I→I ⇒ **I** | STATIC_OUTPUT×4 | I→I→I ⇒ **I** | MISSING_REQUIRED_IO, STATIC_OUTPUT | OK | FAIL (syntax) |
| 21 | Start/stop conveyor with Start_Button and Stop_Button as usual | 5 | no | ISSUES: UNUSED_IO | I→I→C ⇒ **C** | — | I→I→I ⇒ **I** | MISSING_REQUIRED_IO×2 | FAIL (E0600) | OK |
| 22 | Start/stop conveyor with Start_Button and Stop_Button | 6 | no | ISSUES: DEAD_OVERRIDE, STATIC_OUTPUT | I→C ⇒ **C** | — | I→I→I ⇒ **I** | UNUSED_IO, STATIC_OUTPUT×2 | OK | OK |
| 23 | Start/stop dosing with Start_Button and Stop_Button | 5 | no | PARSE FAIL: type code 'Mod' | P→I→I ⇒ **I** | STATIC_OUTPUT | I→I→I ⇒ **I** | STATIC_OUTPUT | FAIL (E0425) | FAIL (E0425) |
| 24 | Start/stop light chase with Start_Button and Stop_Button | 6 | no | PARSE FAIL: Assignment got unexpected kwarg 'name' | P→P→P ⇒ **F** | no AST | C ⇒ **C** | — | FAIL (E0601) | FAIL (E0425) |
| 25 | pH_Sensor reads process pH scaled by 100 (e.g. 700 = pH 7.00) | 3 | yes | ISSUES: UNDECLARED_VARIABLE×2, INPUT_ASSIGNED_TO, DEAD_OVERRIDE×2, STATIC_OUTPUT×2 | I→I→I ⇒ **I** | STATIC_OUTPUT×2 | C ⇒ **C** | — | FAIL (E0277) | OK |
| 26 | Start the conveyor when Start_Button pressed and stop conveyor when St… | 3 | no | CLEAN | C ⇒ **C** | — | C ⇒ **C** | — | OK | OK |
| 27 | Set conveyor RPM using RPM_Set input before starting | 5 | yes | ISSUES: UNUSED_IO | I→I→I ⇒ **I** | UNUSED_IO | I→I→I ⇒ **I** | UNDECLARED_VARIABLE | FAIL (E0308) | FAIL (E0308,E0425) |
| 28 | Set conveyor RPM using RPM_Set input | 5 | AI/DI | CLEAN | C ⇒ **C** | — | I→I→I ⇒ **I** | UNUSED_IO | OK | OK |
| 29 | Set conveyor RPM using RPM_Set input at the beginning | 8 | yes | ISSUES: UNUSED_IO | I→I→I ⇒ **I** | UNUSED_IO | I→I→I ⇒ **I** | MISSING_REQUIRED_IO, UNUSED_IO, DEAD_OVERRIDE, STATIC_OUTPUT | FAIL (E0308) | FAIL (E0308) |
| 30 | Set conveyor RPM using RPM_Set input at the beginning | 11 | yes | PARSE FAIL: type code 'id' | P→P→P ⇒ **F** | no AST | I→I→I ⇒ **I** | MISSING_REQUIRED_IO | FAIL (E0601) | FAIL (E0277,E0308) |

**Patterns to point out in the paper:**
- The hardest tasks for both models are those with **the most I/O and multi-step sequences**: 8 (8 I/O, recipe), 10 (car wash), 20, 23 (ratio dosing), 24 (light chase), 29–30 (8 and 11 I/O).
- 7B's parse failures all fall on **long or complex tasks** (8, 23, 24, 30), where the AST is largest.
- Simple latches, threshold control and single timers (3–6, 13–17, 19, 26) are clean for 7B on the first try.
- The two models are clean on **different** tasks. For example, 1.5B is clean on 7, 24 and 25, where 7B is not. That suggests **ensembling or choosing per task** (e.g. taking whichever run gives a CLEAN result) as cheap future work. The union of CLEAN tasks across 01 and 02 is **21 of 30**: 2, 3, 4, 5, 6, 7, 9, 11, 12, 13, 14, 15, 16, 17, 19, 21, 22, 24, 25, 26, 28.

### 6.4 Parse failures (7B): all are schema violations, not JSON syntax

`json_repair` handled whatever JSON syntax damage there was. Every remaining failure is the model **leaving the compact schema**:

| Task | Error | Interpretation |
|---|---|---|
| 8 | `Unknown or missing type code: 'FALSE'` | Wrote a boolean literal as a node type (e.g. `{"t":"FALSE"}`) instead of `{"t":"Id","n":"FALSE"}` or `{"t":"Lit","tx":"FALSE"}` |
| 23 | `Unknown or missing type code: 'Mod'` | Invented a `Mod` node for the MOD operator instead of `{"t":"Bin","o":"MOD",…}`. **Repaired on attempt 2.** The fix used `MOD(CTU0.CV, 4)` as a FunctionCallExpr |
| 24 | `Assignment.__init__() got an unexpected keyword argument 'name'` | Used the long field name `name` inside an `Asn` node (should be `tg`) |
| 30 | `Unknown or missing type code: 'id'` | Lowercase `id` instead of `Id` |

- **Interpretation:** these look like the base model's prior knowledge leaking through: ST keywords (`FALSE`, `MOD`) and general JSON habits (`name`, lowercase). There is more of that prior knowledge at 7B than at 1.5B, which **never** produced a parse failure.
- **Repair rarely fixes them:** 3 of 4 stayed failed after 3 attempts. The same parse error was fed back each time, and the model repeated the same mistake.
- **Obvious future fix:** constrained or grammar-guided decoding against the compact schema, or a tolerant decoder (case-insensitive codes, mapping `name`→`tg`, treating `TRUE`/`FALSE` as literals).

### 6.5 Rust (Task B) compile results

| Run | rustc OK | Failures |
|---|---|---|
| RUN-fih-03 (no post-pass) | **0/30** | all: `E0432/E0433 unresolved import 'modbus'` (verified by compiling the files) |
| RUN-fih-01 | **18/30**: tasks 1, 3, 4, 5, 6, 7, 9, 10, 13, 14, 15, 17, 18, 19, 20, 22, 26, 28 | 2, 8, 11, 12, 16, 21, 23, 24, 25, 27, 29, 30 |
| RUN-fih-02 | **18/30**: tasks 1, 3, 4, 5, 6, 7, 9, 10, 14, 15, 16, 18, 19, 21, 22, 25, 26, 28 | 2, 8, 11, 12, 13, 17, 20, 23, 24, 27, 29, 30 |

**Root cause of each failure** (from `rust_check_report.txt` plus the printer code). Most are **printer or compiler bugs, not model errors**:

| Cause | Tasks (01) | Tasks (02) | Owner |
|---|---|---|---|
| No AST, raw text saved (`E0601` no `main`) | 8, 24, 30 | — | model (parse) |
| **TP (and other non-TON/CTU/R_TRIG FBs) not emulated.** `tp_x_q` is never declared (`E0425`) | 2, 11, 23 | 2, 11, 23, 24 | **printer** |
| FB outputs other than `.Q` not declared (`ctu0_cv`, `ton_x_et`) (`E0425`) | 11 | 11, 13, 17 | **printer** |
| INT defaults to `i32`, arithmetic with float literals (`E0277` "cannot divide/multiply i32 by {float}", `E0308`) | 12, 16, 25, 27, 29 | 29, 30 | **printer** (type inference) |
| `MOD(…)` FunctionCallExpr printed as `mod(…)`, a Rust keyword (syntax error) | 23 | — | **printer** |
| `T#500ms` literal in an expression printed verbatim (`prefix 'T' is unknown`) | — | 20 | **printer** |
| `ABS()` → `abs(…)` undefined (no helper prelude for it) | — | 12 | **printer / post-pass** |
| Case mismatch: ST is case-insensitive, Rust is not (`CONveyor_Run` → `co_nveyor_run`) | — | 27 | **printer** (should canonicalise to the declared name) |
| Unary op `Id` printed as `-bool` (`E0600`) | 21 | — | **model**, with no operator validation (§7.4) |
| BOOL level switch divided by 50.0 (`E0369`) | — | 8 | **model** (semantic type error) |

- **Important for the paper:** "18/30 in both runs" hides **different** failure sets.
  - The **printer's limited FB coverage (TP, CV, ET)** alone accounts for 3 failures in 01 and 6 in 02.
  - Type-inference gaps account for 5 in 01.
  - These are all **fixable without touching the model**.
- **CLEAN vs Rust OK do not line up:**
  - RUN-01: 13 tasks are both CLEAN and rustc-OK (3, 4, 5, 6, 9, 13, 14, 15, 17, 19, 22, 26, 28). Five are CLEAN but fail rustc (2, 11, 12, 16, 21). Five compile but are not CLEAN (1, 7, 10, 18, 20).
  - RUN-02: only 7 tasks are both CLEAN and rustc-OK (5, 7, 15, 16, 19, 25, 26).
  - This shows the two verifiers (AST semantic checks vs target-language compile) catch **different** failure classes.
- **Scan-count flags** (report only): `_acc >= N` is flagged 9 times across 6 files for RUN-01 and 21 times across 15 files for RUN-02. This is expected, because TON is emulated as `PT_ms/20` scans. Examples: 8 s → `>= 400`, 30 s → `>= 1500`. We note it as a design limitation (§8.5).

### 6.6 Official evaluation (released 4 Sep 2026)

Source: organizers' email "official results of the FIRE 2026 Shared Task on AI4Industrial Automation", 4 Sep 2026. The results are also on the task website, under Results.

| Rank | Task A: NL → ST | Score | Task B: NL → Rust | Score |
|---|---|---|---|---|
| 1 | 8 Bit Thugs | 81.78 | Master Mind | 61.55 |
| 2 | team meooo | 79.31 | CSNLP | 60.43 |
| 3 | Treygram | 78.83 | AutoLogic AI | 59.29 |
| 4 | Master Mind | 76.63 | Treygram | 59.22 |
| 5 | CSNLP | 75.11 | TokenX | 56.67 |
| 6 | AutoLogic AI | 73.62 | **fih** | **53.20** |
| 7 | TokenX | 73.50 | team meooo | 44.20 |
| 8 | **fih** | **63.21** | | |

- **Metric:** Final = **25% Cosine Similarity (CS) + 25% Structural Match Score (SMS) + 50% Program Dependence Graph similarity (PDG)**. These are all **reference-similarity** measures. None of them checks compilation or execution.
- **One score per team:** the leaderboard gives a single score per team per task and does **not say which of our 3 runs** it is. Presumably it is the primary run, RUN-fih-01. Confirm with the organizers if the paper needs to state this.
- **Gap to the top:**
  - Task A: −18.57 (63.21 vs 81.78), and −10.3 below the next team (TokenX, 73.50).
  - Task B: −8.35 (53.20 vs 61.55), and −3.47 below 5th place (TokenX).
  - **Relative to the field we did clearly better on Rust than on ST.**
- **Likely reasons.** These are hypotheses: we have only aggregate scores, not per-metric or per-task ones.
  1. **ST drops the `AT %IX…` addresses** (§8.4). The reference ST likely declares `X AT %IX0.0 : BOOL;`, so every Task A file probably loses some structural and dependence-graph similarity. The Rust printer does encode every address, via Modbus coil/register numbers.
  2. **The Rust printer copies FIRE's own reference template** (the Modbus polling loop from their 4 published examples). That probably boosts CS and SMS in Task B.
  3. **The 3 failed items (8, 24, 30) in RUN-01 were submitted as `// GENERATION FAILED` plus raw JSON**, which scores about 0 on every metric. RUN-02 (1.5B) has no such files, so if RUN-01 was the scored run, those three items cost us.
  4. Our internal gains (lint-clean, rustc-OK) are **not directly rewarded** by similarity metrics. For example, a verbose but correct program can score lower than a short one that looks like the reference.
- **Deadlines:** this email said the working note was due 15 Sep. It was superseded by the later email (10 Sep), which gives **30 Sep 2026** for working notes and 25 Oct for the camera-ready.
- **In the paper:** §6.4 has Table 4 (the full leaderboard) and the hypotheses above. The abstract and conclusion state the ranks.

---

## 7. Qualitative error analysis ("CLEAN ≠ correct")

All the code below is quoted from the submitted files.

### 7.1 Task 2 (traffic light): CLEAN, but does not cycle

`RUN-fih-01/taskA-outputs/task_02.st` (identical in RUN-03):
```
TP_Red(IN := TRUE, PT := T#5s);
TP_Green(IN := TP_Red.Q, PT := T#5s);
TP_Yellow(IN := TP_Green.Q, PT := T#2s);
Red_Light := TP_Red.Q;  Green_Light := TP_Green.Q;  Yellow_Light := TP_Yellow.Q;
```
- **What's wrong:** `TP` fires on a rising edge, and `IN := TRUE` gives exactly one rising edge. The green phase is triggered while red is **on**, not when it ends, and nothing loops yellow back to red. So the lamps overlap and the sequence never repeats.
- **Why it passes the checks:** every lamp changes at least once in 200 cycles, so the smoke test passes.
- **In Rust:** it also fails to compile, because TP is not supported (`tp_red_q`).

### 7.2 Task 14 (two-fan hysteresis): repair fixed the lint issue but lost the hysteresis

- **Spec:** Fan1 on above 30.0 °C and off below 28.0 °C; Fan2 on above 35.0 and off below 33.0. The sensor reads in tenths of a degree.
- **Attempt 1:** `INPUT_ASSIGNED_TO: 'Temp_Sensor'`.
- **Attempt 2** is CLEAN (`RUN-fih-01/taskA-outputs/task_14.st`):
  ```
  Fan1 := Temp_Sensor >= 300;
  Fan2 := Temp_Sensor >= 350;
  ```
- **What's wrong:** the scaling is correct (tenths), but the 28/33 °C switch-off thresholds are gone, so the fans chatter around the set point.
- **Why the checks miss it:** there is no rule for "a spec with two thresholds needs a latch".

### 7.3 Task 22 (jam detection): repair made it CLEAN, but no latch and no interlock

- **Attempt 1:** `DEAD_OVERRIDE` (a trailing `Conveyor_Run := FALSE`) plus `STATIC_OUTPUT`.
- **Attempt 2** is CLEAN:
  ```
  TON_Jam_Delay(IN := NOT Exit_Photo_Eye AND Entry_Photo_Eye, PT := T#8s);
  Jam_Alarm := TON_Jam_Delay.Q;
  IF Stop_Button THEN Conveyor_Run := FALSE; Jam_Alarm := FALSE; END_IF;
  IF Start_Button THEN Conveyor_Run := TRUE; END_IF;
  ```
- **What's right:** the 8 s jam timer is correct.
- **What's wrong:**
  - `Jam_Alarm` is re-assigned every scan, so it **does not latch**.
  - A jam **does not stop the conveyor**, which the spec requires.
  - Start has priority over Stop.

### 7.4 Task 21 (safety light curtain): "CLEAN", but contains `IdStop_Button`

- **Log** (`RUN-fih-01/taskA-outputs/all_results.jsonl`, task 21):
  - attempt 1: `UNUSED_IO: Stop_Button`
  - attempt 2: `MISSING_REQUIRED_IO: Stop_Button` (the model deleted it!)
  - attempt 3: CLEAN.
- **Final ST:** `Conveyor_Run := (Start_Button OR IdStop_Button) AND Light_Curtain_Clear;`
- **Final Rust** (`RUN-fih-01/taskB-outputs/fixed_task_21.rs`, line 110): `conveyor_run = ((start_button || -stop_button) && light_curtain_clear);`, which fails with `E0600` (unary minus on bool).
- **Diagnosis** (confirmed from both printers):
  - The model emitted a **UnaryOp with `o: "Id"`**, i.e. a node type code placed in the operator slot, with `opd = Identifier("Stop_Button")`. The intended node was presumably `NOT`.
  - The ST printer prints unknown unary operators verbatim (`Id` + `Stop_Button`). The Rust printer maps any non-NOT unary to `-`.
- **Why the linter missed it:** the operand is a real, declared variable, so there is no UNUSED_IO and no UNDECLARED_VARIABLE. **No check validates the operator vocabulary.**
- **Interpreter behaviour:** it evaluates any non-NOT unary as numeric negation, so `-True = -1`, which is truthy. The output still toggles, and the smoke test passes.
- **Fix:** validate `UnaryOp.op ∈ {NOT, -}` and `BinaryOp.op ∈` the known set in `compact_json_to_ast` or the linter, and raise it as an issue. The paper's error-analysis paragraph has been updated with this diagnosis.

### 7.5 Task 1 (tank fill): a lint issue that repair never resolves

- **Final** (all 3 attempts, same issue): `Fill_Pump := (Start_Button OR NOT High_Level_Sensor) AND NOT Stop_Button;`
- **What's wrong:**
  - The `Low_Level_Sensor` permissive is ignored, and the linter correctly flags `UNUSED_IO`.
  - There is also no seal-in, so the pump runs only while Start is held, or whenever the tank isn't full.
- **How the models differ:** 1.5B instead drops `Stop_Button`.
- **Lesson:** the model repeats itself under identical feedback. That argues for adding **diversity on retry** (e.g. sampling with temperature on attempts 2–3) or more specific feedback.

### 7.6 Task 23 (dosing): repaired from a parse failure, still STATIC_OUTPUT

- **Final:**
  ```
  R_TRIG0(CLK := Flow_A_Pulse);
  CTU0(CU := R_TRIG0.Q, R := Stop_Button, PV := 50);
  TP0(IN := Start_Button AND NOT Stop_Button, PT := T#1s);
  Valve_A := TP0.Q;
  Valve_B := TP0.Q AND MOD(CTU0.CV, 4) = 0;
  ```
- **What's wrong:**
  - `Valve_A` is a 1 s pulse, not "open the whole time the system is running". There is no run latch.
  - `MOD(...)` is a FunctionCallExpr, which the interpreter evaluates to `None`, so `Valve_B` stays False and triggers STATIC_OUTPUT.
  - In Rust, `mod(` is a keyword, so it doesn't compile.
- **Worth noting in the paper:** part of this STATIC_OUTPUT is an **interpreter gap** (no FunctionCallExpr evaluation), not purely a model error.

### 7.7 Common thread (for the discussion section)

- **Vocabulary vs structure:**
  - The models reliably get the vocabulary right: correct I/O names, correct FB types, plausible presets, correct scaling.
  - Our verifiers are good at checking vocabulary.
  - Most remaining errors are **temporal structure**: seal-in/latching, hysteresis, cyclic sequencing, and interlock priority. These can only be checked against the spec.
- **Next step:** take simple temporal properties from the task text and test them with the interpreter we already have. Examples: "Stop_Button ⇒ motor false next scan", "after T in state X ⇒ state Y". Alternatively, use a model checker, as in LLM4PLC.

---

## 8. Design choices, trade-offs and known limitations (be upfront about these in the paper)

### 8.1 Why use an AST IR instead of generating ST directly
- **Output length:** far fewer tokens, so no truncation on big programs.
- **Structured decoding:** errors are well-typed (unknown code, missing field), which gives targeted feedback.
- **Language-agnostic verification:** lint and interpretation are written once and serve both tasks.
- **One model, two languages:** the Task A/B difference is only in the deterministic printer.
- **Cost:** the model has to learn a custom schema. The 7B parse failures show that schema discipline is not free. And any printer bug hits every output (e.g. TP in Rust).

### 8.2 Why lint and smoke test instead of an ST compiler
- **Fast and in the loop:** no external toolchain is needed on the GPU server.
- **Targets real observed failures:** every lint rule's docstring cites the bug that motivated it (task numbers above).
- **Uses the task text:** the linter checks against the spec's own I/O list.
- **Limitation:** our "compile" check for ST is really **"parses into our AST and pretty-prints"**. We **never ran the ST through a real IEC 61131-3 compiler** (e.g. MatIEC or ruSTy). This is the biggest validity gap.

### 8.3 Exceptions in lint and smoke count as "clean"
- In `evaluate()`: `try: lint_program(...) except Exception: lint_issues = []`, and the same for `smoke_test`.
- A crash in either therefore silently reports no issues.
- **Observed:** on task 14's first-attempt AST, the smoke test raises `TypeError: '>=' not supported between 'NoneType' and 'int'`, which we saw when re-running RUN-03's outputs. The lint issue was still reported, so the task was not falsely CLEAN, but the mechanism exists.
- **Fix:** turn an exception into an issue (`VERIFIER_ERROR`) instead of `[]`.

### 8.4 ST output drops hardware addresses
- The AST keeps `address` (`%IX0.0` etc.), but `st_printer.py` writes `Fill_Pump : BOOL;` rather than `Fill_Pump AT %QX0.0 : BOOL;`.
- **Consequence:** the I/O mapping required by the spec is not present in the ST files. This may affect the official evaluation. Consider adding `AT` for the camera-ready code release.

### 8.5 Rust backend scope
- **FBs:** only TON, CTU and R_TRIG are emulated. TP, TOF, CTD, F_TRIG, SR and RS become comments, and `.CV`/`.ET` outputs are not declared.
- **Statements:** there are no loops (For/While/Repeat are skipped).
- **Timers:** they are scan-count timers (`PT/20 ms`) rather than `Instant`/`Duration`.
- **Types:** INT is always `i32` and there is no numeric type inference.
- **Modbus stub:** it keeps the shape of the interface, but the I/O is simulated (256 coils and 256 registers in memory). This matches Task B's aim (syntax plus logic preservation), but should be stated.
- **Non-standard addresses:** task 28's `AI:`/`DI:` addresses are unmapped. The docstring records this as a deliberate "accepted gap".

### 8.6 Interpreter scope
- It only implements TON, CTU, R_TRIG and TP.
- FunctionCallExpr evaluates to `None`.
- Loops are not executed.
- The timer cap of 10 scans is used for smoke testing only.
- These gaps cause some STATIC_OUTPUT results that are the interpreter's fault (e.g. task 23).

### 8.7 Repair loop design
- **Retries are greedy, but the context differs:** decoding is deterministic, and each retry sees a different conversation because feedback is appended. The model still often repeats the same answer (tasks 1, 7, 18, 27, 29, 30 have the same issue on all 3 attempts).
- **No roll-back to the best attempt:** the loop keeps the **last** parseable program, not the one with the fewest issues.
  - For example, RUN-01 task 20 went from 3 issues (UNUSED_IO + STATIC_OUTPUT×2) to 4 (STATIC_OUTPUT×4).
  - Keeping the attempt with the fewest issues would be a simple improvement.
- **Budget:** 3 attempts, so at most 90 generations. Actual use was 58 generations (7B) and 69 (1.5B).

---

## 9. Packaging inconsistencies to fix before camera-ready

The organizers or reviewers may look at these, so fix them in the READMEs and zips:

1. **The RUN-fih-02 README is copied from RUN-01:**
   - It says "Qwen2.5-Coder-1.5B-Instruct (open-source, **7B parameters**…)".
   - §6 says tasks 8, 24 and 30 failed to parse. **That's false for RUN-02**, which parsed 30/30; its `task_08.rs` is real generated code.
   - It also says the training script is `train_lora_7b.py`.
2. **RUN-fih-02 `code/` ships the 7B drivers.** `run_real_test_set_with_repair_7b.py` and `run_task_b_rust_repaired.py` have `BASE_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"` and `ADAPTER_PATH = "./lora_nl2ast_adapter_7b"` (byte-identical to RUN-01). The README refers to `run_real_test_set_with_repair_1_5b.py` and `run_task_b_rust_repaired_1_5b.py`, which are **not in the folder**. Either ship the 1.5B versions or note which constants to change.
3. **The RUN-fih-03 Task A driver docstring** says "Runs the 1.5B LoRA adapter" and calls itself `run_real_test_set_1_5b.py`, but the code uses 7B. It's a stale docstring.
4. **Folder names:**
   - The code folder is called `code/`, `code/` and `code/` in the three runs, but every README says `code/`.
   - RUN-01's README file is named `README_7B_repaired.md`, but the tree inside it says `README.md`.
5. **RUN-fih-02 taskB has no `all_results.jsonl`**, so there is no Task B attempt log. Its `task_NN.rs` files are the *patched* versions: they include the stub, and are 4–5 KB vs about 2 KB unpatched. RUN-01 instead ships `fixed_task_NN.rs` plus 3 raw `task_NN.rs`.
6. **Missing from every package:** the training script, the adapters, `merge_datasets.py`, the training data and the corpus builder. Add a repository link or state that they are available on request (the README already says this for adapters).

---

## 10. Numbers cheat-sheet (copy into the paper)

- Training pairs: **744** (349 official + 395 own). LoRA r=16, α=32, 7 target modules. Greedy decoding, 2,560 max new tokens.
- AST: **18** node types; **28** field aliases; median test AST ≈ **1,044 chars** (max 2,805). Verbose tags ≈ **40–50%** of size on large programs (estimate).
- Linter: **8** rules (MISSING_REQUIRED_IO, UNUSED_IO, IMPOSSIBLE_CONDITION, FB_DIRECT_ASSIGN, UNKNOWN_FB_TYPE, UNDECLARED_VARIABLE, INPUT_ASSIGNED_TO, DEAD_OVERRIDE) plus the smoke-test rule STATIC_OUTPUT.
- Smoke test: **200** cycles, 20 ms scan, timer cap **10** scans, 3-phase trigger stimulus.
- Repair: **≤3** attempts. 7B used **58** generations and 1.5B used **69**, for 30 tasks.
- 7B: parsed 26→**27**, clean 15→**18**, issues 23→**14**.
- 1.5B: parsed **30**, clean 9→12, issues 45→37.
- **Official:** Task A 63.21 (8/8, best 81.78); Task B 53.20 (6/7, best 61.55). Score = 0.25 CS + 0.25 SMS + 0.50 PDG.
- Rust: **0/30 → 18/30** (both repaired runs). The Modbus import accounted for **81 of ~150** error lines in the first Task B run.
- CLEAN ∧ rustc-OK: **13** (7B), **7** (1.5B). The union of CLEAN across 01 and 02 is **21/30**.
- Scan-count timer flags: 9 in 6 files (01), 21 in 15 files (02).

---

## 11. Suggested paper outline and what to cite (matches `paper/main.tex`)

1. **Intro:** PLCs and IEC 61131-3; the task; our idea (AST + deterministic printers + verify/repair); contributions.
2. **Related work:**
   - LLM4PLC (Fakih et al., ICSE-SEIP 2024)
   - Agents4PLC (Liu et al., arXiv 2410.14209)
   - Koziolek et al. (LLM4Code 2024)
   - Self-Debugging (Chen et al., ICLR 2024)
   - Self-Refine (Madaan et al., NeurIPS 2023)
   - LoRA (Hu et al., ICLR 2022)
   - Qwen2.5-Coder (Hui et al., arXiv 2409.12186)
   - Codex eval (Chen et al., 2021)
   - IEC 61131-3:2013
   - PLCopen TC6 XML
3. **Task and data:** §1 and §3 of these notes.
4. **System:** §4.2–4.10 (figure: §4.1).
5. **Runs:** §5.
6. **Results:** §6.1 table, §6.2 figure, §6.5 table, official leaderboard (§6.6, now in paper Table 4).
7. **Error analysis:** §7.1–7.6 (use 2, 14, 22, 21).
8. **Limitations:** §8.2–8.7.
9. **Conclusion and future work:**
   - constrained decoding for schema compliance
   - operator validation
   - an ST compiler in the loop
   - fuller FB coverage and type inference in the Rust printer
   - keeping the attempt with the fewest issues
   - sampling on retries
   - spec-derived temporal property tests
   - 1.5B/7B per-task ensembling
10. **Declaration on Generative AI** (required by CEUR). Acknowledgments go in the `acknowledgments` environment.

**Still missing before the paper is final:**
- the co-author list
- training hyperparameters (lr, epochs, batch size, from `train_lora_7b.py`)
- the held-out split size for the 96% figure
- a code repository URL
