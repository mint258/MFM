# 11-26 执行适配

遵循[统一调度修订](../interfaces/SCHEDULING_RULE_20261126.md)。已有单次50轮全量微调闭合，四任务×三种子的完整评测点仍待汇总；不改变原 S 配方、实验范围、50 轮微调或配对判定。

- 短 CPU 统计直接 SSH 到健康 CPU 节点，启动前实测 5 秒各核 idle、RAM、磁盘/inode及 UID 配额，记录真实 PID/start_ticks、CPU时间和自有退出。预算曲线的 CPU 统计已接入该入口，数学仍调用原 `budget_readouts_extension.work`，尚未执行新曲线统计。
- 微调先用 0–7 的合规空卡；无合规卡时支持 20/22 原生执行及同任务真实 Slurm 接管。保留原16 CPU需求、64 GiB RAM峰值、GPU余量和输出上限，不虚构 Slurm 分配。新写入先只读检查候选加入后的总需求，通过后才登记预留。
- P 的四个原登记源文件逐项匹配。原生微调仅在加载后的 `main` AST 中替换两处执行元数据：CPU需求读取改为显式16，摘要的作业号改为 `null`；另存真实 PID/start_ticks/原生句柄。优化、归一化、原始几何、采样、损失、内部分割及最佳 epoch 选择均复用原函数体。
- 每段真实35分钟，提前900秒停止领取新工作并保存原完整状态。接管须核实原生主进程身份消失及自有子树退出；安全续接保持源 checkpoint、数据成员、优化器、RNG及原50轮身份。已完成的拟合不重跑。只在自有待机任务 UID/PENDING/零运行核实并 hold 复核后撤销未用待机，不删除输出文件。
- 完成判定须科学摘要完成，并有真实原生退出证明或实际 Slurm C0及自有退出。选中模型保存时核对相同执行身份；`null` 作业号相同本身不构成证明。

检查均在 CPU11/core50 上直接 SSH 执行：新增[6项混合节点检查](../../results/s_recipe/mixed_fullft_runtime_check_20261126.json)，路径绑定收紧后仅复查[受影响1项](../../results/s_recipe/mixed_fullft_binding_check_20261126.json)，另有[2项续接检查](../../results/s_recipe/fullft_resume_check_20261126.json)和2项原生输出空间检查。既有科学统计和旧套件未重跑。原 P 入口的两处元数据适配已编译检查；首次真实拟合仍须在合规资源上完成运行验证，B0/G1优先。

统一读出入口 `execution_20261126/launch_readout_20261126.py ROLE RUN SAMPLES NODE UUID`：`budget`仅原B0/final两条9M的1–8M检查点，`terminal`仅三条新E1的3M及两条新子集的9M终点（含登记的3/6/9M读出），全部固定层6。普通GPU与20/22原生加真实Slurm接管复用同一个原读出函数；2小时真实时限、900秒收尾。未完成的单元从原已保存特征/完整probe文件接续；GPU真正退出并结清未用待机后，分别由 `launch_budget_statistics_native_20261126.py`、`launch_terminal_statistics_native_20261126.py` 接续CPU统计。新增[3项身份及范围检查](../../results/s_recipe/readout_runtime_check_20261126.json)通过。首次真实运行已用于k1的3M正式读出：节点22原生PID229438/start82170434、退出0，自有退出及observer join闭合；未用待机4540341核实零运行取消后，CPU11/core50原统计120.157秒完成。完整来源见[k1记录](../../results/s_recipe/S_E1_k1_s0_3M.json)，未进行额外GPU测试或重抽样。

训练结束后的 `execution_20261126/close_extension_native_resource_20261124.py RUN` 已补齐待机结清：先确认登记预算、原生自有退出及真实PID消失；仅对UID/名称匹配、PENDING且零运行的待机hold，再复核后单次撤销。实际记账确认本账号零运行CANCELLED或成功COMPLETED后才退役写入预留；已启动、竞态变化或取消尚未结算时继续等待。新增[6项状态边界检查](../../results/s_recipe/standby_settlement_check_20261126.json)在CPU11/core50通过，实际父PID282494/start2281542259，墙钟0.467秒、退出0、自有退出及observer join闭合。检查未执行真实作业控制，未改在跑训练，也未重跑旧检查或科学统计。

11-27：k2原生GPU读出成功退出，CPU原统计120.667秒成功闭合。未用接管4540347在写请求前因字符串路径传给Path写入器而FAILED/1:0、运行1秒；batch失败/extern成功及目标节点实查均确认自有任务进程已退出，原生读出PID也已消失，才结清预留。保留该失败终态与源日志，未重跑已完成读出。读出与微调两处请求写入已显式转Path，[2项受影响入口检查](../../results/s_recipe/handoff_path_check_20261127.json)在CPU11通过，真实父PID302126/start2284011468、自有退出和observer join闭合。后续首条B0微调及预算曲线读出已完成真实完整状态/已提交单元接管；不据准备或部分运行宣称完整结果。k2的完整来源、失败待机退出证据及冻结结果见[k2记录](../../results/s_recipe/S_E1_k2_s0_3M.json)。

微调入口的自有读者互斥限定到精确UUID，完整节点RAM仍对所有在跑/候选写入者统一准入，64GiB微调预留未降低。因此合规的不同卡读出可与微调并行。`execution_20261126/advance_closed_gpu_20261127.py`只执行一次显式控制器序列：确认成功结清后接CPU/下一个登记点，不常驻轮询、不启用旧dispatcher。新增[2项边界检查](../../results/s_recipe/controller_sequence_check_20261127.json)确认部分拟合不能推进到别的拟合、最后一个9M前缀后不增GPU点。真实闭合数量及首条已封存最佳编码器/头/归一化工件见[执行进展](../../results/s_recipe/execution_progress_20261127.json)，不据单次拟合选配方或k*。

E1沿用S任务书4.4的冻结判定：WIN需CI下界>0且Δ≥τ，LOSS为CI上界<0，其余TIE。包装器已恢复该规则，仍复用P的原保留抽样Δ/CI/τ代数；不把P主线的额外负向幅度条件移入S。新增2个边界测试并复查4个受影响测试，通过[原S规则检查](../../results/s_recipe/e1_s_rule_check_20261127.json)。k1/k2的既有分数、Δ、CI和判定均未改变，修正仅使用已交付标量，不回读原预测/分数数组、不重新bootstrap或拟合。
