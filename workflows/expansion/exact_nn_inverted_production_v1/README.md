# Native-equivalent inverted continuation — new source, no live patch

This thin package selects the independently compiled Alpha inverted backend.
It changes no original engine, popcount kernel, ranking, UFF or calibration code.
The old production spawn/barrier/bounded-batch/ready/fixed_result API is retained;
only the private reference backend and native proof consumer differ. Workers load
all1,196,122 records and report reference_records_loaded, not RDKit decode calls.
The ordinary score fields remain exactly the old fields, and searched groups are
removed from IPC just as in the old fixed_result. No approximate search, retries,
time limits or reference subset is introduced.

`authority.adopted` directly consumes the actual machine descriptor
`EXACT_INVERTED_NATIVE_EQUIVALENCE_V1`: Main4525827 result/raw parent C0 with
UID1278, Alpha213.0 result/raw STEP C0 with UID1264, old206, ref196 and filter209.
It accepts no new Root approval schema/status/reviewer. Main result bodies keep
original Main UID/paths while their small exact byte replicas are read on Alpha.
Alpha binary/build/ABI/Core5/oracle are loaded only from actual Alpha validation;
Main .so files are never executed on Alpha. Both native producers loaded full
reference in16 workers, tested10 cases and matched192 comparisons/all8 fields/F64
against old/historical206. These are scoped native facts, not full-query workload
representativeness or ETA. The captured parent213 remains RUNNING in the Alpha
step proof; it is not relabelled complete.

Use a new immutable entry layer and plan with:

```
compiled_backend_implementation = INTEGER_INVERTED_CSR_PRIVATE_COPY_PROTOTYPE_V1
backend_adoption_reference = ACTUAL_NATIVE_EQUIVALENCE_DESCRIPTOR_REF
resume_output_directory = ACTUAL_SAME_OLD_NN_DIRECTORY
resume_previous_allocations = [
  {runtime: {endpoint:218.192.171.238:22,uid:1264,job_id:ACTUAL_OLD_ID},
   plan_reference:ACTUAL_PLAN_REF,startup_proof_reference:ACTUAL_STARTUP_REF,
   accounting_reference:ACTUAL_TERMINAL_ACCOUNTING_REF}
]
```

Resume occurs only after actual relevant NN parents/batch/steps are terminal,
under original parent.lock. This writer-safety condition is separate from the
benchmark's step-C0 proof. Do not stop, edit or hotpatch active201/213/214 to run
this source. Root alone coordinates actual replacements and resource plans.

The original source_binding.json has six fields. `binding.establish` requires all
five non-backend fields identical (full filter/reference/assigned buckets/
partition/scope) and an explicit old206→new native-equivalent proof scoped to196/
209. It writes a NEW six-field source_binding_inverted_<digest>.json and separate
small lineage metadata. Original binding, journals, score/projection Parquet
bytes and original score checks are preserved. The current output manifest points
to the new binding, so aggregate's exact six-field equality remains unchanged.
No aggregate relaxation is added. A prior COMPLETE manifest with a different
backend proof is immutable and is explicitly refused rather than overwritten or
relabelled. This hook targets actual partial-shard continuation, not that case.

The only existing orchestrator change is an explicit backend/binding/source-pin
hook in alpha_sharded_novelty_v1/run.py. The old default path remains selected
when compiled_backend_implementation is absent/old. Query ordering/dedup, all
reference scoring, SQL/cache validation, projection and rank mathematics remain
unchanged. Both work partitions must finish with the same new proof before the
existing aggregate will accept them. Pending DAG metadata must use actual new
job IDs; old literal dependencies are not silently rewritten here.

Keep inverted Core5 and the original engine imported from actual
`A/code/inverted_alpha_validation_20261104` used to build the Alpha .so; extend
cached package __path__ with prior paths for workers/run modules absent from that
thin validation layer. Do not shadow Core5/oracle with a newly copied layer.
Native source/proof checks will reject mismatching absolute source bindings.
New production package and updated orchestrator sources must appear in native
startup source pins and actual plan code_references. Real current quota/RSS/
node admission is unchanged; resource caps are actual new plan choices, not the
sample's measured resident bytes copied into a fixed production cap.

Source fixtures: `python -m unittest workflows.expansion.exact_nn_inverted_production_v1.test_binding -v`
(two bounded metadata cases, no compile/SCI). Actual adopted() smoke on Alpha,
new immutable deployment and future production execution remain Root operations;
this source author has not deployed, submitted or touched running jobs.