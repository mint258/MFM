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

规定的闭合作业成本仅汇总一次，真实CPU17/4537571.step15：完整GPU目标作业8.631666666666666墙钟小时、Slurm分配CPU小时43.15833333333333（不是实际TotalCPU）；原训练循环含固定VAL为98.10506871545198样本/秒，1017次原整卡遥测均值245.27235004916423W，来自原0<samples<training_budget的训练活跃采样窗口，不含最终GPU读出；这是整卡点采样均值，不是独占功耗或积分能耗。GPU峰值与首次1000步原报告保持。实际Slurm TotalCPU字段00:00:00只记缺测，不解释为零；主/批/extern不重复计费，原零步失败4537570的39秒单列。第一次本地sacct连接在读取遥测前失败，修复为转录同一Main登录节点原生sacct输出后完成CPU汇总；无额外测速、模型加载或科学QA。成本JSON路径results/d_recipe/D-R0_seed0_complete_GPU_job_costs_20261121.json。

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


2026-11-22T04:32:09.918880+00:00：原缓存逐层GPU读出4537597已COMPLETED0:0/1217秒，原3–5层探针关闭；4537598仍等主CPU统计4537593。F64续接4538515实际FAILED1:0/1秒，失败位于继承Guard构造期的5秒配额快照准入；连同原4537594的3715秒已达两次实际失败上限，按任务书记F64 geometry=UNRESOLVED，停止此项修复/前向。未生效的可选修复与其新测试已撤回；实际运行过的配置和90ccd03cc437b0adea929442d8487f657d3adaaf历史源保留，原check/保护/科学公式继续原样。未开始的原传输4537595与表示统计4537596经UID1278/PENDING/0秒核实后取消，实际均CANCELLED0:0/0秒。GPU7的R1原8+8GiB与CPU10原12GiB未来写入归零，全部原部分/缓存文件和原R0物理缓存保留，联合NFS峰值不变。主统计4537593、比较4537599及逐层CPU4537598链不变；不得将诊断未解决解释为R1的WIN/TIE/LOSS。


2026-11-22T04:46:47.282597+00:00：原R1主CPU统计4537593已COMPLETED0:0/5602秒，实际2分配CPU/请求1CPU，原R3=0.40246475893886535、CI[0.38776123870192125, 0.4165789987907473]，报告项R1=0.23055805758999076、CI[0.2161366706314768, 0.24381363179424703]；原native COMPLETE摘要及聚合/逐任务score元数据转录至Root，不重新计算或复制checkpoint/预测数组。原配对4537599与逐层CPU4537598继续实际RUNNING，未提前判WIN或触发seed1。目标±6报告4538446实际FAILED1:0/7319秒，保留1020928关闭游标；旧CPU16 worker经实际ps确认不存在。CPU16已有Kill task failed的DRAIN状态，未修改任何管理员/同行进程；未启动的只读预检4538531取消0秒。以同原配置/系数/RNG/输出续接4538532/CPU8/1CPU/16GiB；实际CPU8根/tmp可用69081251840B、36567584inodes，NFS5700043407360B、配额353224273920B/有效年龄2.1246秒，MemAvailable390047526912B，新本地数据0，联合NFS峰值不变。


2026-11-22 14:27 CST：原R1 seed0配对JSON及相同日志已在4537599超时之前完整写出，Δ=0.09770468747584315、95%CI[0.08195311354654226,0.11189074805862387]、τ=0.02012323794694327，判WIN。原作业TIMEOUT/3616秒照实记账；备用4538541在未启动/0秒边界取消，不重复比较或抽样。触发一个共享D-R0 seed1及一个D-R1 seed1，均冷启动3M、各自重新校准clip，不继承seed0缓存或权重。配置/存储准备4538547在CPU17进入Python启动RPC等待且尚未生成配置，实际取消（父1045秒/批1064秒）；afterany续接4538549在CPU8执行同一准备，无训练启动。拟额外登记2GiB NFS；现行预算在实际Data计划及配置闭合前保持原值，实际盘/inode/fresh UID配额和全部同行future不放宽。原clip4538532及层CPU4537598保留；逐层CPU上限实际收紧为03:39:00，连同原GPU1217秒最多14357秒，截止16:19:13 CST。GitHub报告及CURRENT_BEST先记录已闭合科学结果；节点侧元数据待存储恢复后与准备产物一起同步，不能把分配/RPC等待记成seed1训练或已准入。


2026-11-22 14:32 CST：实际GPU4/5分区均idle、48CPU空闲；GPU4共享盘5.7TB/29.64亿inode，实际UID1278配额353221890048B、读时有效年龄1.4355814456939697秒。只读目标盘检查4538550在10分钟上限退出：GPU4完整返回，GPU5仅本地根/tmp完整返回，不将不完整节点预检记为准入。现注册两条精确任务书seed1依赖链：R0 GPU4538551/node4/UUID GPU-6965a7c7-025e-e4fd-013a-2be3245ef7c6，R1 GPU4538552/node5/UUID GPU-dac07d74-6269-c7db-8832-340dd3c0b377；均afterok准备4538549，后者必须先封存两个精确配置/registry及实际Data全局NFS预算。CPU统计4538553/4538554各afterok自身GPU；配对4538555 afterok两个CPU，原比较入口/4小时上限。五项均PENDING/Dependency，未占用GPU或启动模型；未把已排队记为训练。运行入口仍在实际节点先核空GPU上下文、显存/5CPU和原DJointGuard的root/NFS字节/inode/fresh5秒UID配额与同行future，失败时不得启动模型或大写入。没有独立重复对照、seed1表示诊断或种子规则外实验。


