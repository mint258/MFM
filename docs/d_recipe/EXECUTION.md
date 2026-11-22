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

2026-11-21 07:05:28 CST：R0主GPU4537572真实COMPLETED/0:0、ElapsedRaw31074、AllocCPUS5；主CPU统计4537573真实COMPLETED/0:0、ElapsedRaw85、AllocCPUS1、compute-0-8。原生summary现为COMPLETE/statistics_complete=true，原快照复制为final_summary_3000000.json；先前training_summary_3000000.json保留训练闭合时状态，不覆盖。主评分原JSON转录为final_readout_summary_3000000.json，仅省略大体积paired_bootstrap抽样数组，原抽样仍保留Lustre源供后续配对比较，没有重算任何分数或CI。原scores.csv（含CYP仅报告）直接发布。

原R3=0.3047600714630222、95%CI[0.2914629069496532,0.3190324065629142]；原R1=0.15029061734585417、CI[0.1336480796754142,0.16715810049540256]，七主任务均包含，分子bootstrap1000次/seed20261025。这些是对冻结随机C1-0编码器的基线分数，不作D-R1迁移配方的判定。CURRENT_BEST仍未冻结、current_best=null，R1和后续全部既定条件保持。

规定的闭合作业成本仅汇总一次，真实CPU17/4537571.step15：完整GPU目标作业8.631666666666666墙钟小时、Slurm分配CPU小时43.15833333333333（不是实际TotalCPU）；原训练循环含固定VAL为98.10506871545198样本/秒，1017次原整卡遥测均值245.27235004916423W，覆盖训练作业及最终读出，非仅训练功耗。GPU峰值与首次1000步原报告保持。实际Slurm TotalCPU字段00:00:00只记缺测，不解释为零；主/批/extern不重复计费，原零步失败4537570的39秒单列。第一次本地sacct连接在读取遥测前失败，修复为转录同一Main登录节点原生sacct输出后完成CPU汇总；无额外测速、模型加载或科学QA。成本JSON路径results/d_recipe/D-R0_seed0_complete_GPU_job_costs_20261121.json。

原GPU固定VAL诊断4537579已在compute-0-7 RUNNING，其CPU传输/统计和3–5层缓存探针仍按原依赖等待；诊断成本另计。原A1和L2仍RUNNING，最近440832/1194228行与3098/4695批。CPU17.step16只转录原结果、通过既有联合磁盘/UID/同行future守卫，没有数组独立复核或新增判定。其他规定臂、直接描述符对照、最终冻结、9M、全部交付、一次全回归与两个未合并PR仍未完成。

2026-11-21 08:01:16 CST：原固定VAL前向4537579真实COMPLETED/0:0，GPU7/2CPU/ElapsedRaw3388，producer manifest为D_REPRESENTATION_FORWARD_V1/FORWARD_COMPLETE：5000分子、47698原允许构象、层3–6、float64 cache，statistics_complete=false。源GPU7的/tmp/d_recipe_20261120_D_R0_seed0_3M/forward/manifest.json及全部原数组保留，没有追加前向或数值回读。实际完成后自动触发原传输4537580，CPU17/2CPU/ElapsedRaw29、COMPLETED/0:0，输出CACHE_TRANSFER_COMPLETE、scientific_values_changed=false、original_sources_copied=false；只消费已闭合VALcache，未复制原始数据库、校验哈希或独立数值QA。

CPU17 F64表示统计4537581和GPU7缓存层读出4537584均实际RUNNING；前者消费同一绝对路径manifest，后者消费原native开发cache，只拟合3–5层R1/R3，第6层复用主结果。CPU层统计4537585继续原afterok依赖。几何诊断当前关闭前缀3388+29=3417秒，原CPU统计3小时上限保持，累计上界14217秒仍小于4小时；不把前向/传输成功冒充最终PR/CEV/CVF/CVF_res或逐层诊断结果。全部诊断不进入采用判定。

