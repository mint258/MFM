# Native-S storage/profile v2

本包是新修订，v1 `b621dabb…`原字节和1126记录保留。1126仅39 unit PASS；parent因GPU fixture FAILED，不能当C0准入。本包尚未运行任何Python/测试/GPU/reservation；静态预计82 CPU项，实际collection以Root执行为准。

## 一棵执行树与三种合同

Root机器记录 `N/native_s_combined_immutable_runtime_v1.json`给出 detached combined runtime，包含Native12和075 accounting。`accounting_leaf_provenance.json`仅保留075实现leaf来源，不声称当前combined HEAD为075。`prepare_runtime_contract.py --combined-record …`机器读取code/tree，实际Git HEAD/tree/clean状态和源字节均核对，不从PTY抄hash。Root在服务器CPU执行一次，输出到**包外fresh文件**；包内`runtime_contract.json`故意是不可准入placeholder。

- `PREPUBLICATION_METADATA_ONLY`：只允许metadata/origin/机制测试，没有数据、GPU或reservation准入。
- `CANDIDATE_PROFILE_ONLY`：按Root明确新增的有限验证范围，要求实际combined checker C0（1127）、Native25 CPU与realreader1实际C0、v2自身QA实际C0、源码前后一致、combined/public exact-tree及原始ref。`full_runtime_status=PENDING`、`production_20k_allowed=false`；只能20次更新、一次完整1024 PRETRAIN_VAL、安全CP/SDK/storage/dtype测量。适配器guard拒绝第21次更新，也不能借该合同/phase启动SCIENCE或长期B结论。
- `PUBLISHED_IMMUTABLE_RUNTIME`：另需完整Root实际C0/源码/原始QA与checker证据，才可用于四成员20k的进一步准入；仍须全部native profile、SDK、closed-census、future-state、precision、accounting证书闭合。

候选公开ce7 exact-tree本身不是full PASS。Root1159因CPU监督器身份工程故障中断的事实保留，不写成pytest数值失败，也不允许它阻止所有验证工作无限开展。candidate profile仍不是20k验收。稳定`runtime_identity`只绑定root/code/tree/public/model与075 leaf源文件；操作QA状态/receipt另绑定，因此后续full C0不会让同源profile因状态变化自动失效或陷入profile循环。

`runtime_origin.py`先检查所有已加载canonical `phychem_mfm*`和bare工具的`__file__/__spec__/__path__/REPO/REPOSITORY`，外树立即拒绝；然后只导入同树canonical模块，核Native Plan/Inputs/Experiment、PreparedBatch/Trainer/MultiView/PerformanceOptions及source collector类/函数身份。没有清`sys.modules`或拼包`__path__`。`origin_probe.py`在fresh子进程覆盖fresh、同树Native-first、外树075-package/bare-origin元数据负例；不构造Inputs、不扫11M、不运行CUDA。负例是明确的origin元数据注入，不声称真的训练075模型。真实profile仍要求CUBLAS在Torch导入前配置，不能因origin通过而绕过该约束。

## 资源与退出修订

outer仍2GiB/7200秒，child6900秒/85% GPU/既有RSS限制。profile严格读取supervisor的`MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES`，必须是outer−96MiB，即1952MiB；不会覆盖或抬高继承值。Root admission `resource_envelope`记录outer、child、96MiB supervisor reserve、实际private预算和额外durable cache增长hold。checkpoint/non-checkpoint/save reserve必须装得进child cap；private/compiler增长不能靠只声明2GiB child hold隐去。

300秒真正接入冻结Native `pause_requested`。guard/预取跨过边界时抛显式pause，关闭未提交验证迭代并按已提交clock保存安全CP；不会消费未提交batch。未满固定20短目标按FAILED非零退出，保留CP/SDK/partial，不能修改短目标或20k门槛。SDK/CP数量不等于1、summary/cleanup异常同样非零；原始异常不被新错误覆盖。原v1“FAILED.json但exit0”路径已删除。

## 实际根覆盖

`root_coverage.py`读取真实父supervisor argv/stdio、UID/start_ticks/PGID/SID/boot/cgroup，与Root `supervisor_launch` raw投影和combined supervisor源逐项核对。Root wrapper需显式传`--output-root/--output-budget-bytes/--record/--observations`。实际stdio若是未知pipe则拒绝；不猜Slurm目录。父argv/stdio/resource图由Root真实wrapper产生，不在本包伪造已执行receipt。

实际`load_storage_bindings`字段按当前helper核实：receipt_path/SHA、schema/job/UID/node/boot、roots身份、environment、compiler key/reuse、initial_bytes、private预算/peak语义/sourceSHA。每个private root校UID/device/inode和真实mount事实；node-local只能是实际/tmp scratch/local FS，durable compiler-cache需有限额外增长hold并注册计量。SDK cache/data/config显式指定，未知HOME默认config拒绝；Python bytecode输出禁止（Root wrapper设置PYTHONDONTWRITEBYTECODE=1，profile在任何本地包导入前也禁写）。