2026-11-22 15:35:44 CST：用户恢复目标后核查仍见原准备4538549及共享I/O等待，五条seed1依赖链未开训。系统绝对路径/usr/bin/env与本机Python3.9.14可立即执行，CPU8实测根盘可用69088989184B/36567573inodes；只读元数据探针仍在打开仓库源文件时陷入openat/NFS等待，未生成文件且未采纳该临时入口，两个只读step4538532.10/.15已终止，原生产allocation保留。发现原第3层scores.json已在13:40:05 CST闭合，首次转录原R1=0.22251130365828092、CI[0.20889490422663376,0.2364367774943568]及R3=0.40784337449791125、CI[0.39454694681264635,0.42062377850793353]，原1000次/seed20261025抽样保持；L4/L5尚无scores，不能选L3代替固定主层6。

收到用户替换版AGENTS后已重读技能1.0.164。五个未运行seed1作业4538551–4538555均核实PENDING0秒后scontrol hold，当前JobHeldUser；新入口退出保护未部署前不能释放。原逐层CPU7598两UID均1278，worker2819839/start_ticks2244339286/父2819751/start_ticks2244338224，均在/job_4537598/step_batch。worker一次TERM后Z；核实父无活子进程后父一次TERM，两实际/proc PID均ABSENT，不只看batch终态。原生作业FAILED0:15/9837秒，未SIGKILL/未TIMEOUT；保留L3和原缓存，累计GPU1217+CPU9837=11054秒，剩余3346秒供健康后的原诊断续接。原完整TRAIN生产4538532及其输出不变。准备进程2827663是slurmstepd，UIDs=[0,1278,0,1278]、start_ticks2244925324、job4538549，不能当成自有用户worker直接信号；需管理员核查kernel/Slurm/文件系统，底层根因未定。节点17本次drain归属未确认。后续入口须采用真实TimeLimit收尾余量至少180秒及完整子进程TERM/join/reap，新代码与测试尚待完成；不修改冻结科学源码、预算、模型或既有结果。


2026-11-22 16:32 CST：未来D入口退出保护代码已写入实际X:/MFM_d_recipe，共新增10个源码/测试文件，原P与冻结D科学worker未修改。exit_lifecycle按实际Slurm EndTime预留默认900秒（下限180秒），使用subreaper接管、自有UID/PID/start_ticks/精确step-cgroup验证、单次TERM及join/reap，无SIGKILL；训练通过原SAVE_AND_EXIT协议在完整更新处保存，不把安全退出75记为成功。新GPU/CPU/比较入口只调用原launcher，运行snapshot只增加资源与退出控制字段。新截断入口须原样传入整个reference配置/集合/报告路径，不能用会改变cursor binding的训练runtime克隆；复用原闭合分子计数和原atomic_cursor，不另算一遍。

现有10项生命周期测试4538556在CPU10完成0:0/1秒，主体0.303秒；16项实际源策略/生命周期测试及3个shell语法4538557完成0:0/23秒/1CPU，主体0.309秒，实际remaining_children=[]。新的含截断入口18项测试4538558在跑，不提前记C0。均无GPU或科学数组读写；未跑完整默认回归。新Slurm日志用/tmp/d_recipe_managed_%x_%j.log，避免Slurm管理进程先打开共享盘日志；必须在实际节点登记所有同行及D同盘未来增长（每条至少32MiB日志，canonical键exit_root_log_future_bytes），并保持max(10GiB,10%)根盘底线、inode及原fresh5秒UID配额守卫。源及此次报告同步在实际head目标以原guard.wait核准：含同行future、拟2GiB和1MiB元数据，无科学准入放宽。

五个旧seed1作业仍持有/未运行；它们已复制旧sbatch脚本，源码就绪不能直接release。实际配置/live Data预算及节点健康闭合后，先验证旧五项仍PENDING0秒，再以新入口替换同一组规定运行、重绑依赖；不新增种子或共享对照。源代码已实现不代表生产入口已激活。本线暂避CPU8持续故障通道，及已知14/16/17/18，CPU21禁用保持。

原完整TRAIN截断worker2822119/start_ticks2244363539、UIDs全1278、无子进程，原cgroup /slurm/uid_1278/job_4538532/step_batch复核后仅一次TERM；15秒观察仍D，start_ticks/UID未变而freezer行变为1:freezer:/，实际PID退出尚未证明，Slurm仍报RUNNING。没有再次signal/scancel/KILL，也未启动替代生产者；1020928/1194228原闭合游标、原配置/系数/RNG/构象选择及数组保留。此观察不证明OOM、磁盘满或底层根因。准备4538549仍为root/slurmstepd2827663启动等待，不能直接作为自有用户worker信号；需要管理员核查kernel/slurmd/slurmctld/文件系统。无任何现有模型训练因规则变更中断，无管理员操作/自行RESUME，节点17本次归属保持未确认。


2026-11-22 16:40 CST：扩展测试4538558在实际共享源码加载时出现原worker2632264/start_ticks2013721784/UIDs全1278、step0、D/rpc_wait_bit_killable；监督器2632262/start_ticks2013721779精确核对后仅一次USR1。内存中的原监督器实际发一次TERM，worker返回-15并OWNED_TREE_REAPED、remaining_children=[]；Slurm FAILED75:0/389秒/1CPU，不是TIMEOUT、不是18项通过。随后CPU15/4538559仅对原样捕获到内存的新截断源做2项策略测试及4个bash语法，实际在测试完成前进入5分钟分配的180秒收尾窗；监督器TERM两个自有PID1112577/4755403314与1112578/4755403317，全部reap、remaining_children=[]，原生FAILED75:0/119秒/1CPU，不算2项或完整集成通过。两次均无GPU或科学数组读写。该扩展入口按两次实际基础设施中断记UNRESOLVED，不继续在故障通道修复/测试；既有4538557的16项通过保留，科学seed0 WIN不改。

