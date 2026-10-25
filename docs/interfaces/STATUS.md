# Model/data interface status

All dates use Asia/Shanghai. Model-line checkout:
`/share/home/zixiao/descriptor_analysis/MFM_model_v3`, branch `model-v3`.
This file records observations in this checkout; it does not declare external
data-line work absent or override another checkout's delivery state.

| Date | Item | Status | Path / evidence |
| --- | --- | --- | --- |
| 2026-10-25 | Model stage 0 | ACTUAL_AUDIT_PASS: Slurm 4520329 COMPLETED/0:0; 6x512+A4 total 22,352,859, backbone 12,709,424; awaiting report commit | `docs/model_v3/00_baseline_review.md`; `docs/model_v3/results/baseline_parameters.json` |
| 2026-10-25 | Model decision rules | PREPARED, awaiting stage-0 report/commit | `docs/model_v3/DECISION_RULES.md` |
| 2026-10-25 | D-1 | NOT_OBSERVED in the inspected main tree; model needs the data-line contract before real integration | Expected `docs/interfaces/training_format_v3.md` |
| 2026-10-25 | D-2 | NOT_OBSERVED: registry v3 with levels, families, groups, pooling, vector storage and physical masks | Data-line delivery path pending |
| 2026-10-25 | D-3 | NOT_OBSERVED: pilot training export | Data-line delivery path pending |
| 2026-10-25 | D-4 | NOT_OBSERVED: TRAIN normalization and elemental references | Data-line delivery path pending |
| 2026-10-25 | D-5 | NOT_OBSERVED: nested molecule subsets and held-out-conformation validation | Data-line delivery path pending |
| 2026-10-25 | D-6 | NOT_OBSERVED: full v1 export and node-local copies | Data-line delivery path pending |
| 2026-10-25 | D-7 | NOT_OBSERVED: descriptive conformation report | Data-line delivery path pending |

The model line proceeds with existing S inputs and clearly marked synthetic
fixtures while these interfaces are pending. Existing WP5 family Parquet and
the historical target-fidelity registry are not replacements for D-1/D-2.

Stage gates: 0 baseline report; 1 profiler evidence on three GPU types; 2
numeric/trajectory and bf16 evidence; 3 real-data head/loss acceptance; 4
TRAIN-only evaluator and integration; 5 architecture decisions; 6 recipe/B-star
plus user confirmation; 7 freeze/tag/real smoke/PR. No stage is accepted by
preparing its implementation alone. No formal pretraining is authorized here.
