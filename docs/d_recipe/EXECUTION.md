# D 线执行登记

2026-11-20（Asia/Shanghai）。用户明确要求严格执行本任务书的 **D 家族**实验，取代此前消息中的 S 家族名称。

任务书来源：`docs/s-d-taskbooks-20261119` 分支的 `docs/d_recipe/TASKBOOK.md`，原文保留。本次完整执行请求授权阶段 0 先行及书中已有的条件运行和 9M 确认；不增加训练臂。

## 分支及范围

- `d-recipe` 从已发布 p-recipe 提交 `49f1c6bc9d699085474fa86b7d5638a3c5231246` 建立。路径 `/share/home/zixiao/descriptor_analysis/MFM_d_recipe`。
- 阶段 0：`data-d-descriptors-20261120`，从已发布 data-v1 提交 `bc47699c709f57bb00108473f17bf4652333d2ec` 建立。路径 `/share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120`。
- P 线的实际未提交工作和在跑任务保持原样；仅包装既有 API，不复制或修改 P 训练与评测文件。

## 执行顺序

1. 阶段 0 过滤规则预注册 → CPU 环境准备 → 固定约 5000 TRAIN 分子 → L1/L2 成本测试 → 全量及下游导出 → 新字段 TRAIN 统计 → 生产清单。
2. P 配方冻结且其 9M 已提交后，将实际 P 配置键逐项登记到训练预注册；验证真实 loader、逐头过拟合和 SASA 原子对应，然后 D-R0/D-R1。
3. 按任务书顺序推进 D-L1、D-L2、D-G1、条件 D-K1 和条件 seed1；每个对照只训练一次并复用。
4. 完成规定诊断、开发面板 A/B/C 及组成参照，与基准线交付特征；冻结 CURRENT_BEST，执行规定 seed0 9M；报告、一次完整回归和仓库检查后开 PR，不合并。

## 当前依赖

P 配方 `CURRENT_BEST` 尚未冻结。F1 日志已记录 3M 与 GPU 读出完成，CPU 统计仍待正式关闭。因此 GPU 训练尚未启动；这不是 D-R1 的 TIE/LOSS 或完成结论。阶段 0 接收验收、全量产物、所有 D 训练与最终报告均未完成。

阶段 0 的 `configs/data_d_descriptors/preregistration.json` 已在读取描述符分布前冻结并发布；训练预注册尚未发布，不能用占位的 P 配方或未核实块权重代替最终配置。

2026-11-20 新逻辑检查已实际通过：compute-0-17 原生 SSH 单核短程测试，UID1278、Python PID1392349，未伪造 Slurm 身份。日志 `/share/home/zixiao/descriptor_analysis/D_native_cpu_tests_20261120_1622.log`：215 tests、OK、exit0，总耗时5.67秒、峰值RSS923640KiB。所用 pyarrow25.0.1 原地只读复用现有 P deps，其他包沿 chemprop 环境，不安装或修改共享环境。NFS 实际挂载点 `/share/home` 的守卫已修正并覆盖测试；本地测试夹具在逐项核查容量的 `/tmp` 下，预留峰值16MiB，不复制真实数据库。

旧7113/7202/7261/7346/7347均已在零运行时间取消。后续成本作业4537408、afterok成本的规划4537409，以及开发/基准无标签输入准备4537410/4537411已重新提交；截至16:21仍PENDING。新逻辑通过不替代真实64分子接收验收，不表示阶段0交付或任何科学臂完成。

后续补齐固定层3–6的读出缓存与诊断接入，新逻辑套件扩展到223项并再次通过（CPU17原生SSH单核，UID1278/PID1392956，日志 `D_native_cpu_tests_20261120_1638.log`，总7.42秒、RSS925336KiB、exit0）。中间层从原开发面板前向捕获，6层主读出及其CPU统计复用，只有登记条件拟合3–5层探针。此处只证明接口新逻辑，不表示实际D读出完成；缓存尚未生产或登记正式存储预算。

## 数据处理与判定

19:55CST 更新：全量结构生产已实际关闭，1201795行，TRAIN1194228、VAL7567、额外VAL_DIAGNOSTIC0（原诊断分子含在既有角色中），source_missing_rows=0、producer_alignment_checked=true；准备耗时4470.94秒。4537508随后进入L1计算，未重跑源准备或成本面板。

新逻辑270项在正式CPU17单核4537544完成0:0，Slurm耗时7秒，原日志MFM_d_recipe_data_tests_4537544.out。QM9 D3配置datasets=[qm9]/native_only只用其完整原生坐标，ExpansionRx仍待政策，按数据集生产不改变原成员和划分；合并仅在原全部成员恰有一个闭合component时RAW_COMPLETE，Root控制入口拒绝部分D3。原D3 wire有一处额外HBA纠正，本线顺序调用时将该函数临时路由到已有canonical HBA（缺失保NaN），finally恢复；原backend预先初始化，避免导入期捕获临时回调。旧D20不重算/替换，原D3公式、参数和原文件均未改。尚未把QM9部分产物称为全D3交付。

