# D 线执行登记

2026-11-20（Asia/Shanghai）。用户明确要求严格执行本任务书的 **D 家族**实验，取代此前消息中的 S 家族名称。

任务书来源：`docs/s-d-taskbooks-20261119` 分支的 `docs/d_recipe/TASKBOOK.md`，原文保留。本次完整执行请求授权阶段 0 先行及书中已有的条件运行和 9M 确认；不增加训练臂。

## 分支及范围

- `d-recipe` 从已发布 p-recipe 提交 `49f1c6bc9d699085474fa86b7d5638a3c5231246` 建立。路径 `/share/home/zixiao/descriptor_analysis/MFM_d_recipe`。
- 阶段 0：`data-d-descriptors-20261120`，从已发布 data-v1 提交 `bc47699c709f57bb00108473f17bf4652333d2ec` 建立。路径 `/share/home/zixiao/descriptor_analysis/MFM_d_descriptors_20261120`。
- P 线的实际未提交工作和在跑任务保持原样；仅包装既有 API，不复制或修改 P 训练与评测文件。

## 执行顺序

1. 阶段 0 过滤规则预注册 → CPU 环境准备 → 固定约 5000 TRAIN 分子 → L1/L2 成本测试 → 全量及下游导出 → 新字段 TRAIN 统计 → 生产清单。
2. P 配方冻结且其 9M 已提交后，将实际 P 配置键逐项登记到训练预注册；原生 D20/D3 的 D-R0/D-R1 可按其已具备的原输入推进；L1/L2 开训前必须完成阶段0真实 loader、逐头过拟合和 SASA 原子对应。此依赖按任务书第2节，宽库交付不额外阻塞原生臂。
3. 按任务书顺序推进 D-L1、D-L2、D-G1、条件 D-K1 和条件 seed1；每个对照只训练一次并复用。
4. 完成规定诊断、开发面板 A/B/C 及组成参照，与基准线交付特征；冻结 CURRENT_BEST，执行规定 seed0 9M；报告、一次完整回归和仓库检查后开 PR，不合并。

## 当前依赖（2026-11-20 22:38CST 更新）

P 官方 CURRENT_BEST 已于12:25:52UTC冻结为 FROZEN_P，组件 A1/B3/B4/F2；规定的五条单种子9M均已提交。D按任务书4.3只迁移A1/B3/B4，F2是P专属标签删项，无D对应物。原生D-R0/R1不等待宽库完成。训练预注册已发布a3b774dc3218fb91b48d98aa84cbe4f930f9aea8。D-R0实际4537572在GPU7运行，A1完整TRAIN拟合4537571在CPU17运行；没有D胜负或完成结论。

原生块锚17/24、6/24、1/24（24个启用字段），原D20/D3和11-07 D4参数不变。A1预先固定ridge alpha=1.0、五折seed20261112、完整TRAIN及原允许构象抽样；没有观察D的OOF结果后选参。新逻辑287项已在真实CPU17作业4537569通过，7秒、exit0，请求1CPU/实际分配2逻辑CPU。完整回归仍仅在开PR前一次。

D联合NFS预测36706053853B保持不变；明确重分配旧未用pilot/基准额度，full范围计入native_stage1的2GiB A1、4GiB四层缓存、1GiB R1检查点与元数据，full新增上界29.75GB，外部保留预测6.930530176GB。原stage0-only预测21673668317B和所有既有文件保留。R0检查点另登记全局Lustre模型池1.25GiB，提交前必须在实际节点通过新鲜UID配额、字节/inode以及所有已登记同行future守卫。

D-R0前1000更新实测32000样本/459.63366344198585秒，69.62066216030972样本/秒，RTX3090整卡15次功耗采样均值219.734W，3M训练外推11.96962665213505 GPU小时（初始化/读出另计）。结果results/d_recipe/D-R0_seed0_first1000_costs_20261120.json由真实CPU17/4537571.step1汇总已有日志，无额外测速。实际4537572已超过32000样本；CPU统计4537573依赖其成功。

