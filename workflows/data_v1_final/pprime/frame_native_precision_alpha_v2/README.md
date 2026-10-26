# Alpha retained-native72 readonly port v2

The registered Alpha v1 job 1884771 failed at its 2 MiB report-size check after
14 seconds (224 allocated core-seconds). Its physical DB observation exists;
the missing final report means this delivery does not assert that its 72 cases
closed. Keep that failed run and cost. This independent v2 changes the technical
full-report cap to **33,554,432 bytes (32 MiB)**. The only `SCOPE` value changed
from v1 is `maximum_report_bytes`; all scientific criteria remain byte-identical.
Whole-output reservation remains 64 MiB and wall remains 3600 seconds.

v2 adds `report_metadata.py`. On successful report write and exact byte/SHA
readback, `diagnosis_summary.json` (at most 262,144 bytes) records actual serialized
bytes, full-report reference/SHA, actual four-fixture result/counts, 72 closure,
case-error count with a shortened list, all 15 original retained failures,
classification totals/by field, per-failure key judgments, original tolerances,
and explicit diagnostic-only print hypothesis. The full report remains plain
JSON and is never truncated to satisfy a capacity check. Publication failure
returns 4 and attempts `report_write_failure.json`, preserving actual serialized
length (or explicit unknown if serialization itself failed), intended digest,
successful-readback reference only when really obtained, partial-file stat,
main errors, fixture state, and actual closure. If filesystem failure prevents
that receipt too, bounded failure metadata is printed to the captured job log.
The 64 MiB whole-output check reserves space for both small receipts.

The original 460 inventory rows and **all their Alpha target locators** remain
unchanged, including the six mapped byte-copy targets in the registered v1 code
directory. v2 additionally carries its own byte-identical six local helpers;
pin both sets when they have distinct paths. `origin_inventory.json` itself is
byte-identical to v1. The new Root map points its `origin_inventory_reference`
to the v2 inventory triple, while all 460 entries stay the same. `relocation.py`
is also byte-identical to v1 and already loads inventory relative to its actual
own source directory. No data file or old registered source is edited.

This namespace reads the existing Main job 4521124 retained outputs on the
independent Alpha endpoint `218.192.171.238:22`, UID 1264. It creates no QM or UFF
calls and grants no pilot, production, 2000-case, or full-population release.
The original 72 cases, 15 `VECTOR_NOT_COVARIANT` failures, tolerances, labels,
parser conversions, and diagnostic-only nearest-decimal-print hypothesis remain
unchanged. C0 means all 72 readonly inputs closed; it cannot revise their gates.
Main job 4521293 and its registered v2 seven source files are untouched.

## Exact input inventory

`origin_inventory.json` is the literal Main-origin to Alpha-target locator list.
It was made with existing small frozen manifests and SSHFS file stat only; no
SQLite, LMDB, result, or program-input scientific body was opened to prepare it.
The stat observation is explicitly not a Linux inode/device identity claim.
Its 460 entries total **18,909,196 bytes**:

| Kind | Files | Bytes |
| --- | ---: | ---: |
| Byte-identical scientific/test helpers | 6 | 34,828 |
| Main native-v2 provenance | 3 | 49,171 |
| Frozen numerical/input-renderer source | 12 | 221,115 |
| Original small metadata | 7 | 876,754 |
| Raw SQLite locators | 72 | 9,973,760 |
| Frozen case-result JSON | 72 | 7,139,066 |
| Actual postcall program inputs | 144 | 307,251 |
| Original prepared program inputs | 144 | 307,251 |

The raw files are exactly
`runs/data_v1_20261025/artifacts/vector_frame_audit/cpu_auto_memory_20261026_v1/run/case-000/all_output_raw.sqlite`
through `case-071/all_output_raw.sqlite`, relative to the Main project. The same
case folders contain the pinned `result.json` and `actual_postcall_inputs` files.
Prepared inputs are under `artifacts/vector_frame_audit/prepared_cpu_v4/inputs`.
The inventory gives every full path, size, historical SHA when one really exists,
and target locator. It does not need `cases.json`, LMDB, a registry, binaries,
population data, or any QM initialization dependency.