当前原A1与L2仍在计算，最近A1 489984/1194228行、L2 3563/4695批。CPU17实际联合盘/inode/UID及同行future准入通过，原NFS36706053853B、full29.75GB、Lustre模型1.25GiB及根盘24/12/12GiB预测不增加。08:01日报与当前状态按已闭合生产元数据更新，没有新测试、bootstrap重算、冻结或候选胜负结论；后续完整目标保持。

2026-11-21 08:22:41 CST：缓存层GPU读出4537584真实COMPLETED/0:0，GPU7/2CPU/ElapsedRaw1177；原CPU层统计4537585真实COMPLETED/0:0，CPU8/1CPU/ElapsedRaw95。原/full/native_stage1/D-R0_seed0_3M/layer_readouts/summary.json为COMPLETE，ordered_layers=[3,4,5,6]、statistics_dtype=float64、encoder_forward_repeated=false；3–5层为原cache上的规定探针，第6层直接复用主读出及统计，不重采样。

CPU17既有4537571分配只执行小型原结果转录，真实联合盘/inode/UID/同行future准入通过：results/d_recipe/diagnostics/D-R0_seed0_3M/layer_readout_summary.json逐字段保存原各层R1/R3分数、CI、任务统计及源路径，省略大体积配对抽样数组；原抽样和预测全部保留生产源。原layer_scores.csv直接复制，包含3–5层逐任务结果，第6层仍指向原主scores.csv。没有模型加载、编码器前向、bootstrap重算、独立数值QA或层选择。

原各层R3依次为0.2308587424764003、0.29486703839088685、0.33386390313542563、0.3047600714630222；各层R1依次为-0.03598715288707174、-0.001692420000947619、0.14474610285525596、0.15029061734585417。原CI逐字段见转录JSON，报告表只显示舍入。全部是对冻结随机C1-0的描述性诊断；R0主分仍是第6层0.3047600714630222，CURRENT_BEST不冻结，不触发seed1或任何新科学臂。

CPU表示几何统计4537581仍RUNNING且未产生闭合summary；A1与L2仍生产，最近508672/1194228行与3695/4695批。GPU7后续上下文已属其他既有Slurm4537291，本线未操作或持有该GPU；未来R1仍等完整A1，届时按实际就绪/资源重新调度。原24/12/12GiB根盘与联合NFS预算保持，原输出保留。源训练clipped_fraction字段已核实为clipped/optimizer_updates，报告说明是梯度裁剪更新比例，不替代待原TRAIN报告的逐字段±6目标截断比例。其余既定臂、完整对照、冻结、9M、全回归及两个PR仍待完成。

2026-11-21 09:28:33 CST：R0原表示统计4537581已真实COMPLETED/0:0，CPU17/2分配CPU/4446秒，固定5000VAL/47698构象、层3–6、float64。只将原完整summary.json及bootstrap.npz原样保存至/full/native_stage1/D-R0_seed0_3M/representation_statistics，版本化representation_statistics.json仅省略原特征值数组，原谱/抽样完整保留；没有重算统计、重采样、额外前向、独立QA或选层。几何链3388+29+4446=7863秒；另加逐层读出1177+95后全部诊断作业秒数9135，小于4小时。四层PR/CEV/CVF/CVF_res、CI已转录报告；主R3仍第6层0.3047600714630222。

未启动R1统计新增可选participation_molecule_chunk=256（默认32保留），仅改变现有精确F64矩累计分块，公式、5000VAL、1000次配对抽样/种子不变，512维单块512MiB RAM，无新盘scratch；不声称实际提速。解析协方差与257分子跨256边界相关7项测试在真实CPU17/4537571.step20通过0:0，Slurm4秒/主体0.227秒，rtol/atol1e-10；未重跑历史302项或真实数据QA。