19:18CST：新逻辑260项通过，真实4537508.step6，1CPU6.14秒、RSS928740KiB、exit0，日志D_new_data_tests_4537508_step6_20261120.log。Section5入口用冻结的选定3M臂名标记配方，9M源对应登记的9M-D-R0或9M-D-final，不将伪装成3M臂名的9M配置作为输入。P官方CURRENT_BEST仍pending（19:15核实），没有D GPU提交。

19:07CST：开发原D20复制导出已实际关闭，真实4537508.step5（CPU10、1CPU、5.41秒、RSS69120KiB、exit0），15518唯一分子、20有序字段/17启用字段，沿原TRAIN参数，不计算描述符或重新拟合统计。清单`/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/development/D20_descriptors/manifest.json`，source_processing_complete=true、current_C1_complete=false；不代替宽库接收。尚未启动的开发宽库导出4537517改为只导L1/L2并引用该原D20清单，避免重复复制。独立L2基准导出4537537已afterok全量4537508排队，4CPU=3worker+parent、8小时上限，实际开始仍须新鲜联合守卫。

开发MLP容量采用“总可训练参数匹配A”的解析整数宽度口径，实际参数差额在B/C输出报告；此为任务书“同容量”的具体执行选择，未依据下游分数选择或扫描。几何缺H政策仍等待用户答复，未选择、未补H。正式训练预注册仍待P冻结及其9M提交。

18:54CST 更新：当前按库处理交付依赖。原基准D20绑定两次未解决仍保留UNRESOLVED，L1完整交付受限且停止此问题修复。任务书4.1规定L2不做D20跨库映射，二维量不依赖几何，因此L2可独立使用active原结构/原成员与唯一全TRAIN字段/参数导出；不重试原D20或几何绑定，不填造其缺失，D3仍由基准窗口接入其既有封存S′ UFF产品。现有两份基准元数据实际物理字节2097127424，L2数值/状态新增约2.827GB，包含在原8GiB基准预测和36706053853字节联合D峰值内，CPU10新鲜守卫再次通过。

最新259项新增逻辑已通过，真实4537508.step4单核6.23秒、RSS928740KiB、exit0，日志D_new_data_tests_4537508_step4_20261120.log。新增Section5执行器及原成员输入接口、明确保留最终H0的默认关闭选项、逐细胞/逐统计闭合续跑；尚无实际对照拟合。A复用主R3及其既有统计，C对两种B的区间只消费已保存的相同bootstrap抽样，不增加抽样或配方/seed决定。准备在最终选定终点执行一套控制，保留其原末层前向，不在3M和9M重复拟合整套。

成本报告已补齐整行失败口径：L1/L2各5000分子均无整行全缺失、source_graph_error_rows=0；L2的100%仅为每行至少一项缺失。汇总在真实4537508.step3读取已闭合pilot valid数组，未增加描述符调用或改变原成本文件，结果发布results/d_recipe/stage0_costs_20261120.json。

18:20CST：真实接收4537514已依赖全量4537508成功，L1/L2各64个原loader分子，冻结随机C1-0 encoder，仅拟合新头并核SASA原atom行；无实际接收结果。新增开发D3生产与成员级六标量拼接，新逻辑244项通过，真实分配4537508内step0单核（全量源读取阶段仅一个I/O等待进程，无calculator workers）；日志D_new_data_tests_4537508_step0_20261120.log，总6.63秒、RSS923848KiB、exit0。未新增CPU分配、无虚构独立job。开发D3仍未执行或选择氢政策；开发二维导出沿原B6兼容列，使用唯一全TRAIN冻结字段/参数，afterok全量后运行。原子SASA只保源映射，不加到分子特征向量。

18:14CST 实际状态：全量4537508在CPU10运行，4CPU=3个descriptor worker+parent；未启动时按现场可用CPU调整并发及解除单节点绑定，未改变科学条件，实际源ac32340a53b4c82a01129c777db7e4306bfab521。active基准准备4537509正常运行退出（5分钟0:0），但manifest仍为UNRESOLVED_CANONICAL_D20_BINDING：194729唯一分子、335120成员、38546绑定未解决，含NMR38514、其余32。该问题4537426/4537509连续两次实际未解决，依任务书3.5停止此项诊断/修复，保留输出；不重算原D20、不把未知绑定改成已知缺失。TRAIN/VAL全量和开发准备继续，完整宽库交付与真实验收前不启动宽库臂。

