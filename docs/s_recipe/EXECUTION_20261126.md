# 11-26 执行适配

11-27当前资源修订见[后续微调物理内存合同](RESOURCE_CONCURRENCY_20261127.md)：仅已实际跟踪的解释器采用8GiB后续微调预留，旧16/64GiB阶段与一次75安全暂停原样保留，预训练64GiB不变。下文64GiB说明记录早期合同。

后续在已登记的16点/192fit范围内，优先完成E1所需原独立3M S-R1（k10）及各cap微调，之后才给T6分配新卡；在跑训练保持连续。有限前台入口的`--point-only`只显式补齐同一点，末格结清后不自动提交其他点，交回根控制器按E1优先选择。两项新增边界检查真实CPU11退出0，见[同点顺序检查](../../results/s_recipe/point_only_sequence_check_20261127.json)；不改变科学点、种子、预算或原B0/G1先行要求。

后续控制器对`current_state.json`和资源future JSON使用同文件系统临时写入后原子替换，避免观察到半段JSON；不修改在跑训练的元数据函数。短CPU入口只在读/改/写future的短临界段取得相同flock＋POSIX执行锁，统计子入口核实实际持锁祖先后复用父锁，避免与GPU控制器并发覆盖或在父锁上自锁。三个新检查在CPU11实际退出0：独立进程被锁阻挡、真实持锁父进程可由子入口复用、替换失败保留完整旧JSON。见[控制元数据检查](../../results/s_recipe/control_metadata_io_check_20261127.json)。没有重跑科学统计或旧套件。

S-N1统计的实际配置始终只选用最新成功的12个fit；控制器报告列表最初也列入了该点旧75段4540393。仅报告元数据已更正为实际选中的12个成功作业，旧75段另列保留，原控制器和台账副本存档；原配置、primary、选中模型和统计计算未改或重跑。后续控制器从已选中的12份退出记录构造来源列表，避免把历史接续段当成功来源。

遵循[统一调度修订](../interfaces/SCHEDULING_RULE_20261126.md)。原S配方、实验范围、50轮微调及配对判定保持不变；实际已交付的四任务×三种子完整点评测见[微调进展](FULL_FINETUNING_PROGRESS.md)。

- 短 CPU 统计直接 SSH 到健康 CPU 节点，启动前实测 5 秒各核 idle、RAM、磁盘/inode及 UID 配额，记录真实 PID/start_ticks、CPU时间和自有退出。预算曲线的 CPU 统计已接入该入口，数学仍调用原 `budget_readouts_extension.work`，S-B0前缀读出已有真实CPU成功结果；数量以执行进展JSON的快照为准。
- 微调先用 0–7 的合规空卡；无合规卡时支持 20/22 原生执行及同任务真实 Slurm 接管。保留原16 CPU需求、64 GiB RAM峰值、GPU余量和输出上限，不虚构 Slurm 分配。新写入先只读检查候选加入后的总需求，通过后才登记预留。
- P 的四个原登记源文件逐项匹配。原生微调仅在加载后的 `main` AST 中替换两处执行元数据：CPU需求读取改为显式16，摘要的作业号改为 `null`；另存真实 PID/start_ticks/原生句柄。优化、归一化、原始几何、采样、损失、内部分割及最佳 epoch 选择均复用原函数体。
- 每段真实35分钟，提前900秒停止领取新工作并保存原完整状态。接管须核实原生主进程身份消失及自有子树退出；安全续接保持源 checkpoint、数据成员、优化器、RNG及原50轮身份。已完成的拟合不重跑。只在自有待机任务 UID/PENDING/零运行核实并 hold 复核后撤销未用待机，不删除输出文件。
- 完成判定须科学摘要完成，并有真实原生退出证明或实际 Slurm C0及自有退出。选中模型保存时核对相同执行身份；`null` 作业号相同本身不构成证明。

