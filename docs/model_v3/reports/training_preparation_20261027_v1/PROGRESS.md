# 训练前整理：在线日志、数值候选与 S 长程执行

2026-10-27，Asia/Shanghai。本次为阶段性证据更新，不是模型或配方冻结。正式预训练、下游最终测试、构象网格、S/S′ 与 P/P′ 决策对比均未执行。

## 问题与预先注册

本轮核验三个问题：离线 W&B 是否真正在线可读；补偿 FP32 数值实现是否满足原完整等变性门槛；已通过准备检查的既有 S 长程试验能否按原配额与存储约束执行。

数值候选预先注册在独立分支 [model-v3-numeric-stability-v1](https://github.com/mint258/MFM/commit/5cdb2772dfa51e1cc72098c659fb741440219772)，实际执行本地提交 `4068623cc455915a34a4aacae4f0df5c56f691b7`，两者 Git tree 同为 `b2b53cde6a099bf4b4d1686bec8823bc0b30bc8e`。候选仍为显式 `compensated_fp32_v1`，默认 legacy 不变；未合入生产模型。

S 的科学执行提交仍为 `3d9b1cc0c580dacc9398a5570b0c2fff3e257618`，公开对应 [ce7cbf5](https://github.com/mint258/MFM/commit/ce7cbf5776ff546cd47538b120c8f884e2e5867d)。v4 仅调整运行检查和失败证据保存，不改变模型、种子、精度、优化器、RNG、输入次序、原验证集或固定 2 万步计划。

## W&B：固定 50 条完整日志已同步

认证已用真实在线访问和同步作业确认。保留原 run ID、原 project 和结束状态；原生 entity 为空时显式使用已认证默认 entity `mint_leaf258`。未输出或提交凭据。

57 条历史 SDK 的实际完整性检查 4521403 中，50 条完整、7 条不完整。随后采用 W&B 0.28.1 官方 core 同步命令，每个 CPU 作业最多依次处理 3 条显式日志。完整复制后只同步副本，原文件与原同步标记保持不变。在线回读逐条核验路由、状态、全部历史行数和 step 范围；无列过滤的流式读取只保留 `_step`，不导出其他指标值。

| 范围 | 实际结果 |
| --- | --- |
| 完整日志 | 50/50 已通过实际 C0 父作业及在线元数据核验 |
| 原结束状态 | 37 条 finished、13 条 failed，均保留 |
| 不完整日志 | 7 条未上传；原件与失败证据保留 |
| 上传方式 | 官方 core 命令、逐 run ID、无 append/sync-all/finish API |
| 4sgxpx8j | 原 4521410 的官方命令已上传；4521428 只核验已有远端，未重发 |

4521410 因历史读取方式不适用而整体失败，原 FAILED 终态不改。独立诊断确认带 `_step` 列过滤返回空历史，而无列过滤可读完整 500 行；后续 v3 更正读取方式。原先失败的同步尝试同样计入成本。

最终 [Root 收口证据](evidence/WandB_sync50_final_Root_closure.json) 绑定试点及 17 个小批作业，accepted=50、remaining=0。X 盘统一入口 `W&B_训练记录.html` 已追加在线核验链接；具体页面为 `runs/phase1_full_corpus/wandb_archive/model_v3_20261025/online_sync50_20261027_v1.html`。现有入口的原始前缀保留，见[发布回执](evidence/WandB_sync50_online_index_publication_actual_v1.json)。此固定清单不包含后来新增的两个 S profile 和长程分段；它们另行核验，活动日志不上传。

## 数值候选：完整回归通过，原 48 项科学矩阵未通过

候选用 FP32 补偿求和、固定分段树和稳定几何累积，保留参数、状态键、RNG 与 H0 API/512 维。普通仓库检查 4521416 实际 C0；针对性 4521413 共 66 项通过。独立完整回归 4521421 在 CPU13、16 CPU/32 GiB、4 个 pytest 子进程执行全部 113 个测试文件。

| 检查 | 实际计数 | 实际父状态 |
| --- | --- | --- |
| 完整回归 4521421 | 2,639 项：2,636 PASS、3 个既有可选 skip、0 FAIL/ERROR | COMPLETED 0:0，134 秒 |
| GPU 首次 4521429 | 在模型执行前因两份元数据 JSON 的 Git/工作树换行身份差异退出 | FAILED 1:0，2 秒 |
| 原完整 GPU 矩阵 4521435 | 48 项：10 PASS、38 FAIL、0 ERROR/SKIP | FAILED 1:0，35 秒 |

[完整回归闭合](evidence/numeric_full_regression_4521421_actual_closure_v1.json)核验了实际父会计、四份 XML、全部文件覆盖、源码前后和当前冻结来源。提交 helper 要求 SBATCH 位于旧 runs 目录，因此复制了冻结脚本的完全相同字节；原回执与计划不改，仅在独立验证器中明确核验这一位置映射。

Git 结束字节本来正确。4521429 的实际问题仅在两份 JSON：工作树保留 CRLF，Git blob 为 LF。独立运行包 v2 对 14 个代码/测试/配置文件仍严格核验原始字节；只对已列明的 SOURCE_PINS 和 VALIDATION_REQUEST 两份 JSON 投影 CRLF→LF，再核验注册长度和 blob。运行时原始 SHA 同时保持严格绑定。没有修改数学源码、权重、夹具或容差。

4521435 使用原 3 个 C1 × 2 种视图 × 4 种头策略 × 2 个种子，全部 3 种刚体变换；绝对误差 ≤1e-5、rtol=0，非零检查保持。48 份结果和每份 52 个终端数组在断言前保存，源码前后一致。独立[失败闭合](evidence/numeric_GPU_1429_1435_actual_closure_v1.json)保留两个 FAILED 父状态及完整矩阵。

仅对实际闭合 case JSON 的只读汇总显示，1,872 个目标/变换观测中有 81 个失败，全部失败的 argmax 位于 32 原子组：

| 目标 | 失败观测/144 | 最大绝对误差（原合成输出单位） |
| --- | --- | --- |
| PD/p_dipole | 35 | 2.1939841283e-5 |
| PD/p_dipole_magnitude | 32 | 5.6512653828e-5 |
| PD/p_extensive | 14 | 1.5497207642e-5 |

其余 10 个目标的 1,440 个观测均通过。全 clean batch 的 H0 最大差约 1.25e-6～1.91e-6，不能当作 32 原子组的分图归因。现有 52 个数组仅含终端输出，未保留本轮 H0/charges，不能据此分离继承的 H0 漂移与预测头舍入贡献。也不能声称最终 FP32 输出量化本身造成 1e-5 下界，或据 C1 的通过数选择架构。

**决定：候选不采用。** 下一步只做有边界的终端链归因；不会仅以补偿求和、单测通过或较少失败宣布 C4 验收。科学阈值、原种子和变换均不改。

## S：保留失败，按相同科学配置重试

4521411 在原生 S 长程首段实际 FAILED 1:0/1,768 秒。最后持久镜像观察为 723 次更新、298,238 个 base samples；该段没有安全检查点或成功 member_result，因此接受更新数为 0，不能从这段尾部无损恢复。

首个异常为 `Quota feed stale or future`。原拒绝 feed 未保存，不能区分当时是过期还是未来时间。后来 Root 封存另遇跨主机设备编号比较：同一共享目录在 sonmi 上 st_dev=2049、在 compute21 上为50，inode 同为32241933288；这不是目录被替换的证据，见[可信主机探测](evidence/Native_S_1411_host_clock_and_inode_actual_v2.json)。

原 ledger 已写入 failed_attempts 与 segment_terminal。补齐操作复用了既存 index8/9，不重复 seal_segment 或计数；原九条索引链、失败、配置和 principal 全部保留，[失败闭合](evidence/Native_S_1411_failed_closure.json)明确仍为 FAILED。

独立 operational v4 做两项运行修正：

1. 仅对精确配额时间异常暂停模型工作，最多等30个单调时钟秒重读；每次保存真正被拒绝的原始 feed、年龄、主机和来源。原0～90秒、quota、inode、lease、来源及完整验收仍须真正通过，其他异常和超时仍失败。
2. 正常和失败封存均在原 compute21 主机执行原 whole_census，保留设备号/inode 门槛。原128 GiB阶段保留量、2 GiB作业/私有域、16 CPU/32 GiB、28 GiB RSS及2小时上限均保持。

[独立 adoption](evidence/Native_S_operational_adoption_v4.json)绑定原 VALIDATED/readiness 与新运行源，未改原科学配置。新作业4521438在同一物理5090 UUID `GPU-22e21021-e572-4562-fc51-cd8c83e74141`从u0明确重试。启动8项元数据检查0FAIL/ERROR/SKIP，状态仍为 `PASS_PENDING_SAME_MODEL_PARENT_TERMINAL`；启动观察已达28更新/11,264样本，不能当作当前最终进度、C0或四条2万步曲线完成。

两次分段的共同配置 SHA256 为 `5a28800e8cb858e9758b96f16c8987653d5de6772f56cd033a0766bf970e78f3`。现有 S TRAIN manifest SHA 为 `2f69b672350744369b08c672b62e3d276487714abc97b766a12140ec5af59997`，仍是原生记录自然计数采样、只读共享输入及原 PRETRAIN_VAL 1024条；不是 D-5 的24万分子代理或新的按分子均匀采样证据。

## 资源与边界

[实际账本](evidence/job_ledger_model_v3_active_v14.json)在2026-10-26 17:30:40 UTC采集411个本任务父作业：825,808分配CPU秒（229.391111核时）、32,106 GPU节点作业秒（8.918333小时），包含全部已发现失败和重试。原始[父会计行](evidence/job_ledger_model_v3_active_v14.psv)可重算。它是点时值，活动4521438成本未封顶，4521338仍排队；GPU节点作业时间不代表显卡利用率、GRES隔离或收费金额。

真实数据线仍报告 D-1 draft.3 未共同冻结，D-3～D-6正式交付未完成。现有 S/合成工作继续，但真实新标签 SDP 冒烟、架构/头选择、配方/B*、最终冻结/tag/HANDOFF/PR均未验收。未更新 main，未使用学校付费服务器。

本次[冻结运行源快照](../../../../tools/model_v3/analysis_sources/training_preparation_20261027_v1/)包含实际同步、回归、GPU矩阵与 v4运行工具。长段 SDK auditor v2仍为准备态，28项前置测试将在真实已关闭分段的CPU审计作业内执行，不借用其他测试称通过。全部 SDK、检查点、原始数据和凭据均未加入Git。
完整的只读目标/变换/配置分布及48份case JSON哈希见[1435分析](numeric_GPU_1435_readonly_analysis_v1.md)。后续[透明捕获与固定H0影子方案](numeric_terminal_shadow_source_plan_v1.md)仍是设计：先捕获本轮缺失的真实bank输入，再对新捕获的同H0做头部算术对照；不会把CPU重建的encoder或新捕获冒作1435的原H0。120秒CPU预算仅为估计，无新capture/shadow已完成的声明。
逐运行结果采用仓库规定的[typed CSV](../../results/native_S_segment_observations_20261027_v1.csv)。CSV状态与耗时来自上述点时会计；observed字段为明确保留的历史观察，1438的history_is_startup_observation=1。原报表草稿已留存于仓库外，修正报表路径/列格式没有修改模型、日志或科学结果。
