# Alpha labels512 independent reduction

This candidate ports the original payload reducer to a new Alpha allocation.
It does not run or accept Main startup authority. The successful scan parent is
Alpha job `1884788`; its predecessor `1884787` remains failed evidence. No frozen
Main or Alpha source is changed.

The primary is `code/payload_reduce_alpha_v1/run.py`; execute
`python -B -m payload_reduce_alpha_v1.run --plan PLAN --startup-proof PROOF` with
`PYTHONPATH=AlphaRoot/code:AlphaRoot/code/labels_payload512_frozen_v1`.
The Root controller supplies a newly reviewed plan/proof for:

- key `labels_payload512_reduce_readonly_alpha_v1`;
- plan `SECONDARY_LABEL_PAYLOAD512_REDUCE_READONLY_PLAN_V1`;
- proof `SECONDARY_LABEL_PAYLOAD512_REDUCE_READONLY_STARTUP_V1`;
- stage `LABEL_PAYLOAD512_EXISTING_VALUES_REDUCTION`;
- Alpha UID1264, an authorized Alpha CPU node, analysis/pilot=false,16CPU, no requested
  Slurm memory or exclusive allocation, wall at most3600seconds;
- output `AlphaRoot/artifacts/labels_payload512_readonly_v1/reduction_v1`;
- reduction output cap2GiB and separately reserved64MiB memory-observer evidence
  at the output path plus `_resource_observation`, with200GB quota reserve.

The scope literal is `guard.PARAMETERS`. The actual input-byte total is derived
from real parent receipts and is not an invented scope constant. All original
quality parameters and the original3861-byte scientific config remain unchanged.
The original config's4GiB reducer cap is retained as provenance; the new wrapper
additionally enforces the stricter2GiB output limit. The resource observer keeps
its existing4GiB MemAvailable soft floor and natural-drain behavior. A STOP before
reduction prevents starting it. Once the single reduction stage has started, it
finishes naturally and produces evidence; this entry never advances another job.

## Exact inputs and the metadata-only inventory

The original reducer consumes65 body files:16 details JSON,16 compact masks
(SHA-verified without interpreting their values),16 coverage Parquet,16 original
owner-index Parquet (only record_ordinal), and the11,231,854-byte role ledger.
Their exact references come from the16 actual group reports and the original
owner plan. No canonical SQLite,209 label Parquet, raw archive, or LMDB is opened.
The actual1884788 small reports and frozen281map declare exactly38,437,705 input
bytes:26,652,140 details;232,897 masks;71,642 coverage;249,172 owner indexes;
11,231,854 role ledger. These are inherited expected hashes and byte counts,
not a claim that this reducer allocation has already verified those bodies.
The16 source group-report JSON files total1,739,357bytes and remain small sources.
The14-by11,231,854 uint8 output coverage map uses157,245,956bytes. No median/MAD is
fitted: counts and review candidates already computed with the matched source
TRAIN pilot reference are merged.

`inputs.py` is also a pure-stdlib small-metadata builder. It does not read, stat,
or hash any65 body input. Its CLI is:

```
python -B -m payload_reduce_alpha_v1.inputs \
  --scan-manifest ACTUAL_ALPHA_MANIFEST_OR_EXACT_SMALL_COPY \
  --config ORIGINAL_SCIENTIFIC_CONFIG_COPY \
  --owner-plan ORIGINAL_OWNER_PLAN_COPY \
  --relocation-map EXISTING_281_MAP_OR_EXACT_SMALL_COPY \
  --report ACTUAL_GROUP_REPORT_OR_EXACT_SMALL_COPY ... \
  --output NEW_INPUT_INVENTORY
```

`--report` is repeated exactly16times. When executed on Main with byte-identical
copies, also provide `--scan-manifest-reference JSON_CONTAINING_ACTUAL_ALPHA_TRIPLE`
and `--relocation-map-reference JSON_CONTAINING_ACTUAL_ALPHA_TRIPLE`. Config,
owner-plan and report copies are checked against the expected references already
bound by the manifest/map. Copy observations remain explicit; an observed Main
copy is never presented as an Alpha runtime or body-verification result.

The inventory schema is
`ALPHA_LABEL_PAYLOAD512_REDUCTION_INPUT_INVENTORY_V1`, status
`EXPECTED_INPUTS_PENDING_THIS_ALLOCATION_SHA`. It includes original Alpha manifest,
config,owner-plan,map and16report references, entries65 with kind/group_index/
origin_reference/reference, kind_counts,body_files/body_bytes and small-copy
observations. No future body receipt has a hash.

## Plan and parent bindings

In addition to the standard secondary plan/review fields, provide:

- `config_reference`, `owner_plan_reference`, `input_inventory_reference`,
  `origin_inventory_reference`, `relocation_map_reference`;
- the existing three `fixture_auxiliary_{config,original,transform}_reference`
  fields, unchanged original54small files, all reused Alpha sources and all new
  reducer sources in source_references;
- `source_equivalence_reference` and a new `storage_reservation_reference`;
- `scan_manifest_reference`, `scan_plan_reference`,
  `scan_startup_proof_reference`, `scan_transfer_verification_reference`,
  `scan_fixture_gate_reference`, `parent_accounting_reference`,
  `parent_accounting_raw_reference` in parent_evidence_references and approved
  source_references; also include the original scan plan's root_review_reference;
- the16 group-report references as approved small sources;
- `data_references` equal to inventory.entries references in their exact order,
  and `data_total_bytes` equal to inventory.body_bytes;
- `transfer_verification_reference=null`, with
  `transfer_verification_expected_output_path=output_directory/input_verification.json`;
- `resource_evidence_output=output_directory+'_resource_observation'` and
  `resource_evidence_output_cap_bytes=67108864`.

The new Root review repeats the resource_evidence fields and data_total_bytes as
well as the standard exact scope/resource/argv/data/parent fields. The actual
accounting object uses the existing Alpha format: endpoint,uid,query_returncode,
actual_parent,raw_sacct_reference,allocated_core_seconds_observed. The raw pipe
table must contain exactly one1884788 parent matching the accounted C0 row.
There are no data body paths in source_references, so pre-fixture source checking
cannot accidentally hash the65 bodies. Every source pin is at most2MiB.

## Runtime order and unchanged science

The new fresh Alpha guard validates all small pins, parent identity and Root
review. The unchanged original six fixture methods then run strictly with no
skip/error/failure/unexpected result. Only after their PASS does this allocation
use the frozen16-thread streaming SHA/fstat worker to validate all65 bodies and
write `input_verification.json`. The original reducer's mathematical core then
conserves whole-owner membership, effective roles,14task slots,146enabled and
264registered component denominators. The original >1% new-mask or structural
failure rule still saves its report and exits2. NULL convergence,8791EA, unknown
native precision/units/frame remain governed by the original rules.

`verify_port.py` is a source-only proof entry for Root. It checks exact inverse
bytes and AST of the original core; the sole core edit replaces creation of the
output directory with its already-created Alpha handle. This lets the six tests
and input verification be saved before reduction without altering the math. It
also records exact reused kernel,coverage-helper and original fixture pins. No
test or scientific body is executed by that proof.

The original audit schema remains unchanged. `stage_closure.json` adds actual
Alpha job/proof/parent/input-verification provenance. Candidate masks remain
unfrozen; no label is edited, native program print precision and physical frame
remain unverified, and neither guide1.5 nor final common D4 is completed merely
by this read-only reduction. Scientific cost overrun remains REPORT_AND_CONTINUE;
scientific quality stops remain unchanged.
