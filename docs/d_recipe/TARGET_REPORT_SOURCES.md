# 阶段2目标报告来源

任务书§4.2、§6、§9要求的逐字段截断比例，直接使用原通用A1拟合器的首次全TRAIN生产输出；不另起数组扫描或复核作业。当前执行遵守[11-25补做指示](USER_DIRECTIVE_20261125.md)，L2 A1/D-L2的旧工程类UNRESOLVED已撤销。

| 库 | 已有生产证据 | 原报告与当前状态 |
| --- | --- | --- |
| L1 | 4539166 / CPU11，COMPLETED0:0，79720秒×1CPU，197分子字段 | [原完整拟合报告](../../results/d_recipe/L1_original_A1_fit_20261124.json)，FROZEN_FIT / unresolved=[]；沿用原fit.fields |
| L2 | 两次旧失败及分段续接记录，1320分子字段 | [旧失败记录](../../results/d_recipe/L2_A1_unresolved_20261124.json)保留为历史；[当前续接](../../results/d_recipe/safe_L1_handoff_and_L2_SSH_segments_20261126.json)RUNNING，2026-11-26 22:57 CST保存1128448/1194228行，尚未生成完整A1参数与逐字段报告 |

L1原完整TRAIN人口1194228，冻结参数在`/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/reference/L1/label_parameters.json`。原root4176565已reap0、children=[]、/proc缺失；这里只引用闭合报告，不重新拟合或重扫数组，原D4不改。

L2旧4539164在首次收集前因路径作用域准入失败（FAILED1:0/46秒）；4539169在729600行时被原额度守卫拒绝（FAILED1:0/81858秒，available313207726080B/required313356249146B），原root4176838已reap1、children=[]、/proc缺失。上述两次是用户已明确分类的工程失败，不据此停止L2或将其判为R3 TIE/LOSS。原局部数组与失败成本保留，当前从同一游标继续，原字段、数据、配置和拟合规则均不变。

只在原全量COLLECTION_COMPLETE、1194228行、实际最后收集器COMPLETE/0且自有树回收并消失后，运行原完整TRAIN拟合与冻结；不拟合部分TRAIN。之后运行原D-L2 3M/seed0，对照复用D-R1，只有seed0 WIN触发seed1。目标库选择等待L1/L2及各自按规则触发的seed1判定，D-K1、冻结、冷9M及A/B/C依序后移。不能把尚未存在的L2参数路径当已交付产物。

`tools/d_recipe/fit_reference.py:fit_collected`调用原`element_reference.make_label_parameters`，同一全TRAIN拟合流程首次输出每字段`field_name`、`target_policy`、`oof_r2`、`n_valid`、`clipped_TRAIN_count`、`clipping_fraction`；阈值是损失截断前标准化目标绝对值>6。L1保留原精度与来源；L2这些数值在完整原拟合前缺报。

旧D20/D3及逐原子SASA继续引用4538573闭合的[原全TRAIN报告](../../results/d_recipe/native_TRAIN_clipping_20261122.json)。旧定义、D4、存储值及原计数不变，不为宽库重读旧SASA数组。最终报告区分原A1拟合器分子计数与既有原生报告来源。

L1固定VAL和完整断点是原训练观测，不作3M/R3判定或目标截断比例。原1.5M续接窗口及旧失败前窗口各自保留，累计native秒包含旧1M prior及额度暂停，不能当作4090整段吞吐。[续接VAL转录](../../results/d_recipe/D-L1_seed0_continuation_fixed_VAL_1500000_20261125.json)。