GPU初次4537570在CUDA初始化失败、39秒、5CPU，未创建训练输出。已复用P现有card-to-environment选择，3090用既有cu118，修复提交9b97858；没有新建环境或改科学条件。运行的两个日级CPU作业不能由普通用户加时（站点拒绝TimeLimit更新），因此排定同配置、afterany、3日上限的闭合断点续算：全量4537574接4537508，A1 4537575接4537571；不并发重复生产，已完成部分直接复用。接收4537514、开发导出4537517、独立L2基准导出4537537现依赖4537574成功。L2当前批次速率外推高于pilot估计1.5倍，按任务书仅报告并继续；这不是修复时间盒或科学失败。

以下为此前运行记录，时间较早的pending状态已由以上现状取代。
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

2026-11-20 22:49CST：必需的原生TRAIN截断比例入口已发布699959a2ac98e38feb4ec32b1af8d9f236680268，294项新增逻辑在实际4537571.step2/CPU17关闭0:0（Slurm8秒，测试主体1.059秒）。CPU报告4537578依赖A1闭合续算4537575成功，使用同一完整TRAIN分子人群和已冻结的每分子原允许构象选择；分子字段复用raw数组，只为此前未收集的原子SASA首次读取原atomic列，原D4/存储不变，不作为判定输入。配置CURRENT_BEST现明确NATIVE_SCREENING_IN_PROGRESS、recipe_frozen=false、current_best=null；不把在跑臂视作胜出或冻结终点。

2026-11-20 23:08CST：300项新逻辑通过真实4537571.step8（Slurm7秒、测试主体1.077秒，0:0），代码890bceb527e0021feb82736a04a3aa8a28de1152和两节点8/12GiB根盘future已同步五个STATUS。固定D-R0 seed0/3M诊断正式依赖链：GPU7前向4537579 afterok4537572（2CPU、原UUID），CPU17 cache传输4537580 afterok4537579（2CPU），CPU17 F64统计4537581 afterok4537580（1CPU）；均尚未实际开始，不产生新训练。源/目标实际开始和运行期仍有根盘与共享quota保护。CPU17/tmp实际XFS/noquota，52891484160B/36501647空闲inode通过12GiB预检；GPU7约53653098496B/36529140，通过8GiB守卫。累计4h诊断时间盒仍适用，超限或连续失败按未解决、不影响采用判定，保留所有产物。

R0已实际超过193024样本；既有producer按预注册的optimizer_step_start轴，在60000–150000窗口得到2813个裁剪前梯度范数，冻结threshold=12.800916213989263，effective_freeze_samples=150016（32样本步边界），initial_clip281.7。原闭合JSON转录到results/d_recipe/training/d_recipe_20261120_D_R0_seed0_3M/clip_calibration.json，不重新计算p99或更改窗口。当前无终点读出、WIN/TIE/LOSS或最终冻结结论。

2026-11-20 23:20CST：已发布29b98943542e79f594a81d3433482b02282104f2的固定缓存层读出配置。实际CPU17元数据解析使用现有prepare_runtime/final_readout，验证计划缓存消费者与原终点producer的run/checkpoint/store绑定相同（无数据帧/前向）。GPU7逐层读出4537584在原3M主作业4537572成功且5000VAL GPU任务4537579终结后排队，2CPU，读取既有native四层cache，只拟合3/4/5层原R1/R3探针；第6层直接复用。CPU统计4537585 afterok4537584及主CPU统计4537573，1CPU。小型探针预测/统计位于已预算的full/native_stage1元数据范围，D联合NFS36706053853B不增加；没有新编码器前向、层1–6扫描或新预训练。当前仍为PENDING，不是诊断已完成。

