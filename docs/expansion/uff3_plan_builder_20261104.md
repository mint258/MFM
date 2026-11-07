# Direct Alpha UFF pilot plan builder

Metadata only; no Slurm submission, DATA-body hashing or scientific calls.
The current source job ID is read from its actual completed source manifest.
Original max3/fixed30/seed/dedup/no-fill/no-retry and189 TRAIN reference remain.

```sh
PY -I -B ENTRY workflows.expansion.uff3_alpha_runtime_v1.prepare \
  --config ACTUAL_CONFIG.json --source-manifest ACTUAL_SOURCE_MANIFEST.json \
  --source-accounting ACTUAL_SOURCE_SACCT_METADATA.json \
  --source-startup ACTUAL_SOURCE_STARTUP.json --output FRESH_METADATA_DIRECTORY
```

Bindings default to the existing actual
`/gfshome/alpha/codex_data_v1_20261026/control/pubchem_expansion_runtime_20261103/uff189_quality_bindings_v1/bindings.json`.
All four source/quality pins come from this file. `--bindings` can point to the
same verified deployment elsewhere without changing the scientific reference.

Config contains actual refs/values, not future IDs/hashes:

- resources_reference: endpoint/UID/profile, actual quota authority/snapshot,
  software tree RSS and node reserve template;
- deployment_reference: actual UFF source code_references;
- baseline_budget_reference: original v3 all-future budget (caps/floor inherited);
- excluded_active_allocations: actual201 runtime, plan_reference and
  startup_proof_reference. Only its private output_directory is excluded, not
  its historical shared exact output_scope_root. No201 files are enumerated;
- closed_allocations: each new completed scope has scope name, runtime,
  plan_reference, startup_proof_reference, accounting_reference. Native parent
  and batch/steps must actually be C0. The new source is appended automatically
  using source_budget_scope (`exact` or the actual registered source scope);
- global_UFF_scope_root: actual own UFF root. Existing nonempty roots need their
  actual terminal bindings; unknown UFF history cannot become an assumed B=0;
- private_caps_bytes: generation, quality, finalizer. These plus actual legacyB
  and routing allowance must fit unchanged global UFF700GB;
- routing_overhead_reserved_bytes, metadata_reserved_bytes;
- workers:32 by default, within the later actual single-node allocation;
- worker_rss_soft_cap_bytes, parent_rss_cap_bytes, software_rss_budget_bytes,
  minimum_node_available_bytes: explicit real reviewed software limits. Combined
  worker+parent allowances must fit the software tree budget; none is a Slurm
  memory reservation;
- maximum_molecule_output_bytes, parent_family_reserved_bytes,
  ledger_rebuild_reserved_bytes: finite actual runtime reserves; the ledger
  ceiling persists for the full allocation, not only its startup prefix;
- user_policy_reference: unchanged actual max3/no-fill/no-retry user policy;
- optional family_batch_molecules (default64), additional_code_references.

The helper rechecks native metadata of original closed census files and new
actual C0 roots once. It reads no Raw/FP/cache bodies and does not modify201.
Device/inode keys are current-host lossless u64; cross-node device equality is
not assumed. Symlinks/unknown types/shared inode ownership are rejected. Actual
closed allocated bytes replace the old frozen33GB exact credit; other future
reserve is recomputed as the sum of every other cap minus genuine closed bytes.

Inline storage_partition.future_budget is accepted by the UFF entry without a
new Root approval/schema. It still binds original caps/floor, native census and
exact remaining/other arithmetic. Credits apply only after a fresh real quota
query is later than every included native mtime/ctime. If needed, wait for the
next real publisher snapshot; post-query bytes never become premature credit.
Original v3 reference-only partitions remain compatible.

Output is pilot_plan_template.json plus native_closed_blocks.json. The output
stage uses a source-hash routing directory and a launcher job-ID placeholder;
the existing NodeLauncher binds actual argv/job/startup/quota publisher. Root/
coordinator supplies launcher/template submission using the existing workflow.
The helper never calls sbatch. Pilot still selects5000 R then5000 N with the
original Random(20261025). Full retains2.5M in the pilot's exact actual directory;
QA/full metadata builders follow using actual pilot/QA C0, not invented IDs.