R0所有本地写入者均C0，按实际关闭撤销GPU7 R0 8GiB和CPU17 R0 12GiB未来预算。GPU7仅余R1两scope共16GiB，未启动R1各配置对应并发16GiB改8GiB；CPU17 R0未来0，CPU10 R1仍12GiB。原R0物理cache GPU7 5133008896B、CPU17 5133246464B全部保留并由df计占用；实际根盘两节点各75125227520B，总可用48517754880B/47753945088B，空闲inode36529111/36501585，系统max(10GiB,10%)仍保留。联合NFS36706053853B/full29.75GB/Lustre模型池1.25GiB不变。CPU17实际联合盘/UID/同行future守卫通过；本次仅元数据、原结果及7项新逻辑证据，无新科学臂、胜负或冻结。A1仍COLLECTING559104/1194228，L2已3777/4695批；全部后续目标保持。

2026-11-21 09:52:13 CST：检查条件seed1配置时发现，通用P新种子助手原样继承diagnostic_feature_root；D seed0逐层缓存绑定原run/checkpoint，若条件seed1沿用该路径会在终点读出被原绑定拒绝。D任务书4.8的逐层诊断仅在既定seed0端点执行，因此在D专用seed_plan._child中仅移除可选diagnostic_feature_root，不改变P源、训练/主读出、A1冻结参数、种子触发或共享对照规则。父seed0配置和全部原cache保留；具体新位置和磁盘预算仍由Root在真实条件触发后准入，没有生成/提交任何seed1运行。

既有获胜子配置测试同时带入候选和对照seed0缓存路径，确认父配置不变、两个子配置都不启用该seed0缓存。相关6项条件种子测试在CPU17真实4537571.step24通过，Slurm COMPLETED/0:0、1CPU/17秒，测试主体0.003秒；实际联合磁盘/UID/同行future守卫通过，未运行训练、bootstrap、实际数据QA或全仓回归。此为执行错误修复，不改变科学预注册。最新A1仍COLLECTING579840/1194228，L2闭合3858/4695批，原生产/后继依赖保持。

2026-11-21 12:18:56 CST：原全阶段4537508已闭合L1/L2原始1201795行、217/1613字段、各4695批，随后L1唯一全TRAIN统计因7个raw非恒定稀有计数在既定type-7缩尾后std0而拒绝最终化。真实4537508 FAILED/1:0、64639秒/4分配CPU；原续算4537574复用原始数组与闭合L1_statistics.json，仍同错FAILED/1:0、43秒/4CPU。依任务书第3节两次实际失败，L1=UNRESOLVED、D-L1不跑、保留对照；没有R3、TIE或LOSS结论。fr_benzodiazepine/fr_diazo/fr_isocyan/fr_isothiocyan/fr_nitroso/fr_quatN/fr_thiocyan原有效TRAIN均1194228，q001/q999/缩尾mean/std均0。原字段过滤、D4、数组和唯一统计全保留，无epsilon、重拟合或删字段。

新增默认关闭unresolved_libraries仅在final manifest明确关闭该库，原raw manifest和统计保持；让L2首次完整TRAIN统计独立继续。3项相关新逻辑在真实CPU17/4537571.step27通过，1CPU/4秒、主体0.006秒；step26初次合成fixture漏mock嵌套NFS守卫失败5秒，修正只在测试。默认零尺度拒绝、未知库/空理由拒绝及关闭库/原统计保留均覆盖；新测试纳入既有最终新逻辑测试清单，未重跑302项或全仓回归。reception.sbatch新增可选整库参数，默认仍L1/L2；CPU17实际bash语法检查通过。

Data修复已推d0d5f05fc0dcd6e5300e2f52f0281953839b4523，Root接收入口已推1bd92d8cf9188ec696a08eeda4678885a7616125。CPU10实查CPUAlloc60/64、目标NFS/root字节与inode后，4537771实际RUNNING CPU10，请求1CPU/3天，仅执行同一stores的L2首次TRAIN统计；NFS/UID/同行future入口守卫保持。新L2接收4537772、原开发导出4537517、原独立基准L2导出4537537均afterok4537771；旧双库接收4537514经UID1278/PENDING/0运行核实后取消，原生会计CANCELLED by1278/0秒。没有触发L1接收或新训练。原A1/R1链保持，最近A1 COLLECTING701440/1194228。

