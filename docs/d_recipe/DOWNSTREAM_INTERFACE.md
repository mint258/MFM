# 下游描述符接口与实际交付状态

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

## 当前生产状态（2026-11-23 03:51 CST）

| 产物 | 实际证据 | 状态 |
| --- | --- | --- |
| 开发原始结构与成员 | 4537410；15518唯一分子、15751成员 | SOURCE_READY |
| 开发原D20复制 | 4537508.step5；15518分子、20字段/17启用 | 已关闭；未重算或拟合 |
| 开发QM9原生D3 component | 4537546；10473成员、41个关闭批次 | RAW_COMPLETE；仅QM9 |
| 开发ExpansionRx D3 | 4539057 C0/1568秒/1CPU；原5278成员、B6固定原坐标补H | RAW_COMPLETE component |
| 完整开发D3 | 4539061 C0/3秒/1CPU；复用QM9后原15751成员/顺序/划分 | RAW_COMPLETE，complete_source_population=true |
| 开发L1/L2 | 原4538204 COMPLETED0:0，612秒、15518唯一分子、各61批 | 已关闭；191/1314启用，原TRAIN参数复用 |
| 基准L2 | 原4538205 COMPLETED0:0，7842秒、194729唯一分子、761批 | 二维源已关闭；下游接收pending，C1未完成 |
| 基准原D20绑定/L1完整交付 | 4537426、4537509均未解决 | UNRESOLVED；停止此问题修复 |

开发D20清单：`/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/development/D20_descriptors/manifest.json`。宽库配置`configs/data_d_descriptors/development_export.json`只导L1/L2并引用这个原D20清单，不重复复制D20。新字段一律使用全TRAIN的唯一有序字段、启用列和参数，保F64原值及uint8状态；不在下游重新筛选或拟合。闭合B6兼容列按原member_uid/source_ordinal复用，其余由相同版本程序计算。

QM9 D3清单：`/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/development/native_D3/qm9/manifest.json`。实际作业CPU17、exit0、Slurm耗时648秒；请求1CPU、站点分配2逻辑CPU，生产耗时647.574秒。六分子字段顺序为PMI1/PMI2/PMI3/PBF/volume_A3/SASA_total_A2，F64数值和uint8状态；逐原子SASA单独保存并保原source atom ID，不进入分子特征向量。只用原packed Z/F64坐标与每成员source-frame图，native_only，无补H、新构象或终点读取，未重拟合归一化。这些是生产关闭证据，未额外读取数值数组做独立QA。

QM9 component明确`complete_source_population=false`，全源15751成员。ExpansionRx政策现已由用户明确选择B6_fixed_native_H；对应component4539057现已RAW_COMPLETE，完整合并4539061亦已闭合；完整开发D3只在`merge_development_d3`以原成员/划分/顺序合并所有关闭component后形成。合并只消费元数据和原数组引用，不重算化学量；Root Section5入口要求`complete_source_population=true`，不能用QM9部分代替整面板。

## 基准交付限制

原D20绑定保留38546个未知项（NMR38514、其余32），不猜别名、不转成已知缺失、不重算原D20。L1完整交付因此受限。L2按任务书4.1不做D20跨库映射，可独立从同一active原图/成员导出，配置`configs/data_d_descriptors/benchmark_L2_export.json`；清单保留原D20的UNRESOLVED事实并声明`canonical_D20_required=false`。二维量不依赖几何；D3由基准窗口接入原封存S′ UFF产品，终点和划分不变。没有最终C1完成声明。

两个保留的基准源准备目录实际物理字节2097127424，L2新增数值/状态约2.827GB，纳入原8GiB基准预算。本线联合NFS峰值38853537501字节包含两条条件seed1额外2GiB，开发D3仍共用原512MiB；该峰值已替代早期14GiB预测；开发D3 components及合并共用原512MiB限额。每次实际写入继续真实节点字节/inode、UID配额和跨窗口未来预算保护。

## 消费与比较

成员使用来源明确的完整键：开发(dataset,member_uid)，基准(dataset,record_id)。二维同分子只计算一次；每成员几何分别保留，不合并同MID的不同构象。原始split、0/缺失/numeric-event均保留。`append_member_d3`只连接六分子字段，可选标准化只用原TRAIN参数，不截尾；不把A1残差参数用于直接化学特征。

