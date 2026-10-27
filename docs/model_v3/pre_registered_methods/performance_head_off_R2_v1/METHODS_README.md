# A1 partial checkpoint-off: new9e16 native-S8M head-off gate

This is one explicitly manual **a03_head_off** experiment on the original node21/C35 RTX5090. It disables the denoising-head checkpoint while preserving distance and outer-backbone checkpoints. It is not all-off, automatic selection, A5 packing, R1 capacity qualification, an ABBA result, or adoption.

The immutable runtime remains MFM_model_v3_performance_integration_v1:
local9e16d4c5a15c558051499d3dc0c55c9bd3787734, public8147f44baa1ea1ecc3822af7affd0a95401ed248,
tree98b3b4bd8bc083a4150f536024e4dc81e6fb6108.
No runtime/old source, model architecture, parameter keys, loss, threshold, source fingerprint, API512 or existing job is changed. Only this fresh operations/protocol package is authored. Root reviews/syntax-checks, binds an exact public method/source receipt, admits resources/reservation, and alone submits.

## Genuine changed execution

The existing302-byte current/configs/model_v3/performance/a03_head_off.json has rawSHA
9e958e8fb4374211f80e2c8ed741266b93f701dbde15f2dd36cb862a9e10723e.
Its distance_checkpointing/backbone_checkpointing/head_checkpointing tuple is true/true/false.
All other options equal a00_control exactly: FP32, tiled distance65536, dense global attention, fusedAdam false, TF32 false, compile false, no packing.

This is not merely a renamed small config. In v3_performance.py:261–263, build_performance_model passes head_checkpointing into ConfigurableDenoisingHead.activation_checkpointing. Its forward:217 makes recompute false, and:230 runs the original _predict_chunk directly instead of checkpoint(...,use_reentrant=False). The present geometry_message_layers=0 means the message-loop checkpoint branch is empty; the prediction chunks are the active changed head path. Distance pair checkpoints and outer layer checkpoints remain enabled. Model math/state/initialization and all supervision remain the original definitions.

## Exact original reference and comparisons

The original paired_a_acceptance.py constructs two **fresh resident models on the same GPU**: original build_memory_bounded_model reference and build_performance_model candidate. It seeds each from0, checks equal complete initial state keys/tensors, and uses the same consumed native batch object. Historical3976 all-onR2 is only an immutable source/data/method anchor; its outputs, losses, gradients, weights or capacity values are not substituted for this run's reference.

The unchanged fixed20 loop, paired:140–170, compares every recursively exposed floating output tensor (mapping/dataclass/tuple/list, including empty tensors) and every named parameter gradient. Keys and shapes must match, tensors must be finite, None gradients match only None. For each tensor, compare_tensors casts only the **audit copies** to F64 and checks relativeL2=norm(candidate-reference)/max(norm(reference),1e-12).
Forward tolerance is1e-5; full-gradient tolerance is1e-4. Max absolute differences are recorded but do not replace this original rule. Loss is the unchanged compute_phase1_loss with supervisionS/original LossWeights/Phase1LossPolicy/Phase1JointSchedule; fixed-batch loss must be finite. There is no new per-fixed-batch loss tolerance or sampled-gradient shortcut.

After all20, the original code refuses a failed gate and preserves evidence. On pass it closes/resets the original input workers, checks the first full input receipt is identical after reset, then performs the original500 optimizer updates. Reference/candidate order alternates by update. Both use original AdamW configuration, finite loss/backward, clip_grad_norm1.0, finite norm and the original optimizer dispatch (fused false means original automatic dispatch, not a new explicit Torch fusedFalse flag). Every1..500 loss must be present exactly once and finite, with abs(candidate-reference)/max(abs(reference),1e-12)<=1e-3. These are the existing v3_performance_acceptance.py rules, unchanged.

Reference comparison/closure keys are:
- configuration: same code/public/model/optimizer/loss weights+policy/supervision/schedule, B1 and A4 rawrefs, actual source map, original snapshot, data_version/sampler/loader/views/seed/deterministic receipt; candidate options differ from historical all-on only in head_checkpointing.
- new fixed_batch_gate: batches20, every forward+gradient row pass under original tolerances.
- new trajectory_gate: updates500, all500 existing relative-loss rows pass.
- new summary: PAIRED_GATES_PASS, fixed_batch_pass/trajectory_pass/full_A_numeric_acceptance alltrue, matching configuration/options SHA and actual consumed records.
- new run_status and supervisor/actual Slurm parent: real terminal state/exit, no failure/cleanup error, descriptor/worker/SDK/private cleanup verified.
Full current2131 tested source refs and actual saved305 execution map remain checked through the existing metadata preflight/Root closure path. No new QA parent is introduced.

## Unchanged input and resource bounds

Existing native-S TRAIN11,104,772; original manifest and original shard snapshot are bound verbatim. Seed0,8workers,8M padded-cost target, original atom buckets, sampler rules, clean/geom/topo association, noise/reset/RNG controls and optimizer stream remain unchanged. The known original full run consumed201216 base records in500 updates; this is an expected same-stream cross-check, not prefilled evidence or permission to truncate/replace the new stream.

