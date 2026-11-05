# 执行与复现记录

2026-10-29 最新用户修订：[每日汇总](DAILY_20261029.md)、[等变性 v2](EQUIVARIANCE_RULES_V2_20261029.md)、[全部 FP32 补偿不采用归档](FP32_COMPENSATION_ARCHIVE_20261029.md)。优先直接实测 S 上 C1-a；每日一份汇总、每周记账。下文旧门槛与诊断待办仅为历史。


2026-10-29 后续：[A00-v2完整通过、Native CP19000与逐字段FP32复查](STATUS_20261029_A00_V2_CP19000_SCALAR_REVIEW.md)。九组旧PASS已完成首项当前源码复核；500步差异为0，原容量消费者实际C0。Native继续20k，残差仍不采用。


2026-10-29 更新：[CPU 自动内存、A5-v2、残差 FP32 与 Native 续接阶段报告](STATUS_20261029_CPU_AUTO_A5_V2_FP32_NATIVE.md)。四套完整 CPU 回归通过；A5 和残差 FP32 仍未通过科学门。旧 A 类 PASS 按新规则逐项复核，D1 joint 与模型侧真实 D3–D6 验收继续待办。


2026-10-26最新：整份模型指南仍未完成。A采样桥接+B候选wire/provider已完成独立与整合回归；最新Root3789c19865f70f80191986675cb13b606ebd210b为2473PASS/2CUDA skip、104文件，实际4项A→B→原trainer贯通全PASS。新独立C4组合检查则为48FAIL/9控制PASS，误差归因继续，不将原单独测试当组合接受。见[候选接口与完整限制](03_candidate_interfaces_20261026.md)及[289条原时间点审计](COMPLETION_AUDIT_20261026_v1.md)。D1draft.3可读而未最终冻结，最终D3–D7未交；没有最终recipe/B*、main更新、tag或正式预训练授权。


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

## 性能实现整合与实际新进度

阶段1报告与图表已发布至model-v3：33671a8f8c13a5907d34102a649a7d0a998c6e54，
与本地ee0c16e7ca3b981c05f1a12c13ed5cb3deb5763d的tree精确同为
349da0be48af8adaa4779b95179686c4670e5c6f。GitHub main仍未修改。

396实际COMPLETED/0:0、21秒，32项A接线/确定性CPU检查全部通过且源码前后相同。
之后发现A00显式fused=False会跳过Torch2.10的默认foreach选择；新make_adamw在
False时完全省略fused，True时才请求fused=True，不强制foreach。完整性能分支
a6c62038643b69d4e44dbb2eb2adf235472cd344经401实际COMPLETED/0:0、75秒，
2,196 passed、1 CUDA-only skip，源码前后校验通过。性能分支现整合到主树，
整合后完整回归另行记录。405已在4090提交真实20固定批次加500更新A00控制，
代码仍a6c6203，原生输入与阶段1同snapshot；未据其启动状态授予任何数值验收。

W&B归档补齐实际393 COMPLETED/0:0、5秒，现21个唯一运行，含352–354失败、
365–367原生性能测量及371/375失败对照；逐文件SHA、原生history与真实终态保留，
原件不删，仍未在线同步。389/391在compute缺少quota/sacct查询能力时各失败2秒，
均未复制SDK；v5使用登录节点实测、SHA绑定且启动时不超过120秒的quota/终态收据，
不伪造资源/状态、不绕过验证。旧归档索引11项保留并加入10项。

下游materialization387实际FAILED/1:0、77秒，旧SoM materializer错误期待直接
native_source_graph_binding属性，而原reader只在sealed provenance中提供。
新兼容桥仅可暴露原证明；399新7项fixture首先因缺少sample_id全部失败，
同次89项旧/已有检查通过。402修正fixture后6通过/1失败，进一步发现旧source3D
坐标fallback为None，不能仅修改断言掩盖。正在对原conformer的FP64坐标及既有
sealed hash作窄兼容，既有frozen reader/materializer均不改。未发布partial store。

SA-4首轮398实际COMPLETED/0:0、15秒，58项架构/视图/既有头与loss检查通过，
只证明合成组件；配置导出、checkpoint/runner与两视图完整接线继续开发。
真实D-1–D-6验收、科学架构选择与配方/B-star仍按原阶段门槛执行。

## 架构与既有TRAIN工具的进一步整合

