# 存储清理补充指示（用户 2026-11-25 B）

适用：storage-cleanup-20261125。取代 `storage_current.md` 中"当前保留与删除规则"里"未知旧 DELETE/ASK 项不扩权""等待旧 DELETE/ASK 索引"两条；其余照旧。

目标不变：/share/home/zixiao 可用 ≥ 2,048 GiB，/lfshome/zixiao 可用 ≥ 500 GiB。

## 1. 规则改为白名单

只有下面列出的内容保留；第 3 节列出的工作区里，不在白名单、不被引用、没有在跑任务使用的内容，**一律删除**，不再默认 ASK，也不等待旧 DELETE/ASK 索引。

**保留（KEEP）**

1. D6 最终产物：`export/D6_full_v31_20261105_v1/compact`（/share），`/lfshome/.../D6_full_v31_20261105_v1/shared_compact/{TRAIN,FULL}`，归一化参数（`window2_TRAIN_normalization_parameters_*`）和标签参数（如 `label_parameters/PM7_A1.json`）。
2. 原只读 LMDB、人口/角色索引、split、250k/500k 等子集索引、atom-count 文件，以及当前配置引用的 `training_inputs*/manifest.json` 与配套 Arrow/索引。
3. WP5 已验收的 family parquet（`runtime/task_*/job_*/parquet`）与验收 catalog/delivery index。
4. P′ 最终标签表、completed catalog、最终成功/失败清单。
5. S′ 正式构象（`sprime_s_convergence_20261013/full/parts`、`conformers/formal_*`）；benchmark_B0/B1 的标签、下游 S′/S 构象和参考模型结果。
6. D 线阶段 0 已验收的 L1/L2 字段、统计与导出；D20/D3 数据。
7. 扩充线（`expansion`、`/lfshome/.../pubchem_completion_*`）中在跑或未闭合批次的全部内容；已闭合批次只删 scratch/tmp。
8. checkpoint：照已定规则（各 label-family arm、采纳配方、250k/500k、E1 终点、9M scaling 网格点、被引用的 ckpt、可能续训的最新完整状态）。
9. 所有指标、配置、日志、报告文本和 Git 仓库。
10. 任何被以下来源引用的路径：各分支 configs/manifest/corpus、在跑或排队作业（squeue）的配置、storage guard 登记的 future。

## 2. 已批准删除的类别（不再逐项请示）

| 编号 | 内容 | 估计 GiB | 门槛 |
| --- | --- | ---: | --- |
| A1 | `runs/model_v3_20261025` 全部（模型 v3 线 11-13 已终止），只留 `selected_train_request_4520413`、`selected_train_store_4520421` 和报告文本 | ~179 | 无 |
| A2 | `runs/model_v3_20261026` 的诊断/测试产物 | ~10 | 无 |
| A3 | `.perf_sync_scratch_20261117`；`MFM_step_overhead_20261114/.../gradients`；`MFM_precision_20261115` 的 school_wheels 与 TF32/BF16 对照产物 | ~26 | 无 |
| A4 | `runs/phase1_wp5_20261011/queue`（WP5 已闭合） | ~18 | 无 |
| A5 | `export/D6_r73_cache_relocation_candidate_20261108_v1` | ~93 | 第 1 节第 10 条无引用即删 |
| A6 | `stage61_data_input_audit_v1/scan_v2` 的 `pieces`、`chunks`、`pipeline_D4_v6_pieces`、`partial_checks`，以及未生效的 `proposed_masks` 版本（D6 实际使用的那一版保留） | ~80 | 无 |
| A7 | `sprime_s_convergence_20261013` 的 `dataset`、`s_training`、`probe_h0_v1`、pilot；`training_inputs_v1` 若被引用则保留 | ~28 | 无 |
| A8 | 所有 `.st_*`、`.pr_*`、`.pq_*` 临时目录，各处 `tmp*`、编译缓存、`__pycache__` | 小 | 无 |
| B1 | `docs/storage_audits/cleanup_property_geom_20261011/geometry/staged_geom_frames` | ~114 | 几何门槛（第 3 节） |
| B2 | `labels/source_status_v1` 下全部投影、覆盖、pilot、resume、day 工作区（被引用的单个文件保留，如 `bounded_old_complete_d5_resume_v2/.../train_240000.parquet`） | ~670 | 标签门槛 |
| B3 | `labels/window2_full_TRAIN_Pprime_statistics_20261106_shared_v1/projection` | ~148 | 标签门槛 |
| B4 | P′ 执行与准备产物：`pprime_formal_packed_sharded_day_v2`、`pprime_formal_packed_day_v1`、`pprime_complete_remaining_20261104_v1`、`pprime_retention_v1`（最终 catalog 与成功/失败清单保留） | ~513 | 标签门槛 |
| B5 | WP5 `raw_archive.sqlite` 原生档案 | ~127 | 已排队的 raw_output_gate（4540058） |