此次暴露出生产入口还需在读取共享模块之前就驻留外层监督器；内存外层在两次真实等待中已经证明能提前收尾，但尚未部署成生产启动链。四个新sbatch模板默认检查D_EXIT_OUTER_SUPERVISION，不满足即64退出，禁止直接提交或仅设置标志冒充具备监督。后续需真实外层监督、配置/全局预算/健康闭合后才替换旧持有作业。本线暂避8/10/15持续故障通道与已知14/16/17/18，21禁用保持。准备4538549真实硬截止18:18:03 CST；root/slurmstepd启动等待需管理员在此前介入，当前权限不能保证该管理进程可安全退出。没有直接信号root/管理员进程、没有KILL或自行重启/RESUME。Root报告和原第3层JSON已按实际head容量守卫同步到节点，未修改或运行新的模型科学配置。


2026-11-22 16:50 CST：恢复目标后的第三轮有界核查仍见4538549 RUNNING/02:31:13/CPU8，原4538532 RUNNING，五个4538551–8555 PENDING/JobHeldUser/0秒。实际head stat确认两个seed1配置和conditional registry仍无文件；准备日志存在但0字节，原mtime16:25:09.048939254 CST。不将历史root/slurmstepd PID身份视为本轮新核实，不再向故障节点添加诊断。前一轮属verified wait，本轮仍同一实在外部阻塞；独立允许的工作已完成，扩展入口两次中断后保持UNRESOLVED/禁用，不能以额外修复绕开停止规则。已满足恢复后连续三轮blocked审计，目标设blocked而非complete。保留原seed0 WIN、原统计及全部阶段1–3/条件种子/规定诊断/冻结后9M/最终A/B/C与两个PR范围，未删文件、未新开模型、未放宽预算/健康/退出门。准备真实硬截止18:18:03 CST，需管理员在此前核查kernel/Slurm/共享文件系统。恢复后先读实际最新产物/作业，保留任何新进展，禁止用此blocked快照覆盖后来的READY或已完成结果。


2026-11-22T09:37:26Z：用户明确要求更换节点完成任务并恢复goal。新核CPU8旧准备4538549已有自有batch PID2828496/start_ticks2245694583、UIDs全1278、父2827663、精确step_batch cgroup、无子进程；仅一次TERM，实际/proc确认ABSENT，原生FAILED0:15/10708秒/1CPU，早于18:18截止，无KILL/超时、未信号root。原clip PID2822119/start_ticks2244363539仍D/freezer根组，未再信号、未起同输出副本。旧准备writer消失后允许生成同一canonical seed1文件；不再等待已失败旧准备afterok。

CPU19真实Slurm MIXED/空32核。4538562实际根/tmp可用69410492416B/36542307inode、MemAvailable240247209984B，shared路径statvfs未返回即进入收尾窗，监督器TERM/reap、remaining_children=[]，FAILED75:0/99秒/1CPU，不把它记为共享盘准入。随后4538564仅在OS本地/RAM中执行原样捕获的原seed_plan、fresh_seed1_configuration和prepare_runtime，未访问共享源码/数组、未在该节点写共享盘；3项新resident渲染测试通过0.001秒，真实嵌套resident监督器/子进程集成0及children=[]，原生COMPLETED0:0/1秒/1CPU。结果按48字符base64行传回作为配置元数据；未重算科学统计或bootstrap。

Root在实际head-target原Guard.wait、fresh5秒UID配额、全部同行future与1MiB元数据预留通过后，以实际旧Data计划为CAS上下文封存原两条fresh3M seed1配置和唯一共享registry。D-R0/R1科学字段、原参数、seed1、样本轴/cosine、60000–150000新clip、原组件与数据顺序均由原prepare_runtime保留；无resume、seed0cache或权重继承。仅移除seed0节点专属基础设施字段。实际Data/live全局NFS36706053853+2147483648=38853537501B，full31897483648B；8槽232MB+128MiB原NFS日志/读出估算保留，Lustre不变。另每实际目标Root联合local日志未来128MiB，含所有拟D日志，实际节点仍按其他同行future与max(10GiB,10%)系统底线准入。

新resident_bootstrap默认不提交任何作业；生成的SBATCH使用系统Python-ISB及Slurm已复制的嵌入监督器，覆盖shell启动和共享模块加载。真实TimeLimit默认900秒收尾，协调USR1到直接managed child后由原SAVE_AND_EXIT保存，精确UID/PID/ticks/cgroup的TERM/join/reap，无KILL。5个原seed1作业仍核为zixiao/PENDING0秒，待本里程碑发布和新复制入口就绪后取消并重绑为同一组运行；GPU拟4/5，文件依赖CPU拟9/11/13，均在真实节点再次原Guard/空GPU检查。此时尚未训练，未发布新科学判定、未冻结或提交9M。原两次扩展clipping入口UNRESOLVED、R1几何UR及原层4/5余3346秒记录均保留，不冒称通过。