性能实现已公开至model-v3的61658a4c1f472de035601dbedc17809315774784，
tree与本地65512d0精确相同。三GPU真实A00控制405/410/411分别为4090/3090/5090，
均通过20个真实固定批次的前向与逐参数梯度门槛，500步轨迹仍在运行。
尚未采用任何A选项。执行code SHA一律由Git/配置收据机器读取；本次修正文档中
A6提交号的一处41位手录错误，科学配置与实测源绑定一直使用正确40位值。

SA-4实现b3e76f9的412整树2,162 passed/1 CUDA skip，实际C0/55秒；
合并44a543a后415整树2,231 passed/1 CUDA skip，实际C0/50秒。
包含共享RBF/元素对变换、封印的生产S内存builder、配置导出、真实样本checkpoint/H0桥，
以及两视图实际loss/metrics/容量/恢复接线。旧默认与H0接口保持。
这不构成阶段5科学验收；D-5/P等代理输入仍未交付，未据预训练loss选择架构。

SA-3兼容与不变量由407十项/409三项实测通过。413 metadata prepare实际C0/18秒，
目标解码0；原379完整selection及各原始contract SHA均精确相同，只更新源码绑定。
原387观测RSS最大2,075,570,176B，421申请32GiB、外层RSS收紧到28GiB，未扩大内部上限。
421实际C0/122秒，17,602条记录COMPLETE_FOR_SELECTED_TRAIN，cohort replay精确相同，
outer_target_records_decoded=0；模型owned新store未生成新属性标签，不替代D-1至D-6。
原385/387partial未复用。421的training_store/manifest原始SHA见外部materialization_result.json。

SA-3整树416在不存在的可选model/v3 glob处启动失败0秒，未运行测试；417依赖作业经
精确JobID/UID/脚本路径核验后仅取消本次未启动任务。修正wrapper后418运行2,096项，
两个旧spawn测试触发原45秒/30秒启动超时，其余2,094通过，失败保留。
同一源码d5edce2未改超时或断言，改4个pytest进程的420全部2,096通过，实际C0/73秒，
源码前后SHA一致。主树整合后的全量回归另行记录，真实九任务评估仍待执行。

C2采用局部noisy几何分桶到三维位移的分析草案，已向用户说明先按推荐方式实现；
旧pair-distance查表数值不冒充坐标RMSE。419核心合成数学检查十项PASS，C0/19秒；
新源角色与runner检查待测，未启动真实拟合，具体方法/预算另行预注册。

## 500步控制、日志与监督器修复

405/4090实际C0/3407秒，411/5090实际C0/2516秒；均完整通过20批与500更新，
各消费201,216个base structure records。它们是A00控制，不能当作已采用提速或独立吞吐。
410/3090在261个已记录更新后因监督器误把psutil墙上时钟创建时间变化作为身份变动而失败，
实际FAILED/1:0/2424秒；不能推断数值失败，也不能授予未完成的500步验收。
精确诊断中仅created相差1秒，其余kernel boot/start、PID/UID、PGID/SID、argv、
cgroup与Slurm身份一致。未扩大旧信号权限，旧PID及选中GPU进程已独立核验消失，未手动发信号。

6df0aa5仅修正授权字段：created保留诊断，稳定内核生命周期字段仍逐项精确匹配。
428实际12项PASS/C0/8秒，433分支完整2,198 passed/1 CUDA skip，C0/106秒。
数学源与405逐文件SHA相同。3090新任务438从零完整重跑，不复用410部分状态。

评估SDK目录与计量修复9638f7c经426十一项（含真实offline SDK）PASS/C0/7秒，
429完整2,098全部PASS/C0/54秒；current包与模型计算不改。
434真实CPU准备C0/7秒、目标解码0，重新核对实际B3权重与完整配置，并封印物理packing。
437真实完整九任务GPU评估已启动，reference_kind明确historical_sanity_only/384；
包含两个读出、匹配随机384、冷H0 cache、bootstrap与SDK.finish，尚未声称满足1GPU小时。
初次交互SSH检查曾读取后续提交文本，未产生作业；后续一律ssh -n，只有实际437计为本次评估。

431坐标查表源/runner新十五项PASS/C0/7秒；432真实SDK探针C0/5秒，
两个原生history行、四种真实链接及闭合均验证，native/optimizer更新0。
用户已明确选择局部几何分桶预测三维去噪向量；C2源码与参数须完成整树/公开预注册后才拟合。

