# Alpha source replica closure and independent V3 adapters

The first entrypoint is byte-only and can run while COCONUT scope remains held:
`workflows.expansion.alpha_all11_index_v3.replicas --plan PATH --startup-proof PATH`.
It does not read a future all11 source manifest or create an index/filter. It
validates every whole file in the already published all10 inventory and its
authority delta, including the four exact old Alpha candidates. It emits the
existing `PUBCHEM_PARENT_TRANSPORT_MANIFEST_V1` only **after** every selected
replica passes native same-FD EOF SHA/size/UID/link/path checks. Original Main
references, proofs and origin UID1278 remain Main; actual replicas use Alpha1264.

Use the existing node launcher, module `workflows.expansion.alpha_all11_index_v3.replicas`.
Plan keys, in addition to the current Alpha resource/profile/Guard fields:

```text
schema = ALPHA_ALL10_SOURCE_REPLICA_PLAN_V1
scope_key = alpha_all10_source_replica_v1
inventory_reference = actual Alpha machine pin of unchanged Main inventory v1
authority_delta_reference = actual Alpha machine pin of authority delta v1
replica_root = /gfshome/alpha/codex_data_v1_20261026/inputs/decontamination_main_origin_20261103
replica_layout = SHA256_OBJECT_PLUS_ORIGINAL_FILENAME_V1
replica_bindings = optional explicit [{source_reference,replica_reference}, ...]
```

The base inventory is Main
`runs/data_v1_20261025/control/pubchem_alpha_return_20261103/noncoconut_all10_transfer_inventory_poolagent_20261103_v1.json`
(996332B); the delta is
`noncoconut_all10_authority_delta_poolagent_20261103_v1.json` (4102B).
Use machine pins of their actual uploaded Alpha replicas; embedded Main origin
paths are preserved. The delta binds the original inventory bytes/SHA.

For the four old body candidates and the old frozen screen source, the inventory
supplies an explicit exact Alpha path. If there is more than one candidate, Root
must select it explicitly. Other files use the **explicitly declared** content
addressed layout `<replica_root>/objects/<SHA256>/<original_filename>`; the base
inventory's proposed path must match it exactly. There is no directory search,
path-prefix replacement, target symlink or basename-only identity inference.

The plan's `code_references` and actual launcher request must include all Python
files in this new package and the imported cached735 `support.py`, plus the actual
current runtime source files. Use16 CPU workers and the current approved memory,
quota, future reservation and free-space values. The code has no invented resource
default or arbitrary time limit. All input bytes already staged count as actual
quota usage; Root maintains concurrent future reservations.

Two native synthetic fixtures run before real source-body verification: explicit
Main-to-Alpha resolution with EOF hashing/tamper rejection, and rejection of
symlinks or undeclared origins. They can also run as the standard unittest entry
`NEW_ENTRY workflows.expansion.alpha_all11_index_v3.test_reader -v`.

Private outputs: `source_tests.json`, `whole_source_replica_verification.json`,
`parent_transport_manifest.json`, and producer `receipt.json`. The transport
manifest can be consumed by existing portable-source callers; extra provenance
fields do not change its schema. The independent strict Reader requires this
closed manifest for index consumers. Its separate `ReplicaVerifier` bootstraps
unverified Root-selected binding requests for this byte-verification producer;
it never fabricates a closed transport manifest before verification.

The result states all10 **input byte replicas** closed, scientific-source adoption
false, all11 false, COCONUT scope unchanged, no source approval inferred, and no
index/filter created. Actual parent C0 still requires Root's ordinary accounting
readback. Original Main/Alpha files and earlier failed verification attempts remain
unchanged.

## Future full-source adapters: no current scope adoption

The independent source-only follow-up adds three node-launcher-compatible modules,
all taking `--plan PATH --startup-proof PATH` and the same actual Alpha runtime
and Guard fields. None is run by installing this source.

| Module suffix | Plan schema | Scope key | Purpose |
| --- | --- | --- | --- |
| `validate` | `ALPHA_ALL11_SOURCE_FIXTURE_PLAN_V1` | `alpha_all11_source_fixture_v1` | Four native synthetic fixtures only; no real DATA or approval |
| `manifest` | `ALPHA_ALL11_SOURCE_MANIFEST_PLAN_V3` | `alpha_all11_manifest_v3` | Portable source-manifest composition after real prior coverage/scope decisions |
| `run` | `ALPHA_ALL11_EXCLUSION_INDEX_PLAN_V3` | `alpha_all11_index_v3` | Full physical all11 source-index production after those decisions |