2026-11-22 18:20 CST：用户要求换节点后的实际模型已开始：GPU4/4538566 D-R0 seed1、GPU5/4538567 D-R1 seed1，均RTX3090、实际5CPU、TimeLimit2天，截止2026-11-24 17:42:02 CST。已在Slurm复制的resident本地代码中先驻留监督器，再加载共享managed入口/原科学worker；真实empty GPU检查分别5/24576MiB，原runtime guard闭合后才初始化模型。18:13:38 CST原生产日志均153600样本/4800更新。各自从原60000–150000窗口新冻结clip：R0=11.076789627075199，R1=25.356171264648438，均2813原更新、边界150016；只转录原事件，没有重新拟合/计算。初值281.7与目标±6截断是不同定义，原统计/存储值/整包与样本轴不变。后续统计4538568/4538569各afterok自身GPU；配对4538570 afterok两个CPU，候选/对照唯一路径与原规则不变，当前仍等待，没有seed1科学胜负或提前采纳。五个旧4538551–8555经zixiao/PENDING0秒核查后仅一次取消，原生全部CANCELLED by1278/0秒/0:0，没有旧脚本释放或重复对照。新Slurm入口省略显式内存参数，不将站点默认值宣称为有限物理保证。

R1剩余缓存层CPU8572已在CPU13完成0:0/81秒/1CPU。原run_cpu明确仅对scores.json尚不存在的层调用原评分，3/6原结果复用，无重抽样/编码器前向；原native summary COMPLETE、F64、1000分子bootstrap/20261025、ordered_layers3–6。实际resident日志OWNED_TREE_REAPED和RESIDENT_TERMINAL0/remaining_children=[]已读。累计GPU1217+原CPU9837+本次81=11135秒，小于4小时。原4/5聚合分值与CI转录至同一结果摘要；L4 R3=0.4230820073504759，CI[0.4089823913117095,0.43713599300959]；L5 R3=0.4160410356655566，CI[0.4026497812118607,0.4292698933378862]。不以更高诊断层替代固定主层6，原seed0 paired WIN不变。F64 geometry仍按原两次失败UR，不重启。

旧clip4538532实际17:33:36 CST以FAILED0:15/17350秒/1CPU结束。一次有界只读SSH在原CPU8确认2822119和旧准备2828496两个原PID均ABSENT，未再发任何信号/KILL；不能把本次补核查写成仅依赖batch终态。原cursor仍1020928/1194228、report不存在。以未改的整个native_D20.json、原collection/choices/分子字段计数/系数/同一output，通过通用resident直接调用原clipping.sbatch，在CPU13/4538573续接；未用未采纳的clipping_managed扩展，未再运行其失败测试。18:16:13 CST原关闭cursor已到1049600，实际RUNNING；producer进程3582788/start_ticks2758861610、监督器3582785/start_ticks2758861604、UIDs全1278、精确job4538573/step_batch已记录。stdout=/dev/null，沿用原cursor/final_report作为进度/产物，避免新增第五个local日志；已有每节点Root128MiB联合日志future不变。没有重复原闭合字段统计或重拟合A1/D4，没有原数据库或checkpoint复制。

全目标仍active，原进程退出与实际新节点工作已闭合，当前无主线外部阻塞；旧blocked快照已作为历史保留。seed1须各自原配对规则确认后才决定阶段2配方；后续全部L1/L2/G1、条件K1/种子、规定诊断、冻结后冷启动9M、最终A/B/C/基准接口/成本/两PR范围保持。实时训练与预期等待不构成goal blocked或complete。普通Slurm观察在head，每1800秒；科学代码/数值仅相应compute角色。


2026-11-22 19:46 CST：原完整TRAIN目标±6报告闭合。CPU13/4538573原生COMPLETED0:0/6260秒/1CPU，19:43:28 CST结束；原atomic_cursor1194228/1194228，原report.json statusCOMPLETE。仅沿原native_D20完整配置/原cohort、A1 choices与RNG、原分子项计数及同一输出，从1020928安全续完剩余原子项，没有重拟合/重复闭合字段。报告给出原24启用字段的D-R0/D-R1 valid/clipped/fraction；原子SASA分母63001422、clipped62681、原fraction0.000994914051305064，两配方相同。原D4/存储值未改，decision_input=false。原JSON通过实时X路径完整转录为results/d_recipe/native_TRAIN_clipping_20261122.json；第一次base64运输输出被截断后只改为完整原JSON传输，不进行独立数值复核、数组回读或新统计。

在Slurm实际CPU13 StateMIXED核查后，一次有界只读SSH直接核实监督器PID3582785/ticks2758861604和workerPID3582788/ticks2758861610均ABSENT；核查窗口11:44:13–11:45:12UTC，无新信号/KILL，不能仅由COMPLETED推断退出。原监督器/原科学worker不改。此前18:20及更早cursor/final_report字样指历史过程；本生产者实际最终路径为clip_reports/D20/report.json，当前已完成。

19:44 CST两实际seed1作业4538566/4538567均620800样本/19400更新，原日志seconds分别7191.102624610066/7230.534508820623；仅原事件转录，不由此新增吞吐/功耗统计或科学判定。原afterok统计4538568/8569和比较4538570继续等待。目标active，所有宽库/G1/K1/条件种子、冻结、冷9M、最终A/B/C/基准交付及两PR范围不变。ExpansionRx H政策再次以异步问题请求明确选择，依赖工作未擅自启动；现有训练保持。


2026-11-23 00:14 CST：原两条seed1 GPU4538566/4538567继续RUNNING，GPU4/5各原日志1852800样本/57900更新，原loop seconds23399.19392556697/23438.120212338865，原clip仍11.076789627075199/25.356171264648438。原1M samples_1000000.pt已各自生成（mtime20:55:22/20:55:27 CST、192027443/203777051字节）；21:14只核对原文件元数据，未读科学tensor或独立复核权重。原未改发布循环在每个登记milestone原子写入model/optimizer/configuration/architecture/clock、sampler及torch/cuda RNG、窗口及clip calibration；每条seed1保持唯一原配置/输出及共享对照登记，没有新训练或resume。

