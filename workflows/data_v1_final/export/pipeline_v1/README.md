# D5 / D3 大表适配候选实现

本目录补齐磁盘物化入口，不修改已登记的 wire_v1、角色冻结源码或旧数据。实现与真实验收分别记账：当前 common/order、最终 family/unit/frame/物理 target 分组尚未共同冻结，不能执行最终生产导出，更不能将 fixture 当作 D3、D5 或 v3.0。Root 是唯一 Slurm 提交者。

## 数据流和内存边界

materialize 先读逐分子的完整角色、common、物理几何、三个构象顺序及分布特征的 Parquet pins。16 个 spawn worker 各处理互不重叠的输入 row group，落外部 SQLite 分片；父进程合并、校验并写真实 Parquet。每进程 SQLite cache 32MiB、temp_store=FILE；metadata batch 512 行，source batch 16 行，Arrow batch / staging record 上限 128MiB，source worker 实测 peak RSS 超 1.5GB 即停止，串行 LMDB 写出父进程超 3GB 即停止。峰值检查在批次边界，不能当成操作系统瞬时硬限额。32GiB Slurm 是整任务硬边界。所有中间 SQLite/partial LMDB 都保留；不删除源或测试证据。

source staging 保留 float64，只有调用 MFM3 writer 时转一次 float32。两个输入波次均最多16 worker：先几何，后标签。真实 WP5 base_geometry 用 len(atomic_numbers) 得到 N，D20/D3 没有 total_atoms，必须由已匹配的 canonical geometry 得到 N。每个 source spec 的每个 RG 只分配一次；不要把同一大文件重复列成16份。不同 task 需要额外显式 row_filters 和 owner task_name，不靠遍历顺序取最后一条。source 分片共享累计字节 cap；父 stage/LMDB 另按总输出 cap 复核。生产还要求一小时内的实际账号 quota receipt、总预算和至少200GB余量。

## 冻结输入契约

所有 pin 含绝对 path、bytes、sha256；hash逐一实核，不能仅凭文件名声称冻结。

| 输入 | 必需字段 |
| --- | --- |
| roles authority | status=FROZEN、validation_source=ROUTINE、all_conformers_same_role=true、source_role_manifest pin |
| 实际角色 manifest | status=ROUTINE_MOLECULE_VAL_ROLES_FROZEN、outputs 中完整 molecule_roles/part-*；不是 validation_molecules 单独子集 |
| common manifest | status=COMMON_POPULATION_V1_FROZEN、membership_tables pins、roles_manifest_sha256 绑定实际角色 manifest SHA16619f25… |
| common 表 | 全 authority 每分子唯一 molecule_id:string、common_population:bool；TRUE 只准 TRAIN/VAL，角色从实际角色表取得 |
| order manifest | status=CONFORMER_ORDER_V1_FROZEN、common_population_manifest_sha256、roles_manifest_sha256、source_geometry_tables、order_tables、order_types=[fixed_random,energy,diversity]、rank_base=0 |
| order 表 | molecule_id、geometry_source、order_type、rank:int64 从0连续、geometry_id；每个 common 分子的两个几何源、三种顺序均为同一组 base ID 的完整排列 |
| 几何表 | geometry_id、molecule_id、geometry_source、native_record_id、sprime_conf_idx、parent_geometry_id、view_id；所有 string 列显式 Arrow string，即使全 NULL；idx 显式 int64 |
| feature 表 | 每分子 molecule_id、element_z:list<int>（元素集合）、heavy_atoms:int、scaffold_id:string；空字符串只代表明示的无环骨架，NULL 拒绝；骨架必须来自提供的权威化学定义 |

几何只包含 frozen common。geometry_id 是提供的 opaque ID，绝不解析成 record ID。PM7 物理键为 (molecule_id,native_record_id)，idx=NULL；UFF 为 (molecule_id,sprime_conf_idx>=0)，其 native_record_id 仅保溯源，绝不用来 join/排除。base 的 parent/view 都 NULL。view 显式引用同分子同源的直接 base，继承物理键；不接受链式或跨源父键。