## C2合并准备、完整面板与资源约束

441的C2分支完整回归为2,187 passed / 1 CUDA skip，实际C0/114秒；
442的可选checkpoint导出分支为2,203 passed / 1 CUDA skip，实际C0/95秒。
443对可靠日志/监督整合主树392643e的完整回归为2,255 passed / 1 CUDA skip，
实际C0/88秒。源码前后SHA均相同。C2整合后仍须单独完成主树全量回归；
分支回归不替代合并后验收。导出分支尚未合并，不改正在执行的457源码。

437实际COMPLETED/0:0、543秒；九任务乘两读出共18个单元全部完成。
guard测得包含冷H0缓存、匹配随机384、bootstrap与SDK.finish的墙钟为
541.2297593103722秒，连同guard cleanup为541.2729373024777秒。
这是historical_sanity_only的384维流程验证，不能选择v3架构，也不能声称512维耗时。
result/guard原始字节保留，独立原生SDK历史核验及归档仍待完成；其Torch峰值可能
受cache helper重置影响，尚不作为全程GPU峰值报告。

449归档实际C0/2秒，累计28个唯一run，包含405/411完整与410失败的两个SDK，
以及432的探针。原SDK和失败保留，离线未同步。437的大于50,000条history须新增
有界只读导出，不能被旧归档扫描上限截断后冒称完整。

456（4090 A01）与457（5090 fused AdamW）使用冻结的可选导出分支，
只有真实20批/500更新数值门槛及SDK收尾通过才导出；外层终态另审。
438为3090 A00从零重跑，仍在执行。当前无任何A项或架构选择获科学验收。

compute-0-20现被其他用户104 CPU、mem=0的作业4520450占满；456处于资源等待。
未修改或取消该他人作业。依用户AGENTS的compute-0-20限制，新增纯CPU作业
暂不迁移；已请求本轮CPU回归/C2临时使用21/22的明确例外，未收到答复前不执行。

用户后续已明确：“cpu任务请提交到可用的cpu节点，这几个节点只能提交模型训练
和微调等gpu任务”。此新指令覆盖上段待答复状态；CPU回归、C2与SDK核验投
现场可用CPU节点，不投20/21/22。站点cpu分区为compute-0-2及8–19，实际
按全用户CPU/声明内存、可用内存、Slurm分配和不少于16核核验；不改其他任务。
regression改为必须显式绑定CPU expected-node，不保留隐含GPU节点默认值。

C2预注册已公开1a8c124571ddf37f87ae06ef9971efa85e417f95，其tree精确等于
执行树dd6cbaf的6ea0f055d9dc35b1319ad6269c8c5bc492ee61d5；新CPU guard
提交另记，不将其SHA混作方法预注册。未启动真实C2前仍须主树完整回归通过。

新CPU节点验证458在Git命令缺失处失败1秒；459因pytest负例夹具的合法测试链接
被生产输出census拒绝而失败35秒，均保留。新test-only adapter只在预先声明的
pytest目录按lstat计量、绝不跟随测试链接；生产/private census、2GiB和RSS上限不改。
472主树59b9ec2实际C0/211秒，2,280 passed / 1 CUDA skip；473实际C0/203秒，
proxy计划12、precision相关29、B3核验21、primary512启动器22，共84 passed。
前后源SHA相同、外层成功闭合。新CPU Git工具独立放外部bin，系统与科学源码不改。

474真实B3核验在100,000条native SDK总记录上限失败5秒；56,738是history行而非
所有protobuf记录。原报告/源SDK不改。新增读取器将总native与history两个预算分开，
保持原history完整匹配与所有科学门槛；修订仍需新CPU验收，不能冒称核验完成。

475 C2 bind实际C0/4秒，native_geometry_records_decoded=0；477继续纯元数据
selection。实际执行树为已全测固定ecdb6eb的独立C2树，预注册仍为公开1a8c124。
主树后续整合不会更改该执行源。拟合须等selection/原角色与人口审阅闭合。

主树完整回归的472产物计量约1.94GB，新增完整checkpoint测试可能超过同一2GiB根。
后续用显式互斥、全覆盖的回归partition分开测试产物，每job预算不变；全部分片
实际C0与源/文件并集校验后才授整树通过，不删除旧测试产物或扩大默认输出限额。

## 后续整合与真实闭合（2026-10-25）

