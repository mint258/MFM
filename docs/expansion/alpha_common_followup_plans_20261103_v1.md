# Accepted Alpha Common followup plans

Root runs `workflows/expansion/alpha_common_followup_plans_v1.py` as an isolated
metadata script **after** the actual full Common parent C0 and Root graph review.
It reuses `exact_nn_cached_v1.alpha_common.validate_manifest`; it never creates
a Common receipt, accounting, review, or accepted manifest. Running/source-only
Common inputs fail before output-directory creation. No jobs are submitted.

Expected current Common consumer locator (not yet asserted to exist):
`/gfshome/alpha/codex_data_v1_20261026/control/pubchem_expansion_runtime_20261103/common_actual_close_1885153_v1/common_reference_manifest.json`.

After deploying this new source file to a separate source layer, Root can run:

```bash
A=/gfshome/alpha/codex_data_v1_20261026
B=$A/control/pubchem_expansion_runtime_20261103
PY=$A/software/pubchem_completion_20261103_venv/bin/python
"$PY" -I -B /NEW_SOURCE_LAYER/workflows/expansion/alpha_common_followup_plans_v1.py \
  --common-manifest "$B/common_actual_close_1885153_v1/common_reference_manifest.json" \
  --output-directory "$B/common_followup_plans_1885153_v1"
```

The builder reads the existing grouped Common resource template, actual audit
exact deployment, actual regression deployment, and nine-replica transport.
It hashes source and small metadata only. Large Parquets remain for the admitted
producer's held-FD verification; prior replica verification is not called a new
data readback. Main regression origin UID1278 and job4520414 remain explicit,
with its original pending-Common fields unchanged.

Outputs are `reference_before_plan_template.json`, `reference_before.sbatch`,
`regression_common_plan_template.json`, `regression_common.sbatch`, and
`build_receipt.json`. The sbatch files use the unchanged
`node_launcher_rpc_v3_resume.py`, with explicit distinct `--module` and `--tag`,
the actual deployed layer entry, and read-only Gluster RPC program. The launcher
assigns the real output/job identity, node quota and startup proof. Its prior
resume option is unused; both stages require fresh scientific output directories.

Both templates preserve the shared exact scope300,000,000,000B,
other-future986,736,873,472B,200GB account floor and24GiB available-memory reserve.
Pack uses8GiB parent/tree and1GiB suggested SQLite main cache. SQL binder uses
48GiB tree/32GiB DuckDB,16CPU. Neither sbatch requests Slurm memory, GPU, exclusive
allocation or a wall limit. These are templates for Root's current resource
review, not claims that concurrent jobs fit a node. With baselineStats48GiB,
Root can consider pack8GiB first; binder48GiB waits for real availability and
admission. No new future-reservation credit is inferred.

Source fixtures:
`test_alpha_common_followup_plans_v1.py` checks argv/shell quoting with separate
module/tag, absence of memory/wall requests, running/missing C0 refusal without
writes, and rejection of rewritten Main transport origin. These are synthetic
stdlib metadata checks; no production or chemistry is executed.
