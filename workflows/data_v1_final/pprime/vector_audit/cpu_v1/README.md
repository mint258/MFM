# Read-only vector input preparation on a real CPU-partition allocation

This isolated variant changes CPU guards, cooperative checkpoints and execution
provenance only. Original `prepare_v1.py`, `common.py`, math/geometry sources,
audit config, pilot config and prepared pairs remain immutable. It renders the
same36..72 input conditions from at most4 molecules selected from the original
closed1000-molecule/2000-UFF pool. It executes no QM, embedding or optimizer and
makes no vector/tensor reference-frame acceptance claim.

The new metadata config binds actual canonical Root source refs, including the
4012B prepared manifest from job4520345 and its exact three output refs. Its
large pair body is read/hashed only by the allocated preparation process. The
original audit config remains byte-identical (2GiB scientific output cap); the
central vector_prepare_1000 scope remains16CPU32GiB/1h,8GiB declaration plus32MiB
monitor reserve. The original5400s field is not used to launch a QM task here.

CPU2/8-19 is validated by the central runtime, actual hostname/partition, exact
scope, allocation, memory evidence and heartbeat. No hostname mocking or guard
bypass. Checkpoint iterators check before next() and render workers check before
new cases. Initial16 render workers rendezvous once; actual native thread IDs
are saved in each case and the manifest, not inferred from max_workers alone.
The central monitor supplies STOP; no signal, kill, automatic retry or Slurm
submission is implemented by this entry.

Source `shard_id` and legacy engine `file_group` are different identities. The
original source record is preserved. New explicit columns retain shard_id as-is,
record an unavailable status when missing and never fall back to file_group.

## Root-only validation and execution

No check, test or scientific execution was performed by the author. Root first
runs repository static checks and this stdlib-only source proof on sonmi:

    "$PY" -B "$REPO/workflows/data_v1_final/pprime/vector_audit/cpu_v1/verify_source_delta_v1.py" \
      --output "$RUN/control/vector_cpu_source_delta_v1.json"

The proof forward-reconstructs declared edits, reverses the entire file to the
exact original SHA, and compares load_audit/choose_pairs/make_cases/render ASTs
removing only declared checkpoints, the render barrier and actual thread-ID
metadata. No scientific function is imported or executed by that proof.

Run only the three new boundary cases in a valid central CPU allocation:

    "$PY" -B "$REPO/workflows/data_v1_final/pprime/vector_audit/cpu_v1/test_cpu_boundary_v1.py" \
      --root-preflight "$INTENT" --output "$RUN/control/vector_cpu_boundaries_v1.json"

Actual CPU entry (run through central launch, no direct/login execution):

    "$PY" -B "$REPO/workflows/data_v1_final/pprime/vector_audit/cpu_v1/prepare_cpu_v1.py" \
      --cpu-runconfig "$REPO/configs/data_v1/pprime/vector_prepare_cpu_v1.json" \
      --config "$REPO/configs/data_v1/pprime/vector_frame_audit_root_v1.json" \
      --pilot-config "$REPO/configs/data_v1/pprime/pilot_v1.json" \
      --prepared-pprime "$RUN/artifacts/pprime/prepared_v1" \
      --prepared-pprime-sha256 3fd2feb6adf9bc125c81fb8be07f97bdbe5737d7bb09f4690da115a8468dcfca \
      --root-preflight "$INTENT" --output "$RUN/artifacts/vector_frame_audit/prepared_cpu_v1"

Root central prepare_request can bind all seven new files as extra small source
refs, retain every original vector32G base source and central policy/runtime pins,
and use the exact scope vector_prepare_1000. The three prepared output refs are
inherited from the small closed manifest; adding them to request.data_references
is useful provenance but must not send their bodies into login source hashing.
Use new intent/output paths; never overwrite an earlier attempt. New fixtures and
actual input preparation may be sequential stages of one32GiB allocation if Root
uses a separately pinned, explicit driver and checks STOP between stages.

## Exact stage list

- workflows/data_v1_final/pprime/vector_audit/cpu_v1/prepare_cpu_v1.py
- workflows/data_v1_final/pprime/vector_audit/cpu_v1/runtime_control.py
- workflows/data_v1_final/pprime/vector_audit/cpu_v1/edits_v1.json
- workflows/data_v1_final/pprime/vector_audit/cpu_v1/verify_source_delta_v1.py
- workflows/data_v1_final/pprime/vector_audit/cpu_v1/test_cpu_boundary_v1.py
- workflows/data_v1_final/pprime/vector_audit/cpu_v1/README.md
- configs/data_v1/pprime/vector_prepare_cpu_v1.json

Do not stage unrelated old/untracked files. No formal Pprime scope/hardware or
legacy raw-retention policy is changed. Root must review actual parent, monitor,
source read closure, input hashes, case count and16 distinct thread IDs before
any later separate64GiB QM audit request. The original8 synthetic numeric tests
and other15-file Pprime fixtures are not rerun by these three incremental cases.
