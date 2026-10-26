# 现有原生 S 的独立 B 精度路径

2026-10-26。状态：源码准备，自审完成后交 Root 统一执行；本文件不声称 CPU、原生 reader、CUDA 或四次20k验收已通过。原 D5 `PrecisionPlan`、authority adapter、配置和 CLI 保持原路径；新路径没有 D5 权威、PM7、Sprime_UFF 或24万分子代理声明。

## 指南范围与数据边界

指南阶段2要求代理规模 S 上 fp32/bf16 各2个真实训练 seed、各20,000次优化器更新；接口段允许 D3 前使用现有 S，不应把整个 B 工作推迟到 D5。阶段5的24万分子、PM7、全部允许构象、6M样本预算属于另一人口和实验。现有原生 S 可以提供独立的阶段2数值证据，不能替代 D5 的分子均匀采样或已见分子未见构象诊断。

真实输入严格复用 `training_inputs_v1` 原 TRAIN：11,104,772条记录、原 `BlockAtomBatchSampler`、原3视图和只读 transport。坐标仅称原记录 `pos`，现有元数据没有足够依据将其命名为 PM7 或 Sprime_UFF。采样单位是原记录，构象数自然影响分子权重；不改为 molecule-uniform，不取旧前缀冒充 D5。

验证仅使用已经冻结的1,024条 PRETRAIN_VAL 成员、55,650原子，选择文件 SHA `9ef81dcd5d3a84411328a76c5fbe7ccf123bc032e72e87a580d0b4c0bdf11e67`。该文件这里只提供成员元数据；不读取 C2 LOOKUP、NPZ、拟合参数或结果。原 WP5整分子组件提升规则、原 S train/full 角色和冻结预训练协议由现有 `role_evidence` 只读核对。新 reader 在第一次绑定时扫描全部 TRAIN Arrow 身份列，必须证明与固定验证的 record/molecule 交集均为0；不把旧8,192条 TRAIN 局部检查当全 TRAIN 证明。

共享原 LMDB 始终只读，`node_local=false` 如实记录。没有创建 LMDB、复制标签、重划 split 或访问下游最终评价。原 S decoder 仍逐条核 payload/原子顺序，原文件和源码 SHA 绑定在配置。切换父进程 TRAIN/VAL 读取时关闭旧 LMDB 环境，spawn worker 独立打开/关闭；恢复先关闭并 join 旧预取，再恢复已提交游标。

## 固定科学语义

真实主干512×6、8 heads、ff_mult2、原 A4 S 头；tiled distance65536、distance/head/backbone checkpoint开启。两侧均保持普通 AdamW 默认路线、TF32关闭、不编译、不改 logical batch。唯一模型执行差异是现有 `PerformanceOptions.precision` 的选择性 bf16：主干矩阵路径，距离/几何/RBF/头/损失/归一化与参数保持 fp32。

S 目标采用当前 v3 的3个已观察原 A4 raw field 的均值：element、noise、positive bond-order。它不同于旧 S runner 的加权总损失；原 source、view、head 和标签不变，这个区别明确写入成员 contract。噪声生成按原源的 seed/logical-index/epoch0规则；原 view level 与 eps loss 的 sigma=.1分别保留。训练 seed0、1是真实两次初始化和训练，不复用 B3 或 bootstrap 作为 seed SD。

每个成员的科学终点是20,000次优化器更新，独立记录已消费 base-record 数。10,240,000是20,000×最大512的样本时钟上界，不是要求消费该数量，也不能用6M替代20k。沿用已实现的 sample-cosine、warmup0、AdamW lr3e-4/betas(.9,.95)/weight_decay.01、clip1；这是本独立阶段2协议，不自动冻结阶段5或最终 recipe。执行前需 Root 将这份独立协议公开绑定。

验证点为0、500、…、20,000，seed0/epoch0固定、同一人口/顺序/掩码/原子数/真实 bond pairs。每点保存原单位 loss、accuracy、MAE、R2、component RMSE、vector RMSE、eps RMSE（适用的字段）。SSE按 fp64 累计：noise component RMSE=`sqrt(SSE/(3*valid_atoms))` Å；vector RMSE=`sqrt(SSE/valid_atoms)` Å；eps component RMSE再除 sigma。不能从字段均值损失推导或平均不同批的 RMSE。内部 `ValidationAccumulator(role='VAL')` 只复用数学 API；输出和绑定始终为 PRETRAIN_VAL，不冒称 D5内层人口。

四成员聚合要求同物理 GPU/环境/源码/计划；同 seed 的实际训练输入 rolling hash、已消费时钟、sampler contract 必须相同。每个验证点核单位/有效人口/输入/目标/掩码/pairs hash一致，然后复用原门槛：bf16每条指标曲线每点处于两个真实 fp32 seed包络内，同 seed component RMSE相对误差≤2%。不改分母、阈值或参数集合。聚合只返回 numeric gate；源码、实际 Slurm、监督器、SDK、CUDA dtype、存储闭合仍需独立核验才可形成最终科学结论。