materialize config 需 roles_authority/common_manifest/order_manifest pins、source_geometry_tables（和 order manifest 精确相同）、feature_tables、seed、maximum_output_bytes、storage_budget。生产不能带 fixture_counts；--fixture 才可给 sizes/pilot_train/pilot_val/diagnostic 小计数。真实输出保留 source_role、effective_role，FROZEN geometry_map manifest 单向绑定 order pin，避免相互 SHA 循环。

## D5 实际文件

- train_120000.parquet ⊂ train_240000.parquet ⊂ train_600000.parquet ⊂ train_all.parquet；pilot_train.parquet 是前者前50k，pilot_val.parquet 为另5k VAL；val_all 另存。
- 均匀抽样用明确 seed 的 SHA256-uniform-order-v1，按 hash([版本,seed,角色域,molecule_id]) 排序，ID打破极小概率平局；使用独立 diagnostic 域。这是新的候选大表算法，不冒称与早期内存 PCG64 candidate 逐 ID 一致。指南只固定均匀抽样/seed，最终 manifest 明记算法。
- diagnostic_base.parquet 正好40k base行，PM7/S′各20k、同20k TRAIN分子；取 fixed_random 最后一个，两个源至少各有2个 base。diagnostic_targets.parquet 另含这些 base 和其全部直接 view。
- training_geometry.parquet 与 training_orders.parquet 先反连接全部 diagnostic target，再重新计算 training_rank；所有分子规模、几何、任务、k条件复用这一次排除。原 rank 保留。k截取必须按 training_rank，不能先截取再排除。
- geometry_map_manifest.status=CANONICAL_GEOMETRY_MAP_V1_FROZEN；diagnostic_manifest.status=SEEN_MOLECULE_UNSEEN_GEOMETRY_DIAGNOSTIC_FROZEN；D5 manifest.status=D5_PARQUET_LISTS_FROZEN。fixture产物一律标 FIXTURE_ONLY。
- distributions 输出各子集相对 train_all（VAL相对val_all）的元素存在率、逐重原子数频率、逐骨架频率、分母和差值；包括子集中频率0的全集类别。16 worker 读取互不重叠的 feature rowid 区间。

不足600k TRAIN、5k VAL或20k符合条件诊断分子直接拒绝，不降低数字。诊断只用于预训练损失诊断，不能模型选择。

## source / owner / mask 适配

source manifest 提供 files 数组，每个 spec 含 file pin、kind=geometry/labels、geometry_source、source_family、task、keys（molecule_id/native_record_id/sprime_conf_idx/view_id/可选geometry_id的列名）、明确 N 来源、可选 row_filters、owner_keys。标签 targets 列出本文件产生的显式 physical target IDs，components 按准确 field_key 配 selector。selector支持 column、JSON decode、嵌套 path、WP5 cell_registry_id（原CELL类型和shape核验）、逐项 project、明确 select_index、声明 reshape。D20 descriptor索引必须由已冻结名字/映射给出，不能猜。

分量 shape 明示 [] / [n_atoms] / [n_atoms,3] / pair行数；不将146统计行当146 heads。vector/tensor 经 wire_v1 显式 target 组合；tensor保留全部六分量和顺序。atom_indices 可显式重排/散射 atom scalar；缺原子必须有已决定的 missing_atom_reason_code，绝不自动补有效0。SOURCE NULL仅当 selector.null_value_policy=masked_nan 且整个mask为false时写NaN，并在header记录原NULL占位语义；没有source记录/没有target仍直接拒绝，不能用NaN伪造记录。

latest_owner_manifest（CANONICAL_LATEST_OWNERS_FROZEN）绑定 geometry_map SHA，owner_tables 行含 geometry_id、source_family、task_name、attempt_id、job_id、task_id。原始 attempt_id 可为 int8、task_id 可为 string：保存规范JSON类型，逐键精确匹配，禁止 int/string宽松相等。候选源不得按分子重复选任意历史attempt。几何可引用独立已核验几何authority；生产标签必须匹配完整 latest owner。