检查均在 CPU11/core50 上直接 SSH 执行：新增[6项混合节点检查](../../results/s_recipe/mixed_fullft_runtime_check_20261126.json)，路径绑定收紧后仅复查[受影响1项](../../results/s_recipe/mixed_fullft_binding_check_20261126.json)，另有[2项续接检查](../../results/s_recipe/fullft_resume_check_20261126.json)和2项原生输出空间检查。既有科学统计和旧套件未重跑。S-B0十二条实际50轮拟合及相应完整状态接管均已成功验证，原P统计生产者在CPU11/core49实际完成；B0/G1优先顺序继续。

统一读出入口 `execution_20261126/launch_readout_20261126.py ROLE RUN SAMPLES NODE UUID`：`budget`仅原B0/final两条9M的1–8M检查点，`terminal`仅三条新E1的3M及两条新子集的9M终点（含登记的3/6/9M读出），全部固定层6。普通GPU与20/22原生加真实Slurm接管复用同一个原读出函数；2小时真实时限、900秒收尾。未完成的单元从原已保存特征/完整probe文件接续；GPU真正退出并结清未用待机后，分别由 `launch_budget_statistics_native_20261126.py`、`launch_terminal_statistics_native_20261126.py` 接续CPU统计。新增[3项身份及范围检查](../../results/s_recipe/readout_runtime_check_20261126.json)通过。首次真实运行已用于k1的3M正式读出：节点22原生PID229438/start82170434、退出0，自有退出及observer join闭合；未用待机4540341核实零运行取消后，CPU11/core50原统计120.157秒完成。完整来源见[k1记录](../../results/s_recipe/S_E1_k1_s0_3M.json)，未进行额外GPU测试或重抽样。

训练结束后的 `execution_20261126/close_extension_native_resource_20261124.py RUN` 已补齐待机结清：先确认登记预算、原生自有退出及真实PID消失；仅对UID/名称匹配、PENDING且零运行的待机hold，再复核后单次撤销。实际记账确认本账号零运行CANCELLED或成功COMPLETED后才退役写入预留；已启动、竞态变化或取消尚未结算时继续等待。新增[6项状态边界检查](../../results/s_recipe/standby_settlement_check_20261126.json)在CPU11/core50通过，实际父PID282494/start2281542259，墙钟0.467秒、退出0、自有退出及observer join闭合。检查未执行真实作业控制，未改在跑训练，也未重跑旧检查或科学统计。

11-27：k2原生GPU读出成功退出，CPU原统计120.667秒成功闭合。未用接管4540347在写请求前因字符串路径传给Path写入器而FAILED/1:0、运行1秒；batch失败/extern成功及目标节点实查均确认自有任务进程已退出，原生读出PID也已消失，才结清预留。保留该失败终态与源日志，未重跑已完成读出。读出与微调两处请求写入已显式转Path，[2项受影响入口检查](../../results/s_recipe/handoff_path_check_20261127.json)在CPU11通过，真实父PID302126/start2284011468、自有退出和observer join闭合。后续首条B0微调及预算曲线读出已完成真实完整状态/已提交单元接管；不据准备或部分运行宣称完整结果。k2的完整来源、失败待机退出证据及冻结结果见[k2记录](../../results/s_recipe/S_E1_k2_s0_3M.json)。

微调入口的自有读者互斥限定到精确UUID，完整节点RAM仍对所有在跑/候选写入者统一准入，64GiB微调预留未降低。因此合规的不同卡读出可与微调并行。`execution_20261126/advance_closed_gpu_20261127.py`只执行一次显式控制器序列：确认成功结清后接CPU/下一个登记点，不常驻轮询、不启用旧dispatcher。新增[2项边界检查](../../results/s_recipe/controller_sequence_check_20261127.json)确认部分拟合不能推进到别的拟合、最后一个9M前缀后不增GPU点。真实闭合数量及首条已封存最佳编码器/头/归一化工件见[执行进展](../../results/s_recipe/execution_progress_20261127.json)，不据单次拟合选配方或k*。