The six byte copies are `precision.py`, `tokens.py`, `raw_reader.py`, `test_v2.py`
from Main native-v2 and `math_v1.py`, `read_outputs_v1.py` from the frozen vector
audit. Do not rewrite original JSON paths or edit any of those copied bytes.
The remaining frozen sources and metadata keep their original bytes in
`Alpha/inputs/native72_v1/main/<Main-project-relative-path>`.

## Explicit transitive archive authority

The Main native72 authority has no original whole-database SHA. Therefore the
plan uses `data_references: []`, exactly as the Main registered stage does, and
`archive_locator_authority_reference == relocation_map_reference`. Its fixed
scope has `exact_database_files: 72`, `exact_case_result_files: 72`,
`exact_input_files: 288`, and
`hash_basis: FROZEN_PER_CALL_SHA_AND_INPUT_METADATA`.
This is a single fixed derived authority, not permission to read arbitrary
undeclared files. The Root-pinned map and inventory fix the complete set.

Root creates a small, separately pinned map after literal byte copies, schema
`NATIVE72_READONLY_RELOCATION_MAP_V1`:

```
{
  "schema": "NATIVE72_READONLY_RELOCATION_MAP_V1",
  "origin_inventory_reference": {"path": "<actual Alpha inventory>", "bytes": "<actual>", "sha256": "<actual>"},
  "entries": [
    {
      "kind": "<verbatim inventory kind>",
      "origin": "<verbatim inventory origin object>",
      "origin_stat": "<verbatim inventory origin_stat object>",
      "target_reference": "<see rules below>"
    }
  ]
}
```

All 460 origins, kinds, stats, and target paths must match the inventory exactly,
with no aliases, symlinks, duplicate or missing rows. When the original already
has a SHA, `target_reference` is `{path,bytes,sha256}` with that same historical
SHA. When it does not (72 DBs and 288 input stat locators), the target is exactly
`{path,bytes}`. Do not insert invented or preobserved SHA fields into those rows.
For inputs, the actual original SHA is supplied transitively by the pinned case
JSON and verified by the unchanged bounded-input read after the four tests pass.
For SQLite, the original raw-call/frame/member SHA/size chain is verified by the
unchanged bounded readonly reader, including gzip EOF/CRC and member readback.

After four real tests PASS, the actual Alpha allocation separately hashes its 72
physical DB files and writes `actual_alpha_database_observation.json` with its
actual Alpha job/node/UID. These are new Alpha observations. The report explicitly
leaves Main's historical whole-DB SHA unknown. It never relabels an Alpha digest
as a historical Main digest. No Main login-node DB hash is needed.

## Root plan and fresh proof interface

Install this directory as
`/gfshome/alpha/codex_data_v1_20261026/code/frame_native_precision_alpha_v2`.
Use the existing pinned base `secondary_cpu_queue_v1` eight helpers and the new
Root thin readonly queue v4 known protocol. No queue framework is added here.
The exact primary module argv is:

```
[AlphaPy, "-B", "-m", "frame_native_precision_alpha_v2.run",
 "--plan", ABS_PLAN, "--startup-proof", ABS_PROOF]
```

`PYTHONPATH` includes `Alpha/code`; `AlphaPy` is the actual selected Alpha Python.
The plan schema is `SECONDARY_NATIVE72_READONLY_PLAN_V2`; fresh proof schema is
`SECONDARY_NATIVE72_READONLY_STARTUP_V2`. Both producer/scope keys equal
`pprime_native_precision72_readonly_alpha_v2`; stage is
`PPRIME_NATIVE72_EXISTING_OUTPUT_DIAGNOSIS`. Copy the literal `run.SCOPE` object
into `scope_parameters` without editing it.

