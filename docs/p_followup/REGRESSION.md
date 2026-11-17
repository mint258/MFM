# 完整CPU回归与失败修复

状态：PASS。200个模块的完整检查及针对失败/改动模块的复测，合并后3659项测试，失败0、错误0、跳过24。成功模块的结果保留；修复只重跑相应模块，不重复科学数据读取或评价。

|阶段|Slurm作业|真实CPU|本次模块/测试|本次失败/错误|执行器秒数|
|---|---|---:|---|---|---:|
|完整检查|4535192|2|200 / 3538|13 / 79|634.06|
|失败模块修复|4535238|16|18 / 490|1 / 0|168.07|
|最后修复及改动模块|4535240|1|2 / 37|0 / 0|10.79|

部分测试在环境缺失时未能收集，修复后收集并执行，合并总数由3538变为3659。计算合并计数时，以重跑模块的新计数替换旧计数，保持其余模块；最后一次同时复测初始化模块。REGRESSION_FULL.json中的seconds、workers、repair_counts对应最后一次调用，counts、modules是保留成功模块后的整体结果；完整检查及两次修复的执行器时间合计812.93秒。

修复采用原有真实运行条件：需要native CLI的测试使用真实16CPU Slurm分配、原有PrivateStorage节点本地目录及既有PHASE1 native/reference Python路径；Git及完整仓库配置已补齐。F64测试在临时目录删除前关闭其mmap；以object.__new__构造的P夹具显式设置新增可选参数；旧D4重拟合测试迁移到当前只剔除分子的prepare_corpus入口，未恢复重拟合。初始化检查观察实际默认分配设备，并保留分配前对非CPU全局默认设备的拒绝，标准CPU/F32初始化与RNG行为保持。

原始日志/XML/模块摘要保留于runs/p_followup_20261116/regression_{4535192,4535238,4535240}。最后复测源28cb506，未改动运行中的冻结C_source。更早4535184为环境不全且D源码仍在增加时的中间记录，不用于本次有效计数；其原报告仍保留。

实际sacct终态依次为FAILED/1、FAILED/1、COMPLETED/0。连同中间4535184，分配时间分别为2CPU×640s、2CPU×636s、16CPU×174s、1CPU×16s，合计1.487 CPU-h；失败消耗包含在内。测试/tmp合计峰值预留10GiB，实际compute20根盘可用349.0GB，并在写入前及过程中保留系统10%下限。所有测试作业均已终止，其未来写入预留关闭；保留文件仍计入实际已用空间。NFS18GiB总预留继续覆盖历史scratch及尚在运行的研究产物。

本回归证明代码检查及上述模块修复通过。B3真实loader验收、C/D的3M训练和R1/R3，以及D2逐头真实使用验收仍分别由各阶段完成。

B1恢复新增的固定7字节句柄比较修复后，在compute-0-20以CPU执行现有F64 sidecar模块：4 passed，0.04秒；源c2984b6。命令为 python -B -m pytest current/tests/test_p_f64_sidecar.py -q -p no:cacheprovider。新增1项覆盖S7标量丢弃尾零、P/U类别和MI/CI差异；其余3项替换该模块原有结果后，当前有效合并3660项、24跳过、0失败/错误。REGRESSION_FULL.json保留原完整门禁3659项及28cb506溯源；本增量结果另存REGRESSION_B1_HANDLE_REPAIR.json，不将新代码归入旧作业。

## 2026-11-18 D′ PMA组合定向验证

用户补充计划要求只验证新组合，不重复64 TRAIN逐头验收。新增test_p_followup_pma_decomposition.py覆盖PMA下两个实际输出，以及conformer_decomposition=None与未设置开关的参数/预测逐位一致。原5项consumer测试同次通过，验证无PMA的D行为与mask/梯度权重仍成立。

实际compute-0-20、CUDA_VISIBLE_DEVICES为空、CPU单线程、既有chemprop环境，执行：python -B -m pytest current/tests/test_p_followup_pma_decomposition.py current/tests/test_p_followup_decomposition_consumer.py -q -p no:cacheprovider；结果7 passed（新增2、复用5），0.16s。改动仅将可选分解头安装移至PMA头安装后；关闭路径不变，正在运行D的冻结源码未改。既有完整回归记录保留，未把该定向结果表述为重新运行完整套件。

D′自动判定逻辑补充定向CPU测试：test_p_followup_dprime_decision.py的2项边界测试通过（2 passed，0.03s），覆盖0.06单种子门槛与严格CI、双seed共同符号和平均效应门槛，以及未触发时拒绝额外seed。四个后续脚本的AST语法检查通过；几何与MAE复用已有数学和固定面板，不新增科学对照。