CPU4538568/4538569与比较4538570均PENDING/Dependency，保留原afterok；尚无seed1主分或科学判定，不提前采纳、冻结、开宽库/G1/9M。真实48h截止Nov24 17:42:02 CST及900秒提前收尾窗口保持。原全TRAIN±6报告已COMPLETE，不重启或重算；R1 F64几何UR及基准D20绑定UR保留，ExpansionRx H政策仍待异步答复，未启动依赖生产。新一天单页日报与实际CURRENT同步原生产进度；完整后续范围保持。原1M元信息和本次运行事件只是生产记录，不是额外数值QA或新统计。


2026-11-23 03:05–03:10 CST：用户在异步选择中明确批准“沿用既有B6补H程序：固定原有坐标，仅补氢坐标，不生成新构象”。Root将选择写入H_POLICY_20261123.md及Data独立配置；原QM9关闭component复用，ExpansionRx配置仅原全5278成员，后续既有merge恢复原15751成员顺序/划分。Data全局峰值38853537501B、开发D3 components/merge共同512MiB不增，source/native坐标、D20与D4不改；未启动新训练臂。

源码路径检查发现原complete_geometry的六个明确化学失败ValueError未被D3适配器的UnavailableD3接收。仅在已批准B6分支对这些原代码进行分类：断连图不支持、源原子顺序不匹配、MMFF参数/力场不可用、原500次不收敛、非有限几何，均保留原成员和原缺失原因，不重试/补值/嵌入新构象。坐标约束和未知错误不掩盖。新增2项测试，另20项相关原测试随源码改动一次运行；完整默认回归未运行。

CPU11现场StateMIXED、16/64CPU分配，root/源NFS/inode/UID配额由Slurm复制resident和原Guard实际准入。4539054真实COMPLETED0:0/8秒/1CPU，22tests/0.280秒通过，root可用69942870016B、inode36569960，原日志actualOWNED_TREE_REAPED及remaining_children=[]。新生产/合并复制入口用原development_d3.sbatch，CPU1、8h/1h、提前900秒收尾，stdout=/dev/null；不增加本节点第五个local日志。测试单独小日志纳入原每节点Root128MiB联合future。正式H生产及合并此时准备就绪，未冒充实际启动或交付完成。两个seed1与原CPU/比较afterok依赖保持。


2026-11-23 03:16 CST：批准H政策及22项真实测试源已发布Root bfa47cb与Data9af334f。原ExpansionRx生产4539057已在CPU11实际RUNNING，03:13:14开始，实际TimeLimit8h/截止11:13:14；原cursor next_member256于03:15:48确认，证明原实际Data/NFS/inode/fresh5sUID配额及同行future写入守卫已通过，不将03:09测试盘快照冒充本次数字。已核实际监督器4169297/ticks2249574973、原producer4169300/ticks2249574979，UIDs全1278、精确job4539057/step_batch，无新信号。

原未启动合并4539058为stdout/devnull复制入口；为使很短的合并也保留实际退出树证据，在原128MiB Root联合future内改为一个≤32MiB本地终态日志。此时测试已关闭并作为物理实存保留，未来3个CPU统计/比较日志+1合并日志仍共128MiB，Hproducer/devnull无额外增长。核实9058为zixiao/PENDING/00:00:00后仅一次取消，原生CANCELLED by1278/0:0/0秒；新4539061为相同原merge、相同config和afterok4539057，未执行两次合并。实际新复制入口及本地日志路径/tmp/d_recipe_managed_D3_merge_%j.log记录在launch配置中。该基础设施替换不改科学字段/坐标/成员/随机状态/预算。

03:15:48两GPU原日志均2707200样本/84600更新，原seconds34304.995509289205/34342.064588090405及clip冻结值未变；原模型CPU/比较afterok链不改。H组件与完整合并未闭合，尚非最终D3、C1或A/B/C完成。


2026-11-23 03:51 CST：原H生产与完整合并均闭合。4539057/CPU11 C0/1568秒/1CPU，03:39:22结束，原cursor5278；4539061 C0/3秒/1CPU，03:39:25结束。原component statusRAW_COMPLETE/member_count5278/complete_source_populationfalse；原merged statusRAW_COMPLETE/member_count/source_member_count15751/complete_source_populationtrue，原policy_by_dataset qm9/native_only、expansionrx/B6_fixed_native_H，原共同峰值203909476B<512MiB。两份原JSON完整转录到Data results/data_d_descriptors/下，没有读数值数组、重拟合或独立QA。完整源清单路径development/native_D3/merged/manifest.json供最终Section5消费；原receptionpending/C1false保留，A/B/C未执行。

原节点CPU11 StateMIXED，一次有界只读SSH核实原supervisor4169297/ticks2249574973和worker4169300/ticks2249574979均ABSENT；观察窗口19:41:16–19:43:04UTC，无新信号或KILL。合并原本地日志实际Rootworker4171120已reap0，RESIDENT_TERMINAL0/remaining_children=[]；原实际Root可用69942276096B/inode36569954，真实1h EndTime04:39:22，实际结束03:39:25。Root本地日志future原128MiB及所有物理实存保留，旧未启动合并9058取消0秒不计科学重复。原坐标/D20/D4/成员/划分不改；已批准H缺失策略不再等待用户。当前两个GPU原03:48:59日志均2867200样本/89600更新，原clip不变，原模型统计/配对afterok链继续。完整后续目标仍active。


