# Read-only vector preparation, central CPU runtime v2

This adds seven new files and leaves the frozen seven v1 files unchanged.
The new entry is a complete visible source file. It only changes its two imports:
the central runtime becomes runtime_v2 and local controls become runtime_control_v2.
The new control source additionally pins prepare_cpu_v2.py and requires metadata
runtime_path to name the imported central runtime_v2.py. The metadata adds only
that path. The scientific schema and historical V1 execution-variant labels stay
unchanged; cpu_runconfig and actual source references distinguish this variant.

No source data, scientific configuration, engine keywords, rotation, perturbation,
geometry adapter, rendering expression, sixteen-worker barrier, PID/TID output,
native source_shard_id or legacy_engine_file_group semantics change. The source
remains the closed parent 4520345 preparation: 1000 molecules, 2000 UFF records
and 20 audit records. Only two to four selected molecules produce 36 to 72
prepared input conditions. No QM call, embedding, optimization or label evaluation
is made. Source records remain intact, with no file_group-to-shard_id inference.

The exact finite scope is vector_prepare_1000, 16 CPU, 32 GiB, one hour.
The original scientific output cap stays 2147483648 bytes. The central scope cap
stays 8589934592 bytes plus 33554432 bytes for monitor evidence. Formal generation
and QM hardware requirements are unaffected.

Root must integrate all seven new files and preserve/pin all seven old files plus
the inherited base-request source references. prepare_request_v2.py automatically
pins central sources. It must not add the 19 MB pairs body to source_references;
the closed small prepared manifest binds its three exact data references, and
the actual entry verifies those bodies in the CPU allocation.

## Root validation commands

These are instructions only; this handoff did not run Python, SSH, Slurm or Git.
REPO and RUN below are canonical remote paths. INTENT is the new v2 request intent.

Pure stdlib source proof (no scientific imports or data-body reads):

~~~sh
"$PY" -B "$REPO/workflows/data_v1_final/pprime/vector_audit/cpu_v1/verify_source_delta_v2.py" \
  --output "$RUN/control/vector_cpu_source_delta_v2.json"
~~~

The proof checks all seven v1 SHA/byte pins, exact declared edits and inverse
recovery for entry/control/metadata/three-boundary entry, direct byte and AST
identity for the four scientific functions and three unchanged control functions,
unchanged three test methods, and metadata equality except runtime_path. It also
chains the frozen original-to-v1 proof. It imports only standard library proof
code and does not execute scientific functions.

Run the three incremental boundaries and actual preparation sequentially under
one launch_v2 allocation, with a v2 checkpoint between the stages:

~~~sh
"$PY" -B "$REPO/workflows/data_v1_final/pprime/vector_audit/cpu_v1/test_cpu_boundary_v2.py" \
  --root-preflight "$INTENT" \
  --output "$RUN/control/vector_cpu_boundaries_v2.json"

"$PY" -B "$REPO/workflows/data_v1_final/pprime/vector_audit/cpu_v1/prepare_cpu_v2.py" \
  --cpu-runconfig "$REPO/configs/data_v1/pprime/vector_prepare_cpu_v2.json" \
  --config "$REPO/configs/data_v1/pprime/vector_frame_audit_root_v1.json" \
  --pilot-config "$REPO/configs/data_v1/pprime/pilot_v1.json" \
  --prepared-pprime "$RUN/artifacts/pprime/prepared_v1" \
  --prepared-pprime-sha256 3fd2feb6adf9bc125c81fb8be07f97bdbe5737d7bb09f4690da115a8468dcfca \
  --root-preflight "$INTENT" \
  --output "$RUN/artifacts/vector_frame_audit/prepared_cpu_v2"
~~~

The three test bodies are unchanged; only their control/proof/runtime imports
switch to v2. Their historical V1 payload schema remains unchanged. They are not
the original numeric or P-prime suites. Actual prepared.json must contain sixteen
distinct render_worker_tid values, real allocation provenance and intact dual
source IDs. Input preparation is not coordinate-frame scientific acceptance.

Central runtime v2 uses node-local /tmp heartbeat, STOP and sample evidence with
the same 1 second monitoring, at most 5 second boot-monotonic freshness, own RSS
75 percent and node reservation envelope 85 percent. Work checkpoints precede
new reads/stages/cases/files/future results; already running work drains naturally.
The launcher exports complete SHA-bound evidence to durable storage after natural
child completion. Parent C0 requires successful durable export and accepted
monitor closure, as well as the boundary/preparation evidence. This handoff does
not claim those actual results or authorize formal generation.