2026-11-20 R1正式队列：已发布5535d8ad099df002cd43ddf07822ae2a3aa734e2，302项新增逻辑真实4537571.step11通过0:0（9秒，主体1.110秒）。GPU7根盘R0 VAL8GiB+R1 native8GiB+R1 VAL8GiB合计24GiB与CPU10 R1 VAL12GiB已只追加五个STATUS；共享NFS36706053853B、full29.75GB、Lustre R0 1.25GiB不增加。R1 cold3M/seed0/A1+B3+B4实际4537592 afterok完整A1闭合续算4537575；当前PENDING，未读取OOF分布或启动R1计算。主CPU统计4537593 afterok4537592；CPU配置仅去掉GPU本地资源标记，与同一科学运行/目标参数绑定。

R1固定诊断：GPU7 4537594 afterok4537592；VAL闭合cache转CPU10 4537595 afterok4537594；CPU10统计4537596 afterok4537595。native cache3–5层读出4537597 afterany4537594且afterok4537592；CPU层统计4537598 afterok4537597及主统计4537593；层6直接复用主结果，不重做编码器前向。配对比较4537599 afterok两个主统计4537593和4537573，结果results/d_recipe/comparisons/D-R1_vs_D-R0_seed0_3M.json；只消费既有七任务R3及1000分子bootstrap，R1/CYP仅报告，不重采样。不提前触发seed1或后续选配方。

GPU7已实际通过自身8GiB+同行16GiB根盘、共享D/同行UID future联合守卫；CPU10实际根/tmp70070484992B、36570105空闲inode、XFS/noquota，目标12GiB及共享守卫通过。每个作业实际开始仍重新核实UUID/CPU/真实盘和quota，不因排队假定资源已分配；若GPU7届时被占，Root按实际可用小任务卡和既定优先顺序调整尚未开始的作业。R0仍原样在跑，没有重启或迁移。全部上述R1任务当前仅排队，无分数、胜负或最终冻结结论。

2026-11-21 00:14:45 CST：跨日仍核实R0/A1/L2原句柄RUNNING，R0已达699776样本；11月20日23:48:21首次500k固定VAL原producer已闭合24字段MAE/单位记录，每分子标量2000观测、原子SASA106325观测。只转录原CSV和路径，不重新评估或手算新的统计；此不是终点主评分。R1 4537592实际SubmitTime为2026-11-20T23:57:32，仍PENDING/afterok4537575，其全部终点评测/诊断和比较依赖已由Slurm核实。新增11月21日日报，11月20日报保留当日最终状态；未冻结或预判任何胜负。

2026-11-21 00:46 CST：R0原作业4537572已保存精确1000000样本恢复点，/lfshome/zixiao/model_v31_20261105/D_RECIPE_20261120/training/D-R0_seed0_3M/samples_1000000.pt，OS大小192027123B、mtime00:45:01+0800；原producer随后已报告1008000样本，未重启、迁移或重新加载。对应results/d_recipe/training/d_recipe_20261120_D_R0_seed0_3M/VAL_original_units_1000000.csv由原固定VAL生产，直接发布，不重算统计或以其替代终点R3。A1原4537571仍COLLECTING，130048/1194228行；L2原4537508最近1005/4695批闭合。R1链维持真实排队依赖，没有新训练或胜负结论。既有B6 v2的补H/MMFF固定原子处理明确仅限独立基线，未据此替D开发面板选择缺H政策，原待答复问题保留。
2026-11-21 00:52 CST：新增FINAL_REPORT.md执行中版本，集中登记已冻结方法、已关闭原始成本/1M证据、缺H与基准绑定局限，以及所有未完成交付。没有新增计算、回读数值数组、提前R3结论或改变预注册；只有原始pilot及成本JSON、已发布方法与配置的转录。最终报告仍需实际全部结果/9M/收尾证据填齐，不能以此草稿结项。
2026-11-21 01:55:58 CST：R0原4537572的既定1500000样本固定VAL已生产CSV（1179B，mtime01:55:23+0800），随后同一producer已报告1500800样本；直接发布原CSV，不增加前向、回读统计或检查点加载。1.5M不是额外下游读出或新的检查点；R0主R3与3M仍未完成。A1原4537571仍COLLECTING，最近193024/1194228行；L2原4537508最近1274/4695批闭合，均保持原配置和依赖。CURRENT_BEST仍未冻结、current_best=null，无D胜负结论。
2026-11-21 03:34:03 CST：R0原4537572已保存精确2000000样本恢复点，/lfshome/zixiao/model_v31_20261105/D_RECIPE_20261120/training/D-R0_seed0_3M/samples_2000000.pt，OS大小192029363B、mtime03:32:35+0800；原producer随后报告2006400样本。对应2M固定VAL原CSV为1181B，直接发布原文件，不增加前向、独立数值检查或检查点加载，保留1M及所有旧产物。当前仍无主R3、胜负或冻结配方。