CPU17/4537571.step29仅原样保存raw manifest和L1唯一统计至Data结果目录，Root stage0_full_status_20261121.json逐字段转录原7字段及真实Slurm/依赖；没有科学数组回读、哈希或新统计。全NFS36706053853B/full29.75GB/Lustre1.25GiB以及GPU7/CPU17R0/CPU10R1未来16/0/12GiB保持，原输出均保留。完整方法/局限与L1未解决已更新FINAL_REPORT、CURRENT_BEST和日报；最终目标继续。

2026-11-21 12:30:12 CST：L2唯一全TRAIN统计已由4537771闭合（1315608B），65个启用字段在既定缩尾后std0。该最终化实际FAILED/1:0、358秒/1CPU；仅复用闭合L2_statistics.json的4537773仍同错FAILED/1:0、13秒/1CPU，没有重拟合。依任务书两次实际失败，L2与L1均UNRESOLVED，D-L1/L2不跑、当前无宽库采纳而K1未触发；不是TIE/LOSS。原有效数据、原过滤和归一化定义未改。

补充全库未解决时全局状态也为UNRESOLVED，相关4项在真实CPU17/4537571.step30通过0:0，1CPU/6秒、主体0.012秒。源修复已推Data a1312c27e62590e29e013c7e65c58ddd5afd45f4。仅元数据最终清单4537774在CPU10真实COMPLETED/0:0、1CPU/12秒；final_manifest.json为UNRESOLVED、两个entry也UNRESOLVED，没有可交付宽库。原L2接收7772、开发导出7517、基准L2导出7537经zixiao/PENDING/0秒核实后取消，原生会计均CANCELLED by1278/0秒。没有动其他owner任务、训练或数据。

CPU17/4537571.step31仅原样保存L2唯一统计和最终清单至Data结果目录，并更新Root阶段0执行转录。两库72个受影响字段及原参数可审阅；若恢复宽库，需明确批准仅对新字段增加缩尾后std0过滤，旧D20/D3/D4及其余原统计保留、不重新拟合、不增变体。当前未执行科学修订，原预注册不改。原生A1最近710912/1194228 COLLECTING，R1依赖原续算7575及所有原比较/诊断保持；最终目标继续，未冻结或提交9M。


2026-11-21 13:30:06 CST：日报补齐原生A1收集结束的线性运行估算，只读取原checkpoint闭合行数762624/1194228与Slurm原耗时54495秒；约11-21 22:04 CST收集结束，未含后续拟合，NFS速率变化可推迟，非停止或科学判定门。CURRENT_BEST中R0表示诊断旧排队状态QUEUED_AFTER_EXACT_3M_ENDPOINT改为COMPLETE，依据已有diagnostic_progress闭合记录；原结果/数组/统计不回读、不重算，配方仍未冻结，原生A1/R1链和宽库未解决状态不变。


2026-11-21 22:24:15 CST：原生A1全1194228 TRAIN/23分子字段采集及唯一五折ridge拟合已闭合，4537571 COMPLETED0:0/85805秒、同输出续算4537575 COMPLETED0:0/32秒。12项元素参考残差、11项原目标、无未解决；系数与OOF结果原样发布至results/d_recipe/reference/D20_A1_parameters_20261121.json，详见A1_FULL_TRAIN.md。R1 4537592于22:12:23 CST在compute-0-7/原RTX3090 UUID冷启动，不继承R0权重。自有SDK快捷链接与full-store扫描冲突已修复，真实日志/训练状态保留，原进程恢复；后续D运行仅将原SDK目录路由至已预算的共享控制scope，默认关闭的D适配器之外不变，原P代码不改。针对路径、容量失败与恢复的9项相关测试于4538106.step0通过，1CPU/Slurm1秒/主体0.027秒；没有重跑完整回归。截断报告原4537578的76秒基础设施退出后，以4538106同配置/同输出/同关闭游标续接，未重拟合A1或重算已关闭分子计数。配方未冻结、两宽库原未解决和全部后续判定/9M范围保持。