可选导出8130b37的478–481整树2,285 passed/1 skip；precision整合bdd03f4的
498–501整树2,294 passed/1 skip；proxy计划整合e692e69的506–509整树
2,306 passed/1 skip。每组四个实际CPU作业均C0，文件互斥并集完整且源码不变。
决策证据39项在483通过；独立分支ee843b0的502–505整树2,319 passed/1 skip。
当前合并后整树验收另行执行，不把分支通过冒作合并后通过。

438/3090 A00从零完整20批和500更新通过，C0/4244秒。457/5090 A06 fused
AdamW实际FAILED/1:0/2272秒：20批通过，500轨迹中477点超过原1e-3门槛，
不采用该选项且无导出。485优化器独立合成梯度诊断C0/41秒，不能代替原真实轨迹。
486/5090新A00控制C0/2332秒，完整20批/500更新后导出512x6权重；READY仍标
待外层终态核验，启动真实512面板前另做只读准入，不复用失败457。

487独立B3原生SDK核验实际C0/7秒，完整170,299 native记录、56,738 history，
clean EOF和退出0，逐指标匹配。原437报告的待核验字段不回写；独立证书与原SDK
SHA绑定。B3仍仅384维历史流程验证，不作架构选择或512维运行时间证据。

477元数据准备实际C0/146秒、几何解码0。482 C2真实拟合FAILED/1:0/1648秒，
只解码8,192条TRAIN/436,120 atoms，在原LSQR检查处失败，未读取验证几何。
旧runner未保存实际stop/iteration，不能断言耗尽500步或归因。原失败保留；后续
仅TRAIN诊断须另固定源码/规则，不把诊断或更换求解器结果冒作v1基线通过。

513和514分别完成独立进程的CPU bf16合成CLI及恢复，实际C0/16秒和C0/13秒；
原生SDK与恢复lineage仍待独立核验，不构成D-5真实20k代理或B精度验收。

决策证据整合0e23364的517–520整树2,345 passed/1 skip、100文件并集完整；
四个CPU父作业实际C0，独立完整证书decisions_postmerge_full_v1.json。
521新专项测试C0/204秒，sample-budget23与C2报告23全部PASS且源SHA不变，
监督器remaining=[]/first_failure=null、private sampling failure=null。
样本预算分支686f9d3的528–531整树2,317 passed/1 skip；当前合并后另测。
新API补齐非原milestone的最终样本预算保存、逐样本边界、恢复与不可变评估outbox；
没有默认6M或WSD分叉，也不授予D输入权威或实际训练验收。

522 primary512首次CPU准备实际FAILED/1:0/196秒：原make_request文件引用
仅含path/SHA，而READY另含bytes，直接字典比较被拒。没有读取下游目标或执行
GPU面板。v1与失败保留，修复用新v2和真实接口形状测试，不削弱原字节核验。
525在5090执行已公开预注册的A05 compile-only20/500验证，尚无科学结果。
另现场核实node22 GPU有其他用户gmx进程，不投本次任务、不改变其作业。

样本预算整合5f96bf2的533–536全量回归2,368 passed/1 CUDA skip、101文件并集
完整，四个父作业实际C0、源SHA不变。537 primary512启动器v2的30项真实接口
形状/拒绝检查全部PASS，C0/7秒；540重新CPU准备，不复用522的partial目录。
公开B3完整18单元聚合报告和一行run摘要，保留负单元/单seed/384维/显存计数器
范围等限制。实际执行的profiler-v2、9638 evaluator、B3独立核验器和已测primary512
v2工具字节快照保存在tools/model_v3/analysis_sources/executed_methods_20261025，
SOURCE_PINS逐文件绑定原路径/执行SHA，原冻结目录不改；不声称副本已搬迁执行。

544实际primary512面板使用540闭合的新v2请求启动，完整选中TRAIN人口不变，
候选和匹配随机均512×6、18单元及1,000 bootstrap，尚待真实结果与独立SDK核验。
525 compile在20批阶段实际CUDA OOM/85%保护FAILED，C0门槛未授；546关闭主干
checkpoint同GPU原batch也因85%容量失败（FAILED/39秒）。细节与失败原件见
02_A_actual_runs_20261025.md。549关闭头部checkpoint另测，未预判数值或速度。