Main compute-0-20 source fixture command:

```sh
python -m unittest workflows.expansion.uff3_alpha_runtime_v1.test_prepare -v
```

These fixtures establish arithmetic/credit/partition boundaries, not Alpha
native census or actual generation. Actual runtime code/profiles/quota/source
EOF and memory protection remain in force.
## Actual pilot to QA to same-directory full

After the actual pilot parent/batch/steps are completed0:0:

```sh
PY -I -B ENTRY workflows.expansion.uff3_alpha_runtime_v1.followup qa \
  --config CURRENT_CONFIG.json --pilot ACTUAL_PILOT_RESULT.json \
  --pilot-accounting ACTUAL_PILOT_ACCOUNT.json --output FRESH_QA_METADATA
```

This produces qa_plan_template.json in a fresh independent quality routing
scope. Config additionally supplies qa_sql_memory_bytes and qa_spill_cap_bytes.
Generation's actual closed prefix is covered by its original generation cap,
not charged again as legacyB; only its remaining cap is reserved as QA's peer.
The same original189 four bindings and source are used.

After actual QA C0, preserving its report before full mutates the generation
index:

```sh
PY -I -B ENTRY workflows.expansion.uff3_alpha_runtime_v1.followup full \
  --config CURRENT_CONFIG.json --pilot ACTUAL_PILOT_RESULT.json \
  --pilot-accounting ACTUAL_PILOT_ACCOUNT.json --qa ACTUAL_QA_RESULT.json \
  --qa-accounting ACTUAL_QA_ACCOUNT.json --output FRESH_FULL_METADATA
```

This produces full_plan_template.json. Its output_directory is the actual pilot
result parent and resume_output_directory is explicitly set for the unchanged
node_launcher_rpc_v3_resume.py. It never requests a new generation directory.
Original source/recipe/user max3/no-fill/no-retry/selection settings remain;
current measured software/molecule/family/ledger reserves come from config.
The existing entry's direct pilot/QA/C0 and same-stage checks run while preparing.

All historical derived_runtime_plan markers are inventoried for resume_binding.
Config.previous_accounting_references supplies real terminal accounts for any
older failed or interrupted attempt; the actual pilot account is automatically
included and duplicates are deduplicated. Existing runtime results provide
recorded parent birth when present, without inventing per-worker records.
Current-host PID checks plus real terminal Slurm steps precede continuation.
Old closed packets/caches are reused, and interrupted scientific work remains
UNKNOWN instead of being tried again.

Source/NN/other closed bindings from the pilot's native budget census are
inherited and refreshed alongside newly completed pilot/QA scopes. Every phase
recomputes current metadata credits with active201 excluded; no fixed33GB exact
credit or whole-budget4x extrapolation is reused.

The helper writes templates only. Root/coordinator deploys source, binds actual
launcher job/argv/profile/quota publisher and submits the jobs. No per-job human
approval file, new seed, replacement conformer generation or Slurm submission is
performed by these builders.
Native closed census JSON uses only the local budget.read_census reader with an explicit64MiB size bound, real Q.verify/Q.load and stable parse frame. It accepts legacy entries/frame census and current records census; old frame need not contain st_mode. General scientific/small-metadata readers are unchanged. Actual >2MiB census fixtures exercise inline construction and validation with real file bytes/SHA, without a mocked census loader.

## Full generation closed storage summary and completion plans

New generation software receipts include `closed_ledger`: actual schema2 SQLite
path, persisted current totals/directory totals, maximum native timestamp, sealed
frame (no cross-node device comparison), and bounded mutable routing/runtime
paths. The Alpha guard is stopped/joined before sealing. A new `native_frontier`
scalar is persisted with normal registration batches. This changes accounting
metadata only; core/native/store, candidate order, seeds, geometry/D values and
masks are unchanged.

After actual parent and recorded steps C0, a closed-allocation binding may contain
`generation_receipt_reference`. Budget collection reads that sealed ledger from
one held FD in readonly immutable SQLite mode and verifies frames before/after.
It reads the two persisted totals rows and native frontier, then stats bounded
runtime/top-level files/directories. It never walks molecule/family subtrees,
uses historical peak as current bytes, or treats the root directory blocks as
subtree bytes. New census `generation_summaries` is explicitly separate from
per-file `records`. Unrecorded subtree files receive no credit. New top-level
unregistered hardlinks are rejected. Same-stage pilot/full bindings select the
latest real C0 seal, preventing duplicate prefix credit. Original per-file
census remains compatible. Every quota query cutoff must be strictly later than
the real seal and observed receipt/runtime timestamps.

