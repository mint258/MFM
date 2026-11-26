# 11-26 执行适配

遵循[统一调度修订](../interfaces/SCHEDULING_RULE_20261126.md)。这是后续运行的执行准备，尚无新 fullFT 结果；不改变原 S 配方、实验范围、50 轮微调或配对判定。

- 短 CPU 统计直接 SSH 到健康 CPU 节点，启动前实测 5 秒各核 idle、RAM、磁盘/inode及 UID 配额，记录真实 PID/start_ticks、CPU时间和自有退出。预算曲线的 CPU 统计已接入该入口，数学仍调用原 `budget_readouts_extension.work`，尚未执行新曲线统计。
- 微调先用 0–7 的合规空卡；无合规卡时支持 20/22 原生执行及同任务真实 Slurm 接管。保留原16 CPU需求、64 GiB RAM峰值、GPU余量和输出上限，不虚构 Slurm 分配。新写入先只读检查候选加入后的总需求，通过后才登记预留。
- P 的四个原登记源文件逐项匹配。原生微调仅在加载后的 `main` AST 中替换两处执行元数据：CPU需求读取改为显式16，摘要的作业号改为 `null`；另存真实 PID/start_ticks/原生句柄。优化、归一化、原始几何、采样、损失、内部分割及最佳 epoch 选择均复用原函数体。
- 每段真实35分钟，提前900秒停止领取新工作并保存原完整状态。接管须核实原生主进程身份消失及自有子树退出；安全续接保持源 checkpoint、数据成员、优化器、RNG及原50轮身份。已完成的拟合不重跑。只在自有待机任务 UID/PENDING/零运行核实并 hold 复核后撤销未用待机，不删除输出文件。
- 完成判定须科学摘要完成，并有真实原生退出证明或实际 Slurm C0及自有退出。选中模型保存时核对相同执行身份；`null` 作业号相同本身不构成证明。

检查均在 CPU11/core50 上直接 SSH 执行：新增[6项混合节点检查](../../results/s_recipe/mixed_fullft_runtime_check_20261126.json)，路径绑定收紧后仅复查[受影响1项](../../results/s_recipe/mixed_fullft_binding_check_20261126.json)，另有[2项续接检查](../../results/s_recipe/fullft_resume_check_20261126.json)和2项原生输出空间检查。既有科学统计和旧套件未重跑。原 P 入口的两处元数据适配已编译检查；首次真实拟合仍须在合规资源上完成运行验证，B0/G1优先。
