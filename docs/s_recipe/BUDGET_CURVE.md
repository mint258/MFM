# 原9M轨迹的预算曲线（进行中）

[budget_curve.csv](../../results/s_recipe/budget_curve.csv)已对齐两条原9M运行每500k保存的固定VAL记录，共36行。34份中间VAL记录只转录一次；两份9M最终VAL与两组9M R1/R3均复用已公开的终点交付，没有重新评估模型或bootstrap。

列名沿用P预算表的基本结构：`arm`、`samples`、`source_training_budget`、`source_run`、`readout_complete`、`R1_mean`/`R3_mean`及其CI、`VAL_loss_*`、`VAL_kind`。VAL保留原生产者的各头均值和观测计数，不从均值重造总损失；`disabled`注明未训练的头，S-final的`s_element`已停用，其原始VAL值仅保留记录。

两条原9M轨迹在1–8M的16个冻结读出及其CPU统计现已全部闭合；1–9M结果、既有9M配对差与固定VAL已填入表中。5个登记的全量微调点仍待完整结果，对应列留空；500k间隔中未登记读出的行明确标为`NOT_REGISTERED_AT_500K`。详见[状态](../../results/s_recipe/budget_curve_status.json)与[冻结读出曲线](../../results/s_recipe/figures/budget_frozen_curve.svg)、[固定VAL曲线](../../results/s_recipe/figures/budget_VAL_curve.svg)。后续复用已交付数组补齐微调列，不再打开原分数、预测或VAL文件，也不重新bootstrap。

全部模型点来自各自同一条9M cosine轨迹，固定第6层H0；中间快照不代表该预算下独立训完的模型，也不与原3M筛选运行作比较。完整微调尚未齐备，不据当前曲线改配方或补seed1。两个分子子集9M现已启动，另按原C2登记推进，不混入本页两条全量轨迹。
