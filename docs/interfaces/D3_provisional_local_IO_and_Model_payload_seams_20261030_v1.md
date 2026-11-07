> 后续源码已落地：以 `workflows/data_v1_final/export/provisional_fast55k_adapter_v1/README.md`
> 和 `provisional_fast55k_model_v2_three_file_patch_v1.json` 为本提案的可执行接缝补充。
> 原文的独立 CLI/exec 方案已撤回：现 I/O `main()` 显式拒绝；必须同一已准入 GPU Parent
> 传入现存 live guard callable、保持原 UUID 锁并 in-process 调用。当前已实现实际 D3
> provisional verifier/typed-reader、F64 local locator、同 PID capture、可选实际诊断角色，
> 以及仅应用到独立 Model 副本的三文件 literal patch/CLI。原文“本轮只实现 I/O”已被此实现取代。
> 所有仍是 Source-only，未执行；r73 数值 frame 与当前 Model exact-geometry typed routing
> 的具体训练限制见新 README，不能把 transport / schema 签认当 actual payload ACK。
# D3 v1-pilot-provisional：现有 CLI、最小 I/O Source 与 Model 接缝

2026-10-30，SB1。仅静态源码/小元数据核对；没有 Python/AST/tests、科学正文、SSH、Slurm 或 GPU 执行。Fast55k 缓存文件数不是分子数/进度；未看到实际完成 receipt 前不声明 D4/D3 完成。本提案不改 Model/旧共享 Source，不增加科学门或测试矩阵。

## 已存在且可用的交接

指南 :221–228 要求 float32 家族 LMDB/no-pickle、10,000 源记录逐字段单次转换对照、真实大小、GPU 节点本地磁盘多 worker 随机读测及分发后 SHA。I/O 在 GPU 节点的已授权真实 GPU 验证/实际 payload Parent 中做，不另投纯 CPU 作业到 GPU 节点；该阶段自身不使用 GPU 计算，也不构成正式预训练。

1. Root 已有 `control/submit_D3_after_actual_fast55k_C0_analysis.py`：先核真实 Fast55k receipt/C0，再提交一个 analysis16/no_mem 的 `pilot_family_D3_fast55k_v1.run`，输出 `.../artifacts/labels/source_status_v1/pilot_family_D3_fast55k_v1/fast55k_provisional_day01_analysis/`。原精确 CLI 为：

```
PY -B -m workflows.data_v1_final.export.pilot_family_D3_fast55k_v1.run --plan ACTUAL_PLAN --startup-proof ACTUAL_CPU_PROOF
```

该 Source `run.py:105–115` 输出 `BOUNDED_PILOT_FAMILY_D3_RECEIPT_V1` / `ACTUAL55K_FIXED_RANDOM_FAMILY_AND_10K_SOURCE_QA_COMPLETE_PENDING_ROOT_MODEL_REVIEW`；`verify.py:37–89` 输出 `BOUNDED_PILOT_FAMILY_ACTUAL_D3_READBACK_V1`，有10,000源值单次F32对照、原F64/整数/索引/mask/reason精确读回，以及原16实际spawn reader。它是 CPU 共享盘读测，不能写 GPU-local 或 Model payload ACK。

2. Root 已有 `control/publish_actual_fast55k_analysis_D2_D3_D4.py`（元数据 publication；不是再次导出）。实际 D3 C0/完整 receipt 后执行：

```
PY -B /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/publish_actual_fast55k_analysis_D2_D3_D4.py
```

它产生 `configs/data_v1/v1-pilot-provisional/{D2_registry,D3_export,D4_normalization}.json`。D3 schema=`DATA_V1_PILOT_D3_FORMAL_EXPORT_DELIVERY_V1`，status=`DELIVERED_PROVISIONAL_SCOPE_NOT_FINAL_COMMON`；正式指向实际 `store_references`、四份 configuration、verification、actual C0/account，50,000 TRAIN+5,000 ROUTINE VAL，只 fixed_random；明确 `performance_evidence_scope=CPU_SHARED_STORAGE_ONLY_GPU_NODE_LOCAL_DISK_PENDING`、`Model_payload_ACK=false`。已有 D5 正式入口为 `configs/data_v1/D5_v1_pilot_provisional_delivery.json`。D2纯定义发布不是数值/归一化或实际payload验收。

3. 旧 `family_export_day_v1/transfer.py:9–42,61–118` 已有复制/全SHA/原Reader/16-spawn本地读测代码，CLI：

```
PY -B -m workflows.data_v1_final.export.family_export_day_v1.transfer --plan PLAN --startup-proof PROOF
```

它要求 `ROOT_ACCEPTED_FAMILY_EXPORT_RELEASE_V1` 和专用 `ACTUAL_D6_CPU_ONLY_DELIVERY_STARTUP_V1`，不接受当前 provisional D3 pointer；源也明确未来 node-local launcher 尚需真实节点权限/分配。不能把 generic CPU proof 传进去当 GPU host proof，不能为复用而伪造旧 final lineage。其 `metadata delivery-template` 仅产 NONEXECUTABLE 模板，没有可直接用于这轮 provisional 的完整 launcher。