compact mask 无需展开巨大dense原因表。mask_binding 输入每 group 的 SHA-pinned owner_index（Parquet或显式 format=arrow_file）、列名映射、mask_tables、geometry_source、task_view_map；用 (group,record_ordinal,task_code) 显式匹配父/扰动几何，逐行保留全部原compact位集、source/new/review reason groups与leaf exceptions，加 opaque geometry_id。输入 field_map pin 明确 field_id↔field_key，并与 registry 全 enabled集合核对。reason_codebook pin单独保留。绑定manifest只冻结此投影，不代替原mask科学验收。

source component 的 compact={field_id,task_code}（或 task_code_column）从绑定表取mask；fixture也支持显式内嵌column。新 granular_store 不改旧wire：逐leaf valid，source/new/review三种字段原因集合、稀疏leaf index/code分开存；header明记粒度和codebook SHA。全false字段的原因集合不会伪造为每leaf独立原因，review不会改变bool。详见接口补充草案。

候选导出也必须有真实冻结D5输入与真实source pins；输入不存在就失败，没有造大表的分支。默认生产额外要求 registry/mapping、unit/family/frame 已验证冻结、MODEL_DATA_JOINT_CONTRACT_FROZEN v3.0 与模型/数据双方确认记录，并认可粒度扩展。P′仍是P在UFF条件下的目标，禁止拷贝PM7标签代填。输出目前固定 candidate/not D3 accepted；共同签字、源10k读回、模型loader、GPU节点本地性能/分发证据不能由源码预检替代。

## CLI

在 compute20 或 Root正式分配内，设置 PYTHONPATH=<checkout>/workflows/data_v1_final/export:<existing Arrow/lmdb deps>，使用 chemprop/bin/python -B：

~~~bash
python -B -m pipeline_v1.materialize --config <pinned_d5_config.json> --output <new_external_d5_dir>
python -B -m pipeline_v1.distributions --d5-manifest <d5_dir/manifest.json> --output <new_distribution_dir>
python -B -m pipeline_v1.mask_binding --config <pinned_mask_binding_config.json> --output <new_mask_binding_dir>
python -B -m pipeline_v1.export --config <pinned_export_config.json> --output <new_export_dir>
python -B -m pipeline_v1.verify --export-manifest <export_dir/manifest.json> --output <new_source_roundtrip_receipt.json>
~~~

export config 提供 registry、mapping、joint_contract（最终生产）、d5_manifest、source_manifest pins，subsets=[pilot_train,pilot_val]，partitions（每项name/kind/family/geometry_source/view_id/map_bytes），group_exposure_mask、family_exposure_mask、maximum_output_bytes、可选更严maximum_staging_part_bytes、storage_budget。source source_family 与最终 export family 不混用。source/mapping未冻结时 --candidate-only 仅放宽科学定稿门，不放宽真实common、roles、orders、ID、shape和source覆盖门。

verify 默认恰好随机10k export记录；不足拒绝。按 source file+RG分组重读原Parquet，逐字段比较原float64→float32后的精确值、signed zero、整数/掩码/原因/粒度header；核验各LMDB记录数、分子数、SHA。另16个spawn进程各自打开、读取、关闭句柄，父进程join后记PID、计数、hash和吞吐（含spawn启动时间）；这不冒充GPU节点本地磁盘吞吐。

Root渲染 run_pipeline.sbatch.in，16CPU/32GiB/1h/compute20，CUDA_VISIBLE_DEVICES空。Root按现场输入规模、存储receipt与profile复核后提交；模板不自行sbatch。

~~~bash
python -B -m pipeline_v1.tests --output <fresh_external_fixture_dir>
python -B -m pipeline_v1.profile --config <configs/data_v1/export/source_profile_owner_pilot_v1.json> --output <new_profile.json> --sample-rows 1
~~~

已实际source profile仅使用旧owner I/O试点的12个容器，每文件一行，只记录类型/shape，不输出科学数值；不是共同人群或训练资格。测试与profile证据由Root外部路径登记。所有真实50k、10k source验收、full导出与GPU节点传输仍需最终科学输入和Root实际作业。