2026-11-21 23:15:15 CST：原生R1已按原60000–150000窗口冻结梯度clip=25.222319259643566，2813更新、有效冻结边界150016，原生产JSON已推送；不涉及目标±6或配方采纳。SSH/X暂时中断已恢复；同R1进程与状态保留，自有SDK别名处理现以脱离交互会话的4537592.step2运行，原200k别名已保留，R1已继续超过201600样本。原截断续算4538106的基础设施退出后，4538112在CPU8/请求1CPU复用68608原关闭游标、原分子计数及同输出继续；没有重拟合或重跑已关闭统计。共享与节点缓存预算、原未解决宽库及所有科学决定不变。


2026-11-22 00:01:21 CST：建立11-22一页日报，转录原R1进度387200/3000000与截断游标138240/1194228；当前Slurm均RUNNING。约11-22 12:16 CST仅为3M训练结束线性报告估计，未含最终读出/统计/诊断，不作停止或采纳门。原参数、科学决定和后续全范围保持；没有回读数组、重拟合或重新评测。


2026-11-22 00:36:36 CST：R1原500k固定VAL原单位CSV已由原生产脚本生成（1184字节，00:31:16 CST），原样推送。原训练已继续到512000样本；仅记录规定固定VAL，不新增前向、重算统计或作配方判定。CURRENT_BEST仍未冻结；其余原依赖与全范围保持。


2026-11-22 02:44:31 CST：R1原1M检查点与固定VAL已由原生产脚本保存，检查点203776923字节，原单位CSV1184字节（02:41:09 CST）；原训练已继续超过1004800样本。CSV原样推送，只登记现有检查点路径和大小；未复制/重新加载检查点、未增加验证前向或统计拟合。主R3与配对判定等待3M终点，CURRENT_BEST保持未冻结。


2026-11-22 04:50:42 CST：R1原1.5M固定VAL原单位CSV已由原生产脚本生成（1188字节，04:49:18 CST），原样推送。原训练已继续至1500800样本；只登记规定的固定VAL结果，不新增前向、统计拟合或配方判定。CURRENT_BEST仍未冻结；后续原依赖链及全范围保持。


2026-11-21T21:39:02.437385+00:00：收到用户明确批准“批准补充过滤，恢复原计划宽库实验（建议）”。两仓库补充预注册冻结原72项名单及唯一统计引用；仅为该零尺度情形补充过滤，无重拟合/epsilon/旧D20/D3/D4变更，原未解决产物保留。先独立amended manifest及真实64 loader逐头验收，宽库训练继续受阶段1配方选择/原种子门约束；原R1及TRAIN统计继续。ExpansionRx H政策未获授权。


2026-11-21T21:52:34.477867+00:00：补充清单4538112.7/COMPLETED0:0/1秒/1CPU，原72字段仅从enabled列排除，原数组与唯一TRAIN参数保留；L1启用191/217，L2启用1314/1613。真实64 loader逐头验收4538200/CPU10/COMPLETED0:0/162秒/1CPU，两库均ACCEPTED，原报告已保存。下游二维导出配置仅绑定新清单，旧D20绑定失败与H政策限制保持；宽库训练待阶段1配方选择。

2026-11-21T22:00:35.455336+00:00：开发双库导出4538204/CPU10/3CPU（2 workers）与基准独立L2导出4538205/CPU10/4CPU（3 workers）均RUNNING，原生产者/原输出路径续接，开始05:55:23 CST；分别15518/194729唯一分子。既有512MiB/3.75GiB预留内运行，无新本地缓存；宽库训练仍待阶段1判定，原D20绑定和H政策不改。

2026-11-21T22:06:20.602716+00:00：开发双库原导出4538204/CPU10/3CPU实际COMPLETED0:0，612秒，15518唯一分子，两库61批均关闭；L1 191/217、L2 1314/1613，沿用原TRAIN参数/原成员划分、不读任务标签、不重拟合。原source_processing_complete=true、reception_acceptance=pending、current_C1_complete=false如实保留；该二维闭合不替代待定D3/H政策或最终A/B/C。基准L2 4538205继续RUNNING。