No compact summary is a new whole-DATA integrity claim: finalizer still checks
all saved F64/cache/family/source evidence once. Actual source bodies are not
rehashed during budget collection. Only closed actual generation stages may use
this path; incomplete/active source allocations cannot.

Generate full QA from actual complete same-stage full result:

```
PY -I -B ENTRY workflows.expansion.uff3_alpha_runtime_v1.completion qa-full --config ACTUAL_CONFIG --generation ACTUAL_FULL_RECEIPT --generation-accounting ACTUAL_C0_ACCOUNTING --bindings ACTUAL_BINDINGS --output FRESH_METADATA_DIRECTORY
```

Generate finalizer after full QA is actually C0:

```
PY -I -B ENTRY workflows.expansion.uff3_alpha_runtime_v1.completion finalize --config ACTUAL_CONFIG --generation ACTUAL_FULL_RECEIPT --generation-accounting ACTUAL_C0_ACCOUNTING --qa ACTUAL_FULL_QA_RESULT --qa-accounting ACTUAL_QA_C0_ACCOUNTING --bindings ACTUAL_BINDINGS --output FRESH_METADATA_DIRECTORY
```

The first template runs `uff3_alpha_runtime_v1.entry` with `runtime_action=quality`
and `mode=full`; the second runs `uff3_candidate_finalize_v1.entry`. Actual
NodeLauncher supplies job ID, paths and startup proof; builders never submit.
Use the actual deployment containing these modules in `code_references`.
Additional finalizer config fields are `maximum_metadata_input_bytes`,
`maximum_molecule_artifact_bytes`, and `shared_input_references` (real read-only
inputs only). QA uses existing finite `qa_sql_memory_bytes` and
`qa_spill_cap_bytes`; private generation/quality/finalizer caps and actual
all-future arithmetic remain inherited from config, never invented future refs.
No per-job Root approval file is introduced. All 2.5M source records, including
zero/sparse/failed/unknown results, must remain present. Future4+ is not run here.

Stdlib source/real tiny-filesystem fixtures (not Alpha full-DATA evidence):
`python -m unittest workflows.expansion.uff3_alpha_runtime_v1.test_ledger_summary workflows.expansion.uff3_alpha_runtime_v1.test_completion workflows.expansion.uff3_alpha_runtime_v1.test_prepare workflows.expansion.uff3_alpha_runtime_v1.test_followup -v`.
## Allocation-local five-stage continuation

`workflows.expansion.uff3_alpha_runtime_v1.prepare_pipeline` prepares exactly one
step, then `execv`s the existing NodeLauncher. It never calls `sbatch`. Run it
inside the real allocated CPU job through the current isolated layer entry:

```
PY -I -B ENTRY workflows.expansion.uff3_alpha_runtime_v1.prepare_pipeline --phase pilot --config ACTUAL_CONFIG --upstream-job SOURCE_JOB --upstream-tag SOURCE_TAG --entry ACTUAL_ENTRY --tag PILOT_TAG
PY -I -B ENTRY workflows.expansion.uff3_alpha_runtime_v1.prepare_pipeline --phase qa --config ACTUAL_CONFIG --upstream-job PILOT_JOB --upstream-tag PILOT_TAG --entry ACTUAL_ENTRY --tag QA_TAG
PY -I -B ENTRY workflows.expansion.uff3_alpha_runtime_v1.prepare_pipeline --phase full --config ACTUAL_CONFIG --upstream-job QA_JOB --upstream-tag QA_TAG --generation-job PILOT_JOB --generation-tag PILOT_TAG --entry ACTUAL_ENTRY --tag FULL_TAG
PY -I -B ENTRY workflows.expansion.uff3_alpha_runtime_v1.prepare_pipeline --phase qa-full --config ACTUAL_CONFIG --upstream-job FULL_JOB --upstream-tag FULL_TAG --entry ACTUAL_ENTRY --tag FULL_QA_TAG
PY -I -B ENTRY workflows.expansion.uff3_alpha_runtime_v1.prepare_pipeline --phase finalize --config ACTUAL_CONFIG --upstream-job FULL_QA_JOB --upstream-tag FULL_QA_TAG --generation-job FULL_JOB --generation-tag FULL_TAG --entry ACTUAL_ENTRY --tag FINAL_TAG
```

