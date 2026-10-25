# Existing downstream sources: TRAIN-only model-side projection

2026-10-25. Read-only audit; no target values, downstream result files, or
old scores were loaded for this review. The tested Python source at
464b96eff38a7b73b2dab5b7fd68bfd7b1146e58 remains unchanged. This is a proposed
adaptation, not evidence that a real nine-task panel has run.

## Scope correction

Stage 4 uses existing downstream sources. The new pretraining label line
D1–D6 is not a dependency for this panel. Requiring an unprovided new data-line
sidecar was unnecessarily restrictive: model code can produce its own bounded
projection from existing authoritative membership and source receipts.

`workflows/phase1_downstream/stage60_downstream_binding_v3/downstream_binding_data.py`
has a material distinction:

- `raw_binding`, lines 71–82: stream opaque bytes through SHA256; no target
  numeric conversion, annotation parser, model inference or score calculation.
- `FrozenDownstreamStore.__init__`, lines 216–268: verify manifest/file/input
  versions, decode index/contracts, and validate role/task metadata. It does
  not call `get` and does not unpack binary target tensors.
- `get`, lines 278–308: open one native frame; the actual target numeric
  unpack is line 301. Calls to this method must remain limited to the fixed
  TRAIN/inner-validation population.

Therefore a whole-file version checksum is not use of final-target values for
model decisions. Future integrity reporting must distinguish opaque byte
hashing, metadata inspection, selected TRAIN target decoding and downstream
evaluation. No historical full-evaluation CLI is needed for this task.

## Physically observed closed inputs

