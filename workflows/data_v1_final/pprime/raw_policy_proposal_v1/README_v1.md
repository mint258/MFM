# Stable P-prime raw retention proposal — execution authority remains separate

Root accepted this minimal rule as the implementation basis on 2026-10-25.
It changes only future output retention. It does not change registered prepared/config bytes, any scientific
input, WP5 task, keyword, perturbation seed, result or numerical tolerance.
There is no execution adapter or submission path in this proposal directory;
the independently versioned `../retention_v1/` adapter still requires Root's
actual pinned request, ordinary resource admission and separate QM authority.

The future full audit sample is a stable hash threshold, approximately 1% in
each source_shard_id x size_stratum. It is not an exact-size stratified draw and does
not claim the original WP5 audit sample identity. Fixed constants are seed
20261010, modulus10000, basis_points100. Compute canonical UTF-8 JSON of

['pprime-full-raw-audit-v1',20261010,source_shard_id,size_stratum,
     'uff_sprime',molecule_id,physical_conformer_identity]

with sorted keys, separators(',',':'), ensure_ascii=False, allow_nan=False.
`source_shard_id` is the original eleven-LMDB source_plan shard identity.
It differs from the original row's `file_group` (observed example6 versus5).
Keep `legacy_engine_file_group` separately and use that unchanged value only
in the old engine's membership guard. Never overwrite either frozen source.
Interpret the complete SHA256 digest as an unsigned integer; select iff modulo
10000 <100. No Python hash(), final population size/rank, pilot/full ordinal,
canonical ID renaming, source file path or native trace participates.

For accepted original S-prime use
`{"namespace":"accepted_original_sprime","source_conformer_id":<original integer sprime_conf_idx>}`.
For a real fill geometry use an explicitly frozen identity map with
`{"namespace":"data_v1_fill","seed":<int>,"candidate_id":<int>,"task_key":<64hex>}`.
The code cannot invent that map from a native anchor or a parquet row ordinal.
Any N1 supplementary namespace needs its separate scientific/interface review;
the proposal selector currently rejects it. Sampling metadata is not permission
to create or accept N1 geometry.

The new pilot retention manifest takes the union of the original frozen20 IDs
and stable-rule hits among its 2000 inputs. Keep every selected record's full12
raw outputs. Original20-only records are extra reproduction retention, so they
need not become members of the future full audit sample. All ordinary failed
call raw is retained irrespective of sampling. Original source_audit and new
policy/sample/union manifests are independently pinned and never overwritten.

Suggested new manifest schema (real values required, no placeholders accepted
by a future production adapter):

    schema: PPRIME_STABLE_RAW_RETENTION_EXECUTION_BINDING_V1
    status: PREPARED_NOT_QM_EXECUTED
    audit_policy: {path,bytes,sha256}
    root_policy_decision: {path,bytes,sha256}
    original_prepared: {path,bytes,sha256}
    original_audit_membership: {path,bytes,sha256}
    original_audit_selected20: {path,bytes,sha256}
    physical_identity_mapping: {path,bytes,sha256}
    source_audit: {path,bytes,sha256}
    stable_full_hits: {path,bytes,sha256}
    pilot_retention_union: {path,bytes,sha256}
    engine_record_audit_membership: {path,bytes,sha256}
    scientific_input_or_numerics_changed: false

Rows in source_audit preserve record_id, geometry_source, molecule_id, original
physical identity, source_shard_id, legacy_engine_file_group, size_stratum, hash/bucket, stable selected flag,
original20 flag and full12-retention flag. Report universe/hit count and actual
fraction per stratum; no exact1% or whole-population claim from a 2000 pilot.

Future run closure must verify raw bundles after durable write/readback and
publish an all12-raw proof per stable-hit record: all12 task names, execution IDs,
input bundle SHA, output member SHA, archive/container pin, source_audit and
policy pins. Missing full12 raw blocks pilot import under this policy; it never
silently reruns QM. Formal import can reuse scientific failure outcomes with
their actual masks/statuses, never replace them with old P labels or zeros.

Root must approve the policy and actual physical-identity mapping before a
separate versioned execution adapter is implemented or used. The original
pilot runner and its frozen20 audit are unchanged by this proposal.
