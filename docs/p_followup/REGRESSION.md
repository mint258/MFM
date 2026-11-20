# 完整CPU回归与失败修复

## 2026-11-20 最终完整执行与原生上下文补测

最终完整执行4536755已结束（FAILED/1:0）：实际compute-0-17、8CPU、710秒分配；没有模块筛选或repair-from，覆盖全部203模块、3666项，3585通过、7失败、50错误、24跳过，执行器661.852107秒。源8406f1bf0d40debd53325ed71574d05270aa0e21在开始与结束相同。196个模块通过，全部本线新逻辑模块通过；七个旧native CLI模块的57个失败/错误均触发原有真实16CPU准入，不能将本次整体写为PASS。

七个待补测模块为architecture_wiring_smoke（36项）、execution_checkpoint_bridge（74）、long_run_storage（21）、pilot_entry（46）、proxy_runner（20）、training_entry（35）、wsd_fork（18），均带test_model_v3_前缀。原模块、16CPU保护和Slurm身份保持。补测4536800已提交，普通优先级、单机真实16CPU、限定CPU节点8–19、无GPU/非exclusive；以原始regression_4536755/summary.json为repair-from，只重跑这七个模块/250项，并保留此次完整运行的196个成功模块。当前排队，尚无补测通过证据。完整运行24项跳过是既有数据/显卡或显式数据准入条件，不是CPU缩配新增跳过。

默认仓库检查已实际执行两次，均FAIL/202项：4536755内首次9610文件/5017 Python/1307冻结来源，原报告原样保留runs/p_followup_20261116/repository_check_4536755.json。去掉检查器中重复的本线聚合CSV条件后，4536802再次执行默认命令，9612文件/5017 Python/1307冻结来源、202项；无路径过滤、未开启更强的verify-export。其真实FAILED/1:0、15秒、请求1CPU/实际分配2CPU。前一次4536801缺Git路径在0秒失败，保留日志并补同完整回归使用的现有Git路径后续跑；未改变检查规则。

202项全部是历史results/model_v3_diagnostics_20261112资产及旧p_recipe的两个CSV。对每个错误路径比较共同基线e1926db4d5a2faceff2659a901dc94a4b54093ef和当前HEAD的Git树blob，202/202相同，本线新增或改动错误0；没有删除或移动历史资产以消除报错。检查器相对基线只新增任务书指定的本线小型聚合CSV白名单，仍限2MiB/无NUL；没有放宽上述历史路径，不能声称检查器字节未改。当前REPOSITORY_CHECK.json保留实际失败结果。

后续只等待4536800的真实补测，补齐实际结果与成本，然后更新已创建的[未合并草稿PR #14](https://github.com/mint258/MFM/pull/14)；不再跑一遍完整203模块或重算科学结果。下文为历史验证，不能代替本次结果。

历史门禁：PASS。200个模块的完整检查及针对失败/改动模块的复测，合并后3659项测试，失败0、错误0、跳过24。成功模块的结果保留；修复只重跑相应模块，不重复科学数据读取或评价。当前修订的最终完整门禁待全部科学任务完成后执行，结果以新的实际执行记录为准。

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

D′ seed1组合统计复用新增test_p_followup_dprime_reuse.py：实际compute-0-20、CPU1/空CUDA，2 passed（0.04s，既有依赖弃用警告1条）。覆盖匹配的已关闭seed0不再读分数/计算，以及不同运行不得错用缓存；未重跑完整套件，全部工作完成后仍执行一次最终完整回归与仓库检查。

后续结项入口已准备为tools/p_followup/final_validation.sbatch（仅通过bash -n，尚未提交/运行）：完整调用full_regression.py，不带--repair-from；随后执行默认tools/check_repository.py，两者真实退出均保留，任一失败则作业失败。仅在更新任务全部完成后提交，不把准备入口或旧门禁当作新完整回归PASS。C3另用C3_geometry_cpu.sbatch，只补C3第6层，不重复已关闭的D′。

## 结项门禁范围核对（2026-11-19 03:38 CST）

current/pyproject.toml的默认pytest目录为tests。当前current/tests平铺203个test_*.py模块，无嵌套模块或额外*_test.py模块；其余4个Python文件是conftest及3个夹具。既有隔离回归器完整枚举全部203模块，逐模块pytest仍加载公共conftest；final_validation.sbatch调用full_regression.py时不带repair/module筛选，因此覆盖当前默认目录的完整测试范围。

仓库唯一GitHub默认检查为.github/workflows/source-check.yml中的python tools/check_repository.py；结项入口在完整CPU回归后执行同一默认命令并保存真实结果。当前只完成静态范围核对，尚未运行新的完整门禁；此前200模块门禁及后续定向测试保留各自来源，不合并表述为本次完整执行。

2026-11-20 22:36 CST调度修正：短工程补测4536800此前沿用UNLIMITED，可能限制短窗口回填；依据已测完整203模块710秒、旧16CPU修复174秒，将原PENDING作业原位更新为TimeLimit=00:30:00，scontrol实际回读成功。HPC技能测试条款要求明确测试墙钟上限；该30分钟只针对这次工程补测，覆盖参考完整执行时间的两倍以上，不是科学训练/拟合的新增停止门。编号、提交时间、普通Nice0、单机16CPU、允许CPU8–19及七模块/250项范围不变，未重新提交或启动训练。原提交脚本保留；生效值来自scontrol原位更新，仓库repair入口同步声明30分钟供后续复用。当前仍待实际分配，不把更合适的资源请求表述为已经开测或通过，也不把Slurm远期StartTime当成可靠ETA。
