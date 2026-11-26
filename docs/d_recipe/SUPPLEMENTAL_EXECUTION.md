# 已授权补充实验的执行接口

权威为[全量微调指示](USER_DIRECTIVE_20261123.md)和[scaling 指示](USER_DIRECTIVE_20261123B.md)。以下包装均未启动实际补充训练；主线判定、最终冻结及实际资源准入先行。

`tools.d_recipe.finetune_entry`在本进程内包装P原`finetune_entry.main`与`run_finetune`，保留原四任务、50轮、优化器、R3头、内层选择和完整状态续接。D-R0/R1按指示取3M seed0；其它表列3M臂的已实际触发并完成的seed1评测点也受“每个评测点”指示覆盖，不能用微调触发新预训练。9M及scaling均只有预训练seed0。微调种子始终0/1/2。现包装只支持真实Slurm身份；原生SSH混合后端尚待接入，不生成不符合后端的运行配置。原P相同协议scratch在实际统计阶段首次消费时复用。

`tools.d_recipe.budget_readout_plan`调用P原checkpoint读出配置构造函数；两条原生9M实际训练、读出和统计完成后，才准备各1M至8M的L6/H0 R1/R3。两条分子子集只新增3M/6M读出；各9M终点复用原输出。所有中间点标注原9M cosine轨迹，不能解释为3M独立预算训练。实际GPU/CPU驱动与`budget_curve.csv`原VAL联表仍待主线就绪后接入。

`tools.d_recipe.scaling_selection`为默认关闭的原P清单解析与D TRAIN交集；训练适配器仅在`d_explicit_molecule_selection`出现时替换TRAIN索引，VAL、全TRAIN归一化与A1系数保留。两个子集各自冷启动9M、seed0并重新校准本臂p99，不继承已拟合阈值。只有9M终点做全量微调。尚未生成实际D交集或任何子集运行。

原始P选择身份清单已定位于现有S生产者封存的两个`T5/T6_original_P_selected_MIDs.parquet`，由原P选择函数和原冻结配置导出；原生产者COMPLETE/exit0，文件均UID1278正规文件。所需的是这两份原始P身份清单，后续按原native身份映射解析并与D TRAIN交集。输入出处和实际路径见[源清单](../../configs/d_recipe/scaling/P_actual_selected_sources_20261126.json)。现只定位来源、读取原生产控制信息与文件元数据，未重读原标签、预测或选择数组。源清单仍是本线未完成工作的输入。