Use actual endpoint/UID 1264, a Root-authorized Alpha CPU node, `cpus:16`,
`pilot:false`, `memory_policy:SLURM_DEFAULT_UNSPECIFIED`, `wall_seconds:3600`,
`output_cap_bytes:67108864`, and no explicit memory or exclusive/GPU request.
The 3600-second request is a wall limit, not a runtime forecast.
The remaining plan fields are `python`, `run_root`, `node`, `execution_argv`,
`startup_proof_path`, `output_directory` (a new Alpha artifacts leaf),
`root_review_reference`, `resource_authority_reference`, `source_references`,
`parent_evidence_references`, `relocation_map_reference`,
`archive_locator_authority_reference`, `data_references:[]`, and `inputs`.
`inputs` has the original unmodified Main triples keyed `evaluation`,
`run_closed`, `config`, and `pilot_config`; the resolver locates their actual
Alpha copies through the approved map.

The exact Root review schema remains
`EXACT_SECONDARY_BOUNDED_READONLY_ROOT_REVIEW_V1`, status
`APPROVED_FOR_EXACT_STAGE`, reviewer `root`. Its scope/identity/resource/argv,
source set, parent evidence and empty data set match the plan. The map and its
authority field, output/input locators, and all plan bytes are also bound by the
Root-pinned plan reference and the fresh proof's `plan_reference`.

`source_references` includes every local `.py/.json/.md` file, the small relocation
map, all 28 mapped source/provenance/small-metadata rows, actual Alpha authority,
and approved base/v3 helper sources. Every entry is a real small triple. Include
the actual Root controller/source/storage/parent reviews as required by v4.
Do not put the 72 case-result bodies or 288 program-input bodies in the startup
source-verification set: those are fixed transitive inputs read after four PASS.
Do not fabricate future hashes, jobs, proof identities, or Main paths on Alpha.

Startup checks the actual `__main__` file, Python, complete CLI, Slurm CPU16/node,
UID 1264, boot/process/cgroup identity, fresh Root controller proof and storage,
literal approved sources, actual script, and 3600-second allocation. It consumes
the Root proof; it cannot issue one. The common fresh storage observation must
reserve the entire output cap plus other registered caps and leave 200 GB.
Main UID1278, endpoint, preflight, or proof cannot satisfy this runtime.

## Preserved science and bounded execution

Four original fixture methods run inside the allocation before any raw DB hash,
SQLite read, or retained program-input read. Their actual receipt records all
four successes or complete failures/errors; failure submits no retained reads.
There is no extra fixture matrix. `scientific_source_equivalence` also compares
the copied scientific driver function ASTs against frozen Main-v2 during the
actual job. The sole `read_case` AST difference permitted is wrapping its raw
container locator with the explicit resolver. This source check cannot invoke
QM and is not a substitute for the four fixtures or the 72 real readbacks.

`relocation.py` builds new isolated namespaces from the exact hash-verified
function ASTs of the original parsers, pure input renderer, archive unbundle,
and measurement functions. It skips only original absolute-path/import bootstrap
and lifecycle code; it does not import an old module and monkeypatch its paths.
The parser's own original selective AUX/sparse-sigma hook wiring is retained,
as in Main-v2. `initialize_worker`, program launch, registry, and QM binary checks
are never called. Exact parser field selection, unit factors, binary64 bitwise
checks, original rendered bytes, actual input geometries, R/t/noisy-geometry
comparability, and exact Fraction propagation are unchanged.

There are at most 16 spawned read/parser workers and library threads are 1.
The original max raw/result/input/atom caps apply. The copied reader streams gzip
with a `max_raw+1` bound before allocation can exceed that bound. Each active
worker may copy at most one original bounded raw body to node-local `/tmp`, so
the maximum concurrent output-body copies are 16 times 16 MiB. This 256 MiB
node-local bound is separate from the durable 64 MiB whole-output reservation.
RSS 8 GiB soft cap, MemAvailable 4 GiB floor, and 600-second wall reserve STOP
new reads and let running reads finish naturally; no forced signals are sent.
The final report is exclusively written, capped at 32 MiB without truncation or
fake PASS. Actual physical-DB observation is capped at 256 KiB. Root still closes
terminal accounting, including failed allocations and cleanup; no self-reported
process time is substituted for allocated CPU cost.

This is source-only delivery: no Python, AST, tests, raw body, SSH, Slurm, or Git
execution was performed by this child. Real four-test/72-input evidence remains
the responsibility of the actual Alpha allocation and Root acceptance.
