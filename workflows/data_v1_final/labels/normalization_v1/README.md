# 最终 TRAIN-only 统计 v1（实现候选，真实冻结输入待齐）

本目录补上最终 fit 侧表、规范读取器、多阶段计算与从 parquet 独立重建的可执行入口。旧 streaming_v1、scan_v2 及其配置/验收字节未改。当前没有真实 frozen common/geometry/diagnostic 和全量 final masks，配置中的 null 是明确缺项，运行入口会拒绝；本目录没有产生真实 D4。

## 权威输入与几何排除

`configs/data_v1/labels/normalization_v1.json` 是待绑定模板。正式运行另建配置，不覆盖本模板或旧已登记配置。四个 authority 必须是实际物化文件的 path/bytes/sha256：

| manifest | status / 关键字段 |
| --- | --- |
| common | `COMMON_POPULATION_V1_FROZEN`；`membership_tables`；`roles_manifest_sha256` |
| roles | 已有 `ROUTINE_MOLECULE_VAL_ROLES_FROZEN` 实际 manifest（SHA16619f25…），读取原 `molecule_roles` 16分片的 effective_role |
| geometry_map | `CANONICAL_GEOMETRY_MAP_V1_FROZEN`；`map_tables`；`order_manifest` pin |
| diagnostic | `SEEN_MOLECULE_UNSEEN_GEOMETRY_DIAGNOSTIC_FROZEN`；`excluded_geometry_tables`；`target_exclusion_tables`；common/geometry/order 三方 SHA；20k TRAIN 分子/各20k PM7与S′ base；`all_excluded_geometries_materialized=true` |

common 表为完整 authority molecule_id 唯一行及非空 common_population bool，非共同人群行保留原因供守恒；不能把“该分子缺一行”默认为共同人群。geometry map 至少列：

```
molecule_id:string, geometry_source:string ('pm7'/'uff_sprime'), geometry_id:string opaque,
native_record_id:string?, sprime_conf_idx:int64?, parent_geometry_id:string?, view_id:string?
```

base 行 parent_geometry_id=NULL。PM7 的物理 key 为 molecule_id+原 native_record_id，UFF 为 molecule_id+整数 sprime_conf_idx；二者只通过冻结 map 得到 opaque geometry_id。base 物理 key 与 opaque 复合 key 均唯一。view 的父 key 必须是同分子同来源的直接 base，禁止循环或跨源父键。UFF 的 native/source record ID 只作溯源，完全不参加 UFF join 或排除。不会解析 P′ record_id 前缀。order manifest 状态为 `CONFORMER_ORDER_V1_FROZEN`。

diagnostic excluded_geometry_tables 只放4万 base 复合键 `(molecule_id,geometry_source,geometry_id)`；两种来源必须恰是同一批2万共同TRAIN分子，每个来源每分子1个。target_exclusion_tables 物化 base 及直接 view 的复合键，每个目标都必须映射到被排除 base；冻结 map 中对应的 base/view 不能遗漏。其它审计列可保留。

最终 fit 逐 owner 记录物化 side parquet，完整保留纳入和排除行、effective_role、common 标记、geometry key及理由。只有 common 且 effective TRAIN 且非诊断几何可进入统计。PM7 一条 base owner 对应其全部量化任务，排除该 owner 会同时排除其扰动梯度目标。UFF 只排除指定构象，不会因共享原 LMDB parent record 而误排其它 UFF 构象。VAL、FULL、EMBARGO 和所有非共同人群均不进 fit。

## 标签源契约

`datasets[].manifest` 指向 `FINAL_NORMALIZATION_DATASET_V1` / `CANONICAL_MASKED_DATASET_FROZEN`：

```
dataset_id, label_group ('P_D'/'Pprime'), geometry_source ('pm7'/'uff_sprime'),
adapter='canonical_typed_family_v1', owner_record_semantics='base_geometry_with_task_views',
allowed_geometry_status:[...], enabled_field_ids:[...],
group_plan:{path,bytes,sha256}, mask_scan_manifest:{...}, mask_reduction:{...}
```

group plan 使用现有 canonical full owner分组 schema；PM7 owner_index 的 record_id 是原 native key，P′ owner_index 另有 int64 sprime_conf_idx。每组拥有 owner_index、base_files、label_files、expected_records，计划拥有 field_map、task_codes、element_basis、总 record/molecule 数和 coverage fingerprint。P′ 的 typed family和 base_geometry 必须来自其独立 UFF 标签数据，不能使用 `ORIGINAL_PM7_GEOMETRY` 状态。若未来 P′ 的实际基础几何布局不同，需新增明确 adapter 并验证，而非默默套原 P 的值。

mask scan 必须 full+phase=mask，绑定同一个完整 plan；reduction 必须守恒且 stop_fields=[]、每字段 new_mask_fraction<=1%。compact mask 从已 SHA 固定的 group receipt 输出读取。适配器重读原 typed cell、原 owner五键、lane/natom与原子序/payload SHA，重建原掩码并逐字段比较 source/new reason、bitsets、partial leaf exceptions；z>20/收敛NULL只复核，未转成新掩码。只在临时内存展开当前有效 TRAIN 记录，不复制正常原值。

