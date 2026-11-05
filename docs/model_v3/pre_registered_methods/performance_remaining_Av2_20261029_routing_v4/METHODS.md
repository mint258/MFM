# Remaining six A-v2 cohorts: routing v2 with fresh C35 measurements

This is one finite parameter plan and one shared Slurm entry, not six packages. It is SOURCE_ONLY until Root completes its usual source inspection/checker, publishes the exact five method files (including Root_submit.py and source_pins.json), performs fresh resource/quota/independent-hold admission and explicitly submits one selector. No new result, profile, GPU allocation, speedup or adoption is asserted. No project Python, AST, Git, tests, models, SDK, NPZ or data payload were executed/read by this author.

Execution uses the unchanged tested A source: local 7ffe8a5557590b1481f4ca74073007f070dc6a50, public 2b4a4df8636e5d65915d535472ba01084ea72dab, tree 8f9530415034bdb885c1c765aee434797c70e7c7. Rule v2 is the actual public 4f6ba16973ea4a30472c7fb33d3aadec974a4462 and its exact document/publication refs in PLAN.json. The existing full115/2673P+3old skips closure and same-source current full graph are checked by the already used manual-A-v2 source_guard.validate_sources(), unchanged. Root's existing fixed Git checks and actual source qualification remain mandatory; no synthetic capacity proof is introduced.

| Old job | Original candidate JSON | Backbone / distance / head checkpoint | Routing-v2 target GPU / node |
|---|---|---|---|
| 4520486 | a00_control.json | true / true / true | C35 RTX5090 / compute-0-21 |
| 4520405 | a00_control.json | true / true / true | ec788ed1 RTX4090 / compute-0-20 |
| 4520456 | a01_backbone_off.json | false / true / true | ec788ed1 RTX4090 / compute-0-20 |
| 4520438 | a00_control.json | true / true / true | a967b766 RTX3090 / compute-0-0 |
| 4520411 | a00_control.json | true / true / true | NEW C35 RTX5090 / compute-0-21; historical22e unchanged |
| 4520549 | a03_head_off.json | true / true / false | NEW C35 RTX5090 / compute-0-21; historical22e unchanged |

The six science rows and original configuration/options/data identities are retained.
Routing v2 explicitly changes only the411/549 target physical UUID from historical
GPU-22e21021-e572-4562-fc51-cd8c83e74141 to same-model RTX5090
GPU-c35f2434-9137-9723-1af5-dc69b6295243 on compute-0-21. These are new
measurements, not qualification of22e or migration/restart of its Native job.
The other four physical targets are unchanged. Root selects one case per
invocation; there is no automatic queue, loop, retry or live-capacity claim.
Every executed v2 selector reruns its own complete20+500 and later fresh matched
R1. No old500 or historical cross-UUID timing is reused. Native22e and all other
jobs/locks/old attempts remain untouched.

All six original configurations have performance_execution absent. Therefore these six use NO --performance-execution flag, no manual observation opt-in, no auto profile, no packing and no residency relabelling. In particular486 is not3976 and549 is not4580. Reference PerformanceOptions.backbone_checkpointing=None retains the original model's activation_checkpointing=true. All six candidates use RuntimeDenseAttention, tiled distance MLP pair_rows65536, FP32 and TF32-off; use_radius_mask=false means global attention. Stored radius8 and sparse_query_chunk32 do not activate sparse/radius attention and do not qualify A4. Fused and compile are false; all original bias Parameters remain. The three historical export runs456/486/549 do not re-export a checkpoint here: export was a post-gate artifact and is not part of this new numerical gate.

Each submission independently executes the original fixed20 paired forward/backward, then ONLY after a passing fixed gate the original reset and500 updates. No old500 result is reused, no fixed-only/smoke/resume flag exists here, and failures retain the original return behavior. Native S /seed0 /P8000000 /8workers /original snapshot /6x512 /8heads /A4/noise/masks/member order/RNG/Adam/loss/clip/schedule remain as the original paired runner. Original metadata refs and current unchanged option raw bytes are recorded in PLAN.json; old v1 results are never relabelled.

The v2 check is each element abs(candidate-reference)<=1e-8+1e-4*abs(reference), with the six source-identified active analytic-zero bias gradients BOTH norm<=1e-8. General bothNone inactive heads remain legal, singleNone/shape/key/nonfinite mismatches fail, and active analytic-zero bothNone fails. Forward relativeL2<=1e-5 and every500-point loss relative difference<=1e-3 are unchanged. Model arithmetic stays FP32; validation's F64 host arithmetic is not a model mode.