All paths below are under `/share/home/zixiao/descriptor_analysis` and their
live Windows equivalents are under `X:\`.

| Input | Observed source binding and scope |
| --- | --- |
| `docs/phase1/evidence/stage43_downstream_membership/run_4511949/summary.json` | SHA256 `9bac2f11eeae2d411e1eb4ca45d85330aff37970c1c67f399cd63782c2745bfd`; `complete=true`, status `COMPLETE_TARGET_FREE_MEMBERSHIP_EXPORT`, `target_values_decoded=false`, 150,770 original records |
| Same directory, `membership_manifest.json` | 23,930 bytes; SHA256 `b778eac757e06774d829031780bae8ca595dd9550f4484f4382902896a7c98fa`; binds original role/structure sources and geometry receipts |
| Same directory, `members.jsonl` | 172,436,698 bytes; SHA256 `f2810f60abc21a4a397ba38ff86aefc71cdfbe9fdbfe3afccf27f78e8d4c56d5`; native UID/index, fold/official role, source frame, geometry reference, and `label_masks=NOT_MATERIALIZED` |
| `docs/phase1/evidence/stage60_geometry_cpu_launch_v1/run_4512067/geometry_inventory.json` | 73,869,137 bytes; SHA256 `a92fd4da3d99757a0ed6f95f996116892ad224f68ff4b201ace5b33ed3ce0cf5`; physical prefix confirms `complete=true`, `target_fields_decoded=false` and the same membership-summary SHA |
| `docs/phase1/evidence/stage60_actual_all_som_geometry_audit_v1/all_2112_geometry_bindings.json` | Existing receipt reference: 847,252 bytes, SHA256 `d4c52da0100d02697f7db1b332cdead7931d0f2d997573477053ec14657689a4`; remeasure/validate before actual use |

The membership export's native counts are QM9 133,885, CYP 2,003 and
ExpansionRx official TRAIN 5,326 / official held-out 2,282. Only original
fold-0 TRAIN and fold-1 inner-validation metadata are projected for scaffold
data; ExpansionRx uses official TRAIN alone before its frozen group split.
The unrelated QM7/AZ populations and their labels are not panel inputs.

QM9/CYP full chemical identity comes from the original `members.jsonl` rows.
ExpansionRx TRAIN is a special case: the old membership exporter deliberately
wrote `inchikey=null` for this population, rather than recomputing training
structure identity (`export_ordered_membership.py`, lines 292–299). A UID
fallback is still invalid. The existing closed Expansion geometry inventory
already supplies the required full key: `prepare_expansion_geometry.py` lines
132–143 derive `full_inchikey` from the native raw structure, bind it to
`member_row_sha256` and `raw_frame_sha256`, and lines 189–193 carry it unchanged
into every geometry-inventory record. The model-side projector can consume
that existing identity after its exact source/member join; it needs no new
chemistry calculation or label definition.

## Native packed-store closure

No complete `store_manifest.json` has yet been located in the three known
historical native-store launch output directories. In particular,
`stage60_native_store_cpu_launch_v3/run_4512072` physically has `FAILED.json`
and a 110,048,762-byte partial `records.bin`, with no record index/contracts/
complete manifest. Its failure receipt is `FAILED_CLOSED`, AttributeError,
185.29 seconds. It cannot be used as a closed store or promoted by reading
the partial payload. This is a statement about the located outputs, not an
exhaustive claim about every server directory.

If a separately closed store is found, the minimal metadata projection is:

1. Bind its actual manifest, index and contracts and check their original
   seals/closure. Opaque whole-file raw hashes are permitted version checks.
2. Select only the three panel datasets and one fixed original contract per
   dataset. Validate source role/UID associations before any `get` call.
3. Copy exactly the native frame offset/size/SHA/shape/task/geometry fields;
   do not copy row provenance text, target values, masks or normalizers.
4. Join each selected native row to its original membership row using source
   member index, UID and `original_member_row_sha256`; derive full groups
   from the bound original membership or closed Expansion geometry inventory.
5. Publish a fresh external TRAIN-only sidecar accepted by the existing
   `TrainOnlyPackedStore`. Nothing in the original source or split is changed.

`materialize_downstream_bindings.py` lines 511–519 create the native index
metadata including the original-member-row hash. Lines 639–640 remove the
internal `_targets`, `_candidate` and `_supervision` fields before publishing
that index. Projection does not need to reconstruct or decode these arrays.

## Fallback if no complete native store exists

Use a new, separate model-line tool and a fresh output directory. Do not
rerun the historical all-role materializer and do not change the tested H0
bridge or data-line files.

First create a metadata-only plan from the closed original membership and
geometry inventories. Bind native fields/units from the unchanged frozen
protocol, fill Expansion full groups through its existing geometry receipt,
apply the frozen chemical-group overlap rule and 8,192/2,048 caps, and persist
the final membership and hash. Default outer roles are unavailable. Every
target-producing callable must check the selected native UID/index allowlist
before invoking a numeric or annotation decoder.

Then materialize only that preselected TRAIN population:

- QM9: original fold-assignment CSV join and native XYZ geometry. Reuse the
  existing `_joined_member` structural proof and `observed_scalar` numeric
  recipe; call numeric conversion only after the native allowlist check.
  Scanning/framing the source CSV as opaque field bytes is distinct from
  decoding target numbers for excluded members.
- ExpansionRx: only its official TRAIN file; use the already closed native
  geometry/identity entry and exact raw-frame/source-member hash. Reuse the
  same original numeric recipe, units and native task order.
- CYP: source file bytes/structure may be indexed without annotation
  decoding (`SourceRecordStore.__init__`/`get` are target opaque). Only the
  allowlisted source record reaches the frozen `som_payload` / PRIMARY_SOM
  decoder and original atom mapping. Use existing saved native coordinates;
  do not regenerate geometry or infer unknown labels.

The original numeric and SoM bridge sources are
`stage60_downstream_binding_v3/materialize_downstream_bindings.py`, lines
181–200 and 275–343; the graph structural join is
`stage44_missing_masks/graph_field_masks.py`, lines 80–124. Bind their actual
file hashes and required source implementations. Malformed labels remain a
typed failure, unknown labels keep the original NaN/mask rules, and unavailable
geometry remains explicit. Failed partial output is retained and rejected.

Publish a new manifest stating **complete for the explicitly selected native
TRAIN population**. Bind its newly generated packed-frame index and the old
source/role/geometry receipts. Do not claim a historical full 150,770-record
FrozenDownstreamStore or original packed-frame hashes when those never closed.
A final metadata projection of this new, closed TRAIN materialization can use
the existing selective reader; source-kind/closure claims must explicitly
distinguish this route from projection of a historical complete packed store.

The next real panel can use the now physically verified B3 checkpoint and a
matching 384-dimensional random reference as descriptive sanity evidence. Its
runtime and nine-task scores must still be measured; historical B3 evidence
does not replace the required 512-dimensional candidate comparison.
