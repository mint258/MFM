# 阶段2目标报告来源

任务书4.2、6、9要求的宽库逐字段截断比例，直接使用原通用A1拟合器的首次生产输出；没有另起数组扫描或复核作业。

| 库 | 原作业与实际终态 | 分子字段 | 原报告与状态 |
| --- | --- | ---: | --- |
| L1 | 4539166 / CPU11，COMPLETED0:0，79720秒×1CPU | 197 | [原完整拟合报告](../../results/d_recipe/L1_original_A1_fit_20261124.json)，FROZEN_FIT / unresolved=[]，原fit.fields已转录 |
| L2 | 4539164 FAILED1:0 / 46秒；4539169 FAILED1:0 / 81858秒，均1CPU | 1320 | [两次失败与原退出记录](../../results/d_recipe/L2_A1_unresolved_20261124.json)，UNRESOLVED；完整A1参数与逐字段拟合报告未生成，D-L2不运行 |

L1原完整TRAIN人口为1194228，冻结参数保留在`/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/reference/L1/label_parameters.json`。实际root4176565已reap0、children=[]、/proc缺失；本页只引用已关闭报告，未重新拟合或重扫数组，原D4未改。

L2原完整采集游标为729600/1194228，原peer配额守卫拒绝新增写入（available313207726080B，required313356249146B）；实际root4176838已reap1、children=[]、/proc缺失。依TASKBOOK3.5的连续两次失败规则停止此项，保留原partial数组且不以部分人口拟合、不第三次修复。L2的Stage0字段、统计、64样本逐头接收及完整二维导出仍有效；本项缺少A1报告和神经臂结果，不构成R3 TIE/LOSS或更大库无效的证据。未曾发布的L2参数路径不能作为已存在产物使用。

`tools/d_recipe/fit_reference.py:fit_collected` 调用既有`element_reference.make_label_parameters`，在同一全TRAIN拟合流程中首次输出每字段`field_name`、`target_policy`、`oof_r2`、`n_valid`、`clipped_TRAIN_count`和`clipping_fraction`；阈值为损失截断前标准化目标绝对值>6。L1沿用原报告精度与来源，不改写成独立原生标准化复核；L2这些结果如实缺报。

已有原D20/D3及逐原子SASA报告仍引用[原全TRAIN报告](../../results/d_recipe/native_TRAIN_clipping_20261122.json)，由4538573完成。旧字段、D4、存储值与原报告计数不改；不为新库重读旧SASA数组。最终报告区分原拟合器分子计数与既有原生报告来源，不重复生成旧统计。


## 2026-11-25 · 原续接1.5M固定验证（报告，不作判定）

原GPU4539402在GPU20由原1M完整状态续接后自然到达1500000样本/46875更新，原固定2000 VAL写出198字段原单位误差。[续接原窗口](../../results/d_recipe/D-L1_seed0_continuation_fixed_VAL_1500000_20261125.json)、[原CSV转录](../../results/d_recipe/D-L1_seed0_continuation_VAL_original_units_1500000_20261125.csv)。三块loss及梯度裁剪更新fraction逐字符串保留原生产值；未做额外前向/统计/重采样或校验。旧GPU4539360失败前1.5M报告独立保留，不覆盖、不据两窗口数值差选择配方。L1的R3门仍等待原3M、统计和同seed原R1配对；累计native秒含原1M prior和配额暂停，不标成整段4090吞吐。用户接手配额问题，本线推进已具备的独立工作，原进程/依赖/科学参数保持。
