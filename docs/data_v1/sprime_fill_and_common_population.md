# S′ 补齐与共同人群 v1

状态：补齐试点实现已准备，尚未运行；未发布共同人群，未宣称全量补齐完成。本文由 SB-2 维护，真实试点与全量统计将在对应脚本产物闭合后补入。

## 目的与输入

按数据线指南 1.2 补齐已有 S′，保留 UFF、图一致性、指定立体化学、源原子顺序和 0.5 Å RMSD 定义。原 LMDB、WP5 parquet、旧 S′ 数据和历史验收只读。

已闭合来源与 SHA256：

| 输入 | 路径（相对服务器项目根） | SHA256 |
|---|---|---|
| 原 S′ 科学实现 | `runs/sprime_s_convergence_20261013/scripts/sprime_v6.py` | `d6f1d29a6de673a1faf186e095c4fef7534a81022a09a4840ec65e5d8fa424d3` |
| 原来源读取辅助 | 同目录 `prepare.py` | `4b10dc5c0c2c1f3c42250ca1c8541c43661ada301484f92a6ce7bfce512f4a10` |
| 已验收 S′ manifest | `runs/sprime_s_convergence_20261013/dataset/manifest.json` | `a67e36e4fb1203f7fb72074abad3614bef6cd0e34140a38088f2492005912e01` |
| 最近严格对齐报告 | `runs/pretraining_readonly_audit_20261023_v1/reports/s_sprime_alignment_v4.json` | `764b4ccde3e51ed99990084bb4d26fd2972b27d4fb7b0f22ac6ef84e595286fa` |
| 对齐分子表 | 同审计根 `tables/s_sprime_per_molecule_v4.parquet` | `9b53e4611c5a3f199f785c8c201aa56ce76f559e3c81ccf10d1819624e03e354` |

原记录、分子索引的路径、字节数和 SHA 也固定在 `configs/data_v1/conformers/pilot_v1.json`。准备程序实际核验这些 pins；大型旧 S′ parquet 的预期 SHA 由已核验的闭合 manifest 继承，核对文件大小，所选行在生成阶段另核验几何/原子/立体信息。报告会明确区分继承的整文件 SHA 与本轮重新计算的所选数据 SHA。

## 规则与参数

- RDKit 数字版本固定 2025.09.5；ETKDGv3，单 worker 单线程，强制 chirality；UFF 2000 步、energyTol=1e-6、forceTol=1e-4。
- 普通去重不足：生成 min(10N,300) 个候选。原子索引重原子 proper Kabsch RMSD ≥0.5 Å 优先保留；仍不足时，从尚未选取的真实收敛候选中依次选最大最小 RMSD，记录 `below_dedup_threshold`。不复制坐标或记录凑数。
- 部分/技术失败：只进行一次新种子重试，ETKDG 嵌入 maxIterations 从 200 增至 400，并使用随机起始坐标。图、元素/原子顺序、源 SMILES/PM7 立体检查不放宽；不通过者保留失败。
- 既有成功且收敛的 S′ 行保持坐标与 seed，并保存原 `sprime_conf_idx` 映射；新输出的连续索引不冒充原索引。
- UFF_UNSUPPORTED 保持排除，不换力场。用户已批准仅 Se 单元素排除超过 20% 的例外；总排除 >2% 和其他元素 >20% 的停止条件继续适用。
- 新候选原始数据只在内存存在；所有失败及按分子 ID 固定 hash 抽样约 1% 的成功分子保存全部候选诊断。每个样本都有所选几何复现包，原始 LMDB payload SHA、几何 SHA、原子顺序、立体签名、seed、source_record_id 均可追溯。

## 已有基线统计

以下仅转述上述已闭合审计，并非本轮新计算：

