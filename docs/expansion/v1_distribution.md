# v1 与 PubChem 分布对照（结构统计已完成）

截至本次验收，完整 Common 与修正后固定 PubChem 100 万样本的结构统计和三组图表已完成；任务书 2.1 尚缺完整 100 万查询的精确最近邻分布及其分析。此页不能作为完整 2.1 或 250 万扩充批次的完成证明。

| 群体 | 分子数 | 不同泛化骨架 | 单例骨架 |
|---|---:|---:|---:|
| 当前 PubChem 固定样本 | 1,000,000 | 221,134 | 166,863 |
| 完整 v1 Common TRAIN/VAL | 1,196,122 | 185,507 | 114,742 |

统计作业 Alpha 1885190 实际 COMPLETED/0:0，16 CPU、6,209 秒。当前样本采用原种子 20261025、原 hash 域和去污染前 min-CID/full-key 母体；与历史样本相比换入 31 个、换出 31 个成员。Common 已关闭的完整统计原样复用，没有重算 Common 特征，也没有用均值相减推算新样本。

![11 项描述符的原始分箱概率质量](population_statistics_20261104/descriptor_distributions.svg)

![28 类官能团的分子出现比例](population_statistics_20261104/functional_group_prevalence.svg)

![元素比例与骨架长尾](population_statistics_20261104/elements_and_scaffold_long_tail.svg)

绘图作业 Alpha 1885198 实际 COMPLETED/0:0，16 CPU、29 秒，2 项原生分箱及骨架频谱变换测试通过，三张 PNG 已逐图检查。图表从六份已验收计数表直接读取，保留原分箱、完整尾部和原 28 项官能团定义；没有读取分子或数据库，也没有重算化学。描述符图按原分箱显示阶梯质量；横轴显示两群体原分箱的 0.5%–99.5% 范围，完整尾部仍在 CSV。骨架图显示前 10,000 名，完整频谱保留。不同群体规模和组成会影响描述比较，不能据此声称覆盖增益或统计显著性。

可查看[完整结构统计报告及方法](population_statistics_20261104/v1_distribution_population_only.md)、[精确产物索引](population_statistics_20261104/artifact_index.json)、[统计验收](population_statistics_20261104/current_baseline_Common_statistics_1885190_root_actual_v1.json)及[图表验收](population_statistics_20261104/population_figures_1885198_root_actual_v1.json)。PDF/PNG 与完整分类 Parquet 保留在 Alpha，Git 提供 SVG、汇总表、代码及其字节数和哈希。

尚待实际完成：100 万查询到完整 Common 的 exact ECFP4 最近邻、稀缺结构分析、1000 万固定 R/N 队列、首批 250 万分子的 UFF/D 标签及覆盖分析。只生成最多 3 个实际 UFF 构象、不补足、不重试；本页不改变这些生成规则。

2026-11-04进度补充：按修正规则的全池过滤已实际完成，109,875,599个输入保留105,670,833个；当前去污染来源和版本/哈希见[登记清单](../../configs/data_v1/decontamination_sources.json)，[生产清单](results/20261104/exact_key_filter_1885209_manifest.json)保留完整分片与评估剔除证据。此项不代替尚在计算的100万最近邻或UFF/D完成证明。
