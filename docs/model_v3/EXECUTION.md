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
| 4520343 | 4090 合成 profiler 重试 | compute-0-20 / 16 CPU / 64 GiB / 12 min | COMPLETED/0:0，228s；仅 3 个合成分子，2 测量步；run 8rdupcyh |

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

## 后续实际验证与整合

下列作业也均为本任务精确登记的父作业，未列出的 ID 不纳入本任务成本。
所有 CPU 验证仍在 compute-0-20，每项16 CPU，CUDA显式隐藏。

| Slurm ID | 实际结果 | 执行版本 / 范围 |
| --- | --- | --- |
| 4520346 | COMPLETED/0:0，81s，2,066 passed / 1 CUDA skip | SA-2初版50788d5 |
| 4520347 | COMPLETED/0:0，140s，2,067 passed / 1 CUDA skip | SA-2有序优化器绑定28edd616，10项trainer集成已通过 |
| 4520349 | COMPLETED/0:0，20s，九类头全部R²≥0.95 | 固定合成H0；发现共享W&B core缓存，完整自有归档未通过，原结果/SDK保留 |
| 4520350 | COMPLETED/0:0，17s，31 + 37 passed | native绑定/存储/归因 + checkpoint/H0桥；34份源码前后SHA相等并已快照 |
| 4520351 | COMPLETED/0:0，18s，九类R²与349完全相等 | 仅日志目录修复1ac3d8c；原生SDK历史和自有归档验证通过 |
| 4520355 | COMPLETED/0:0，53s，2,067 passed / 1 CUDA skip | SA-2合并到主树76bceb59后的完整回归 |
| 4520358 | FAILED/1:0，78s，2,075 passed / 1 failed | 唯一失败为旧spawn测试首次取数30s超时；新桥接全部通过，原失败保留；B3后置检查未执行 |
| 4520360 | COMPLETED/0:0，37s，26 + 1 passed，真实B3检查PASS | A工具26项、原30s测试原样隔离通过；实际B3权重SHA重测、安全加载及两分子H0完成，无下游目标/旧评分读取 |
| 4520362 | COMPLETED/0:0，8s，9 passed | 分次profiler采样协议与旧profiler回归，源码前后SHA相等 |
| 4520363 | 完整同版本回归2,076 passed，无skip | SA-3同464b96ef，未改原30s门槛；原358失败不改写 |

原生 S 三卡 profiler 为352/353/354，分别在compute-0-0/20/21的3090/4090/5090，
每项16 CPU/64 GiB/45min，执行提交
`f9245bda42f4ce9933f046c0a6b373a74546338e`。三者均完成20个测量批次，但均未验收：
352在汇总期触发56GiB进程树RSS上限，FAILED/1:0/1114s；353与354在trace导出时
触及原输出预算，分别FAILED/1:0/1071s与1552s。监督仅处理实际绑定的自有进程，
最终remaining为空；原步骤、失败和SDK保留。不得把已执行训练步当作报告验收通过。
原始shard snapshot预先固定raw SHA为
`d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f`；
v2 adapter仅在副本内投影node-local st_dev，原JSON/LMDB不改。
compute21的独立task known_hosts与受信Slurm4515020的ED25519指纹严格一致，
没有关闭host checking或更改全局known_hosts。CPU/显存/临时与持久输出预算保持原上限。

343旧trace的独立CPU分析已在350完成：3,102个唯一kernel，重复0。
旧trace缺少新tile重算标签的部分仍保留unknown，不用inclusive区域相加宣称瓶颈。

合成容量测试使用固定随机512维H0、每个toy分子3个原子，不训练完整主干，
不替代D-3真实逐字段验收。R²范围0.9664153246869207–0.9952283447302109，
每例25–100次更新。修复日志后数值完全复现，未改fixture/seed/loss/optimizer/阈值。

统一阅读入口`W&B_训练记录.html`已增加模型v3链接，命名归档位于
`runs/phase1_full_corpus/wandb_archive/model_v3_20261025/`。337/343及351九个run，
共11份原生记录已逐文件SHA与history行数验证，原件保留。对343精确在线同步尝试
退出1，原因是服务器未配置W&B认证；不宣称在线可见，不读取或保存新凭据。
失败日志为外部`wandb_sync_343_v1.log`。