E1沿用S任务书4.4的冻结判定：WIN需CI下界>0且Δ≥τ，LOSS为CI上界<0，其余TIE。包装器已恢复该规则，仍复用P的原保留抽样Δ/CI/τ代数；不把P主线的额外负向幅度条件移入S。新增2个边界测试并复查4个受影响测试，通过[原S规则检查](../../results/s_recipe/e1_s_rule_check_20261127.json)。k1/k2的既有分数、Δ、CI和判定均未改变，修正仅使用已交付标量，不回读原预测/分数数组、不重新bootstrap或拟合。

S-B0首个完整微调点的原P统计与其余选中模型封存合计14.505秒、真实退出0；统计计算本身2.218秒。交付首次因目标子目录缺失退出1，修复后只复用原已闭合primary，0.532秒成功交付，未重跑统计、拟合或bootstrap。逐种子MAE、四任务三种子均值、平均预测CI以及十二个已封存模型的原退出收据写入`results/s_recipe/full_finetune/`。新增[2项汇总边界检查](../../results/s_recipe/reporting_delivery_check_20261127.json)确认两种CI估计量不混用，且最后一个前缀未闭合时不能提前消费任何原分数。曲线全部16个前缀完成后，`budget_curve_delivery_20261127.py`只填已有CSV的读出/微调列并绘图，既有VAL列原样复用。

登录节点的本地XFS与计算节点NFS上，原`flock`不处于同一互斥域。[实际跨主机检查](../../results/s_recipe/metadata_lock_check_20261127.json)在CPU11/core49持有NFS锁时确认：登录侧单独flock未被阻塞，POSIX lockf被正确阻塞。后续登录控制器在原执行锁外同时取得lockf，兼容计算侧既有NFS锁，不改已加载的训练/微调/读出源码。B0 8M点原生阶段已安全暂停，实际4540365读出成功并自有退出；台账被并发覆盖后，依据完整身份、实际C0与原生PID消失证据，仅恢复对应行，见[单点恢复收据](../../results/s_recipe/B0_8M_takeover_reconciliation_20261127.json)。随后正常结清并接续CPU统计与S-final 1M读出，没有重跑8M科学计算。

跨主机原生入口的时间新鲜度下界调整为-5秒，与既有短CPU容差一致；超过60秒的旧任务或超过5秒的未来时间仍拒绝。截止点取创建时间与实际节点当前时间的较早者，再加原登记时长，900秒收尾不变，因此容差不会延长运行窗口。[3项边界检查](../../results/s_recipe/native_clock_anchor_check_20261127.json)通过。两次原生入口在Guard创建前抛出校验异常，原PID已消失且无新科学产物；旧stderr/task及未观测到原生wait状态的事实均保留。只在核实原4540371/4540372仍为本账号同名、held且零运行后，冷启动同一尚未计算的任务并释放原待机，未另交作业，见[实际恢复记录](../../results/s_recipe/native_startup_recovery_20261127.json)。只修改当时已无在跑任务的读出/微调入口，不动k5预训练；恢复后的原生与真实Slurm身份分别记录。

11-27 07:35：S-R1独立3M点的12个全量微调拟合均真实C0、自有资源结清。统计入口首次以相对脚本路径调用，在精确父进程路径绑定阶段拒绝、尚未启动CPU；改用既定绝对路径后成功启动原统计一次，未重跑拟合。CPU统计及12个选中模型封存16.046秒、退出0；交付0.538秒，配对代数4.540秒，均自有子树及observer闭合。k10参照的真实三种子均值CI也由该次原统计保存。完整结果见[微调进展](FULL_FINETUNING_PROGRESS.md)和[配对对比](FULL_FINETUNING_CONTRASTS.md)。同一GPU已接E1 k1，未启动N2或子集T6抢占E1优先级。上文64GiB微调预留为历史入口状态；当前后续预留及一次真实75暂停的保留证据以[11-27资源修订](RESOURCE_CONCURRENCY_20261127.md)为准，预训练64GiB不变。