550因Root测试清单将三条路径拼成一条而在pytest前FAILED/1秒；原错误清单与失败
保留。新独立清单551实际C0/6秒，C2 TRAIN诊断20项全部PASS、源前后相同，
supervisor remaining=[]/first_failure=null。新诊断协议与精确源已固定；须本提交
公开后才实际重放TRAIN，不读验证，不改原482失败或猜测其未保存的stop。

本轮公开cd0c434bb39824cd75c24d7c6de0531946da1de5精确tree为
eecadc77e71a4d290f7a6b00c7d0906e14e58f3f，与local c65db8b完全一致；
GitHub main仍037546cd7f07b32dbb46bc21a69109dfd273f8da。无freeze/tag/正式预训练。

544 primary512实际C0/512秒，含guard cleanup509.329587999秒；完整18单元/
1,000 bootstrap，FP32运行策略前后相同，实际产物1,609,482,708B低于2GiB。
565独立reader/report37项通过，C0/3秒；566真实原生SDK核验及报告C0/8秒，
170,295 native/56,738 history逐标量和step匹配、clean EOF/exit0，原core标志不改。
主汇总0.126942645758；回归MAE和SoM1-hit@1、全部负单元、单seed限制见完整报告。
不是模型选择或充分训练验收。原SDK及cache保持，归档复制另记。

557新归档工具24项PASS/C0/8秒；562实际归档C0/9秒，438/457/485/486/513/514/
482/525及B3证书487全部闭合、索引41唯一run。485真实101history/315native与mirror
匹配，513→514恢复样本0–7、updates2→4、samples4→8、cursor6→10和两段原生
SDK payload均独立核验；不构成真实D-5精度验收。失败525原85%/CUDA OOM和未完整
SDK均保持FAILED，未在线同步。源码和原件保留，入口W&B_训练记录.html不变。

559在公开注册后实际提交TRAIN-only诊断到CPU12，RSS24GiB/整作业输出128MiB/
3300秒不增加。外层CPU guard也明确128MiB，计入private、日志、journal和预留；
未读取验证。原482仍FAILED；诊断实际结果、后续是否需新的基线solver协议另记。

569实际v8归档C0/12秒，546软容量失败和544/566完整原生记录/CSV均归档，索引44；
568对应17项PASS/C0/2秒。586 v9测试24项PASS/C0/2秒，587实际归档559/549 C0/3秒，
索引47。559 SDK两行按固定logger与保存结果投影逐字段验证，明确无原fsync mirror。

559实际C0/1486秒：原受控500次stop7，active/Jacobi同目标stop2/74次，solver分别
34.5504945s/4.7119295s；全部工作含原矩阵构建时间，不能只报solver作为整作业。
VAL读取0、来源和CSR未变，原482 stop未知不推断。后续用独立新协议接受这份TRAIN
参数并首次VAL；不回写559为基线通过。575基线v2库17项PASS/C0/6秒，591恢复31项
PASS/C0/10秒；新ADOPTED协议和源须先公开。详C2_ARTIFACT_BASELINE_V2_PREREG.md。

549 A03/head-checkpoint-off实际完整20/500 PASS、C0/2196秒。随后同一UUID的单模型
A/B/B/A 576/579/580/583分别C0/77/108/70/85秒；2warmup+20测量，无profiler，输入
receipt精确相同。588实际CPU报告C0/2秒，基线152.070610737、候选131.706676698
base records/s，候选/基线0.866088957。本次未见收益，不采用head-off；四个窗口
原值/波动完整保留，不因数值通过就宣称提速。独立SDK归档另行追加。

549监督日志1043个采样观察的owned进程组CPU RSS最大18,470,543,360B（非exact peak）。
后续589 TF32/590 distance-checkpoint-off各申请32GiB、明确外层RSS28GiB，预先核验
全用户加新两作业声明64GiB低于node21的85%及实际MemAvailable；数学/数值门槛与
源码8ece不变。实际589 FAILED/122秒，20批数值门槛未通过；590 FAILED/30秒，
GPU85%容量失败并保留清理故障。无任何训练配方冻结或学校服务器提交。

C2首次VAL入口595实际FAILED/1:0、2秒，错误为本地/公开Git提交号混比，发生于
任何原生几何读取及输出创建之前。v3修复保持科学定义，599 CPU8/16核40项全部
PASS/C0/60秒（包括真实559 metadata-only）。旧v2、输入与失败原件不改。
新协议先经真实TRAIN产物独立预检，再公开精确tree核验，之后才首次VAL。
594 v10归档测试41项PASS/C0/14秒，596实际归档四个ABBA作业C0/7秒、index51；
原生日志真实22行含2warmup+20计时逐字段核验，保留0.866088957负结果，无在线同步。
598 C2报告工具33项PASS/C0/10秒；后续修复源需新报告源绑定及独立测试。