2026-11-23 03:59 CST：一次性源同步检查原先将D已落盘产物仍全额计为未来，并未按P-heads原共享守卫扣除自身已提交物理块；因而保守总要求344316954333B高于当时实际UID余量342364442624B，20秒只读观察没有通过，未在此期间写入源文件。改为直接复用既有h_peer_storage.concurrent、h_resources.allocated及原模型remaining_nfs_other的容量记账：原D已提交物理块26927168593B，D剩余11926368908B，P-heads剩余1062502400B，followup剩余4626096128B。完整原同行预留和100000000000B底线后加1MiB元数据，实际目标原Data.guard要求302677289612B，fresh5秒快照准入通过。只更正临时head元数据准入的重复计入；没有修改任何已登记预算、同行future、100GB/根分区底线、5秒TTL、运行中科学代码或runtime守卫，也没有删除文件/读数值数组/暂停模型。新H原结果及全15751输入在源同步受阻前已经C0关闭，后续按原结果发布。

2026-11-23 04:16 CST：可选宽库 A1 计数复用适配器测试 4539136（1s）/4539137（0s）均失败，实际 resident 已回收子树；按两次失败规则记 UNRESOLVED，CLI 停用、测试显式跳过，不再修复或重试。宽库可交付状态及现有模型不变；若阶段1确认迁移胜出，后续使用既有通用 fit_reference 入口和原冻结 A1 规则，原 D4 不变。

2026-11-23 04:20 CST：两个 fresh seed1 的原训练汇总均已关闭为 TRAINING_COMPLETE_EVALUATION_PENDING，均3000000样本/93750更新、B32且has_resume=false。R0原seconds=38099.351692557335、clip=11.076789627075199、GPU_peak_bytes=4530274816；R1原seconds=38135.12057595514、clip=25.356171264648438、GPU_peak_bytes=4541469184。两者原3M原子发布完整状态断点已生成（192031923B/203781531B，原mtime UTC20:18:28.077220/20:18:31.709232）；04:20仅一次核对文件元信息及原配置arm/seed/budget，不载入或独立复核模型张量。GPU4538566/4538567仍RUNNING执行原规定读出，不能写成批作业已完成或已证明子树退出。CPU4538568/4538569、配对4538570仍依赖原链，逐seed WIN规则不变，尚不采纳迁移/冻结。原标量与元信息见[训练转录](../../results/d_recipe/stage1_seed1_training_20261123.json)。

## 2026-11-23 04:40 CST · 阶段1整包迁移确认

原seed0 ΔR3=0.09770468747584315，95%CI[0.08195311354654226,0.11189074805862387]；原seed1 ΔR3=0.1244890629833722，95%CI[0.10891211543183203,0.13955854300080836]，各自均WIN。按注册规则采用A1+B3+B4整包，γ=0.1597693323500406。没有合并种子CI、重抽样或第三种子。新五作业4538566–4538570全部C0，自有树均实际reap、remaining_children=[]。完整结果与边界见[阶段1报告](STAGE1_TRANSFER_RESULTS.md)，原比较/两种子采纳记录均已转录。

阶段2仅原L1/L2/G1，复用同seed D-R1控制；L1/L2用既有通用完整TRAIN A1入口，CPU11本地峰值分别4/16GiB。普通容量登记新增模型池3GiB（12槽×250000000B及221225472B读出/日志/缓冲），联合NFS从38853537501B增至42074762973B；保留全部旧输出与同行future，100GB/fresh5s/根盘max10GiB10%保护不改。新参考收集不拷贝原数据库，CPU11共同Root future38788923392B（新20GiB+既有16GiB+128MiB日志），系统底线另计。实际CPU11元信息Root可用69943164928B、inode36569937，MemAvailable387362352kB；新预算head准入要求305463892220B已通过，生产入口仍重查实际节点字节/inode/fresh UID配额。

04:36时0–7具备5CPU的节点4/5/6/7均有现存CUDA上下文；0/1/3 CPU不足，2不在现有gpu分区。实际20两张4090各约26GiB/49GiB，22的5090为14428MiB/32607MiB，均超过30%共存门槛。G1就绪等待合规卡，按1800秒复查；不进入占用卡、不操作现有上下文，不绕过故障节点。最终配置尚未冻结，完整后续实验继续。

2026-11-23 04:55 CST：原通用A1生产当前CPU11/L1 4539166、L2 4539169，各1CPU。原生产checkpoint分别闭合2048/1194228行（197分子标量，206.4338698759675生产秒）和512/1194228行（1320标量，64.1053820438683生产秒），实际Root余量69906649088B/inode36569906；只读原进度元信息，不触碰数值数组。实际EndTime分别11-25 04:50:12/04:52:37 CST，均真实48h、预留900秒收尾；原字段/算法/原D4不改。

首次4539163/4539164在创建数组前因原收集器对最近既存祖先/tmp做作用域检查而分别退出1（60/46秒），两原子树已reap/children=[]。入口仅先用原execution_site+DJointGuard核实实际输出，再创建其独立自有根目录，然后exec原reference.sbatch；两库各首个已关闭批次现已实际写出。Slurm非零显式mem dry-run不准，恢复与先前成功CPU作业相同的无mem声明/1CPU入口；dry-run的9162估计不是实际作业/成本。没有重试已UR的可选复用适配器。已跑两库不停止或迁移，G1等待21:06 UTC原定资源复查。联合NFS42074762973B、CPU11 Root future38788923392B和全部底线/同行预留不变。