同次实际句柄4537508/4537571/4537572均RUNNING；A1仍COLLECTING，274944/1194228行；L2按原生产checkpoint的completed_parts长度已有1673/4695批关闭。此前部分实时进度使用stdout的closed_part零基批号作为批数，少报1批；以后以该原checkpoint长度报告，不改变任何生产数据或统计。R1 4537592仍PENDING/Dependency，原评测、诊断、比较依赖保持。完整报告、9M及两个未合并PR仍待全部既定步骤完成。
2026-11-21 05:11:03 CST：R0原4537572的既定2500000样本固定VAL已闭合CSV，1186B、mtime05:09:21+0800，同一producer随后已报告2505600样本。直接发布原CSV，未增加前向、独立统计或检查点加载；2.5M不是额外检查点/下游探针，1M/2M旧点保留。主统计4537573、终点诊断4537579仍PENDING/Dependency，R1 4537592继续等待完整A1。

原生产metadata同次记录：A1 353280/1194228行COLLECTING、elapsed24508.84916986525秒；L2 completed_parts长度2385/4695、elapsed31495.685714006424秒。日报据此补充日程粗估：R0训练主体21日06:30–07:30，L2原始计算13:00–16:00，A1收集21:00–24:00；后续TRAIN统计/接收/拟合/读出与队列另计。这是已有进度的运行计划估计，没有额外测速或修改规定的首次1000步成本报告。CURRENT_BEST仍未冻结，无D胜负结论，完整任务继续。
2026-11-21 06:56:04 CST：R0原4537572已真正完成精确3000000样本/93750更新。原生summary状态TRAINING_COMPLETE_EVALUATION_PENDING，actual_samples3000000、seconds30579.45974943787、clipped_fraction0.027584、clip12.800916213989263、B32/micro32、GPU_peak_bytes8374157824。原summary逐字节复制为results/d_recipe/training/d_recipe_20261120_D_R0_seed0_3M/training_summary_3000000.json；它是训练闭合时的producer快照，非额外接收收据或独立复核。seconds包含固定VAL训练循环，排除初始化和最终读出，完整原GPU作业及整卡遥测成本待终态后一次汇总。

3M恢复点/lfshome/zixiao/model_v31_20261105/D_RECIPE_20261120/training/D-R0_seed0_3M/samples_3000000.pt实际192031603B，mtime06:54:12+0800；1M/2M及全部原产物保留。原3000000样本固定VAL CSV1180B，mtime06:54:13+0800，直接发布；没有加载权重作二次验证或增加前向。4537572仍RUNNING并接续其既定最终GPU读出，4537573/4537579仍PENDING/Dependency，主R3、bootstrap及规定诊断尚未完成，不能据训练终点作胜负或冻结结论。

同次原生产状态：4537508、4537571仍RUNNING，L2原checkpoint已有3040/4695批、A1仍COLLECTING且432640/1194228行闭合。CPU17在既有4537571分配下以1CPU执行真实联合资源准入，通过当前D模型/NFS/同行future守卫，无新预算、数组回读或科学计算。日报将R0训练主体粗估替换为实际06:54闭合，其余生产/后续读出仍分别报告。全部既定臂、判定、9M、直接描述符对照、接收/交付与两个PR继续作为未完成范围。