Root submission, after the existing fresh admission

Root must bind exact new method publication, inspect strict knownhosts for the row's actual node, verify the exact UUID has no foreign compute context, maintain original GPU85% /all-user CPU and memory85% /MemAvailable /quota reserve64GiB and all existing reservations, and register a separate2GiB one-job hold using the existing registry_lock. This shared script only binds raw frame identity; it is NOT a new resource admission authority. Do not invoke it merely with invented JSON or hashes. Root_submit.py is mechanically based on the already used auto-A-v2 Root
resource/hold driver. It consumes exactly one PLAN selector and freezes the actual
node/UUID/type/interpreter from that row. It uses the original source-only
manual validate_sources(), never the auto capacity selector, and delegates the
reservation mutex only to the existing root_phase.registry_lock via the exact
source-bound helper used by Native. It does not add a lock framework.
Node21/20 use their pinned existing compute21/compute20 public known-host
projections. Node0 uses only the original /share/home/zixiao/.ssh/known_hosts and
requires its actual SHA at each attempt. All SSH is BatchMode and
StrictHostKeyChecking=yes; no keyscan, accept-new, trust edit or invented trust
source is permitted. Missing/untrusted hosts stop before sbatch.

Resources remain16CPU /64GiB /2h Slurm; unchanged run_supervised.py receives6900s /RSS56GiB /persistent2GiB /private2GiB. Root accounts child+control+supervisor/top files within the same one-job hold. Only paired_a_acceptance takes the public physical UUID lock; no outer fd9 or second holder is added. No resource override, dispatcher, daemon, loop, array, retry or environment repair is included. Persistent native offline W&B uses the original paired normal/exception finish; actual SDK audit/selective sync follow real terminal evidence. New exact fixed_batch_gate.json may be up to16MiB; other Root JSON/source limits remain2MiB, whole/private2GiB unchanged. Old4MiB files and consumers are not rewritten.

Root-only invocation after the usual checker and actual exact-tree/readback
publication of all five files:

```bash
"$ROOT_METADATA_PYTHON" -u -B \
 /share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/performance_remaining_Av2_20261029_routing_v4/Root_submit.py \
 4520411 \
 --method-publication "$ACTUAL_NEW_METHOD_RECEIPT" \
 --method-publication-sha256 "$ACTUAL_RECEIPT_SHA" \
 --source-pins-sha256 "$ACTUAL_NEW_SOURCE_PINS_SHA"
#4520549 is a separate explicit invocation after its own fresh admission.
#4520438 additionally requires --known-hosts-sha256 ACTUAL_EXISTING_PERSONAL_TRUST_SHA.
```

The driver alone obtains fresh scontrol/squeue/MemAvailable/NVML process/GPU
observations, quota and public-lock precheck; the original complete120-second
deadline includes observation latency. It requires16 actual free CPUs, preserves
the original all-user declared-memory85% plus MemAvailable reserve,64GiB quota
reserve in addition to ALL registered remaining holds, and the original selected
GPU process checks. It records a durable submission intent before exactly one
full sbatch argv including the selector. Unknown submission outcomes do not retry.
Resource failure leaves actual evidence/hold for Root to resolve; no automatic
release, cancellation or registry repair is added. The one-job2GiB hold has a new
case-specific reservation ID and family, with other reservations byte-preserved.

The child uses the unchanged original supervisor/paired runner and actual physical
UUID lock. No outer fd9 holder is added. All resource bounds remain16CPU/64GiB/
2h,6900s/RSS56GiB/whole2GiB/private2GiB and runtimeGPU85%. Child+control+supervisor
and top files remain within this family and Root's single reservation. Fresh
families are trials/recheck_OLDJOB_routing_v3, not the v1 paths. Partial output
refuses re-entry; a retry would need a separately declared protocol, not a loop.

Fresh paired R1 / ABBA after each actual new20+500 closure

No change to single_a_benchmark.py or a_speed_report.py is needed for these NO-integration cases. The latter reads the new v2 fixed-gate pass/results structure, requires all20 and all500 actual passes, and binds candidate-options/code/GPU/model/loss/reference/data/determinism. It does not independently establish rule-v2 publication, actual parent C0 or all raw-source authority; Root must supply the already closed v2 numeric gate, original source/SDK/C0 proofs and the current same-source R1 runs. R2 capacity is not borrowed as R1 capacity. Each R1 member has one actual model and its own runtime guard/22 updates.

