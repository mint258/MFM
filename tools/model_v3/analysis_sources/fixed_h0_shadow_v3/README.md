# Fixed-H0 CPU shadow operational revision3

This is an independent CPU metadata adapter for the already completed GPU capture
4521492. It does not produce or relabel that capture as revision3. The immutable
capture producer remains numeric_fixed_h0_shadow_v2_source/source_pins_v1.json.
The original v1/4521484 audit failure and successful v2 capture remain unchanged.

The original Root sacct invocation and complete raw stdout are retained exactly.
The station returns three rows: unique parent, named batch and named extern.
All six fields are checked. Parent must be zixiao/COMPLETED/0:0/16CPU; both named
steps must have empty User/COMPLETED/0:0/16CPU, nonnegative integer elapsed time
bounded by the parent. Missing, duplicate, unknown and mismatched rows are rejected.
No -X query, stdout filtering, validator monkeypatch or invented accounting is used.
The source-bound raw observation is fixed_h0_capture_4521492_actual_accounting_full_v1.json.

The new CPU manifest explicitly binds the original capture producer source manifest,
actual1492 COMPLETE/manifest/supervisor/accounting and the independent CPU source.
The expected supervised capture command still points to the original v2 script.
All original producer files/dependencies are retained in the runtime source inventory;
source before/after includes both versions. Original capture schemas and completed
CAPTURE_COMPLETE status are not rewritten. CPU result retains the v1 mathematical
schema and additionally records both source manifests and metadata preflight.

All code before main() in shadow_terminals_v1.py (including FP32/FP64 functional
math, decode, selfchecks, four-way decomposition and closure) is byte-identical to
revision2. shadow_common.py, execution_request_v1.json and protocol_v1.json are raw
identical. New cpu_metadata_v3.py performs only accounting parsing plus one synthetic
positive and15 synthetic negative controls within the same analysis job. These
controls do not claim any actual job succeeded. No extra QA/model capture is requested.

Resource rules remain CPU16, memory16GiB, RSS12GiB,4workers*4BLAS, wall120s,
whole output2GiB/private2GiB and input128MiB. The three-minute SB includes cleanup
reserve. Actual capture is48 cases/192encoder forwards with10 physics passes and38
failures; operational capture success does not make the numeric candidate accepted.
Fresh-H0 lineage remains distinct from the original1435 data. All48 cases/two seeds
and three transforms are analyzed without selection. No threshold, tensor, model,
initializer, backend or original science source changes.

Root must normal-check and publicly register this revision before CPU execution.
Use the new OLD/run_fixed_h0_shadow_CPU_v3.sbatch with actual CPU_BINDINGS_v3.json;
Root's existing CPU submit helper supplies the fresh expected-node/resource proof.
The bindings file is generated after the source manifest to avoid a self-hash cycle.
The previous prepare_fixed_h0_CPU_after_actual_C0_v1.py is not used because it expects
one accounting row and the same capture/CPU source version. No Python, model,
SSH, Slurm submission or tests were executed by this revision's author.