SA-2合并提交`76bceb59d5372515fb10f8916b89ec2bb42fd4ed`已由355完整验证。
SA-3实现快照`464b96eff38a7b73b2dab5b7fd68bfd7b1146e58`仍待完整回归/整合。
为不改变352–354的执行源码，A工具后续接线在独立`MFM_model_v3_sa1_a` /
`model-v3-sa1-a`工作树进行，起点f9245bd。尚未接受A/B提速或任何架构选择。

资源补救另在`MFM_model_v3_profiler_v2` / `model-v3-profiler-v2`实现，362实测后
checker通过，预先提交`dc22d3f3bb68ce6949bf40f38e677f74a35c407d`。详见该树
`docs/model_v3/01_bounded_profiling_v2.md`：固定20测量更新，分别采集相对0/10/19
三步，逐份导出并释放；主吞吐量来自其余17个完整step的实际墙钟。所有原阈值与
资源上限沿用；三卡复测365/366/367已提交，分别3090/4090/5090，尚待闭合。

## 用户已明确的面板决定

2026-10-25 用户答复：“允许用现有 SoM 二分类满足分类覆盖”。依据是冻结
ExpansionRx 的九个字段全部为连续回归；不自行阈值化。实际开发面板与指标、
两种读出合并方式、无标签分子抽样上限在 DECISION_RULES 和 dev_panel_v1 中登记，
在模型比较前提交；本轮合成单测不会用于架构选择。

## 尚未验收

A/B 数值与训练轨迹、真实 1,000 分子逐字段过拟合、真实 D-3
三 GPU SDP smoke、真实 checkpoint 完整快速评估、架构比较、配方/B-star 和
冻结交接均未完成。2026-10-25 用户已明确答复 D-1 至 D-6“尚未交付，继续 S 与合成部分”；
接口相关代码标注模型侧 DRAFT，不自行编造数据线权威契约。

最终模型/配方只有在阶段 6 的具体结果经用户确认后才冻结；阶段 7 后开 PR，
不直接推 main、不自行合并、不恢复任何旧训练队列或旧已完成工作流。

## 阶段1实际验收与当前诊断

原生S复测4520365/366/367均COMPLETED/0:0；独立分析369处理9份trace，
汇总378实际COMPLETED/0:0、13秒。主agent核对17步吞吐分母、三卡相同输入、
20步峰值、失败成本及环境差异，并逐张查看三张PNG，阶段1报告现已验收。
报告与逐运行CSV/紧凑JSON/三张PNG位于docs/model_v3及其results目录。
原始summary生成时的review_status保持原字节，不追写为自动科学验收。
dist_mlp占三个采样窗口汇总GPU busy的72.7582%/78.7592%/76.0836%；
当前证据没有证明其为峰值显存的因果主因。SA-4可据此安排实现优先级。

A旧源对照375未过逐参数梯度门槛，失败仅在六层dist_mlp末层bias的极小梯度；
381零更新诊断发现旧模型首遍与后续遍自身亦有同类差异，默认模式不能授予A验收。
确定性控制384实际COMPLETED/0:0、85秒，六组比较的全部输出与逐参数梯度
均通过原门槛，失败参数为空；模型状态不变、优化器更新0。这是toy零更新诊断，
未运行真实20批次/500步验收或采用A选项。将对baseline与candidate同时显式设置
确定性控制，先验证A00；原逐参数门槛、分母和所有参数仍保留，不以全局误差替代。
新增诊断实际代码044a29f，后续提交号另记。

既有下游TRAIN数据准备不依赖新D-1至D-6。379实际C0/25秒，仅元数据选择，
target_records_decoded=0；request raw SHA为
ed8b4682ece4f11bf6645ab266000a1f7d26f0a071730c61f3bd1a487b243da1。
预注册使用已公开39cf4929299cd227a3c361183a4b26c8b1405900（与本地3b19230
tree精确相同）；SA-3执行代码6650501。已审计原字节framer与单选中成员解码边界，
真实materialization385实际FAILED/1:0、5秒，目标解码前SHA校验拒绝。
Root手录提交参数将64位SHA误抄为65位；已从原preparation_result机器读取64位SHA，
并与实际sha256sum相符。原request未变、原校验未放宽，新v2 wrapper保留失败wrapper。
所有旧失败和原数据保留。SA-4独立分支已按指南开始实现，不据此选择架构。
