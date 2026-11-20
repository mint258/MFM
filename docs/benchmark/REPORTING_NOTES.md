# 下游报告的固定说明

论文局限使用用户指定表述：**P 预训练模型在下游接收的是 UFF 几何。**

C1 的量子字段组标为 P′、P′+D；只消费对应 B0 已封存的数据和原生缺失掩码。原子级 C1 为原子 P′ 字段加 RDKit 原子特征，LightGBM；不把推测的 pKa microspecies 当实验位点。预训练、B2 全量表示提取、B3/B4 均未在本次执行范围内。

PPE 主任务仍为实验生成焓减 BensonGA、实验生成焓减作者发布 PM7 两个残差。pGrAdd 2.9.14 的固定 BensonGA 库在 298.15 K、kcal/mol 给出 896 个原生估计，其中域内残差 895 点；缺失基团值保持缺失。单独报告固定 BensonGA / 已发布 PM7 对原实验生成焓的基线与覆盖，不另拟合基团值、不重算 PM7、不新增候选端点。B0 参考几何与原始目标字段保留。

ExpansionRx 的榜单尺度与 B1 TRAIN 均值筛选尺度分别报告，见 [评分协议](EXPANSIONRX_METRIC_PROTOCOL.md)。Joung 的条件输入和冻结折见 [光学输入协议](JOUNG_INPUT_PROTOCOL.md)；NMR 只引用同发布划分数字，见 [NMR 说明](NMR_SPLIT_AND_LITERATURE.md)。

最终 B1 名单只执行一次预注册规则，并要求汇齐三个基线及完整折 / TEST 记录。Biogen / TDC 的原定附录角色不能由性能自动晋升。B1冻结时pKa机制因唯一位点定义未决而保留UNRESOLVED，该历史CSV与SHA不再改动。2026-11-21用户已批准作者37官能团目录；B0闭合投影7635给出5465 TRAIN/9个SAMPL6/7盲测原子端点。依[预先登记的补充协议](APPROVED_PKA_ATOMIC_SUPPLEMENT_20261121.md)完成首次基线和C1原子LightGBM，结果固定列附录，不重选任务。实验微观标签仍为0；原宏观值仅在目录定义唯一位点下复用，不做多位点分配，也不把目录当所有电离过程的完备性证明。目录来源TRAIN单/多/未决为5588/18838/5546，外部为9/29/6；这些是目录定义计数，不能称为全局物理位点分类。

统一 UFF 更新：C7/PPE 的早期 C1-D 参考构型 D3 输出只保留为历史记录；最终 C1 接 B0 已封存的统一 UFF D20/D3。实验目标与冻结 scaffold25 折不变；P′ 与 P′+D 均明确采用 UFF 单点性质，按同一实际构象 ID 对齐。最终汇总遇到缺失/不配对产出会停止定稿，只有已按两次连续失败或四小时规则关闭的项才能明确列为 UNRESOLVED。

C1 的分子 P′ 向量直接读取预训练原始 schema 的 67 个分子级 P 数值列，字段、单位、分量顺序不变；原子任务读取该 schema 的原子级 P 列并接原始 RDKit atom37。没有为表格输入新增原子/原子对池化统计。Joung 各特征组均保留原始溶剂二维描述符和显式 gas 条件，未生成溶剂构象或量化标签。原始原子映射不覆盖的 UFF 新增氢没有实验原子 ID，保持缺失。

PPE 固定经典基线的原生报告已交付至 [`PPE_native_classical_baselines.csv`](../../results/benchmark/PPE_native_classical_baselines.csv)：直接复制已关闭生产端4537083的204行输出，包含原始全体/域内可处理点以及方法原生可用/两方法共同可用的覆盖口径，并保留固定25折结果。没有重算统计、拟合基团值或新增任务；无额外SHA。

B1的17个必需神经配置均已完成第二种子确认：16项原显著改善中15项复现，ExpansionRx HLM CLint未复现显著性；¹H因原实际训练绑定重做按例外单列。固定B1名单不变。见[确认表](../../results/benchmark/B1_Chemprop_confirmation_results.csv)及[原生首次CPU统计与完整配对证据](../../results/benchmark/B1_Chemprop_confirmation_evidence.json)。后续C1最终打包直接复用已关闭的B1确认CSV，不重算其统计。

新批准的pKa原子附录首次生产7644已0:0完成：三基线TRAIN5465、盲测9；C1原生P′可用TRAIN4347、TEST9，缺失TRAIN不补。见[原样聚合表](../../results/benchmark/pKa_atomic_approved_baselines.csv)与[首次配对比较](../../results/benchmark/pKa_atomic_approved_comparisons.csv)。Chemprop较最强传统控制无显著改善，未触发第二种子。最终C1仅消费该闭合报告替换既有机制占位行，保留历史冻结角色字段；原B1表及其SHA不变。
