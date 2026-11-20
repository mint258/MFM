# 下游描述符接口（结构来源已定位，导出未执行）

此页登记任务书 4.1.5 / 5 的既有输入和待接接口，不是数据交付或评测结果。所有新字段、启用列和归一化必须引用阶段 0 的唯一 TRAIN 冻结产物，不在下游重新拟合或依据 TEST 值过滤。

## 开发面板

七任务由 `configs/p_recipe/protocol.json` 的 `scored_tasks` 与 `configs/dev_panel_v3.json` 冻结，沿用 P 评测器的划分。

- 实际成员入口：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/selected_train_store_4520421/native_store/training_store.json`。仅取 `train` / `train_inner_validation` 成员元信息。
- 按既有 `member_uid` 连接 `docs/phase1/evidence/stage43_downstream_membership/run_4511949/members.jsonl` 的结构 `source_frame`。该文件位于已有模型工作树；实际运行显式指定现有来源路径，不复制原数据。
- 复用 `workflows/data_v1_final/downstream_descriptors_v2/worker.py` 的结构读取器：QM9 `read_xyz` 跳过目标行；ExpansionRx `scalar_smiles_from_span` 只读取已登记 CSV 的 SMILES 物理范围。
- 已有 B6 二维特征：`/lfshome/zixiao/data_v1_20261025/window2_B6_descriptors_20261105_v2/shard-000-of-001/manifest.json`，`rdkit_descriptor_names` 对应 Parquet 的 F64 `rdkit_values` / `rdkit_mask`，通过原 `member_uid` / `source_ordinal` 连接。

B6 曾在 `source_structure` 后执行 `RemoveHs`，不能未经生产步骤的输入口径绑定便宣称其全部来源与当前原 D20 图口径逐位等价。相同图处理、软件版本和字段定义的闭合列才复用；其余按同一新库程序计算，不改变旧数据。

## 基准线

只读 `benchmark-b1-20261119` 的既有冻结策略，不修改其文件、终点或作业：

- `configs/benchmark_data/B0.DELIVERY.json` 当前引用 `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/delivery/directive19_current_counts_4537016/manifest.json`。
- `source_groups.*.records` / `records_by_nucleus` 为原始结构行 Parquet。只投影 `dataset`、`record_id`、`source_file`、`model_smiles`、`original_smiles`、`official_split`、`retained`、`domain_eligible`、`model_atom_to_source` 等已存在结构元信息；不解码含标签的 `original_fields_json`。
- 活动范围沿用 `workflows.benchmark_data.task_selection.select_active_tasks`；已有 endpoint catalog 位于相邻 `benchmark_B1_20261119/endpoint_catalog/job_4536889/manifest.json`。这不等于自行宣布最终终点已冻结。
- `configs/benchmark_data/B1.deferred_tasks.json` 的五个端点为 `EXCLUDE_FROM_CURRENT_EVALUATION`，身份不公开。不得推断身份或恢复比较；其未来恢复需要用户另行授权。
- 可复用二维特征入口：相邻 `benchmark_B1_20261119/B1_molecular_features/job_4536908/manifest.json` 与 `job_4536920/manifest.json`，字段 `rdkit_2d_names`、`rdkit_2d`、`feature_smiles`、`record_id`。沿用已登记 ID，不新建结构哈希。
- 现有 D20 原 F64/mask 与 UFF D3 引用位于 `benchmark_B1_20261119/C1_D_features/job_4536892/manifest.json`。

D3 继续由基准窗口按 S′ UFF 口径提供：`benchmark_B0_20261119/directive19/uniform_Sprime/geometry/shared_v1/queue.manifest.json`、`geometry_bindings.parquet`，使用封存产品的 `SharedB0Reader.get(dataset, record_id)` 与原 `model_atom_to_source`。不拿历史参考 XYZ 替代 UFF，不读取未封存 P′ 库。

## 已实现的接口（待测试与实际导出）

唯一分子表保留已有 UID / `shared_molecule_id`、原图 SMILES 与 source-frame 引用；成员表保留 dataset、record/member UID、原始划分、活动范围引用及 feature-row。多端点共享同一分子行，不重复计算。同一程序版本生成每库 F64 值与 uint8 状态（missing / valid / numeric event）；清单引用原 TRAIN 的 ordered-fields、enabled-columns、参数和版本。结构失败保留 missing，不补零。

已写好 `prepare_development`、闭合 B6 兼容列复用、`export` 和只读 `DownstreamDescriptorStore`。开发输入配置为数据分支 `configs/data_d_descriptors/development_inputs.json`，预估新增峰值 512MiB，仅为计划，未预约或提交作业。生产步骤保留每个成员的独立 D3 构象引用，只共享二维分子行；旧 D20 无法绑定时明确标为 UNRESOLVED，不用全缺失冒充完成。

导出支持 L1/L2 与原生 D20：仅复制 D20 时不初始化描述符计算器或 worker pool，17 个启用字段复用原参数。宽库保留全 TRAIN 的启用列和参数，不在下游重新过滤；状态和原始 F64 缺失保留。消费者以 dataset＋原成员 ID 连接，原始 split 原样保留，禁止用 A1 残差参数直接标准化化学描述符特征。

依赖仍未完成：上述新逻辑 CPU 测试、阶段 0 字段/统计冻结与真实接收验收、基准最终活动范围及实际导出。开发 A/B/C 尚未执行；MLP 容量口径正待用户确认，不能用现有 B6/C1 特征入口代替这些比较结果。

`prepare_benchmark` 已写好最小结构输入包装，必须由现有最终冻结 roster 驱动，候选 endpoint catalog 不作为冻结。旧 C1 缺少 C7/PPE/NMR 的新版 canonical/统一 UFF 绑定，以及无官方划分数据的冻结 CV 映射；这些依赖必须由基准线既有产物补齐，不能用全缺失表宣称交付。

`dev_descriptor_readouts.run_descriptor_probe` 直接复用既有 R3 训练循环，B 用描述符 MLP，C 在原 R3 分子 MLP 入口拼描述符；容量与 raw/原 TRAIN 标准化策略均由调用者显式提供。所有统计遵守既有内部 TRAIN 留出，保留原始缺失，只在模型输入边界做数值 padding 并附缺失指示。解析整数宽度不使用验证分数。最简组成参照提供完整含 H 元素计数加重原子数，供既有 ridge 读出使用，不新建预训练臂。
