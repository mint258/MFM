# 执行与复现记录

日期：2026-10-25（Asia/Shanghai）。执行指南为项目根《模型线工作流程：模型 v3、
训练代码与训练配方（Codex A）.md》。本任务不包含正式预训练。

## 分支和源码

服务器工程 `/share/home/zixiao/descriptor_analysis` 的 X 盘为 live SSHFS。
主工作树为其下 `MFM_model_v3`，分支 `model-v3`，从 GitHub main 的
`037546cd7f07b32dbb46bc21a69109dfd273f8da` 克隆，未覆盖旧源码。
子树 `MFM_model_v3_sa1/sa2/sa3` 分别对应性能、标签损失、评估。
Git 无法同时保存分支名 `model-v3` 和 `model-v3/sa1-*`，因此实际子分支为
`model-v3-sa1-performance`、`model-v3-sa2-labels`、`model-v3-sa3-evaluation`。
SA-4 在 profiler 后另安排；平台同时最多支持主 agent 加三个工作 agent。

阶段 0 服务器提交 `b71729e` 的 tree 与 GitHub 发布提交
`3441b280bc34431bf8e7596465af28be073644b6` 完全相同：
`d8950ec6503f39ddfc956cf97eb9e24308e9f47c`。
发布使用已连接 GitHub 工具创建 Git tree/commit/分支；保留实际服务器 Git SHA，
不把两种提交号混为一谈。预注册引用公开提交，执行另记实际 code SHA/文件 SHA。
服务器辅助并行测试工具提交为 `e64fb16aebb1b3d9ad2ceea16e1cfb6c441218e0`。

## 已提交的有限计算

| Slurm ID | 内容 | 节点 / 请求资源 | 已观察状态 |
| --- | --- | --- | --- |
| 4520329 | 三配置参数与合成 H0 审计 | compute-0-20 / 16 CPU / 16 GiB / 10 min | 实际 COMPLETED/0:0，251s，4,016 CPU秒，无 CUDA |
| 4520330 | 原有 61 个核心测试文件，16 个独立 pytest 进程 | compute-0-20 / 16 CPU / 32 GiB / 25 min | COMPLETED/0:0，316s；2,016 passed，无 skip |
| 4520331 | SA-1 profiler正确性、SA-3结果CSV安全测试 | compute-0-20 / 16 CPU / 16 GiB / 10 min | FAILED/1:0，37s；SA-3 10 passed；SA-1 3 passed/1 failed：合成调用缺必需参数 |
| 4520332 | SA-2标签核心、SA-3开发评估核心 | compute-0-20 / 16 CPU / 32 GiB / 12 min | COMPLETED/0:0，51s；19 + 8 passed |
| 4520333 | 修订后的性能、训练、传输和评估单测 | compute-0-20 / 16 CPU / 32 GiB | COMPLETED/0:0，16s；9 + 28 + 31 passed，1 CUDA skip |
| 4520336 | 原 S 桥接、运行监督与实验工具集成测试 | compute-0-20 / 16 CPU / 32 GiB | FAILED/1:0，179s；56 passed/1 failed/1 CUDA skip，唯一失败为 CPU 多线程反向逐位比较 |
| 4520337 | 真实 W&B 0.28.1 离线 SDK 布局及原生历史读回 | compute-0-20 / 16 CPU / 16 GiB | COMPLETED/0:0，10s；run 5fpnfle0，两条历史读回，四种 SDK 链接核验；未在线同步 |
| 4520338 | S 桥接反向差异诊断，零优化更新 | compute-0-20 / 16 CPU / 16 GiB | COMPLETED/0:0，7s；8线程原实现自身重复即有差异，单线程所有比较逐位一致 |
| 4520339 | SA-1 分支完整核心回归 | compute-0-20 / 16 CPU / 32 GiB | COMPLETED/0:0，97s；2,040 passed，无 skip |
| 4520340 | 4090 合成 profiler 首次冒烟 | compute-0-20 / 16 CPU / 64 GiB / 12 min | FAILED/1:0，14s；源码记录误收 PyTorch 伪相对路径，训练前失败，零优化更新 |
| 4520342 | 源码绑定修复、S 严格梯度、H0 装载定向复核 | compute-0-20 / 16 CPU / 32 GiB | COMPLETED/0:0，11s；2 + 1 + 27 passed，前后源码 SHA 完全一致 |
| 4520343 | 4090 合成 profiler 重试 | compute-0-20 / 16 CPU / 64 GiB / 12 min | 已提交；执行 SHA 14b98d03932b53b2d4f132afb69c4e652b747888，终态待实际产物 |

