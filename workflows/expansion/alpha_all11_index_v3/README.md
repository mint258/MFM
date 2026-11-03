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
