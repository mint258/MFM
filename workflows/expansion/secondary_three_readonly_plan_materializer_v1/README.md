# Three fixed Alpha metadata plans

This helper prepares only the already installed Pprime print-interval diagnosis,
the six-CSV newline diagnosis, and the six-CSV physical identity profile. It uses
stdlib and the existing stdlib base queue helpers on the Alpha login node. It
does not run fixtures, import scientific workers, open/hash/parse scientific
data, query/submit Slurm, create a startup proof, register output caps, or approve
a Root review. All scientific source files and both queues retain their frozen
bytes. The CSV full protocol is deliberately absent.

The source author has not run Python, AST, tests, SSH, Slurm, or this helper.
Root must install/review these four new source files before using it.

## Fast path

Alpha root is `/gfshome/alpha/codex_data_v1_20261026`; use its existing Python:
`/gfshome/alpha/codex_data_v1_20261026/chemprop_compatible_v2/bin/python`.
Set `PYTHONPATH=/gfshome/alpha/codex_data_v1_20261026/code` and
`PYTHONDONTWRITEBYTECODE=1` in Root's existing Alpha metadata session. The helper
requires UID 1264, login hostname `sonmi`, no `SLURM_JOB_ID`, and its exact
deployed module location. These are metadata invocations, not compute jobs.

Root writes an actual `request.json` under Alpha `control/`, following
`request_schema.json`. Use `task=pprime_print_intervals` first, then
`csv_newline`, then `csv_profile`, with a separate new control leaf, science
output leaf and startup proof path for each. A draft contains no approved plan:

```sh
/gfshome/alpha/codex_data_v1_20261026/chemprop_compatible_v2/bin/python -B -m secondary_three_readonly_plan_materializer_v1.materialize draft --request /gfshome/alpha/codex_data_v1_20261026/control/readonly_plan_requests/print_intervals_v1/request.json --output /gfshome/alpha/codex_data_v1_20261026/control/readonly_specs/native72_print_intervals_v1
```

Review `plan_fields.json`, `root_review.template.json`,
`transfer_requirements.json` and `draft_receipt.json`. Root independently creates
`root_review.json` by preserving the template's exact scope, fields and source
list, setting `status=APPROVED_FOR_EXACT_STAGE` and `reviewer=root` only after
actually reviewing it. The generator never makes this edit. Root may add notes.

```sh
/gfshome/alpha/codex_data_v1_20261026/chemprop_compatible_v2/bin/python -B -m secondary_three_readonly_plan_materializer_v1.materialize finalize --draft /gfshome/alpha/codex_data_v1_20261026/control/readonly_specs/native72_print_intervals_v1/draft_receipt.json --root-review /gfshome/alpha/codex_data_v1_20261026/control/readonly_specs/native72_print_intervals_v1/root_review.json
```

Finalize rederives the draft from unchanged actual metadata and source pins,
consumes the actual Root review hash, writes a new `plan.json`, and calls the
fixed queue's metadata-only adapter. Only a successful adapter check produces
`materialization_receipt.json`. It does not submit. If final adapter validation
fails, the new plan can remain alongside stderr, without an accepted receipt;
do not call it accepted or overwrite it. Inspect the failure and create a new
draft leaf after any required independent correction. Old artifacts stay.

Root can then use the already frozen queue controller: v15 for either short
diagnosis, v12 for the identity profile, with the actual generated plan and the
existing source review/authority/storage admission workflow. The helper does
not create that review, current free-space evidence, cap reservation, held job,
runtime proof, or accounting. `scope7` plus current registered caps and 200 GB
effective free space must still be checked at real admission. Parent terminal
accounting is historical evidence, never a fresh runtime proof.

## Actual request inputs

Required fields are `schema=THREE_FIXED_READONLY_PLAN_REQUEST_V1`,
`status=REQUESTED_FOR_ROOT_REVIEW`, `requested_by=root`, `endpoint=218.192.171.238:22`,
`uid=1264`, one of the three task names, a currently selected allowed CPU node,
`wall_seconds`, new `output_directory`, new `startup_proof_path`, and the actual
four-file `generator_source_references`. Supply pure actual `{path,bytes,sha256}`
triples; never fill a future or zero hash. The Root request is a request for a
draft, not permission manufactured by this helper.

Two actual producer references are mandatory for all three requests:

1. `source_installation_reference`: Alpha
   `control/secondary_cpu_queue/pending_sb4_sb3_actual_source_installation_20261027_v1.json`,
   32130 bytes, SHA256
   `fe599157df150a192058d2f2b486a1748f3aca78ea927d9c5db9711217f2cf82`.
   It records the actual 71 source installations. The helper validates only the
   selected known namespace members, not unrelated SB3 sources or data.
2. `identity_profile_receipt_reference`: Alpha
   `artifacts/coconut_identity_norm_profile_v1/v1/receipt.json`, 39563 bytes,
   SHA256 `4271a20cf3e3b14e845ef9dde0bb2405c6c4450b13c9cbcfba9c81731607340e`.
   This is actual coconut identity B job **1884785**, not PubChem B. Its producer
   pins supply the original Python, resource/cost authorities, exact four B
   source files and five original identity sources, original kernel references,
   base queue source pins, plan/proof and ancestor metadata. Its actual 20000
   physical row sample and three earlier fixtures are evidence, not a new PASS.

Also supply `identity_profile_accounting_reference`: Alpha
`control/secondary_cpu_queue/coconut_identity_norm_profile_v1/accounting_1793025248397025902.json`,
1681 bytes, SHA256
`33978dfc416050136d0ab54aeae13b24745b76f5739721fbe1f2314763644e02`.
The helper checks its producer-pinned raw sacct and actual COMPLETED/0:0,
UID1264, CPU16, node and `ElapsedRaw*16`. It observes 3552 allocated core seconds;
this is not the full data-line cost ledger.

For `csv_newline` or `csv_profile`, additionally supply
`format_accounting_reference`: Alpha
`control/secondary_cpu_queue/moleculenet_missing11_identity_format_probe_v1/accounting_1793034078162218988.json`,
1706 bytes, SHA256
`27da67e13dc9eb4c26ca952317655d5adb779a67ab097223a99233bbd09796f6`.
Actual job1884792 C0 accounting/raw is 1216 allocated core seconds. Other 792
producer references come directly from the installed byte-identical
`secondary_moleculenet_csv6_identity_v1/format792_authority.json`: original
receipt, plan, proof, eight-fixture result, source fixture and six report pins.
The original six payload references remain data locators and are not accessed.

For Pprime, native72 contract and v15 constants supply the exact actual1884773
CLOSED72 small summary, plan/proof/review/C0 accounting/raw (240 core seconds),
original evaluation and native report locators, original configuration and
frozen precision/invariant helpers. No new arbitrary parent path is accepted
for this authority. v15's actual metadata adapter rechecks CLOSED72 and the
unchanged original 15 failures before accepting the final plan.

The Root current scope7 file is
`control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json`.
Its actual bytes/SHA are read as small metadata, not fabricated. Resource/cost
authority references are inherited from B's actual plan and verified unchanged.
The old B scope3 observation is not reused as current storage admission.

| task | fixed queue | wall | output cap | pilot/performance | body refs |
|---|---|---|---|---|---|
| `pprime_print_intervals` | v15 | exactly600s |32MiB|false/false|2 existing JSON reports|
| `csv_newline` | v15 | exactly1800s |64MiB|false/false|6 original payloads|
| `csv_profile` | v12 | Root selects whole minutes, <=14400s |2GiB|true/true|6 original payloads|

All three are analysis, CPU16, scheduler-default unspecified memory, no
exclusive/GPU. Exact scientific parameters are imported only from their
stdlib contract modules; no scientific workers or tests are imported. For the
CSV profile, original `frozen_identity_source_references` are copied unchanged
from B's actual plan, rather than inferred from filenames. Full8argv includes
the future plan **path** and new proof **path**; no future file hash, actual job
ID, proof, profile result, actual cost, or PASS is invented.

`transfer_requirements.json` is an explicit locator inventory, not proof that
data were copied or verified. It uses existing Alpha source and parent paths
unchanged and lists data separately. After independent admission, the CPU job
still must run its original fixtures before bodies: 11 for print intervals, 11
for newline, and 7 for CSV profile. Original full body SHA/fstat, CRC/EOF and
scientific checks stay in those consumers.

Pprime's original15FAIL/HOLD and causal UNKNOWN remain. CSV physical rows,
blank rows, invalid rows, duplicate/zero IDs and no-key rows are not effective
molecule counts or exclusions. These plans cannot release full Pprime/2000 QM,
CSV full, decontamination, pool, or training. Allocation cost overrun remains
REPORT_AND_CONTINUE with original scientific thresholds unchanged. Actual new
stage terminal cost remains pending until Root captures it.
