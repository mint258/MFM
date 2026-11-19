# MFM development workflow

## Downstream benchmark active scope (owner decision 2026-11-19)

- Five unnamed endpoints are deferred from current B1–B4 benchmark evaluation. They remain solely in historical B0 source/provenance records and in a separate owner-controlled private mapping. Do not reintroduce them into active tasks.
- Before B1 baseline fitting or later endpoint evaluation, use `workflows.benchmark_data.task_selection.select_active_tasks` with the exact registry in `configs/benchmark_data/B1.deferred_tasks.json`. Verify all five matches on the complete task inventory; fail closed if unresolved. Current B0 source counts are historical provenance, not the B1 task roster.
- For routine modeling/research conversations, prefer `docs/benchmark/DEFERRED_TASKS.md` and the active benchmark plan; do not load raw source acquisition manifests unless the work genuinely requires source-level reconciliation. Do not rename raw scientific datasets to disguise their provenance.
- This is a prospective owner scope adjustment, not a B1 performance-driven deletion. All remaining endpoints and archived results stay unchanged.


- Read `docs/DEVELOPMENT_HANDOFF.md` and `docs/DATA_PIPELINE.md` first. Develop under `current/phychem_mfm`; root MoE code and `legacy/descriptor` are historical implementations.
- Canonical downstream representation: `SharedBackboneMFM.encode_atoms(batch)` (H0). Preserve source atom order and explicit labels/masks. Do not add task fusion or gates to H0.
- `docs/SOURCE_MANIFEST.json` records exact server exports. Record new source revisions separately; do not silently rewrite historical hashes or checkpoint provenance. Preserve frozen configurations and evidence.
- Keep real data, weights, checkpoints, computed labels, caches, databases and credentials outside Git. Run `python tools/check_repository.py` before committing. Credentials use existing keys or environment variables.
- Server means `zixiao@202.38.247.57:22`; project means `/share/home/zixiao/descriptor_analysis`. `X:\` is its live SSHFS view. Server edits use `X:\`, not the local OneDrive copy. Verify `Test-Path X:\` and key-based `ssh descriptor-analysis-remote` first.
- Non-GPU computation runs only on `compute-0-8` through `compute-0-19` under the 2026-11-18 CPU policy. Login-node Git, Slurm, quota and process metadata are allowed; scientific computation is not. Never run server scripts using a local Windows interpreter. Formal computation uses the established Slurm workflow; this snapshot adds no experiment or queue-restoration authorization.
- Paid school server `202264640132@202.38.252.202:22` is only for explicitly approved formal pretraining. Recover its existing sbatch workflow before submitting; never use it for development/tests.
- Use the installed `huagong_hpc_requirement` skill for actual server operations. Do not modify/cancel others' tasks or unrelated active WP5 work.
- Normalization and model selection use TRAIN only. Preserve official ExpansionRx membership and source atom IDs. PM7 energy is FINAL HEAT OF FORMATION (kcal/mol); charge is NET ATOMIC CHARGES (e).