For each chosen eligible case, use the same current W and original candidate-options
path in four NEW supervised members, reference1,candidate2,candidate3,reference4,
with one NEW case-specific series-id and the exact new numeric-gate GPU UUID.
The411 a00 and549 a03 option hashes differ; they therefore require two separate
four-member series. Neither historical22e timing nor reference members tagged
for another candidate-options hash can supply those new series. Keep original
2warmup+20timed; do not replace it with the R2 capacity or500 trajectory.

```bash
# Existing supervisor flags and Root resource/hold admission remain as above.
"$PY" -u -B tools/model_v3/single_a_benchmark.py \
 --candidate-options "$EXACT_CASE_OPTIONS_PATH" \
 --reference-config "$W/workflows/sprime_s/formal_s/B1_seed0_v2.json" \
 --input native_s --seed 0 --workers 8 --max-padded-cost 8000000 \
 --expected-gpu "$ROW_GPU_TYPE" --code-sha 7ffe8a5557590b1481f4ca74073007f070dc6a50 \
 --prereg-sha 2b4a4df8636e5d65915d535472ba01084ea72dab \
 --shard-snapshot-sha256 d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f \
 --deterministic-controls --role reference --abba-position 1 \
 --series-id "$ROOT_DECLARED_FRESH_SERIES" --output "$FRESH_R1_MEMBER1"
```

Positions2/3 use candidate, position4 reference. No v2 CLI flags are added to the single tool; those flags belong to the paired qualifier. It keeps original2warmup+20timed and original SDK logger fields, no new speed algorithm. Once all four actual members close, the existing CPU entry is:

```bash
"$PY" -u -B tools/model_v3/a_speed_report.py \
 --runs "$R1" "$R2" "$R3" "$R4" \
 --supervisors "$S1" "$S2" "$S3" "$S4" \
 --numeric-gate "$ACTUAL_NEW_PAIRED_CHILD" --output "$FRESH_ABBA_REPORT_JSON"
```

That report cannot use current4712/4722 for these six other cohort/source-option/GPU scopes, cannot use fixed-only results and cannot upgrade old R1 speed by assumption. Old true time/SDK results remain preserved; no repeats are proposed for fused/TF32/A5 scientific failures. Four SDKs can be independently audited as one later batch, then explicit selective sync, with no per-member new QA parent. Production-stage optimizer decisions, optimal capacity, full three-card optimization table and scientific adoption remain separate unfinished requirements.


Closure scope and limits

There is no pre-existing dedicated six-case closer, and this package does not
claim otherwise. Root must close actual parent/supervisor/source/resource/private
evidence, the existing complete v2 fixed-gate audit (all20, all parameter elements
and analytic zeros), paired outcome/all500, and SDK journals individually.
The existing speed report independently requires new matching code/options/GPU/
model/loss/data/deterministic controls across numeric gate and all four R1 members;
its summary alone neither establishes v2 publication nor grants new numeric
acceptance. All five new source/method leaves must be published before submission.
Old v1 method bytes, old500, original22e records, failed runs, and Native science
are preserved. No submitted job, capacity, result, speed gain or adoption is
asserted by this source-ready package.


## Routing v3：仅修实际提交前代码缺陷

保留冻结v2全部原字节。Root在发布/执行前发现NVML的 `for row` 会覆盖选中case字典，导致后续 `row['logical_python']` 类型错误。v3把selected case固定为 `case_spec`，NVML仅用 `app_row`。复制sbatch环境时删除全部继承 `SBATCH_*`，防止exclusive/资源选项隐式覆盖；显式原16CPU64GiB argv不变。GPU自动内存仍待用户授权，不借CPU自动内存规则。六case及411/549→同型C35路由、完整20+500和新同UUID R1、原阈值/数据/options/资源/锁/quota/信任全不变；仅新family和新method版本。无新增模型/benchmark/监控/重试/QA父，也未执行任何源或提交。


## Routing v4：Bash诊断字符串窄修

保留v3全部源及实际CPU4524767的bash -n失败，未将其发布或GPU执行。唯一执行语句修正是将参数展开的诊断 `Root binds the plan's original logical interpreter` 改为不含撇号的 `Root binds the declared original logical interpreter`，避免Bash在parameter word内等待未闭合引号。其余SB正文仅v4 namespace；Root driver仅namespace。原六case科学参数、64GiB、16CPU、85%、原锁/配额/120秒/20+500/新R1要求全保留。作者没有运行bash/Python/AST或提交；Root必须重新在CPU检查并发布精确v4源后才能准入。