Manifest/index plans require a real closed `parent_transport_manifest` and explicit
`data_references` triples for **every** file read (including nested authority,
parent accounting/raw sacct, original plan/proof/request, source raw/strict5,
ledger, audit, user-reply and coverage references). The strict reader rejects an
undeclared ref or a Main-origin ref without an exact registered replica. It
hashes JSONL while parsing to EOF and verifies current file type/UID/link count,
every ancestor, FD identity and before/after stamps. There is no transparent Main
path fallback. Original metadata dictionaries are not rewritten to Alpha.

Both source plans bind `ready9_manifest_reference` and
`root_molnet21_acceptance_reference`. The manifest plan additionally needs the
future real `root_coconut735_acceptance_reference`; the index plan instead needs
its actual `source_manifest_reference` and explicit `sqlite_cache_bytes`. The
final manifest schema remains
`expansion_decontamination_sources_with_constraints_v3`, with original status
`ALL11_SOURCE_EVIDENCE_COMPOSED_PENDING_ACTUAL_INDEX_AND_FILTER`. No future
acceptance or complete manifest is supplied by this package while the question
is unanswered.

The manifest adapter retains the original `compose.__code__` object and uses a
new function namespace with one explicit portable `read_ref` I/O binding. It
does not monkeypatch the original module or alter its science/gates. Indexing
calls original `identity_keys`, `install_tables`, `insert_constraint`, `rules`
and `index_header` objects directly, pinned by their actual deployed source files.
Include these original V3/legacy/manifest source files and transitive imports in
the actual admitted code/source references, alongside this package and runtime.
No original Main quota helper or chemistry function is called.

The nine READY source field bindings must equal the full original READY9
manifest, including roles, subdatasets, version, identities, raw and coverage.
Their complete declared raw inputs are whole-SHA verified. The v1 exclusion
population stays all11236754 roles/embargo records and is never replaced by a
Common subset. MolNet preserves the actual Main1278 C0 proof, all806735 base rows,
six overlay rows, both positive bounds and all21 physical dispositions. Imported
Main parent identity remains Main; it is not the current Alpha producer identity.

The complete future COCONUT coverage must retain735 original physical rows on
one accepted ledger with hold0; this does **not** require735 finite graph keys.
Its existing Root V3 acceptance/impact gates remain. Additional coverage fields
bind actual `original735_receipt_reference`, `original735_DATA_reference` and
`original735_actual_accounting_reference`. The data source is the already closed
native1885146 chain. Each physical ledger row requires:

* `source_id=entries:<id>:<block>:<ordinal>`, `binding` with original table, block,
  ordinal and SQL row SHA, `original_identity_resolution=UNKNOWN_UNCHANGED`, and
  complete `evidence_references`.
* An explicit `new_exclusion_status`: `EXACT_COMPOSITION_COVERED` (bound
  `identity_source_ids` and matching `exact_compositions`, empty full keys),
  `CONSERVATIVE_LOWER_BOUND_COVERED` (bound `rule_ids`),
  `CANDIDATE_DOMAIN_DISJOINT_X02` (full `fixed_non_H_atom_observation`, including
  forbidden elements), or `APPROVED_SOURCE_SCOPE_DISPOSITION` (no invented keys
  or bounds; `not_a_chemical_exclusion_rule=true`).

The last branch additionally requires a real prior `source_scope_authority_reference`
with schema `ROOT_COCONUT_SOURCE_SCOPE_ACTUAL_APPROVAL_V1`, status
`ACTUAL_USER_APPROVAL_RECORDED`, reviewerRoot, `actual_user_reply_observed=true`,
an immutable `actual_user_reply_reference` (actual `role=user`, nonempty `text`),
the exact `approved_source_ids`, `original_records_retained=true`,
`original_graph_unknowns_retained=true`, and the actual complete735 structural
`audit_receipt_reference`/`audit_actual_accounting_reference`. It records Root's
existing review of an actual reply; it is not a new approval request. The current
pending proposal, assistant text or an absent reply cannot satisfy it. The full
audit and original735 source-ID/row-SHA sets must match. Thus a genuinely approved
future732 disposition can close that axis while retaining every original record;
this code neither assumes that reply nor forces the records to become graphs.

The fresh private SQLite index streams all source rows, preserves original
full/WP5/exact-composition equality and only independently accepted positive
source-bound constraints, checks role/row conservation and native integrity, then
closes without sidecars. Empty COCONUT constraint files are legal when its genuine
accepted ledger requires zero chemical bounds. The original V3 header retains
`constraint_source_datasets=['coconut','moleculenet']` as the allowed source-domain
contract; actual per-source rule counts are reported separately. Source-scope
dispositions cannot be inserted as identities or chemical rules. Partial indexes
remain private on failure; no COMPLETE receipt is written.

Output receipt schema is the unchanged
`expansion_exclusion_index_with_constraints_v3`; a successful stage still requires
Root's independent actual parent C0 review before the existing Alpha filter can
consume it. This adapter does not create that Root acceptance, invoke a candidate
filter, generate a queue or publish a pool.