Root `root_coverage`逐role对应child、三SDK目录、private roots/env/receipt、supervisor record/observations、Slurm stdout/stderr、lineage、management、准备期额外source snapshot等，并指向实际已注册disjoint counting root。private sampler和durable census分域，不能把允许Unix socket的scratch误丢进只接受普通持久文件的计量器。目录source snapshot必须有显式manifest字段映射，逐**相对path**核bytes/SHA，并与所有物理文件集合相等；没有按basename猜路径或仅采样128/132项。

## 算子观察与SDK证据

`precision_observer.py`对每层分别记录QK、softmax、AV，包含实际input/output shape/dtype/device、B/H/N/head-width与模块类；即使N等于head-width也按源码顺序/softmax位置区分两阶段。distance difference、distance-squared、softmax、RBF exp、native_layer_norm分别coverage。没有bmm/不支持Flash时是NOT_OBSERVED，不以输入bf16冒称内部证明。只描述一个已观测forward形状的**算子接口dtype**，不证明kernel accumulator或所有未来TRAIN形状；CPU证据永远不是CUDA acceptance。

profile保存准确`SDK_expected_configuration.json`、按fsync mirror折叠并显式写入SDK的`SDK_expected_summary.json`、原始`history.jsonl`与SDK refs，供完整tap核验。v7 bounded reader原schema可证明全history/EOF/exit/runID，但只验证paired_role配置，不能升级为本任务full config/summary。`evidence_graph.py`因此要求独立raw full-config/summary tap；当前尚无实际Native profile/tap，缺它会明确拒绝long准入，而不是重命名C2/v12或A06证书。Root/SA3可按真实tap schema另接，不能静默改未知结果名。

证据图需真实raw sacct argv/stdout/returncode/parent job行解析COMPLETED0:0；producer原源SHA、输入manifest、真实command/UID/job/C0；原SDK/mirror/reader调用binding/v7结果/config-summary tap；actual safeCP+shape/source/future-bound计算；原算子观测；实际Root supervisor/process/private closure。完整Root raw projection字段见`evidence_graph.py`，它只校验，不生成已执行证书。QA/ref引用图单向：terminal链接已产生raw artifact，后置projection链接terminal与raw artifact，不能构造SHA循环。

原来所谓SDK_bytes实际是所有non-CP输出，v2已改名`non_checkpoint_output_bytes_before_profile_result`。保存`profile_result.json`后才采样并在stdout输出`native_S_profile_post_result_census_v2`；不声称写报告之前的值是最终census。长期准入另需Root在实际child退出/SDK闭合后的`closed_output_census` raw/ref，派生总non-CP bytes并覆盖external/private。原SDK文件本身bytes独立记录，未说已在线同步。

## Root实际调用

以下均是待执行，不是已通过/已分配。Root≥16CPU现场CPU节点、GPU隐藏、PYTHONDONTWRITEBYTECODE=1，先生成metadata合同，再设置`MODEL_V3_NATIVE_S_RUNTIME_CONTRACT`运行本包所有`test_*.py`。不得在GPU节点运行这批纯CPU测试；不读取真实成员清单/LMDB/LOOKUP/NPZ/既有权重。

```bash
python "$PACKAGE/prepare_runtime_contract.py" --combined-record "$N/native_s_combined_immutable_runtime_v1.json" \
 --git "$KNOWN_GIT" --metadata-only --publication-receipt "$N/native_integration_public_receipt_v1.json" \
 --publication-sha256 "$MACHINE_RECEIPT_SHA" --output "$FRESH_METADATA_CONTRACT"

MODEL_V3_NATIVE_S_RUNTIME_CONTRACT="$FRESH_METADATA_CONTRACT" CUDA_VISIBLE_DEVICES='' \
 PYTHONDONTWRITEBYTECODE=1 python -m pytest -q "$PACKAGE"
```

v2实际QA C0、checker/公开source后，Root可用`--candidate-profile-only --candidate-admission FILE --candidate-admission-sha256 SHA`生成新candidate合同；full合同则需要`--full-runtime-verification FILE --full-runtime-verification-sha256 SHA`。实际Root reservation、quota、job/resource/coverage字段按新v2 schema填写：configuration=`existing_native_S_storage_configuration_v2`，capacity用`non_checkpoint_bytes`；sources稳定pin为`canonical(runtime_identity(contract))`，不是包含QA时间的全合同SHA。

实际GPU只由Root新wrapper提交：

```bash
python "$PACKAGE/profile_native_s_storage.py" --runtime-contract "$CANDIDATE_OR_FULL_CONTRACT" \
 --output "$FRESH_PROFILE" --precision fp32 --updates 20 --expected-gpu TYPE \
 --code-sha "$ACTUAL_COMBINED_CODE_SHA" --prereg-sha "$MODEL_PUBLIC_SHA"
```

其余native scope不变：原S记录采样/原pos、TRAIN和固定1024 PRETRAIN_VAL、全11M disjoint；不称final-D/PM7/Sprime/24万代理，不读C2拟合权重。原Root075 final-D分支、原v1、已跑A证据/阈值不改。本包没有SSH/sbatch/reservation创建、删除原件、正式训练或学校服务器入口。
