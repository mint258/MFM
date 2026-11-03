# Provisional D3: local I/O inside the real GPU parent

Source-only draft. No Python, tests, AST, Slurm, GPU or science was executed by
the author. This does not deliver D3, local-performance evidence or Model ACK.

`run(plan_path, host_context_path, check_host_resources=existing_parent_guard)`
is an **I/O phase inside an already authorized GPU validation / actual D3
payload parent**, after its real GPU guard has admitted the actual node/UUID
and before its real model consumer. It does not submit a pure CPU job on a GPU
node, allocate another GPU, start training, or change Model modules. The same
Parent includes its actual copy bytes/scratch/RSS in the existing budget.
No separate review or tests are introduced.

There is no standalone or exec CLI. `main()` deliberately exits. The same
admitted GPU process must call `run(..., check_host_resources=its_live_guard)`;
the required callback is the existing actual guard, still holding its UUID
lock. `provisional_fast55k_adapter_v1.host_context.capture_and_readback` captures
PID/boot/ticks/full argv and immediately calls this function in process.
The original host proof/request are preserved. This source observes actual
scontrol/nvidia-smi and rejects old CPU proofs; it grants no new GPU authority.
CUDA visibility can be the actual UUID or the existing guard's explicitly
verified visibility-to-UUID mapping, never an inferred device zero.
Plan schema `PROVISIONAL_D3_GPU_HOST_LOCAL_IO_PLAN_V1`, with exact fields used
by this entry:

```
version: v1-pilot-provisional
D3_export_reference: actual {path,bytes,sha256} of the formal D3_export.json
local_root: fresh literal /tmp/... directory on the actual GPU node
copy_cap_bytes: actual finite file+metadata cap covered by the host scratch budget
owned_rss_soft_cap_bytes: the existing host's allowed whole owned-tree RSS budget
local_disk_reserve_bytes: existing host's explicit local-disk reserve
drain_reserve_seconds: existing host's wall drain reserve
source_references: exact new entry + every actual original Reader/codec/export
  dependency + actual GPU context-producing source (old sources unchanged)
```

The actual GPU host provides a small observational context with schema
`ACTUAL_MODEL_GPU_PARENT_IO_CONTEXT_V1`:

```
endpoint: 202.38.247.57:22
host_purpose: AUTHORIZED_GPU_VALIDATION_OR_ACTUAL_D3_PAYLOAD
io_plan_reference: exact actual plan pin
uid/job_id/node/pid/process_start_ticks/boot_id: actual current identity
observed_monotonic_seconds: actual same-node/process time at capture
host_remaining_wall_seconds: actual remaining allocation wall at capture
host_full_argv_sha256: SHA256(json.dumps(actual /proc/self/cmdline list,
  separators=(',', ':'), ensure_ascii=False).encode())
gpu_uuid/gpu_name: actual already admitted physical GPU
host_startup_proof_reference/host_request_reference: unchanged actual GPU originals
host_gpu_guard_already_admitted: true only after existing host admission
context_source_reference: actual pinned source that captured this context
```

The implemented capture function is `provisional_fast55k_adapter_v1.host_context.capture`;
its original GPU proof schema is not fabricated here. No future bytes/hash or
old CPU startup can substitute for it. Existing GPU UUID/lock, live process,
memory, quota and allocation checks continue in the host. Pass its existing
resource check callback to `run` in process; no exec/CLI handoff is supported.

The formal publisher already exists at
`control/publish_actual_fast55k_analysis_D2_D3_D4.py`. Only after the actual
Fast55k D4 and subsequent D3 have genuine complete receipts and C0 may it write
`configs/data_v1/v1-pilot-provisional/D3_export.json`, schema
`DATA_V1_PILOT_D3_FORMAL_EXPORT_DELIVERY_V1`. The entry joins that pointer to
its actual D3 receipt and real raw accounting. No finalCommon/D6/D7 or Model ACK
is required to run this I/O phase.

For each actual closed store it copies original `data.mdb`, `manifest.json`
and the permanent F64 sidecar, with bounded chunks, full EOF SHA, unchanged
source identity and a second local reopen SHA. Only origin-to-target locators
are new; no immutable manifest/schema/value/mask/sidecar is rewritten. The
filesystem is observed from actual mountinfo and must be a physical local
disk, not NFS/Gluster/tmpfs. It reopens with the original
`family_export_day_v1.store.Reader`, verifies schema/store counts, conserves
all55k distinct MIDs, then reuses **the exact existing**
`family_export_day_v1.verify.read_initializer/molecule_reader` with16 spawn
workers and the existing hash-based random whole-MID order. This is mechanical
compatibility: Fast55k's Reader inherits that same Reader and merely adds its
ordered/F64 convenience methods. The numerical decoder/validator is unchanged.

Output `ACTUAL_PROVISIONAL_D3_GPU_HOST_LOCAL_IO_RECEIPT_V1` reports actual
host GPU allocation/proof refs, original D3 pin, local inventory SHA/locators,
filesystem/capacity,16 real worker PID identities, handle closure and
molecules/s including process startup. Cache state is explicitly after copy,
full SHA and index reads; no OS-cache flush/cold-cache claim. Only one read
window is measured; no scientific performance acceptance threshold is added.

`Model_payload_ACK` always remains false. The actual model reader/hook must
subsequently load these same local payload bytes, preserve146 definitions,
r73 authoritative F64/once F32, source masks/reasons and target-local r674
LOSS_DISABLED, then emit its own actual execution receipt/ACK binding the exact
D3 and local inventory. This source does not implement or impersonate that
model consumer. The new provisional_fast55k_adapter_v1 hook provides the real typed-reader seam; its README records the precise training limits. Partial files/receipts remain on failure, with no cancellation,
signals, overwrites or automatic retry.