2026-11-22 06:58:13 CST：R1原2M检查点与固定VAL已由原生产脚本保存，检查点203779163字节，原单位CSV1188字节（06:56:49 CST）；原训练已继续超过2003200样本。CSV原样推送，只登记现有检查点路径和大小；未复制/重新加载检查点、未增加验证前向或统计拟合。主R3与配对判定等待3M终点，CURRENT_BEST保持未冻结。

2026-11-22T00:07:24.373897+00:00：基准独立L2原导出4538205/CPU10/4CPU实际COMPLETED0:0，7842秒（分配CPU 8.713333333333333核时，TotalCPU未知），194729唯一分子/761批，1314/1613启用。原TRAIN参数、成员划分不改；原source_processing_complete=true，reception_acceptance=pending、current_C1_complete=false保留。原D20绑定未解决和H政策仍待定；该二维导出不构成基准接收或最终A/B/C完成。原清单已转录至数据分支，Root摘要results/d_recipe/benchmark_L2_export_20261122.json；现行36706053853B联合NFS预算不增。


2026-11-22 08:56:22 CST：R1原2.5M固定VAL原单位CSV已由原生产脚本生成（1196字节，08:54:49 CST），原样推送。原训练已继续至2502400样本；只登记规定的固定VAL结果，不新增前向、统计拟合或配方判定。CURRENT_BEST仍未冻结；后续原依赖链及全范围保持。


2026-11-22T03:34:15.435547+00:00：R1原4537592实际COMPLETED0:0/46468秒/5CPU，3M与93750更新及GPU读出闭合；原3M检查点203781403字节、固定VAL1193字节，原生产summary原样保存。主CPU统计4537593、配对4537599及规定诊断继续原链，未作科学判定。CURRENT_BEST两宽库当前状态纠正为已验收等待阶段1选择，修订前UNRESOLVED完整保留于original_unresolved_closeout；补充过滤已批准执行，未改原统计。目标±6报告从原游标1002496以4538446/CPU16/1CPU续接，旧4538112持续RPC等待后取消40853秒并确认旧worker消失，配置/输出/系数/RNG不变；新进程仍共享软件I/O等待，无新关闭行。日报归并为一页；原始里程碑保留于本执行记录。此次仅有界元数据写入，在实际CPU16以真实statvfs、fresh UID配额和全部注册未来峰值保守计账核准；未改科学运行守卫、未扫描/复制原数组。


2026-11-22T03:36:10.225177+00:00：R1已关闭GPU作业的原遥测一次归账，1489条30秒整卡功耗样本均值216.565876427132W，原循环含固定VAL 65.334289464229样本/秒，父作业46468秒、5CPU，TotalCPU站点缺测记null。成本源results/d_recipe/D-R1_seed0_complete_GPU_job_costs_20261122.json；不新增测速或前向，CPU统计与诊断另列。


2026-11-22T04:25:06.573972+00:00：R1原F64诊断4537594已实际FAILED1:0/3715秒，原输出保留；瞬时容量不可核实时以默认关闭的wait_for_capacity开关复用原Guard.wait，未改原check、5秒新鲜度、根盘/UID/同行预留或科学公式，源已推90ccd03cc437b0adea929442d8487f657d3adaaf。新增6项与既有23项相关资源测试分别在4538446.18/.19通过0:0，主体0.003/0.018秒，1CPU；完整回归未重跑。续接4538515以同3M检查点、同输出、GPU7原UUID、2CPU、最多4200秒，在原缓存逐层读出4537597之后运行；原传输4537595只改为afterok4538515且与4537596一同保持持有，待实际前缀归账后按4小时累计余量释放。实际GPU7根/tmp共盘可用45433475072B、36529116inodes，已计16GiB未来与10GiB系统底线；fresh实际UID1278配额353271521280B，旧F64文件和原R0缓存均保留。原主统计4537593和配对4537599链未重启，原截断报告关闭游标已推进到1020928。
