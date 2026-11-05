# Original full502 technical UNKNOWN evidence audit

Source-only diagnostic; Root deploys and submits through the existing Alpha
`node_launcher --plan --startup-proof` route. No molecular package is imported.
No retries, screening, recovery, minCID merge, fixed1M selection, or filtering is
performed. All original UNKNOWN decisions and the old baseline remain historical.

Run entry:

```text
<private-python> -B -m workflows.expansion.pubchem_alpha_technical_unknown_audit_v1.run --plan <actual-plan.json> --startup-proof <actual-startup-proof.json>
```

Plan schema `PUBCHEM_ALPHA_TECHNICAL_UNKNOWN_AUDIT_PLAN_V1`, scope key
`pubchem_alpha_technical_unknown_audit_v1`. Use the current shared Alpha profile
and native Gluster quota authority, UID1264 / endpoint218.192.171.238:22, 16 CPU
workers on an actually admitted idle CPU node. A software process-tree budget
24GiB and node reserve24GiB suffice as a starting recommendation; these are not
Slurm memory reservations. Use Root's current report aggregate cap/future budget
and fresh quota snapshot, not stale resource values from the old bulk plan.
Recommended fresh private output below the existing `reports` scope, within its
shared5GB allowance. Root controls actual admission and resources.

Resource fields are the existing shared API fields: `workers`, `endpoint`, `uid`,
`runtime_profile_reference`, `quota_authority`, `quota_snapshot`,
`output_directory`, `output_scope_root`, `output_cap_bytes`,
`other_future_reserved_bytes`, `minimum_free_bytes`, `software_rss_budget_bytes`,
`minimum_node_available_bytes`, and current native-quota startup bindings as
required by the deployed runtime. `execution_argv` must be exactly the actual
entry above with the final plan/proof paths. No arbitrary wall/retry limit.

Additional exact reference triples (derive actual bytes/SHA natively):

| Plan field | Actual source locator |
|---|---|
| `original_handoff_plan_reference` | `A/control/pubchem_expansion_runtime_20261103/bulk_plan.json` (the actual1885148 source plan, not497c584 resource revision) |
| `full502_projection_manifest_reference` | `/gfshome/alpha/pubchem_expansion_20261103/bulk/original502/projection_manifest.json` |
| `full502_actual_parent_reference` | `A/control/pubchem_expansion_runtime_20261103/typed_full502_actual_parent.json` |
| `full502_producer_receipt_reference` | `/gfshome/alpha/pubchem_expansion_20261103/bulk/original502/parent_1885148_14717.json` |
| `original_typed_kernel_reference` | `A/code/secondary_pubchem_screening_alpha_v1/kernel.py` |

Here `A=/gfshome/alpha/codex_data_v1_20261026`. Plan construction is metadata
only: hash these five small files with `alpha_runtime_v1.common.reference`, merge
the actual Root resource fields, and set the exact execution argv. The original
source plan embeds the complete502 input fragments and coverage/frozen/science
pins. They are read and checked by the audit, never copied into a fictitious
Main namespace. Startup `source_references` must pin all new package `.py` files,
the deployed shared runtime, and `pubchem_closed500_bulk_v2/schema.py`; original
kernel/science refs may also be included and are independently verified.

The original schema preserves `category`, int64 `ordinal`, `cid_source_ascii`,
whole `source_smiles` and its SHA, `source_part_reference_json`, technical codes,
legacy reasons, independent parse/X flags, full dispatcher JSON, and
`error_evidence_json` with stage/type/message/traceback. Typed rows do not retain
raw TSV byte offsets; output explicitly records null, without journal replay.
Every observation has the exact original Parquet reference, zero-based physical
row/group/row-in-group, CID/ordinal, and unchanged source field strings.

Every source category column is read, with exact three-way count conservation.
Only row groups with UNKNOWN rows have the evidence columns read; all46,201
observations are retained in private DATA JSONL. Per-fragment technical code
frequencies must equal the already closed original projection receipts. Those
receipts currently record42,502 PARSE_FAILED and3,699 dispatcher exceptions
(the latter also carry dispatcher-result-unavailable). These are original
aggregate categories, not a claim that3,699 share one exception or are repairable.

Recorded traceback frames, types, exact messages, technical codes, legacy
reasons, and independent X flags are counted. An official
`Scaffolds/MurckoScaffold.py:MakeScaffoldGeneric` frame, RemoveHs call text, and
AtomValenceException jointly receive a diagnostic candidate flag. Names or
message fragments alone cannot set it; no P5 cause or recoverability is inferred.
One meaningful standard-library fixture exercises that evidence boundary.

Historical full-body SHA was verified by actual1885148C0 and all502 closed
receipts. This audit hashes those small receipts but does not freshly rehash93GB
of original typed bodies. It records and compares current before/after full
file frames including device/inode/ctime on the actual node. It makes no
historical inode or cross-node same-device claim. If fresh whole-body SHA is
desired later, it requires a separately declared read; this receipt never claims
that work has occurred.

Full completion requires502 fragment receipts,124,857,440 conserved category
rows, and46,201 observed UNKNOWNs; partial output is never a complete audit.
Receipt status is `COMPLETE_DIAGNOSTIC_UNKNOWN_UNCHANGED`. Actual parent C0 remains
for Root to read back. No scientific acceptance or pool/sample version is emitted.