A 类合计约 434 GiB，B 类约 1,572 GiB，/share 合计约 2,000 GiB，已超过 1,765 GiB 的缺口。

## 3. 门槛（只做一次，由删除前的那一步做）

**标签门槛**（B2–B4）：对每个工作区 W，指定它被覆盖的最终产物 F（D6 compact、WP5 parquet 或 P′ 最终表）。

1. ID 覆盖：W 中状态为成功的全部（分子, 构象）ID 都在 F 中。全量比对键，不读数值。
2. 字段覆盖：W 的字段 ⊆ F 的字段。只存在于 W 的字段，抽出这些列另存为一个小 parquet（键 + 列），然后照删 W。
3. 数值抽样：每个 W 按字段分层随机抽 10,000 个（ID, 字段）对（不足则全取），要求 |a − b| ≤ 1e-6·max(|a|, |b|) + 1e-9·s_f，s_f 为该字段样本的中位绝对值（为 0 时取 1）。这个容差同时容纳 float32 存储的舍入（约 6e-8 相对）。缺失在两边一致算相等；W 有值而 F 缺失算覆盖失败。

**几何门槛**（B1）：帧的 (principal, 编号, 帧号) 全部能在正式几何源（原 LMDB 或 PM7 几何库）找到；抽 2,000 帧，原子数和元素序列完全一致，坐标最大 |Δ| ≤ 1e-4 Å，能量 |Δ| ≤ 1e-6·|E| + 1e-4 kcal/mol。找不到正式几何源的帧保留。

门槛失败：该工作区保留，日报记一行原因，继续其他项。**不是停止条件。**

## 4. 未盘点的部分（与第 2 节并行）

1. `/share/home/zixiao` 下项目以外的约 760 GiB（环境、缓存、其他目录）：按目录深度 3 计量，按第 1 节分类；pip/conda/torch/HF 缓存直接删。
2. `/lfshome/zixiao` 除 D6 以外的约 1,100 GiB（`model_v31_20261105` 下各运行、`LATENT_V3_*/readout_cache` 等读出/H0 缓存、`M2_DIAG_*` 诊断、`pubchem_completion_*`）：按同一白名单处理。读出/H0/embedding 缓存在对应分析已闭合时直接删（可由保留的 checkpoint 重建）；checkpoint 照第 1 节第 8 条。
3. /lfshome 若仍差：在 /share 达标后，把 /lfshome 上已结束、不再被训练读取的保留内容（结束的 checkpoint、闭合结果）迁到 /share。复制后比对一次总字节数和文件数，一致即删源。D6 TRAIN/FULL 不迁。

## 5. 停止条件

- 要删除不在第 2 节类别、也不在第 4 节规则内的内容：列入报告的 ASK 表，不阻塞其他项。
- 要停止或修改其他线在跑或排队的任务。
- 需要付费服务器。

其余一律日报记一行，继续。工程失败照 `docs/interfaces/TIMEBOX_RULE_20261125.md` 修好重跑。

## 6. 报告

`storage_current.md` 每天更新一次，达标时再更新一次：各类实际释放量、门槛失败项、ASK 表、两个账号的实时可用量。

## 7. 不做

- 不等待旧 DELETE/ASK 索引，不对第 2 节类别默认 ASK。
- 不逐文件算 SHA，不做删除后的二次回读；收据和 SHA 只给最终交付物。
- 不删 WP5 family parquet、D6 产物、原 LMDB、split/子集索引、正在用的 normalization/label 参数。
- 不压缩或重建 D6 LMDB（单独由用户决定）。
- 不动扩充线在跑或未闭合的批次。
- 不在 GPU 节点上跑扫描、门槛或复制；用 compute-0-8 ~ compute-0-19。
