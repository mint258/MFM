# v1 标签适配工作流

本目录只增加新的适配器。WP5、S′、原 LMDB、历史登记表和统计报告均只读。

## 当前可执行入口

1. `build_registry.py`：仅重排已闭合的小型字段字典与统计 CSV，逐项生成登记表草案；不会拟合新阈值。
2. `prepare_pilot_plan.py`：交叉核验最终 catalog 与全量读回清单，生成新试点的来源文件投影和参数。Root 另提供 canonical record manifest 与真实 quota 收据。
3. `pilot_masks.py`：在默认 compute-0-20 的真实 16 核 Slurm allocation 内，spawn 16 个 worker 读取 family 文件。限定最多5,000条 canonical records，逐字段保留 float64 值、逐叶 mask、既有缺失、新规则原因和复核原因。它不会做全量验收。
4. `fit_normalization.py`：读取外部 observations，在冻结 TRAIN/common/training_eligible 上拟合。ROUTINE 作为 VAL；不会重新切分 TRAIN。未冻结角色时拒绝任何拟合。P′ 按独立 `geometry_source=uff_sprime` 计划处理。

所有输出新建，已有输出路径导致失败；失败证据保留。程序不删除原文件或临时目录。

## D2 重建

在服务器 compute-0-20 上使用已核实逻辑入口：

```bash
/share/home/zixiao/.conda/envs/chemprop/bin/python -B \
  workflows/data_v1_final/labels/build_registry.py \
  --pins configs/data_v1/labels/registry_sources_v1.json \
  --output /external/new_label_registry_v3.json \
  --summary /external/new_registry_generation_receipt.json
```

在项目仓库工作目录中执行；示例 `/external/` 必须换成 Root 指定的新目录。

## 试点输入接口

Root 提供的 `record_manifest.parquet` 每条 record 必须唯一，列为：

| 列 | 约束 |
|---|---|
| record_id、molecule_id | 与权威 population 一致 |
| attempt_id、job_id、task_id、lane | 与 latest_molecules 的最终 COMPLETE owner 完全一致 |
| total_atoms | 正整数 |
| new_role | TRAIN / VAL / FULL / EMBARGO；来自冻结角色清单 |
| common_population_v1 | 布尔；完整共同人群未冻结时只可供试点诊断 |
| atomic_numbers | `[N]`，与几何原子顺序一致；归一化元素参考与按元素统计必需 |
| training_eligible | 归一化必需；共同人群的 TRAIN 几何且不属于已见分子未见构象诊断集 |

每个分子的全部构象按同一角色；诊断构象仅改变 `training_eligible`，不改为 VAL。

quota 收据为新 JSON：`status=QUOTA_METADATA_VERIFIED`、`available_bytes`、`observed_at_epoch`，并应包含原始 quota 输出及 SHA 引用。程序要求距启动不超过1小时，且新产物预算后仍有200 GB。不能使用 `df` 代替账户 quota。

```bash
python workflows/data_v1_final/labels/prepare_pilot_plan.py \
  --catalog /share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/acceptance/final_20261016_v1/catalog/catalog.json \
  --verification /share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/acceptance/final_20261016_v1/D20_failure_aware_v2_4515602/verification_report.json \
  --record-manifest /external/pilot_records.parquet \
  --registry configs/data_v1/label_registry_v3.json \
  --mask-rules configs/data_v1/labels/mask_rules_v1.json \
  --quota-receipt /external/fresh_quota_receipt.json \
  --output-directory /external/new_label_pilot_plan \
  --max-records 2000 --max-output-gib 8
```

不扫描所有历史 attempt，也不打开 WP5 SQLite。来源大文件完整 SHA 继承已闭合 catalog/readback，试点读取前后额外核对 inode、大小和 mtime/ctime；小型输入和新输出实际重算 SHA。

为限制试点 I/O，优先从同一个 canonical owner job 选完整分子，先用约32–128条记录测量，再以实测内存、源投影 I/O、吞吐和失败率决定约2,000条试点。`max_records` 是 record 而非分子计数。每个 worker 内部还有保守的未压缩内存上限，不能按压缩 parquet 大小推断 RAM。

## 归一化计划格式

`schema_version=v1-label-normalization-plan.1`；`workers=16`；`mode=pilot|final`；`geometry_source=pm7|uff_sprime`；`expected_fit_train_records` 为计划中实际 TRAIN/common/training_eligible 的条数。

`sources` 对每项提供 path/bytes/sha256：`registry`、`observation_files`（JSON，内容为 observations parquet 引用列表）、`frozen_record_manifest`、`split_authority`。`storage_budget` 与试点相同，应预留16个 worker 的 DuckDB spill 峰值，默认每个2 GiB。`per_worker_duckdb_memory` 默认1GB。输入观察值列表本身必须已具备完整来源与 mask 验收，不能把试点观察文件当全量。

`split_authority` 要求 `status=FROZEN`、`all_conformers_same_role=true`、`validation_source=ROUTINE`。final 还要求 `common_population_frozen=true`、`training_eligible_records` 精确相符，计划中 `full_enabled_field_coverage_verified=true` 与 `diagnostic_geometries_excluded=true`。逐字段还实际检查 observations 数量、唯一 record 数及期望覆盖数，不能只靠这几个布尔字段通过。

```bash
python workflows/data_v1_final/labels/fit_normalization.py \
  --plan /external/normalization_plan.json \
  --output /external/new_normalization_output
```

此命令同样必须在16核 Slurm 中运行，不在登录节点运行。Root 是唯一提交者。试点模板不是可直接全量提交的脚本。

标签扫描、元数据准备、归一化均属于 `analysis`，在默认 compute-0-20 上仅用 CPU。旧草案把标签统计也限14–19是执行角色范围的过度泛化，已修正；量化/P′科学计算及UFF构象生成仍限14–19。此次修正不改变标签来源、mask阈值或任何科学结果。

## 尚未完成的科学验收

全人群 mask、每类最严重20例、全构象跨字段检查、矢量参考系受控验证、所有字段 size ρ、共同人群冻结、P′ 独立统计和独立重建逐位一致性仍需实际执行。当前非标量 size ρ 明确待确定旋转一致的分子级聚合定义，不把数组叶、xyz分量或索引混成分子标量。

本目录没有宣称这些步骤完成。任何字段新掩盖率超过1%会保存证据并非零停止；z>20 和收敛证据未知均只入复核，不自动 mask。