## 本轮新增最小机械 I/O Source（未执行）

`workflows/data_v1_final/export/provisional_d3_local_readback_v1/{__init__,run}.py` 与 README。没有 queue/submitter/新测试。

主接口 `run(plan_path, host_context_path, check_host_resources=existing_parent_guard)`；CLI：

```
PY -B -m workflows.data_v1_final.export.provisional_d3_local_readback_v1.run --plan ACTUAL_IO_PLAN --host-context ACTUAL_SAME_PROCESS_GPU_CONTEXT
```

只能嵌入已授权真实 GPU 验证/实际 D3 payload Parent。CPU16 reader 是其串行 I/O 阶段，不与训练进程额外并发占核。已有 GPU launcher/Model 实际 Parent 验证自己的原 GPU proof、UUID/锁/资源后，采集同PID/boot/ticks/完整argv/剩余墙钟上下文；原 GPU proof/request 字节与 schema 保留，本入口不签新 proof。具体 plan/context 字段见同目录 README。CLI 不提交作业；上下文不能来自另一PID。`host_context` 是已有 GPU Parent 的观测接缝，不是新增 Root 批准层；不得仅靠 `host_gpu_guard_already_admitted=true` 绕过宿主实际 guard。

输入严格绑定实际 `D3_export.json`、原 D3 完整 receipt 与 raw C0会计；每个 closed-store 中原 data.mdb/manifest/F64 sidecar 以 O_EXCL `.partial` 复制，完整EOF SHA+本地再开SHA、源身份/原schema/计数；文件源/目标 locator 显式分开。实际 mountinfo 验证物理本地磁盘，statvfs/全量未来复制预算/RSS/宿主剩余墙钟观察。128MiB metadata reserve 包含在宿主 copy cap 内，不能越过原宿主 scratch/output 配额。D3真实大小到达后把实际复制预算计入同一GPU Parent，不假定原小诊断2GiB预算能容纳整份D3。

机械兼容已从源码确认：Fast55k `writer.Reader:28` 继承 `family_export_day_v1.store.Reader`，只增加 ordered/get_f64 便捷方法；后者的原 decoder/validator 与 Fast55k 实际验证一致。新增入口直接复用原 `verify.read_initializer/molecule_reader:53–73`，不改值/掩码/顺序/数值算法。全55k MID守恒后按原 hash 顺序选16个 whole MID；每worker读该MID全部实际家族/构象，记录真实PID、自然join与包含spawn的分子/秒。缓存状态明确为完整复制/SHA/索引读之后，不宣称冷缓存。

输出 `ACTUAL_PROVISIONAL_D3_GPU_HOST_LOCAL_IO_RECEIPT_V1` / `EXACT_D3_LOCAL_COPY_AND16_READER_IO_COMPLETE_NOT_MODEL_ACK`，引用真实宿主GPU分配/原proof、原D3、local origin→target inventory、实际磁盘容量与16worker结果。`Model_payload_ACK=false` 永久保持。失败留 partial，不删旧文件、不发信号、不重试；不调用 UFF/QM、模型训练或新的诊断。

## 实际模型入口：已存在的能力与真实限制

旧 `X:/MFM_model_v3` 仍有10月26日历史 Source；本审查沿已签 Model ACK 对应的较新 `X:/MFM_model_v3_delivery_integration_v2` 核对。不能据旧树把新模型消费者能力说成全无，也不能把新树 synthetic 回归说成实际 D3 验收。

- `current/phychem_mfm/phase1/v3_data_adapter.py:259–329` 有真实 release verifier seam，要求外部 `verify_model_v3_release_authority(request,documents)`；:550–615 有真实 `RealDataProvider`，:641–691 的 `make_proxy_inputs` 返回原 `ProxyInputs` 并接原 collate/PreparedV3Batch。已实现 ordered-entry/Tensor6/source frame/normalization 逻辑。
- `v3_proxy_run.py:286–310` 要求已pin外部 hook `verify_and_bind_model_v3_pilot_TRAIN_inputs(request)`，真实 readonly/node_local/Data权威，不允许 candidate fallback。实际限定 hook 在本轮已审 data/model Source 中未定位到；仅有抽象接缝和 fixture 实现不能构成可运行的当前D3 adapter。
- `v3_data_adapter.py:103,133–257,267–288` 目前仅接受 `actual_final_release_v1`；硬核旧 `ROOT_MODEL_JOINT_FINAL_LABEL_POLICY_V1`、`ROOT_FINAL_LABEL_RELEASE_V1`、`family_export_day_v1` producer/candidate、five wrappers、旧release固定目录。当前 provisional 发布不符合，不能重标schema绕过。
- :40,267 还要求 evidence 里名为 common_population 的旧键；:367–384 的实际D4 schema 路由是旧 final normalization，不能拿 Fast55k 原 statistics 当旧final文档。`v3_pilot_smoke.py:99–113` 的 aliases 假定 joint.contract_reference/model_ack_reference；新共同冻结实际字段是 frozen_data_source_references/model_ack_reference。`v3_physical_policy.py:130–147` 只查 joint.evidence_source_references，新D1是 frozen_data_source_references。
- `v3_wire_provider.py:1,119–122` 仍为 synthetic-only；不能开 allow_candidate 后传真实payload。新 `v3_data_adapter` 是另一条真实 seam。