2026-11-20 18:10CST 更新：成本作业4537446已在CPU10完成0:0，L1/L2各5000 TRAIN。L1为217字段，CPU40.9365核秒、p99每分子0.02594秒；L2为1613字段，CPU652.2037核秒、p99为0.74502秒。L2每分子至少一个缺失的比例为100%，平均有效字段1454.403；这不表示整行失败，最终95%有效率筛选仍只按全TRAIN执行。人口与计划4537409完成，1201795唯一分子=1194228 TRAIN+7567 commonVAL，诊断分子按既有成员关系覆盖。全量新增峰值预测21673668317字节；与之前pilot/下游预算合计36706053853字节，已在CPU17核验真实根盘/NFS字节、inode及新鲜UID1278配额，运行时继续同一联合守卫。全量准备、生产和统计拟合合并为一个日级CPU作业，已关闭批次复用，不重算成本面板。

开发面板无标签输入4537410已完成SOURCE_READY，15518唯一分子/15751成员，原D20没有未解决绑定。旧基准输入4537426虽运行完成，但canonical绑定未解决，保留原产物；active输入改用基准线已批准的NMR2018/pKa结构manifest和原几何命名空间，显式域外且从未分配UFF任务的成员沿原缺失分类保留。只做特征准备，不读目标值、不创建终点或改划分。

最新新增逻辑233项已在CPU17单核原生SSH通过，日志`D_native_cpu_tests_20261120_1802.log`，总7.40秒，RSS923912KiB，exit0；无虚构Slurm身份。原始source_path/real_index到已有WP5原始SMILES列精确连接；批量SQLite读取保留原PM7 LIMIT1的首构象规则，不复制数据库。P官方CURRENT_BEST仍为pending_round3_M3，F1实际4536900仍在运行，不能据此启动D GPU或声称实验完成。真实64分子接收、全量交付、D臂和最终报告仍未完成。

沿用原人群、划分和原子 ID；现有 D20/D3 与 11-07 参数不变，新字段只用 TRAIN 拟合。宽库存储值不截断，损失中的标准化目标统一截至 ±6，报告各字段比例。阶段 0 的真实接收验收仅按任务书第 6 节执行一次。

主指标 R3 七任务均值，R1/CYP 只报告；分子级配对 bootstrap 1000 次，seed 20261025，95% 百分位 CI；τ=max(0.01,0.05×较大 R3)。WIN/LOSS/TIE、删除项和条件种子严格采用任务书 4.6。CI 描述固定模型的抽样不确定性，不代表训练随机性；未做多重比较校正。尚无 D 实验结果可作统计结论。

2026-11-20 20:12CST：QM9原生D3 component实际关闭，4537546 COMPLETED0:0，CPU17，请求1CPU/站点分配2逻辑CPU，Slurm648秒（分配1296 CPU秒；TotalCPU缺测，不写成实际消耗0）。生产647.574秒、10473原成员、41批，六分子F64/u8及逐原子SASA/源atom引用，native_only，不补H/重嵌入/读终点或重拟合。清单runs/d_recipe_20261120/development/native_D3/qm9/manifest.json标记RAW_COMPLETE、complete_source_population=false；ExpansionRx政策待答复，完整合并和实际接收尚未完成。只登记生产清单/Slurm关闭证据，未二次读取数值或另做QA。
2026-11-20 20:20CST共享预算核对：实际S runtime.TOTAL_PEAK为64GiB，基准STATUS18:34登记40GiB；D现将两者完整纳入future，另保留既有24GiB环境、1GiB杂项和model/P25327352832B。新范围B0 Pprime实际4536906及尾4536907均COMPLETED0:0，access immutable/writers_closed/UID1278且producer ALL_QUEUED_PPRIME_TERMINAL，故释放该封存产物未来写入预测；实存3739791360B仍在quota占用中。旧B0原4536588仍RUNNING，其未来预测不释放。更新只改本线storage_reservations.json的数据，现有守卫代码不变。CPU10真实根/tmp可用70070603776B、36570105空闲inode，NFS6797840613376B、2964415751空闲inode；新鲜UID守卫通过，观测other future221053414400B、D联合36706053853B及100GB UID floor均计入。全量4537508不中断，不改科学条件或其他线代码/作业；S旧D14GiB需要其owner按当前联合值更正，已只追加STATUS通知。

2026-11-20 20:27CST生产里程碑：全量L1 checkpoint为RAW_COMPLETE，shape=1201795x217，4695批全部闭合，真实4537508/CPU10/3worker，observed elapsed3671.846866656095秒，原5000行pilot全部复用。L2已在同一作业生产（20:27CST观测2个关闭批次），不重启L1或源准备。原始计算完成不等于字段/统计冻结、下游导出、真实接收或D科学实验完成；仍无D GPU提交。