第5节执行器`tools.d_recipe.development_panel`按GPU/CPU阶段复用原R3探针、原C1 LightGBM默认模型和原ridge组成参照。A复用选定终点H0主读出，B为同批描述符的MLP及LightGBM，C在原分子MLP入口拼H0与同批描述符。B/C按总可训练参数匹配A，以解析最近整数宽度实现并报告差额；无容量扫描。组成来自每成员原source_smiles图的完整含H元素计数和重原子数，不用缺H坐标数量代替。

模型/预测与既有bootstrap结果关闭后直接续用，A不重复抽样；C对两种B只消费对齐的原1000次抽样给描述性差值区间，不触发配方或额外seed。最终9M源与冻结选定3M臂名显式对应9M-D-R0或9M-D-final。H0保留开关默认关闭，只在登记了未来存储峰值的选定原末层前向中启用。

270项新逻辑已通过4537544（请求1CPU/实际2逻辑CPU，7秒、exit0）。全量字段与唯一TRAIN统计已冻结；用户批准的原7/65项缩尾零尺度补充过滤已执行，真实64分子逐头接收4538200两库均ACCEPTED（L1 197/197头、L2 1320/1320头）。开发A/B/C和最终C1仍未完成；实现和单元测试不替代这些实际结果。
2026-11-21T22:06:20.602716+00:00：开发双库原导出4538204/CPU10/3CPU实际COMPLETED0:0，612秒，15518唯一分子，两库61批均关闭；L1 191/217、L2 1314/1613，沿用原TRAIN参数/原成员划分、不读任务标签、不重拟合。原source_processing_complete=true、reception_acceptance=pending、current_C1_complete=false如实保留；该二维闭合不替代待定D3/H政策或最终A/B/C。基准L2 4538205继续RUNNING。

2026-11-22T00:07:24.373897+00:00：基准独立L2原导出4538205/CPU10/4CPU实际COMPLETED0:0，7842秒（分配CPU 8.713333333333333核时，TotalCPU未知），194729唯一分子/761批，1314/1613启用。原TRAIN参数、成员划分不改；原source_processing_complete=true，reception_acceptance=pending、current_C1_complete=false保留。原D20绑定未解决和H政策仍待定；该二维导出不构成基准接收或最终A/B/C完成。原清单已转录至数据分支，Root摘要results/d_recipe/benchmark_L2_export_20261122.json；现行36706053853B联合NFS预算不增。


2026-11-23用户明确批准[既有B6固定原坐标补H](H_POLICY_20261123.md)。Data配置development_D3_ExpansionRx_B6_20261123.json只生产原ExpansionRx component，再以development_D3_merged_B6_20261123.json消费原QM9与新component；完整15751成员合并清单未闭合前仍不进入最终B/C。CPU11/4539054的22项相关测试已COMPLETED0:0/8秒，实际目标盘/UID守卫和自有子进程reap通过；此测试不是科学交付或A/B/C结果。上文带旧时间戳的“政策待定”记录保留为历史。


2026-11-23 03:51 CST：完整原D3清单已生成：`/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/development/native_D3/merged/manifest.json`，全部15751成员、complete_source_population=true；每dataset政策保留qm9/native_only与expansionrx/B6_fixed_native_H。原component/merged JSON转录见Data results/data_d_descriptors/development_D3_ExpansionRx_B6_20261123.json与development_D3_full_20261123.json。原峰值203909476B在共同512MiB内；原D20/D4/坐标和成员划分不变。实际H父子PID均ABSENT，合并原resident日志reap0/children=[]。Source接收pending与C1false保留；此输入闭合解除此前H政策及完整D3人口依赖，最终A/B/C仍等待冻结选定终点、规定9M和实际原评测。以上带旧时间戳的准备/等待描述是历史。

2026-11-23 04:40 CST：阶段1两种子各自配对WIN，后续选定配方为A1+B3+B4整包；目标库/D3去留/K1仍待阶段2–3，因此最终C1交付库及模型终点尚未冻结。完整15751开发D3继续可用，不据此提前运行最终A/B/C或改变基准冻结终点。