2026-11-23 05:10 CST：原seed1成本4539171/CPU11 C0/8秒/1CPU，实际root4179323已reap0、children=[]。只对原闭合遥测作所需成本记账；R0/R1原整GPU作业墙时10.837222222222222/10.723333333333333h，分配CPU时54.18611111111111/53.61666666666667h；原训练循环含固定VAL吞吐78.74149734117515/78.66764165658762样本/秒，整卡采样均功耗285.0964274447949W（1268点）/232.4880378250591W（1269点）。父分配TotalCPU均原报00:00:00，记录为未提供而非测得0。只计原父分配，不将batch/extern/观察step或排队重复加入成本。

功耗范围按原record_gpu_telemetry源码条件0<samples<training_budget：原整卡点采样均值覆盖该训练活跃采样窗口，最终GPU读出不进入功耗样本；GPU分配墙时仍包含它。历史seed0功耗数值沿用，原含最终读出的范围措辞据源码澄清，不重新读取旧遥测。不是积分能耗或设备独占功率归因。原新成本文件见[D-R0 seed1](../../results/d_recipe/D-R0_seed1_complete_GPU_job_costs_20261123.json)和[D-R1 seed1](../../results/d_recipe/D-R1_seed1_complete_GPU_job_costs_20261123.json)。

21:05–21:09 UTC原定资源复查：节点1虽然有4CPU、可在将来空卡时用较少读取进程，但现仍有2个CUDA上下文；4–7亦均有上下文。20两卡26111/49140与26115/49140MiB，22卡27088/32607MiB，均不满足30%门槛。G1继续就绪等待，下一次21:36 UTC；两个CPU原A1生产保持。共同128MiB日志future内：两个参考日志各≤2MiB、新成本日志≤1MiB、两原计划统计/比较各32MiB，共≤69MiB；旧关闭日志在实际df中，不新增磁盘总预算。

2026-11-23 05:18 CST：原注册D-L1/D-L2/D-G1的主CPU统计和同seed D-R1配对入口已备妥，未提交，不增加训练臂/对照/抽样。CPU profile仅去除GPU本地缓存/节点绑定，保留模型科学条件及原输出；原prepare_runtime/closed_training_summary/compare_runs继续负责条件与配对绑定。实际GPU完成后，统计afterok该GPU、比较afterok该统计；候选CPU9/11/13、各1CPU，实际节点健康/Root/共享盘/5秒UID配额守卫及原resident收尾保留。统计8h、配对4h，预留900秒；不在登录节点执行统计，也不为等待GPU预占CPU。共同日志future仍128MiB：两参考各≤2MiB、六原计划统计/配对各≤8MiB共≤52MiB；已闭合成本/旧日志由实际df计入，预算总数不变。

2026-11-23 05:25 CST原进度：CPU11 L1/4539166 COLLECTING26368/1194228、197分子标量、原生产计时2040.1112610213459秒；L2/4539169 COLLECTING15872/1194228、1320标量、1905.9052537754178秒。实际Root可用69645864960B、inode36569896；两作业均RUNNING。按原生产秒/已关闭行作普通排程外推，收集阶段预计L1约11-24 06:32 CST、L2约11-24 20:44 CST；后续原ridge拟合/发布另计，实际速度会变，该估算不作停止或采纳门槛。下一次原游标检查21:55:36 UTC。

任务书4.2要求的输出头参数/名义前向成本已由冻结源码列于[HEAD_COSTS](HEAD_COSTS.md)：选定PMA维度577，H1每个分子标量头578参数；D20/L1/L2分子头数23/197/1320、参数13294/113866/762960，B32前向MAC424672/3637408/24372480。原子SASA头32897参数保持；G1关闭损失保留原头，二维块不放大。此为源码解析，正式训练前1000更新的原吞吐/功耗/峰值另记，没有新增模型/前向/探针或训练。

2026-11-23 05:36轮GPU准入检查于05:39闭合：实际gpu分区0/3无空闲CPU、2不属当前gpu成员；节点1/4/5/6/7均有CUDA上下文（分别2/1/1/1/1），即使节点1可按需减读取进程也不满足空上下文条件。20两卡26111/49140、26115/49140MiB，22卡27086/32607MiB，均超过30%；无合规目标，G1未提交。实际节点State均mixed/allocated、Reason none，无故障节点重提/绕行。CPU11原A1两作业于05:39仍RUNNING（49:26/47:01）；下一次GPU检查22:06 UTC，原游标21:55:36 UTC。


2026-11-23 06:55 CST：原就绪D-G1在优先组实际GPU7空卡补位，4539204/5CPU/3workers、fresh seed0/B32/3M；原日志4736样本、75.868646658957循环秒。原D20/A1与A1+B3+B4保持，仅关闭D3损失、二维权重不放大。CPU统计4539205→同seed原R1比较4539206按afterok原链提交CPU11/各1CPU、8h/4h；当前依赖等待，无采用判定。Slurm复制resident沿既有监督器，真实EndTime25日06:53:49前900秒安全收尾，实际Root45429927936B/inode36529018准入；某个preflight子树reap不代表完整训练已退出。GPU7共同Root未来17314086912B、CPU11未来38788923392B和联合NFS42074762973B不增，实际磁盘/配额/同行future保护保留；在跑作业保持。L1/L2原A1仍RUNNING，06:40原闭合84992/57344行；同一CPU纯排程粗估采集至24日06:20/17:50 CST、拟合另计，无科学阈值或预算更改。完整后续TASKBOOK范围保持。

## 2026-11-23 · G1主流程已闭合、终点诊断已提交

