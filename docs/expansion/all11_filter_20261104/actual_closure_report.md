# 全来源过滤与精确参考的实际闭合结果

本文保留 1885199 所用旧策略的实际结果。后续 case18 来源复核已实际完成，见[1885203 来源审查](../case18_source_recovery_20261104/actual_source_review.md)；该审查本身尚未生成新索引或重筛结果。

当前严格策略下，109,875,599 个候选的完整过滤已结束，只剩 52,859 个，不能形成要求的首批 250 万分子及累计 1000 万固定 R/N 队列。没有生成缩小后的替代批次，也没有把这次计算的成功终态当作扩充任务完成。

| 阶段 | Alpha 作业 | 实际终态 | CPU | 秒 |
|---|---:|---|---:|---:|
| 完整 11 来源排除索引 | 1885187 | COMPLETED / 0:0 | 16 | 9,855 |
| 完整 Common 精确指纹参考 | 1885196 | COMPLETED / 0:0 | 16 | 7,582 |
| 当前完整候选池过滤 | 1885199 | COMPLETED / 0:0 | 16 | 284 |
| 固定 64 查询缓存实测 | 1885200 | COMPLETED / 0:0 | 16 | 52 |

Slurm 返回的 TotalCPU=00:00:00 不表示实际零 CPU 消耗。上述 CPU 数为分配核数；分配核时可用秒数乘核数计算。原始账本文件保留。

## 全 11 来源索引

[独立验收](all11_index_1885187_root_actual_v1.json)及[原生产收据](all11_index_1885187_receipt.json)覆盖 15,291,170 条身份来源记录，另保留实际两条 MoleculeNet 正组成下界约束及已批准的 COCONUT 732 条范围处置。来源计数包括 v1 全角色及 embargo 的 11,236,754 条记录：SOURCE_TRAIN 11,104,772、SOURCE_ROUTINE 11,322、SOURCE_FULL 115,760、SOURCE_EMBARGO 4,900。它不是只覆盖 Common。

实际 577 项消费记录的全体 EOF/SHA 由生产者完成，Root 在相同计算节点复核关闭文件的实际 metadata；原 4 项 replica/V3 边界测试及 1 项实际依赖测试通过。342,609,920 字节 SQLite 的 SHA、原始科学函数指针证据和来源消费索引绑定在收据中。Root 没有重复声称读取整库 SHA；后续过滤在自己的资源保护下重新校验了整库。所有原图 UNKNOWN 保留。

用户批准的隔离仍严格限于原 732 条 COCONUT 记录。恢复的 3 条仅以精确非 H 组成参与排除，没有升级为已修复完整图。原原文、逐条审计和旧索引均保留。

## 过滤结果与实际瓶颈

[过滤验收](corrected_filter_1885199_root_actual_v1.json)及[完整生产收据](corrected_filter_1885199_receipt.json)记录：

| 项目 | 数量 |
|---|---:|
| 原始去重候选 | 109,875,599 |
| 排除候选（按 CID 去重） | 109,822,740 |
| 当前策略下可用候选 | 52,859 |
| 命中证据行（多来源可重复） | 190,222,694 |
| MoleculeNet case:18 下界命中 | 109,814,476 |
| MoleculeNet case:00 下界命中 | 3,750,394 |
| 仅保守下界带来的额外排除 | 48,953,492 |

候选守恒成立，52,859 个输出 CID 和完整键均唯一，Root 在 sonmi1 读取输出 footer 并重新校验了 14,760,580 字节候选文件 SHA。约 2.087GB 的命中 Parquet 保留在 Alpha，Root 复用生产者的全 SHA，只复核其 footer 和关闭 metadata。原 110,050,006 条别名按原两份物理数据引用保留。

case:18 绑定 PDBbind 1pts 的七肽配体。旧批准策略仅根据其原始稀疏模型观测到的三个 C-alpha 形成 C>=3 下界，因而命中几乎所有有机候选。case:00 绑定 ClinTox 的原 wildcard 结构，已知下界为 C>=14、N>=2、O>=7。两者都没有被用户此次 COCONUT 732 条批准自动豁免。

正在审查[独立来源对应证据草案](../molnet_case18_source_correspondence_PROPOSED_20261104_v1.md)：原 benchmark 1slg 的整个 formula 字段、既有组成身份行、官方明确序列与完整原子记录，以及原研究对同一配体复测的关联。该材料仍为 PROPOSED，尚无新策略采纳、索引改动或来源隔离。原 1PTS 的三个位点、原 graph UNKNOWN、旧下界、21 条审计和旧产物都保持原状。若新证据不足以闭合化学物及终端对应，旧规则继续生效。

## 精确参考和完整 100 万查询

[完整参考验收](fullCommon_exact_reference_1885196_root_actual_v1.json)及[指纹清单](fullCommon_exact_reference_1885196_manifest.json)包含全部 1,196,122 个 Common 成员，含恢复的 119 个。指纹为 306,207,232 字节、完整键为 33,491,416 字节；原 ECFP4/2048/radius2/chiralityFalse/RDKit2025.09.5 配方不变。关闭数据库有 1,196,122 个 MID、1,182,853 个不同完整键、185,507 个泛化骨架，身份与骨架频数总和均为 1,196,122。Root 在原节点完成 SQLite quick_check 和计数，原数学 9 项及元数据 3 项测试通过。

[固定 64 查询实测验收](fullCommon_profile64_1885200_root_actual_v1.json)表明 16 个实际 worker 各自完整解码全部参考一次，最大 load RSS 为 613,609,472 字节，最大 batch RSS 为 609,505,280 字节。每条查询的实际搜索数加严格界剪枝数均覆盖 1,196,122 个参考。该测量没有生成完整 100 万覆盖结果或放行候选。

完整固定 100 万查询已经作为 Alpha 1885201 在 compute-0-1 启动，实际申请 64 CPU、无 GPU。它保留当前修正样本的全部成员、原精确算法及最早 ordinal tie；query_batch/cache_commit_queries 都为原支持的 4,096。每 worker 软件预算 1GiB、parent 8GiB，总软件预算 72GiB，并要求额外 24GiB 节点余量；这些不是 Slurm 内存预留。没有科学墙钟或成本停止阈值。作业仍在运行，未宣布完整最近邻完成，也不打开活跃 SQLite 做外部全表进度统计。

当前真实可读结构分布见 [v1_distribution.md](../v1_distribution.md)。首批 250 万正式 UFF/D、1000 万 R/N 队列、扩充后覆盖及最终 batch1_report 仍未完成。