| source_role | 分子 | PM7 构象 | S′ generated | S′ usable | 不足 N 的分子 |
|---|---:|---:|---:|---:|---:|
| ALL | 1,220,466 | 11,231,854 | 10,782,661 | 10,782,419 | 99,351 |
| TRAIN | 1,206,608 | 11,104,772 | 10,660,568 | 10,660,328 | 98,242 |
| FULL | 13,858 | 127,082 | 122,093 | 122,091 | 1,109 |

usable 严格指 `status=SUCCESS AND converged=True`，不能将 242 条其他 generated 行当成可用构象。补齐缺口包含 13,592 个零可用分子及 85,759 个部分可用分子；状态失败 13,736 个中包含 144 个 PARTIAL。Se 不可恢复排除下限已由 Root 预检核实：ALL 7,441/24,683=30.1462545%，TRAIN 7,383/24,396=30.2631579%；这解释了用户批准 Se 例外的必要性，不会成为修改 UFF 的理由。

## 本轮试点与验收

两个关键接口已逐项核对。严格可用数来自原 producer `s_population_alignment_v4.py` 的 `SPC_SQL`：`count(*) FILTER(WHERE status='SUCCESS' AND converged IS TRUE) AS Sprime_conformers`；相邻的 `Sprime_generated_rows` 才是无过滤 `count(*)`。该 producer SHA 为 `6d835e763411aca8fa127d45d4ceca0365c8f08cfa3aba0fd885df8cba9e6ae3`，与闭合对齐报告的 source pin 相符。Root 的 `control/source_schema_probe_v1.json` 已在 compute-0-20 用 PyArrow 25.0.1 仅读 footer 核实正式 WP5 `formal_record_index.parquet` 确实包含记录 ID/分子 ID/源路径/real_index/payload SHA/原子数/energy_raw/SMILES/两列分子立体冲突标记；不是误将 S′ 临时表的 schema 套给正式索引。原记录索引有 11,231,854 行、86 row groups，分子索引和 perMol_v4 均为 1,220,466 行。

脚本位于 `workflows/data_v1_final/conformers/`，准确 CLI 和资源模板见同目录 README。试点选择 320 个待补齐分子和 16 个充足对照，以 cohort、原失败状态、file_group、重原子数和 Se/P/Si 分层固定 hash 排序。Root 在新鲜 quota/节点/全部用户声明内存核验后统一提交；本实现不提交作业。

准备阶段建议 16CPU/32GiB/1h；生成阶段 16CPU/64GiB/4h，16 个 spawn workers，节点只用 14–19。每步新增输出上限 8 GiB，写入后仍须留 200 GB 配额。先报告每分子/构象耗时、成功数、真实失败原因、`below_dedup_threshold` 数量和磁盘占用，再决定全量。实际分配核时以 Root 留存的 Slurm 主作业 AllocCPUS×ElapsedRaw 为准，包括失败作业，不相加 batch/extern。

准备产物有所选分层表、源记录指针、旧可用构象和输入 pins。生成产物有 float64 parquet、全试点逐几何 SHA 读回、三种构象顺序、逐分子压缩复现包和 receipt。单个试点失败与整体程序/身份校验失败分别记录；后者不会被升级为成功。

## 共同人群与已知限制

最终共同人群为同时有完整 PM7 和充足 S′ 的 TRAIN 与 VAL 分子。按用户最新决定，VAL 来自既有 ROUTINE（7,610 个分子/11,322 条原记录），保留原 source_role 与 ROUTINE 记录 membership；需由 SB-1 冻结分子级 role 清单。当前试点在旧 TRAIN/FULL 中评估补齐，不能把全部 FULL 改名为 VAL，不能自行从 TRAIN 留出新家族。

最终仍需：全量补齐、按冻结 role 合并共同人群、对总排除和非 Se 元素停止阈值逐一核验，并报告排除前后元素/重原子数/骨架分布。N=1 分子的 P′ “前两个构象”接口需由双方明确处理，不能用复制满足两条要求。试点的分层抽样不是最终共同人群分布，不可用试点比例代替全量比例。
