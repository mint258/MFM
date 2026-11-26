# 11-26 执行适配

遵循[统一调度修订](../interfaces/SCHEDULING_RULE_20261126.md)。这是后续运行的执行准备，尚无新 fullFT 结果；不改变原 S 配方、实验范围、50 轮微调或配对判定。

- 短 CPU 统计直接 SSH 到健康 CPU 节点，启动前实测 5 秒各核 idle、RAM、磁盘/inode及 UID 配额，记录真实 PID/start_ticks、CPU时间和自有退出。预算曲线的 CPU 统计已接入该入口，数学仍调用原 `budget_readouts_extension.work`，尚未执行新曲线统计。
- 微调先用 0–7 的合规空卡；无合规卡时支持 20/22 原生执行及同任务真实 Slurm 接管。保留原16 CPU需求、64 GiB RAM峰值、GPU余量和输出上限，不虚构 Slurm 分配。新写入先只读检查候选加入后的总需求，通过后才登记预留。
- P 的四个原登记源文件逐项匹配。原生微调仅在加载后的 `main` AST 中替换两处执行元数据：CPU需求读取改为显式16，摘要的作业号改为 `null`；另存真实 PID/start_ticks/原生句柄。优化、归一化、原始几何、采样、损失、内部分割及最佳 epoch 选择均复用原函数体。
- 每段真实35分钟，提前900秒停止领取新工作并保存原完整状态。接管须核实原生主进程身份消失及自有子树退出；安全续接保持源 checkpoint、数据成员、优化器、RNG及原50轮身份。已完成的拟合不重跑。只在自有待机任务 UID/PENDING/零运行核实并 hold 复核后撤销未用待机，不删除输出文件。
- 完成判定须科学摘要完成，并有真实原生退出证明或实际 Slurm C0及自有退出。选中模型保存时核对相同执行身份；`null` 作业号相同本身不构成证明。

检查均在 CPU11/core50 上直接 SSH 执行：新增[6项混合节点检查](../../results/s_recipe/mixed_fullft_runtime_check_20261126.json)，路径绑定收紧后仅复查[受影响1项](../../results/s_recipe/mixed_fullft_binding_check_20261126.json)，另有[2项续接检查](../../results/s_recipe/fullft_resume_check_20261126.json)和2项原生输出空间检查。既有科学统计和旧套件未重跑。原 P 入口的两处元数据适配已编译检查；首次真实拟合仍须在合规资源上完成运行验证，B0/G1优先。

统一读出入口 `execution_20261126/launch_readout_20261126.py ROLE RUN SAMPLES NODE UUID`：`budget`仅原B0/final两条9M的1–8M检查点，`terminal`仅三条新E1的3M及两条新子集的9M终点（含登记的3/6/9M读出），全部固定层6。普通GPU与20/22原生加真实Slurm接管复用同一个原读出函数；2小时真实时限、900秒收尾。未完成的单元从原已保存特征/完整probe文件接续；GPU真正退出并结清未用待机后，分别由 `launch_budget_statistics_native_20261126.py`、`launch_terminal_statistics_native_20261126.py` 接续CPU统计。新增[3项身份及范围检查](../../results/s_recipe/readout_runtime_check_20261126.json)通过，尚无真实新读出结果。

训练结束后的 `execution_20261126/close_extension_native_resource_20261124.py RUN` 已补齐待机结清：先确认登记预算、原生自有退出及真实PID消失；仅对UID/名称匹配、PENDING且零运行的待机hold，再复核后单次撤销。实际记账确认本账号零运行CANCELLED或成功COMPLETED后才退役写入预留；已启动、竞态变化或取消尚未结算时继续等待。新增[6项状态边界检查](../../results/s_recipe/standby_settlement_check_20261126.json)在CPU11/core50通过，实际父PID282494/start2281542259，墙钟0.467秒、退出0、自有退出及observer join闭合。检查未执行真实作业控制，未改在跑训练，也未重跑旧检查或科学统计。