Model 现有真实 GPU CLI（须先得到实际 provisional hook/admission，不能现在执行）：

```
PY -B MODEL/tools/model_v3/run_proxy_experiment.py run \
  --request ACTUAL_PILOT_REQUEST --request-sha256 ACTUAL_SHA \
  --input authoritative_pilot --output FRESH_OUTPUT \
  --lineage-root ACTUAL_LINEAGE_ROOT --lineage ACTUAL_LINEAGE \
  --segment-id SEGMENT --until-samples REGISTERED_SEGMENT_ENDPOINT
```

其 execution_context 只允许非engineering实际GPU UUID；原 `authoritative_pilot` 是2000有效更新及完整已绑定验证人口，不能拿它冒充仅加载ACK。阶段5已有 `prepare_architecture_wiring_smoke.py --base-request ... --base-request-sha256 ... --trial ... --output ...`，派生50有效更新接线，但必须先有实际admitted D3 base。`run_proxy_experiment.py ack` 是长程storage ACK，不是数据payload ACK。

## 模型侧精确最小改动提案（未改共享 Model Source）

1. `v3_data_adapter.py` 新增独立 family `actual_pilot_provisional_fast55k_v1`，只允许 `authoritative_pilot` / `versioned_provisional_pilot_TRAIN`，另行验证上述真实 D2/D3/D4/D5 pointers、50k/5k、D3真实C0/raw、同D1双方冻结+Model签署、相同Source/geometry/mask/归一化。`is_actual_data_release` 对这一实际暂定family也为true；旧 final family 验证保持原字节逻辑。新family使用 `provisional_population` evidence，不制造 Common，也不要求 D6/D7/独立全P′。
2. 外部新独立 `provisional_fast55k_adapter_v1` 实现上述 verifier/hook 和 readonly local reader factory。原 core Reader+copy_inventory 解析只改 locator；原146 field/target/condition/role/atom/geometry/source-anchor/mask/reason/codebook 显式一一投影到既有 typed对象、SamplingIndex/DecodedSample，不从字段名推断物理含义，不静默drop字段/补默认尺度。r73走原 F64旁车/S.unpack与既有 OrderedEntryTarget，仅一次F32；原双端basis/channel/onsite/重复/ordinal全部保留。r674原full6/mask/实际统计保留，按已签目标物理政策 LOSS_DISABLED，不作原点变换或新QM。
3. `v3_data_adapter._tensor6_record` 对新family只加实际 Fast55k D4 schema→原n/winsor bounds/std/raw-mean-F绑定的读取分支；真实数字/fit TRAIN/heldout排除/actual population SHA由原D4指针给出，统计公式、尺度规则、loss math均不改。实际字段 layout 尚待真实D4完结件；不得先造 `FINAL_TRAIN_TARGET_NORMALIZATION_CANDIDATE_V1`、s=1或猜JSON path。小authority/normalization投影只能保留原值并引用原实际Source，不能伪旧final parent。
4. `v3_pilot_smoke.verify_pilot_evidence_aliases` 仅新family映射 D1共同冻结/实际D2配置/实际D3/D4 delivery/Model原签署/actual reader；不改原2000 update/FP32/真正验证定义。`v3_physical_policy.physical_policy_for_release` 仅新family从已共同冻结五份原source三元组验证同一物理决定，旧final evidence_source_references 分支不变。无新物理PASS或r674启用。
5. Model 真实 payload ACK 应由同一实际 GPU Parent 的独立加载阶段产生：调用上述真实factory读取明确实际 TRAIN/VAL MID/geometry/各实际family的payload，走原 typed Decode/collate，绑定原D3 pin、本地inventory SHA、实际Model source/reader/配置/规范化/进程/记录和原mask来源，再由 Model Root 记录其真实加载结论。它不需要等待完整Common/D6/D7、额外20k全量读测或2000训练结束；但字段名/schema/D1 policy ACK、仅fileSHA、仅数据侧Reader benchmark都不足以替代。正式阶段3/50更新/2000 SDP按已授权模型主线随后执行，不能把仅loader ACK说成这些已过。

这不是只换一条路径即可成功的机械model接缝，涉及已有真实admission的独立family及Source-bound typed projection。因此本轮只实现能确认兼容的数据I/O；模型侧变动交由 Model 当前工作树负责人按上列最小diff实施，不在数据线改共享模型模块。若当前还有较新的已登记实际adapter，应以其明确Source/CLI替换此提案，不能仅依据旧STATUS推断不存在。
