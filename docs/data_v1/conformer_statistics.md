# 构象统计与顺序（D-7）

状态：计算工具已准备；当前没有本轮全人群统计结果。真实数字由 `workflows/data_v1_final/conformers/statistics_tools.py` 从试点产物生成，不用人工填写结果。

## 目的与输入

分别描述 PM7 和 S′ 的 0.5 Å 去重构象数、≥2/≥5/≥10 的比例、构象数与大小/可旋转键/环数的 Spearman 相关性、PM7 生成热范围，以及 PM7–S′ 的 RMSD 分布。源 manifest、原子顺序和配方的固定 SHA 见 `configs/data_v1/conformers/pilot_v1.json` 与补齐报告。

## 规则

重原子采用源记录固定 atom index，对齐只允许平移及 proper Kabsch 旋转，不做反射和对称原子置换。去重阈值为 0.5 Å；分子内构象按能量排序后贪心去重。明确区分实际生成数、SUCCESS 且 converged 的可用数，以及去重后的构象数。补齐允许低于阈值的真实候选，它们保留标记，不据此虚增“不重复构象”数。

每个分子、每种几何来源保存三套索引排列：

1. 固定随机顺序：以 `sha256("data-v1-conformer-order:20261025:<molecule_id>:<source>:<conformer_id>")` 排序；相同 seed 下不依赖输入读取顺序。
2. 能量顺序：升序，能量相同以构象 ID 破同分。
3. 多样性顺序：从最低能量开始，每次选到已选集合的最小 RMSD 最大的构象；相同距离依次按能量与构象 ID 破同分。

S′ 能量为 UFF kcal/mol。试点 PM7 使用旧 S′ 科学实现的原生 PM7 energy 作为固定立体锚点和**诊断**排序依据。最终 v1 的 PM7 能量排序必须换成 canonical WP5 的生成热，并发布新的权威顺序产物；当前诊断产物明确命名 `pm7_native_anchor_diagnostic`，不能作为已定稿的 D-7 或训练接口。固定随机顺序本身不需要拟合标签或读取验证/测试表现。

## 输出与解释边界

试点输出 `conformer_statistics.json`、`orders.json` 及逐分子复现包。分布分位数使用 NumPy `method=linear`；Spearman 输入为每分子的去重构象数及对应结构统计，任一向量为常数时输出 null 并说明未定义，不伪造 0 相关。PM7 重合比例按 `(原构象数−去重数)/原构象数` 汇总，不能将此单一比例称为所有构象真实收敛路径的因果证明。

当前 trial 是刻意偏向缺口/失败的分层样本，因此所有产物标记 `PILOT_DESCRIPTIVE_ONLY`。完成全量后，需在最终 TRAIN+ROUTINE VAL 的共同人群上重新生成全人口计数、分布/相关性与哈希清单；需要的 canonical WP5 HOF 和最终 role 由对应数据接口提供。不得将旧 generated=10,782,661 代替严格 usable=10,782,419，亦不得把 countwise matching 当成 RMSD 对应。

## 原始构象数策略溯源

当前有限只读检索尚未找到最初决定每个分子构象数的生成策略。已检查：`legacy/descriptor/dataset/build_lmdb.py`、`workflows/dataset_rebuild/scripts/wp0_inventory.py` 及既有 S′ 的 `prepare.py`、`full_dataset_v7.py`。现有 S′ 实现按正式人口索引的已有 PM7 记录数 N 生成对应数量；`wp0_inventory.py` 统计原有数量，不说明原数据首次生成时的 N 选择依据。

最终报告应继续检索服务器历史生成流程并列出实际发现的源码路径与 SHA；找不到则写“未找到”。上述“未找到”仅限定目前明确列出的检索范围，不能推测 N 由可旋转键数、重原子数或经验公式决定。

## 异常与后续

身份、原子顺序或已验收旧构象立体校验不一致时留证并使本轮失败；不重新编号原子以强行配准。没有充分能量的分子仍可统计几何，但其能量顺序标记缺失。完整报告尚待实际试点、独立小样本复现、全量去重/排序和权威 WP5 能量对齐；当前文档不代表这些项目已完成。
