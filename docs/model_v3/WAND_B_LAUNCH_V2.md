# Canonical offline SDK layout and external launch v2

Real selected-TRAIN materialization 4520421 completed C0/122s with 17,602
native records, exact cohort replay and zero outer target records decoded.
The source metadata request 413 retained the original 379 scientific selection,
groups and contracts. This data closure does not establish real model scores.

The evaluation tool's logging environment is now declared before importing
or initializing W&B: `WANDB_DIR=output`, `WANDB_CACHE_DIR=output/cache`,
`WANDB_DATA_DIR=output/wandb_data`, `WANDB_MODE=offline`. Canonical ordinary
directories are required. The previous `sdk_cache` location is preserved in
older source records but is not used by the new logger. Model math, precision,
source fields, native population, panel tasks and readout recipes are unchanged.
Nothing in `current/phychem_mfm` changes for this fix, preserving the closed
store's source inventory.

`current/tests/test_model_v3_wandb_layout.py` separates a narrow environment
helper test from a real offline SDK process: actual `wandb.init`, one synthetic
committed log and `finish`, a physical SDK file, and validation by the existing
fixed profiler output accountant. That test is not a tracker mock or evidence
of model training/online sync. Its actual CPU result remains pending until
Root reports it.

New external drafts are in
`runs/model_v3_20261025/sa3_b3_panel_launch_v2`; v1 is retained. The CPU helper
requires a machine-derived evaluator SHA from the newly verified committed
logging source, alongside the actual execution commit. It does not silently
replace the old v1 bridge pin. The public panel/rules preregistration stays
`39cf4929299cd227a3c361183a4b26c8b1405900`.

V2 reads and byte-binds exactly
`/share/home/zixiao/descriptor_analysis/MFM_model_v3_profiler_v2/tools/model_v3/runtime_monitor.py`
from the Root-validated fixed dc22d3f tree. The exact file SHA is computed on
the executing machine and included in the spec. The guard verifies and imports
that module with registration in `sys.modules`, then directly calls
`owned_output_bytes`; SDK symlink and hard-link rules are not duplicated or
weakened. Maximal independent roots are counted once, so an H0 cache nested
under the evaluation root is not charged again. `eval/h0_cache` is the canonical
v2 H0 location. The three new external accounting fixtures test canonical link
shapes and nested/disjoint root counting; these manual fixtures are separate
from the actual SDK test.

V2 requests 32 GiB and enforces 28 GiB owned-group RSS, with a common 2 GiB
budget for evaluation, H0/cache and guard outputs. Root's aggregate supervisor
also covers detached SDK descendants, node memory/UUID admission and actual
Slurm cost. Effective FP32/TF32/matmul policy is recorded unchanged; whole-panel
and W&B-finish deadlines remain explicit. No live B3 panel or one-GPU-hour
performance claim is made before actual completion and accounting closure.

Actual Root allocation4520426 completed0:0 in7 seconds: all11 checks passed
(1.54 seconds pytest), including the real offline SDK write/finish/layout
probe and three independent output-accounting cases. Source hashes before
and after execution matched. The raw SDK remains in its own external test
directory; this is a logging diagnostic, not a B3 evaluation result.
