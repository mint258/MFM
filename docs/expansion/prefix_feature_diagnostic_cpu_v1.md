# Three original CID failures on the reviewed CPU partition

This isolated variant does not modify the frozen diagnostics, screen.py,
full4520414, old4520427 outputs, or identity-source drafts. It diagnoses the
same CIDs7,52,53 without a repair or added exclusion. CPU nodes are exactly
compute-0-2 and compute-0-8..19; node21 is not permitted. Resources remain
16CPU/4GiB/1h/32MiB on partitioncpu for this bounded test only.
The request additionally reserves32MiB for the central memory monitor, making
the whole-run output/quota budget64MiB; the scientific cap stays32MiB.

`prefix_feature_diagnostic_cpu_v1.py` preserves the four original scientific
functions from `prefix_feature_diagnostic_v1.py`: `json_safe`,
`mol_property_snapshot`, `diagnose_case`, `read_target_prefix`. Only explicit
CPU checkpoint statements are inserted before each case, nested stage and
prefix record. Checkpoint exceptions prevent new work without altering a
scientific result or converting the failure to a chemical exclusion.

`verify_prefix_science_cpu_v1.py` is a stdlib-only metadata check. It parses
both small source files, strips only a no-argument expression statement
`cpu_runtime.checkpoint()`, compares all four full ASTs and reports original
source references plus normalized AST SHA values. It does not execute Python
source functions, RDKit or a data record. The pending check is:

```bash
/share/home/zixiao/.conda/envs/chemprop/bin/python -B REVIEWED_REPO/workflows/expansion/verify_prefix_science_cpu_v1.py --baseline REVIEWED_REPO/workflows/expansion/prefix_feature_diagnostic_v1.py --candidate REVIEWED_REPO/workflows/expansion/prefix_feature_diagnostic_cpu_v1.py
```

The CPU entry calls the Root central runtime with actual intent and plan
paths: `root_guard(intent_path, plan_path,33554432,wall_limit=3600)`. Both parent
and case threads use the same runtime checkpoint, whose heartbeat and STOP
come from `DATA_V1_CPU_INTENT`/`DATA_V1_CPU_GUARD_DIR`. The central launcher
must supply and monitor those. No hostname is substituted or mocked in the
production entry. Its actual proof is retained in the diagnostic receipt.

`data_authority_cpu_v1.py` accepts only completed raw producer4520348 from
node20 and the exact old prefix4520427 node20 consumer. The latter's pinned
small receipt contains the historical raw inode/mtime_ns/size/UID frame. Those
four fields must match the current CPU file. Only cross-node st_dev can
differ. Current CPU full frames, including its own st_dev, remain identical
before/after full1.49GB SHA and after diagnosis. This is not a relaxation to
arbitrary producer receipts or stale source hashes. All body reads stay in
the actual reviewed CPU allocation; no raw download is repeated.

The new request needs `scope_key=prefix_feature_three_cid`, `pilot=true`,
`partition=cpu`, `resource_policy=CPU_BOUNDED_TEST_LIVE_MEMORY_V1` and a single
specific allowed CPU node, together with Root's exact new decision/scope
references and central runtime/launcher/submitter source pins. It binds the
same small427 receipt/old plan/rejections/raw producer and original/new code;
only the raw body goes in data_references. Live quota is not relabeled fresh.

This change grants no adjustment to formal full/generation resource policy.
The original64GiB and85-percent declared-memory conditions remain independent.
No AST check, test, diagnostic or submission has been executed during source
preparation; Root alone runs checks, materializes reviewed inputs and submits.

`materialize_cpu_expansion_pilot_v1.py` is a new stdlib-only Root helper for
both finite expansion scopes. It consumes the actual new Root decision/scope
policy, exact original request (including all its small sources), all five
central runtime files and the unchanged original controller. It performs only
the source AST comparison while preparing new READY plan/script/request. No
raw data body/stat, quota query, scheduler or scientific function runs.

After Root merges and reviews the new sources, its metadata CLI is:

```bash
/share/home/zixiao/.conda/envs/chemprop/bin/python -B /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/expansion/materialize_cpu_expansion_pilot_v1.py --repository /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository --run-root /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025 --reviewer root --node ROOT_SELECTED_CPU_NODE --scope-key prefix_feature_three_cid
```

New paths use job`dv1_prefix_feature_diag_cpu_v1`, plan
`control/requests/dv1_prefix_feature_diag_cpu_v1_plan.json`, request/script with
that job name, and `artifacts/expansion/diagnostics/prefix_features_cpu_v1`.
Root alone validates the new CPU request, publishes actual fresh quota and
submits through the new monitored CPU submitter. The old node20 request/output
destinations are preserved, irrespective of whether they ever executed.

The companion scope`identity_source_pins_76` generates job
`dv1_identity_input_pins_cpu_v1` and output`identity/source_pins_cpu_v1`.
Its new producer`identity_v2/pin_inputs_cpu_v1.py` retains all original76 input
tasks and scientific/schema/count functions; checkpoints alone are inserted
before new tasks/batches/members/hash chunks. Verify with the same AST helper
and `--function physical_stat --function describe_identity_source --function pin_one`.
Its receipt schema`identity_only_current_physical_input_pins_cpu_v1` records
the real CPU node/proof, not node20. The already frozen NOT_READY stage-two
consumer does not accept this new schema; a separately reviewed consumer
adaptation will be needed after actual CPU source pins exist. No identity
export or all-source acceptance is implied by this first-stage producer.