目前 P′ manifest 缺失时显式保留 pending。可以先计算已有 P/D 的数值统计，但 `normalization_completed` 不会为 true，不能发布完整 D4 或复用 P 统计冒称 P′。

## 执行步骤与代价

生产入口同时核 Root request 与实际 `SLURM_MEM_PER_NODE>=65536MiB`、`SLURM_CPUS_PER_TASK>=16`；32GiB申请会被拒绝。共享 streaming guard 的32GiB通用下限供prepare/reduce使用，不替代此生产64GiB守卫。小型synthetic fixture可用8GiB，它只验证生产守卫的接受/拒绝行为，不运行最终源统计。

Root 先用新鲜 quota、全用户声明内存与 source refs 物化 `final_fit.sbatch.in`。默认 CPU analysis / compute20、16 CPU、64GiB、4小时、CUDA空；每 worker Arrow CPU/IO各1、BLAS/OMP各1。最多10遍源读取，64GiB unique inode 输出硬限（含侧表、统计scratch、目录、失败证据），DuckDB spill最多16GiB，worker RSS2.5GiB及单报告/压缩buffer256MiB、1百万radix项硬停。64GiB是限额而非实测消耗；提交前必须按实际 pilot 重新预算并保持账户至少200GB余量。没有自动 sbatch、重投、全量扫或原数据删除。

```
python -B workflows/data_v1_final/labels/normalization_v1/run.py \
  --config /external/real_frozen_normalization_config.json \
  --root-preflight /external/fresh_reviewed_intent.json \
  --output /external/new_final_fit_run
```

入口在同一批准的资源预算内，明确执行：

1. 校验四种冻结 authority及每个 full masked source，构建所有 owner 的 eligibility side table，核纳入+各理由排除=原source记录、人群与跨组ID唯一。
2. 第一遍由16个真实worker对绑定源文件重算SHA（包括未进入fit的源分片字节），并只在最终fit几何的有效TRAIN能量上做确定分组顺序TSQR。保存元素basis、系数、intercept、rank、singular values、rcond。秩亏或无值明确报告。
3. 接下来最多7遍用IEEE float64 radix同时闭合精确type-7 q0.001/q0.999：原始分量、每元素原子分量、能量元素残差、物理矢量xyz/norm、tensor Frobenius/trace各为独立审计series。保存prefix质量、查询与压缩计数。不会把所有正常leaf值持久复制到磁盘。每遍原始有效值、mask、几何和fit样本SHA必须与第一遍完全相同。
4. 最后一遍仅在临时统计副本上缩尾，算mean/std(ddof0)与按元素统计。raw能量及其元素残差分别保留尾分布/缩尾分布。空元素为n=0/mean=NULL/std=NULL，常量保留std=0，不造分母1。逐元素有效leaf总数必须等于相应全局原子leaf数。物理group另给完整有效矢量的原始均值向量与covariance，tensor norm按对称张量off-diagonal二倍平方加权。此统计不决定逐轴归一化、模型head或等变性约定，相关项均draft，frame实证仍单独待齐。

典型最坏约9遍源扫描（元素参考1+双尾radix7+moments1），另第一遍源SHA读取。其I/O与核时成本必须按真实试点测量，不隐瞒为单遍。达到预先批准的source pass、内存、输出或时间预算就保留失败/partial证据并退出，不能偷偷改近似分位或提高预算续跑。

## 独立重建与交付状态

第一次输出 `fit_population_manifest.json`、元素参考、各轮查询/计数/receipt、尾分位、`normalization_numeric_statistics.json` 和总 manifest。所有文件引用附真实hash。数值payload不含 walltime/PID/输出目录，来源、fit质量摘要与所有统计都包含在内。

Root 再以新鲜预算和新目录运行相同入口，额外传：

```
--replay-of /external/first_final_fit_run/manifest.json
```

它从冻结 parquet 与侧表定义重新生成 eligibility、重拟合元素参考、重新闭合所有尾分位、重算moments，然后逐字节比较规范数值JSON。不能只拿旧阈值重算mean当作独立重建。第二个 Root intent 必须绑定原 manifest，配置SHA必须一致。第一次数值统计不冒称已独立验证；P′缺项保持pending；模型的归一化/head约定仍待共同冻结，`D4_published` 永远不会由本脚本自行改为true。

fixtures入口（25项，含真实reader/worker的合成端到端重建）：

```
python -B workflows/data_v1_final/labels/normalization_v1/test_semantics.py \
  --output /external/new_normalization_fixture_receipt.json
```

仅小合成数据，16实际进程并行；覆盖真实侧表SQL、UFF共享parent不误排、PM7/扰动排除、角色/common泄漏、opaque键与诊断外键、空元素、常量、秩亏能量、P/P′独立、精确双尾/原值不变、部分向量、tensor权重、mask理由漂移、质量漂移及确定重建。测试待Root实际Slurm运行，静态审阅不能替代执行结果。
