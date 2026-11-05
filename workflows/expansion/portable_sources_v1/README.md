# Real endpoint/source transport for PubChem

These new adapters preserve original source bodies, recipes, parent manifests
and proofs. They do not modify the Main SDKs, create historical Main paths on
Alpha, substitute UID1278 for1264, or relabel old Alpha502 output as a new Main500
RAW reconstruction. No job submission exists here.

Alpha plans use pool's `runtime_profile_reference` (actual
`ALPHA_FREE_CPU_RUNTIME_PROFILE_V1`), `output_scope_root`,
`software_rss_budget_bytes`, fresh directory-quota authority and the same normal
stage/resource fields. Admission delegates to `alpha_runtime_v1.profile.admit`.
Launch through that package's absolute `entry.py` using Python-I/-B from the
exact clean code cwd. Alpha home contains `string.py`; do not delete it or start
project Python from home. No Slurm memory reservation is inferred from a
software allowance. Root chooses actual idle CPUs and submits all jobs.

`transport.bind_plan(plan)` opts only new consumers into the actual Alpha profile.
`transport.verify(ref)` then resolves imported references using optional
`plan.parent_transport_manifest`; original dictionaries and nested proofs remain
unchanged. Without an Alpha profile the old Main verifier is used. Standalone
`Transport(manifest_ref,endpoint,uid).verify(ref)` is available too.

Transport schema `PUBCHEM_PARENT_TRANSPORT_MANIFEST_V1` has status
`VERIFIED_REPLICAS_CLOSED`, `destination={endpoint,uid}` and `replicas` entries:
`origin_endpoint`, `origin_uid`, `source_reference` and `replica_reference`.
Both refs are path/bytes/SHA triples with identical bytes/SHA. The destination
replica must be an actual owned stable regular file; Alpha paths stay under
`/gfshome/alpha`. No implicit SSH/network read, basename match, prefix rewrite or
fake Main symlink is used. Same-FD SHA checks and inode/mtime/ctime guards protect
the bounded verification cache. Imported Main C0/UID1278 evidence remains
Main-origin evidence; the new stage separately records actual Alpha execution.

Original UFF source packaging (metadata-only on Main):

```
python -B -m workflows.expansion.portable_sources_v1.capsule prepare --output FRESH_BUNDLE
```

This copies the original recipe bytes (SHA cfd153fb...), frozen S-prime source,
original descriptor/selection/wire/family/quality modules and necessary runtime
Python sources. It reads no molecular DATA, fits no statistic and performs no
UFF/QM. Its status is PREPARED_SOURCE_BYTES_NOT_DESTINATION_DEPLOYMENT.

After Root actually transfers the bundle, finalize on Alpha using its isolated
clean entry (metadata operation, no Slurm/science claim):

```
...entry.py workflows.expansion.portable_sources_v1.capsule finalize \
  --bundle ACTUAL_BUNDLE_JSON --payload-root ACTUAL_PAYLOAD \
  --endpoint 218.192.171.238:22 --uid 1264 --output FRESH_CAPSULE_METADATA
```

Finalization hashes every real owned replica. `capsule.json` preserves actual
replicas and original refs separately. It explicitly says native portability
has not yet been validated. Root must run actual native fixtures in the private
Alpha environment before production; source packaging is not a native PASS.

`kernel.Capsule` loads those unchanged function objects in a fresh worker and
requires original Python3.11.14/RDKit2025.09.5. It never calls historical source
DATA loaders, embedding fallback, fill, QM or training. The original wire's
historical path constant remains unchanged in its source; imports resolve to
the verified actual replica package and its file paths are checked. D20 uses
the same original descriptor function objects; D3 uses existing NativeKernel
APIs and independent corrected_base binary64 seam checks. No universal
cross-machine coordinate-bit guarantee is claimed. Existing saved coordinates
remain immutable for future append operations.

UFF plans add `source_capsule_reference`. Their declared output_scope_root must
equal the generation output_directory so the durable inode ledger covers the
entire scope. Alpha's5-second Guard uses synchronized ledger callbacks, never a
walk over millions of per-MID files. NN/SQL scopes must be separate small
aggregate work trees; they may contain retained attempts and reference/coverage
stages, and must never include the generation per-MID tree.

Quality uses unchanged original task_components, masks, cross-field checks and
robust-z review objects. The fixed50000-TRAIN D4 reference is provisional and
review-only, not full true Common TRAIN calibration; no R/N fit is allowed.
Taskbook1.5 makes >1% label masking a user-report trigger, not automatic record
deletion or candidate-release stop. Physical/cross-field masks remain active;
z>20 remains review-only. Root's approved domain review is still required.