## 分段恢复与运行保护

通用安全 checkpoint 包含参数、真实 Adam、Python/NumPy/Torch/CUDA RNG、原 sampler已提交游标、sample/update clock、LR、全部已有验证点、日志游标、父 run lineage 和完整 member/source contract。使用 `weights_only=True`读回、COMPLETE最后发布；既有目录不覆盖。恢复要求同成员、精度、源、配置和运行语义，不消费未提交预取，不重放已记录验证0点。

每段 fresh outside-Git 根与 fresh offline W&B；所有日志显式 step/commit，并 fsync本地镜像。恢复记录父 SDK ID。每个成员固定10k/20k checkpoint；另在显式 segment endpoint 或预留墙钟边界保存当前位置。默认6900秒 child预算，提前最多300秒在更新边界暂停保存；突发故障只恢复最后完整 checkpoint，partial 保留。暂停不改变训练数学或样本序列。

CLI保持2GiB单段输出和原 GPU85%/RSS56GiB保护，实际 child还必须由 Root 的有界 supervisor、私有 storage/quota/UUID锁和现场资源准入包裹。整个四成员长程存储由一个单独 hash-pin 的 Root adapter控制：`bind_native_s_precision_storage(request)`返回普通 JSON `binding`及`guard(action, experiment)`/`close()`。`binding`是跨成员/恢复不变的存储政策，进入成员配置绑定；每段路径、时间和job观察另存在运行回执，不能混入该稳定政策。它必须处理全部段、checkpoint峰值、失败partial、SDK、private/cache与quota；没有该实现时真实CLI拒绝，原因是内部长程存储尚未接通，不是 D5 未交付。不得把2GiB单段当四成员总预算。每个约22M参数的参数+双Adam矩状态粗上界约256MiB，7–13个不可覆盖checkpoint约1.75–3.25GiB/成员，还未计SDK/partial；Root须按实物再做有限存储协议。

首次真实 forward记录 Linear/LayerNorm输出和参数 dtype，属于模块边界观察；它不替代 QK/AV CUDA kernel 的独立实测，CPU bf16测试也不构成 CUDA验收。原17未profile步的耗时仅可作条件估计：3090/4090/5090单成员20k约23.86/18.45/13.04小时，四串行约95.4/73.8/52.2小时；不含本路径的验证、checkpoint、初始化和未知bf16增益。不能把该估计当实测吞吐或学校服务器正式训练授权。

## Root 的测试与 CLI

以下都是待执行命令，当前没有测试结果。CPU-only先运行三个新 test 文件；专门原生 I/O作业必须设置 `MODEL_V3_REQUIRE_NATIVE_S_INTEROP=1`，否则显式 skip不能算真实贯通。PYTHONPATH需要 `current`、`current/tests`、`tools/model_v3`、原 scripts与既有 pyarrow/lmdb deps。资源由 Root 现场按适用 CPU规则选择，≥16CPU，GPU隐藏，不使用GPU节点。原生测试会校验/扫描原 metadata并真正读取TRAIN/VAL记录、启动2个spawn workers、丢弃未提交预取后重放，最后 close/join并核原 input FD关闭；receipt仅小型元数据，不输出成员ID或标签。

```bash
MODEL_V3_REQUIRE_NATIVE_S_INTEROP=1 python -m pytest -q \
 current/tests/test_model_v3_native_s_precision.py \
 current/tests/test_model_v3_native_s_precision_cli.py \
 current/tests/test_model_v3_native_s_source_interop.py
```

Root 的 bounded CPU allocation可另做真实 offline SDK合成端到端（不等价20k）：

```bash
python tools/model_v3/run_native_s_precision.py member \
 --input synthetic_native_fixture --device cpu --updates 4 --until-update 2 \
 --precision bf16 --seed 0 --output "$FRESH_SEGMENT" \
 --code-sha "$ACTUAL_CODE_SHA" --prereg-sha "$PUBLIC_SHA"
```

恢复须在另一fresh根加 `--resume-checkpoint "$COMPLETE_CHECKPOINT" --resume-output-root "$OLD_SEGMENT"`，保持所有科学参数不变。真实入口同一个CLI，换成 `--input existing_native_S --updates 20000 --device cuda --deterministic-controls --expected-gpu TYPE --storage-hook FILE --storage-hook-sha256 SHA`；还需 Root真实准入/公开协议/原生CUDA dtype与resume短测，不能直接据本文启动四个长任务。四个完整成员的`member_result.json`交 `report --members …四文件… --output "$FRESH_AUDIT_JSON"`。

新文件清单和 SHA见 `native_s_precision_source_pins_v1.json`。原D5路径的冻结字节另列在同一receipt中，仅供核查保留；旧实验、失败、权重和标签没有改写。