Public C2 identity revision0f26274 has exact tree87d533a matching local916697e;
actual602 TRAIN array-only preflight C0/6s preceded publication and all VAL access.
603 fixed1024VAL actualC0/127s, currentTRAIN0; independent606 SDK/report C0/4s,
31 native/two scientific rows, complete config/summary/steps/exit0/EOF. Report
tests60144PASS/C0/67s; PNG reviewed byRoot. No weights or8192-member receipts
enterGit. Corrected complete analysis is05_C2_coordinate_baseline.md; original
482/595 failures preserved. Archivev11 tests60440PASS/C0/3s;605 actualC0/1s
adds589/590 four nativeSDKs toindex55. 589 child2 vs Slurm1 and nativeexit1,
590 abort-6/Slurm1 and header-only SDKs remain separate domains, no fake histories.

Point-in-time owned-model parent ledger job_ledger_C2_report_publication_v7.json
contains172 actual parents,568112 allocatedCPU-seconds and26241 allocatedGPU-job
seconds, including failed attempts. Only4520456 remains pending in this capture.
GPU-job wall is not measured utilization/GRES reservation; prior CPU jobs onGPU
node names are not mislabeled GPU work. Eleven actual paired A parents now have
typed CSV rows and raw configuration/Slurm bindings; paired wall is not speedup.

C2 independent verification-backed archive v12:618 tests49PASS/C0/5s;621 actual
C0/ElapsedRaw0, index56 unique entries including603. Zero accounting seconds are
whole-second Slurm resolution, not zero actual work. The unchanged606 certificate
is reused explicitly; no additional native scan/mirror is claimed. Raw SDK and
safe aggregate reports are copied; full fit/result/selection are hash references,
LOOKUP/NPZ unopened. Original482/595 failures remain intact. Root report publication
dbb53d2 has exact tree4a9a213 matching local8fa743e; no main update or recipe freeze.

A later read-only discovery found D1draft.3 in the data-line worktree. SA2review
31/31 source SHA stable,264registry metadata rows with exact line references;
no target data read or scientific test claimed. Root appended reviewed opinions
underactual docs/interfaces/training_format_v3.md without altering the original
15581bytes. Full report, field audit and append receipt are inmodel_v3 docs/results.
The contract remainsdraft.3; no sharedv3.0 signature, data Git commit or newlabel
transformation. The independent old-native S bond loader transport repair uses
a fresh isolated worktree from8fa743e; Root will require targeted tests, branch
full regression and postmerge full regression before production integration.

S bond transport actual targeted643 C0:49PASS/2CUDA skips (new21=20PASS/1skip). Independent branch648–651 and integratedRoot656–659 complete disjoint union102files, each2388PASS/2skips, all source/outer C0. Branch 8e1223ba79861f7e3f8d9d453d7b3599ee447d4d; actual integratedRoot 91f0c40a78478447a14ef2e8e91f05c07e0f5019. Old native raw/status/count and all parameter gradients remain exact on controlled CPU; no D1 codebook or new label transformation.

Latest point-in-time owned model ledger contains188 actual parents,575712 allocated
CPU-seconds and26241 allocated scientific GPU-job seconds, including all failures.
Only4520456 is pending; GPU-job elapsed is not measured utilization. The source
accounting method remainscapture_ledger_v7, and the raw query/receipts are retained.
No final model/recipe configuration, tag, Phase7 acceptance or formal pretraining
is inferred from completed source/tests/reports; interface and finaldata remain pending.

## 2026-10-26 候选发布与诊断补充

候选代码 exact tree已发布为ce7cbf5，完整新Root回归仍待完成。实际GPU组合矩阵2/48通过；原1e-5门槛保持。新增实际55/24/52项工具QA、两幅结果图及C4/A01实验前注册见[Root补充报告](reports/20261026_v2/ROOT_ADDENDUM.md)。

27项C4 inference-context修订和45项CPU身份修订已分别实际C0；独立新八片回归仍待完成。详见[第二份补充](reports/20261026_v2/ROOT_SECOND_ADDENDUM.md)。
