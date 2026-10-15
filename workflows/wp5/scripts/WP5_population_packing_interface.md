# WP5 正式人口与打包接口

脚本只读取已关闭的分析 parquet，不重新做几何识别或 QM，不写任何 LMDB。输出只放在本轮新根；主 agent 是唯一 Slurm 提交者。指南全文已经读过，正式配置采用无 POLAR、ESP、Hessian，C/D 与 xTB 全构象。

## 执行

使用已核实的 chemprop Python 与 scan_v2/deps。两个 sbatch 草案均为 compute-0-17 / cpu / 24 CPU / 32 GiB / 2 h；这属于提交前人口与打包准备。Root 按当前节点声明内存与准入修改节点后提交，pack 依赖 population 成功。正式科学作业另按指南 24 CPU / 32 GiB / 48 h。

```text
wp5_population.py --threads 24 --memory-gb 20 --spill-root /tmp
wp5_pack.py --threads 24 --memory-gb 20 --spill-root /tmp
```

两个脚本的 --check 只解析 AST，不跑数据。population 的 --expected-counts 可接收真实 fixture 的七项闭合计数 JSON（键为 physical_records、analysis_records、analysis_molecules、excluded_records、excluded_molecules、formal_records、formal_molecules）；正式默认固定 15,879,477 原物理、11,236,754/1,220,956 起点、排除 4,900/490、正式 11,231,854/1,220,466，不自动放宽。

## population

主输入为筛查 relaxed_quality_annotations.parquet、stereo_pair_classification.parquet、A1_stereo_consistency.parquet。缺失属性直接明确报错，原输入不变。

- population/formal_record_index.parquet：每个正式 record 一行，全部既有列和 QC 保留；源 source_path、real_index、record_payload_sha256 与原值一致。
- split 是新的 train/full；new_role 是 TRAIN/FULL。member_train/full 更新，member_routine 保持。original_split、original_membership、original_member_* 保留原角色，旧 logical_index 仍是来源索引，不冒充新划分视图顺序。
- component_id 来自所有正式重识别 14 位＋质子化键的二分连通分量。任何含原 FULL 的组件使其中原 TRAIN 的完整分子进 FULL；新移入分子不会加入 ROUTINE。
- file_group/file_bin 为整数 1–5，界限 22/26/30/36；原 file_bin 另存 original_file_bin。分箱按正式记录中每个分子的最大重原子数，同分子不跨组。
- population/molecule_index.parquet：molecule_id、records、max_heavy_atoms、max_total_atoms、component_id、split、file_group、原角色和迁移布尔字段，供打包直接消费。
- split_migrations.parquet、identity_components.parquet 保存整分子移动与组件证据；excluded_unassigned_index.parquet 保存排除的全部原列及原因，排除者不进入科学任务。
- population/manifest.json：每步记录/分子闭合、TRAIN/FULL/ROUTINE、五组、正式七层 strata（size_stratum/records/molecules/atoms）、三口径 TRAIN–FULL 零交叠、QC 正命中与未知、输入 SHA。

键复现异常使用旧 A 的 audited_difference_class 逐记录公式：对照 pair 解析源/生成 key 与该 record 的 stored/reidentified key。仅直接读取 pair.difference_class 会漏掉 42,088 类。QC 同时保留原解析类别、审计类别和接受键差异范围计数；手性/EZ 冲突复用已有 affected-molecule 缓存，不声称重算了全量立体或证明优化翻转。原引用 28,146/8,108 与 42,088/2,263 描述分析域，正式域过滤后的实际数单列，全部只标不删。

## packing

输入 population/manifest.json、C1 v3 方案矩阵、旧 analysis_geometry.parquet 10,020 行。所选成本方案为 relaxed/POLARdrop/ESPdrop/Hessnone/CDall；12 个保留任务的 all-record 均值已有 paired no-POLAR 缩放。原 native 每个 task 对每个 record 都有一次 outcome，因此各任务层内最大总原子数与该 geometry 表相同，可复现 C2 大尺寸规则而不重复扫描 131,701 outcomes。

分子服务成本为该层 12 项均值之和 × 正式构象数 × max(1,(总原子数/该层原pilot最大总原子数)^3)。规划分配成本只再乘一次旧 allocated/service 因子和固定 1.71。无任何 Hessian 或 ESP 成本。实际 5 万核时停止条件不能拿保守膨胀后的规划核时替代。

- 同 file_group、同 large_class 才可同任务；large_class 以分子 max_heavy_atoms>75 定义，普通目标 40 h、大分子类 20 h，24 lanes。每个 cohort 内按预测成本降序，整分子分到最轻 lane；任一任务预测超过 46 h 前重开任务。
- 单个分子如本身预测超过 46 h，会写明确 oversized 清单并报 REPACK_REQUIRED，不能把其构象偷偷移到另一任务或遗漏其人口。
- packing/tasks.json：tasks 内每项含 task_id、file_group、class/large_class、target_hours、molecules/records、24 项 predicted_lane_hours、predicted_wall_hours、预测核时、单分子峰值、node/node_slot、priority_rank 和 record_directory。
- node_slots 固定为 compute-0-14…19 的 4/4/4/8/4/5。用最早可用槽位的降序任务列表给出 ideal makespan；15/16可能排队的情况明确标注，不替换节点。
- packing/molecule_assignments.parquet：每个分子一个 task_id/lane/sequence_in_task，保留成本参数与新角色；全分子单任务、单组、单类计数闭合。
- packing/record_partitions/task_id=<id>/ 下是该 task 的完整 record index 与 QC。Root runner 直接按 task.record_directory 读少量 parquet，不逐任务反复扫描 1,123 万条总索引，也不建立逐 record 目录。
- packing/manifest.json：总任务、分子/记录闭合、各组×任务类计数、总规划核时、29 槽 makespan、完整模型来源与输入 SHA；输出分片完成后才发布关闭 manifest。

## 资源与存储

DuckDB 24 threads/20 GB；analysis_retained/eligible 是视图，不复制多份 1,123 万条宽表。连通分量 Python 仅留共享骨架的薄子图，全部分子表由 DuckDB 管理。packing 的 122 万 tuple/dict/Arrow 预计数 GiB，连同 DuckDB 可落在 32 GiB 分配内。数据密集阶段均由并行 SQL 扫描/分组/联接/排序/COPY 执行。

spill 新建在 /tmp 的 job_id+pid 私有目录，成功后删除本轮自有临时目录。正式索引和 task partitions 预计几 GiB；SHA、fixture 证明和永久 parquet 保留。没有删除任何旧文件。本阶段预算和最终任务数量以实际 Slurm 关闭结果为准，源码准备不等于已通过 runtime。