All job arguments are actually assigned IDs, never proposed IDs. The helper
reads `node_epochs/<tag>_job<ID>/plan.json` and `startup.json`, checks their exact
binding/UID/endpoint, then locates `source_manifest.json`, a unique
`receipt_job<ID>_*.json`, or QA `result.json` in that actual plan's output.
Native parent and batch/steps accounting must be terminal C0. The existing
prepare/followup/completion functions preserve 189, budget, masks, source and
same-pilot scope semantics. New metadata goes in
`node_epochs/<tag>_inputs_job_<CURRENT_ID>/`; it does not touch upstream outputs.

Pilot config may additionally list
`closed_allocation_sources: [{scope: "exact", job_id: "ACTUAL_ID", tag: "ACTUAL_TAG"}]`.
Only when the pilot allocation starts are these real allocations queried and
merged into existing `closed_allocations` by actual plan pin. No not-yet-running
job is labeled C0. Later phases inherit the pilot census and add their actual
closed inputs. Existing actual201 exclusion bindings are preserved; its active
SQLite is never opened. Space collection remains metadata-only.

`accounting_command_prefix` defaults to `["sacct"]`, executed without a shell.
If native compute-node Slurm accounting needs an already configured explicit
command prefix, supply that real prefix; unavailable/wrong accounting refuses
continuation. The helper has no fallback that invents terminal status.
Optional `--python`, `--base-root`, `--launcher`, `--control-root` and
`--gluster-rpc-program` select actual deployment tools; defaults match the
existing Alpha continuation launcher. The default Python is the existing
`software/pubchem_completion_20261103_venv/bin/python` alias. Actual immutable
pipeline source must be present in deployment `code_references`; use a new
source layer containing this helper and its test. No old layer is mutated.

Small source fixture: `python -m unittest workflows.expansion.uff3_alpha_runtime_v1.test_pipeline -v`.
## Taskbook1% continuation stop and full-QA reference catalogs

The taskbook final stop list explicitly requires stopping and reporting the user
when any field's anomalous mask ratio exceeds1%. Earlier report-only wording
was an implementation interpretation, not a user override. `quality_gate` reads
actual `all_stream_field_counts` and uses original NEW canonical-record counts:
`100 * newly_masked_records > canonical_records`. Exactly1% automatically
continues. SourceNA, component fraction and robust-z review do not supply the
numerator. Full preparation and native entry both enforce the gate, as do final
closure preparation, native entry and producer. An exception lists actual field,
counts and fraction. QA may finish C0 after preserving the entire report; no
records are deleted and no Root approval artifact or cost threshold is added.
Old inline QA including219 is checked from its actual counts despite the old
report-only metadata wording; historical producer files remain untouched.

New full QA writes `family_file_references.jsonl` and
`batch_manifest_references.jsonl`. Small `result.json` contains
`all_family_file_references_catalog` and
`closed_batch_manifest_references_catalog`, each with schema/kind/path/rows/bytes/
wholeSHA. It omits the old inline keys rather than writing empty placeholder
arrays. Each newline row preserves the complete original ref, including all
additional family metadata. Pilot continues to emit its original small inline
lists; consumers reject ambiguous inline+catalog representations.

Catalogs are literal own regular single-link files directly in the private QA
root. Writer/reader verify sameFD and path frames; reader verifies bounded
newline rows, duplicates, declared row/byte count, wholeSHA and actual EOF.
The finalizer exhausts both catalogs and performs exactly the original family
set comparison. Normal private QA/finalizer accounting remains active; no
wide generic scientific metadata reader or duplicate scientific body scan is
introduced. Source fixture: `python -m unittest workflows.expansion.uff3_alpha_runtime_v1.test_quality_metadata -v` (two targeted tests).