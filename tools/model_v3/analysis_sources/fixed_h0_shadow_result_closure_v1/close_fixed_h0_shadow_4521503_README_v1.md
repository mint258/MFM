# Independent metadata closure for fixed-H0 CPU shadow4521503

The independent read-only SSH sacct call actually returned
4521503|zixiao|COMPLETED|0:0|13|16|compute-0-13. Its complete tool output,
including the SSH welcome banner, is preserved in
fixed_h0_shadow_4521503_independent_sacct_readonly_v1.json. It is explicitly a
combined tool stream, not fabricated separate native stdout/stderr. No model
or CPU scientific computation was run by the reviewer.

Closed JSON metadata confirms48 cases/432 observations, complete before/after
maps for212 source entries (3,166,588B), and identical map-file raw SHA.
CPU metadata preflight reports1 positive plus15 rejected negative parser
controls, not a new2639 regression. Tiny-head checks cover4 original forms.
The maximal saved CPU_FP32 closure is1.0587911840678754e-22 and saved FP64
closure1.3234889800848443e-23. The original fixed1e-10 component closure
and physical FP32 threshold remain unchanged. CPU source is revision3;
the GPU capture producer remains its actual revision2, never relabelled.

`close_fixed_h0_shadow_4521503_v1.py` is the independent stdlib-only Root
closer. Root reviews AST/raw source and executes it using the existing33577
session or another actual key-authenticated login metadata session:

```bash
P=/share/home/zixiao/descriptor_analysis
export CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
/share/home/zixiao/.conda/envs/chemprop/bin/python -B \
  "$P/runs/model_v3_20261026/close_fixed_h0_shadow_4521503_v1.py"
```

It independently binds COMPLETE/result, full expected source inventory,
212 source before/after entries and actual current source bytes, metadata16
controls, tiny4-head checks, all48x9 coverage, saved maxabs and component
closures. It aggregates closures using only saved JSON scalar terms; it
imports no scientific package and opens no NPZ/tensor/checkpoint/SDK. It
captures a fresh exact-parent sacct frame, validates the CPU supervisor,
remaining process list, storage-stop/final-census failure status and observed
private/output budgets, then writes fresh files:

- N/fixed_h0_shadow_4521503_raw_accounting_v1.json
- N/fixed_h0_shadow_4521503_Root_closure_v1.json

The CPU supervisor has no GPU-style private_storage_cleanup_errors field.
The closer reports the real first_failure=null and storage observation;
it does not invent a separate private deletion receipt or exact memory peak.
Its source-only preparation has not executed this closer or rehashed212
live source files; the separate reviewer observation says so explicitly.

No existing output/source/phase/registry is modified, no new Slurm job is
created, and the full regression is not rerun. This closure is operational
metadata proof, not FP32 equivariance acceptance, architecture adoption or
a replacement for SA4's independent attribution analysis/report.