Root's actual counts4524574 C0 is referenced as planning evidence only: global maxN712,3views, largest singleton cost1520832,21 native records with singleton cost>500k. Its500k first500 prefix did not contain the maximum. The8M all-off static NoGo remains; the500k all-off proposal is not submitted or hidden in this experiment. No new count file, LMDB, labels, geometry, NPZ, weights or SDK body is read by this source author.

Each actual paired attempt retains16CPU/64GiB/7200s Slurm,6900s original supervisor, RSS60129542144 bytes(56GiB), whole persistent2147483648 and separate private2147483648 bytes, unchanged inherited child=outer-96MiB, and original actual GPU85% process-memory guard. Only paired_a_acceptance owns the shared UUID lock; no outer flock is added. Node21/C35 is fixed, with strict known-host/key SSH only in Root's existing admission flow. Fresh CPU/RAM85%/MemAvailable, NVML no-foreign/idle, shared-lock availability, account quota with original64GiB reserve rule, and an independent2GiB durable hold are required before submission. No prior resource frame, hold, UUID, R2/R1 capacity receipt or other process is borrowed/modified.

## Root invocation

Use the existing successful Root resource/reservation/sbatch flow; this package does not submit. Suggested fresh family is
N/performance_head_off_R2_v1 with child/ and supervisor.json plus control/.
Root must preserve all management/stdio/source/prelaunch bytes in the same whole2GiB accounting, including the SB log. Keep the Native phase and existing manual/auto/A00-R1 families untouched.

Mandatory worker environment is the original MODEL_V3_GPU_UUID,MODEL_V3_EXPECTED_NODE,MODEL_V3_OUT,MODEL_V3_RECORD,MODEL_V3_PACKAGE_PINS_SHA256 plus the actual Root ADMISSION/QUOTA/HOLD PATH+SHA pairs. It also requires MODEL_V3_METHOD_PUBLICATION_PATH and MODEL_V3_METHOD_PUBLICATION_SHA256: this is a real Root-verified exact source/protocol-publication receipt, never an unknown prefilled commit. The worker hashes that receipt; Root's pre-submit flow retains the semantic current-Git/publication/resource/hold authority. The runtime --prereg-sha stays the existing published8147 scientific-method identity; the new exact operations/protocol publication is recorded separately.

After actual admission and copying source-identical run_head_off_R2.sbatch to a fresh O script, Root uses the existing immediate submission route, binding node21 and the one admitted physical CUDA UUID through the original environment/--export=ALL. Do not invent new GRES/dispatcher policy; retain the actual existing Root submission flags. Do not call the hardcoded old auto/all-on Root drivers with this candidate. Exact child argv is already in the SB and handoff:

    PY5090 -u -B tools/model_v3/paired_a_acceptance.py \
      --candidate-options current/configs/model_v3/performance/a03_head_off.json \
      --performance-execution current/configs/model_v3/performance/a1_manual_capacity_observation_v1.json \
      --performance-execution-sha256 7cabbd4a0300d551154ffb9bcbed5466fc9886d0eb886a1ae37ee3e7f70db46e \
      --reference-config W/workflows/sprime_s/formal_s/B1_seed0_v2.json \
      --input native_s --seed 0 --workers 8 --max-padded-cost 8000000 \
      --expected-gpu 5090 --code-sha 9e16d4c5a15c558051499d3dc0c55c9bd3787734 \
      --prereg-sha 8147f44baa1ea1ecc3822af7affd0a95401ed248 \
      --shard-snapshot-sha256 d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f \
      --deterministic-controls --output ACTUAL_FRESH_CHILD

This preserves original fixed20+500 behavior: no smoke, export, resume, bucketing/padding change or new loader/monitor. Original failure states and diagnostics persist; no failed run is promoted by later metadata.

## Registered follow-up R1 timing, still pending

R1_registration_DRAFT.json fixes a distinct A03_head_off_R1_C35_9e16_v1 series with reference1,candidate2,candidate3,reference4,2warmup+20measured,8M/nativeS/seed0 and exact a03/manual bytes. The single_a_benchmark.py tool computes real resident_models=1 itself. All4 --candidate-options references name a03, while reference roles still build original all-on models. There is no automatic checkpoint choice and no R2 capacity borrow.

Before any follow-up, Root must bind the **new actual head-off** complete20/500 result and actual clean C0 closure. Then use the original R1 guarded submission/member-closure flow with only a03/expected boolean tuple, new family/series/package and this numeric-gate binding mechanically adapted. The frozen A00 R1 SB/driver are all-on-specific and must not run unchanged. This source registration intentionally contains null future gate refs/no future job/run IDs.

Four real completed single runs are compared with original a_speed_report.py. It requires matched candidate-option/code/C35/source/config/data/actual deterministic-control signatures, all4 measured input receipt digests equal, original order/windows/no foreign risk, complete real supervision/cleanup, and all20+500 rows from the **new** matched numeric gate. Integrated padding/workload/resolved-options/implementation signatures must match; numeric R2 residency does not grant R1 capacity. Normal SDK finish/original persistence are retained per member; full SDK verification and the original speed report may share one post-four CPU batch, with no extra per-member QA parent.

No speedup, all-off/auto qualification, A1 complete adoption, A5 acceptance, cross-GPU table, B precision or final-data authority is claimed by this package.