原4539204 GPU7 C0/37702秒×5CPU，4539205 CPU11 C0/54秒×1CPU，4539206 CPU11 C0/15秒×1CPU。原resident每棵子树已reap，最终children=[]，实际节点/proc对应原root均ABSENT；不以首个预检OWNED_TREE_REAPED代替整作业收尾。原R3和配对TIE、CI不跨0，故D3保留，无seed1；见STAGE2_G1_RESULTS.md。

3M原端点唯一、主统计已闭合。经技能11-22/11-06重读、实际健康/字节/inode/findmnt/GPU UUID零上下文核验、共享同行future登记和源先发布7fab219，启动原诊断：GPU6/4539284(2CPU/1h/提前300s)→CPU13传输4539286(1CPU/30m/300s)→几何统计4539287(1CPU/2h30m/900s)；缓存原GPU7/4539285(5CPU/45m/300s)→CPU13层统计4539288(1CPU/3h15m/900s)。CPU均afterok新原生产ID，不依赖已从scontrol移除的旧主统计job再提交。五入口为已有resident生命周期副本，原科学执行器未改；几何/层各累计分配预算4h、两失败UR，当前前向原cursor已608。

NFS42074762973B及CPU11原38788923392B保持；新GPU6与旧GPU7各17314086912B，CPU13 38788923392B，系统max10GiB/10%另留，实际与fresh UID守卫持续。原几何scope独立，只转闭合cache，不拷数据库/开发层缓存，不改在跑宽库/他人任务。

原RTX3090单次成本已闭合：80.61110553165612样本/秒，训练活跃采样窗整卡点均功耗228.29927302100162W/1238条，原GPU父分配10.472777777777777卡时、52.36388888888889分配CPU时。窗口不含最终GPU读出，父分配时长含读出，功耗不是积分能耗。[原成本](../../results/d_recipe/D-G1_seed0_complete_GPU_job_costs_20261123.json)只汇总一次；CPU13原生产4539289 C0/8秒×1CPU，实际子树已reap/children=[]。旧周成本/遥测不重读，TotalCPU与单价仍未知。

完整目标active；无暂停/缩减/提前冻结或新科学审批项。后续G1诊断/宽库原A1与既定全部关卡继续。

## 2026-11-23 20:06 CST · G1终点诊断全部闭合

原CPU13/4539292 COMPLETED0:0/4027秒/1CPU，原统计COMPLETE/F64/5000分子/47698构象/层3–6/1000配对bootstrap seed20261025，actual resident原root1757811/1757777均reap0且/proc ABSENT、children=[]。完整科学指标与原95%CI见[原转录](../../results/d_recipe/G1_geometry_native_summary_20261123.json)，退出/逐阶段成本见[G1几何记录](../../results/d_recipe/G1_geometry_3M_20261123.json)。几何累计原父分配7397秒包含原75失败前缀，声明4h不变；统计早于原900秒收尾窗口完成，无TIMEOUT/KILL。G1主结果/缓存层/规定几何均COMPLETE，无新seed或采纳门。

宽库L1/4539166和L2/4539169在CPU11各1CPU继续完整1194228 TRAIN，不停止/迁移。19:44原闭合783872/474880行，Root61668700160B/inode36569827；A1来源复核仅查看冻结代码：TASKBOOK4.1.4保留旧D20/D3/D4基础统计，4.3对全分子字段独立拟合A1，仅残差分档在各reference/L1,L2/label_parameters.json内派生其目标残差归一化，其余deepcopy原参数；不写旧D4/D20控制、不重算补充过滤统计、不重试已UR适配器。NFS42074762973B与CPU11/13原共同future38788923392B暂保守保留，不删除实存cache或减少同行预留。最终冻结/条件臂/冷9M/A-B-C/基准/一次完整回归与两个未合并PR仍待完成。

## 2026-11-24 03:07 CST · L1原A1闭合与宽库3M入口

L1/4539166原完整1194228 TRAIN拟合COMPLETED0:0、79720秒×1CPU。原FROZEN_FIT/197字段、unresolved=[]、original_D4_modified=false；原参数路径reference/L1/label_parameters.json，系数继续使用该原文件，逐字段R²/目标策略/有效数/±6截断计数比例原样转录L1_original_A1_fit_20261124.json，无新拟合、raw数组复核或统计重算。实际resident root4176565已reap0、children=[]，原CPU11/proc ABSENT。

技能11-22/11-06重读后，实际GPU5 SlurmIDLE/48空CPU、RTX3090 UUID GPU-dac07d74-6269-c7db-8832-340dd3c0b377，24576MiB仅5MiB、零CUDA计算上下文，Root57211424768B/total75125227520/inode36540394、/tmp同xfs root、UID1278。登记自身8GiB+保守同行8GiB+128MiB日志=17314086912B，系统max10GiB/10%另留；原NFS42074762973B已包含本3M checkpoint/readout池、不增。当前S两9M在20/22、P尾部未声明活动5，物理原cache保留、不动其它owner。

D-L1 fresh seed0/3M/B32/A1+B3+B4/原D3和原子SASA块、±6、旧D4、原新库统计及60000–150000新p99窗口全部保持；仅绑定GPU5/5CPU/3workers和已冻结原L1参数，无resume。入口复制既有G1 source-independent resident，48h/900秒收尾，原生命周期和科学worker未改。原CPU统计/配对各1CPU绑定已核健康CPU11，8h/4h、900秒，afterok新GPU/新统计；CPU11原joint future38788923392B仍保守保留。此时只发布准入与入口，未提交，不把准备写成模型已运行。L2/4539169仍原完整TRAIN生产，不停/迁移；最终配方未冻结，全部后续目标保持。
