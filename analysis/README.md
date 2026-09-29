# Analysis for the working note

Run everything from the repository root (the folder containing `RUN-fih-01/`, `RUN-fih-02/`, `RUN-fih-03/`).

```
pip install json_repair tokenizers
python3 analysis/compute_paper_numbers.py --tokenizer qwen_tokenizer.json   # pipeline-level numbers
python3 analysis/analyze_outputs.py                                          # output-level numbers
python3 analysis/check_paper_claims.py                                       # asserts every number in the paper
```

`qwen_tokenizer.json` is the `tokenizer.json` of `Qwen/Qwen2.5-Coder-7B-Instruct` (only needed for token
counts). `rustc` must be on PATH for the stub-only ablation.

| File | What it does |
|---|---|
| `compute_paper_numbers.py` | Re-verifies the single-pass run, repair budget curves, issue types, McNemar tests, Rust compile causes, stub-only ablation, representation cost → `paper_numbers.json`, `budget_curve.dat`, `issue_types.dat`, `task_matrix.dat` |
| `st_sim.py` | Parser, name resolver and time-accurate interpreter for the ST subset our printer emits (TON/TOF/TP/CTU/CTD/R_TRIG/F_TRIG/SR/RS with IEC semantics; FBs update only when called) |
| `probes.py` | Behavioural scenarios and checks for the 30 test tasks, written from the task texts |
| `probe_reference/` | Hand-written reference programs used only to show every probe check is satisfiable (169/169) |
| `categories.py` | Hand assignment of each active check to memory / timing / direct |
| `analyze_outputs.py` | Front-end check, interface and timing fidelity, probes (with do-nothing and always-on baselines), repair edit rate, Rust Modbus-address checks → `output_numbers.json` |
| `check_paper_claims.py` | Asserts the numbers quoted in Sections 4–5 |
| `mkfig_tasks.py` | Builds the per-task figure (`fig_tasks.tex`) from `task_matrix.dat` and `output_numbers.json` |

Configurations: `oneshot7` = RUN-fih-03 (7B single pass), `repair7` = RUN-fih-01 (7B + repair),
`repair15` = RUN-fih-02 (1.5B + repair).

Probe conventions: buttons are momentary and normally open; photo-eyes read TRUE when blocked; outputs the text
names but never describes (Running_Lamp, start_light) are not checked; word outputs named after the actuator carry
the set-point while running (tasks 27–30). Identifiers are matched case-insensitively, as in IEC 61131-3.