计算与日志均在外部 `runs/model_v3_20261025/`，没有真实数据、权重或 checkpoint
进入 Git。pytest 的合成 fixture 不代表真实 D-3 验收。失败和超时原样保留并计账。
CPU 作业显式隐藏 CUDA。GPU 将分别核验实际 UUID、空闲显卡进程、共同 UUID 锁、
单卡环境和节点全部用户声明内存；不把无 GRES 的 CPU allocation 称作 GPU 预约。

本表只列本任务登记的作业，ID 空隙属于其他工作，不计入本任务。阶段成本按
各登记父作业实际 `ElapsedRaw × AllocCPUS` 统计，失败同样计入；GPU 节点作业
分配时长与 GPU 利用时间分开。原始账本为外部
`runs/model_v3_20261025/job_ledger_after_343_v1.psv`，343 尚未终态的快照不作最终成本。

SA-1 完整测试时源码随后提交为 `ddb0740bf65d22beafdbee4687723046136a1fa7`。
340 的故障修复仅涉及 profiler 来源记录和回归测试，checker PASS 后提交为
`14b98d03932b53b2d4f132afb69c4e652b747888`；不改模型、精度或计算表达式。
340 supervisor 核验了实际子进程身份与 Slurm cgroup，自然退出、remaining 为空，
没有发送终止信号或操作他人进程。UUID 为
`GPU-ec788ed1-7da1-8f93-bb23-b4fdb2018b02`；另一张卡上的外部进程保持原状。

336 的 S 梯度失败未放宽为 allclose：338 证明 8 个 intra-op 线程下，原始 S
loss 自身重复反向也不能逐位复现；最大绝对差 1.86264514923096e-9，仅出现在
noise 到 backbone atom embedding 的梯度。单线程所有源/桥接梯度完全相等，故
严格单测限定单线程并恢复线程数，342 实际通过。未据此认定某个具体算子为原因。
源 raw loss/count、RNG 和实现保持；原失败与诊断保留。

每次定向测试记录前后文件 SHA。331/332/333/336/342 的源码副本保存在外部
`source_snapshots/`，342 共 15 份；测试后发生的源码变动不冒充已测试内容。

## 用户已明确的面板决定

2026-10-25 用户答复：“允许用现有 SoM 二分类满足分类覆盖”。依据是冻结
ExpansionRx 的九个字段全部为连续回归；不自行阈值化。实际开发面板与指标、
两种读出合并方式、无标签分子抽样上限在 DECISION_RULES 和 dev_panel_v1 中登记，
在模型比较前提交；本轮合成单测不会用于架构选择。

## 尚未验收

三 GPU profiler、A/B 数值与训练轨迹、真实 1,000 分子逐字段过拟合、真实 D-3
三 GPU SDP smoke、真实 checkpoint 完整快速评估、架构比较、配方/B-star 和
冻结交接均未完成。2026-10-25 用户已明确答复 D-1 至 D-6“尚未交付，继续 S 与合成部分”；
接口相关代码标注模型侧 DRAFT，不自行编造数据线权威契约。

最终模型/配方只有在阶段 6 的具体结果经用户确认后才冻结；阶段 7 后开 PR，
不直接推 main、不自行合并、不恢复任何旧训练队列或旧已完成工作流。
