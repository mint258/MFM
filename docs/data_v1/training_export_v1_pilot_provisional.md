# 训练导出：v1-pilot-provisional

重建本报告：`python -B workflows/data_v1_final/export/render_D3_pilot_report_4525880_v1.py`。仅使用本轮正式元数据。

## 1. 目的

交付固定试点 TRAIN 与 ROUTINE VAL 的 D-1 v3.0 家族 LMDB，并将已关闭 D5 诊断载荷绑定到实际 D3 父作业。本报告只读取正式 JSON 元数据，不读取 LMDB/SQLite/Parquet 正文，不执行新 QA、哈希、复制或性能测量。

## 2. 输入数据及其哈希

正式入口：`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/v1-pilot-provisional/D3_export.json`。实际导出父作业 `4525880`；正式记载原生状态 `COMPLETED/0:0`，节点 `compute-0-8`，分配 CPU `16`。下表沿用正式引用中的 SHA256，不重新计算；源分片、几何和统计组件由试点组件入口及实际计划追溯。

| 输入/证据 | 路径 | 字节 | 已公布 SHA256 |
| --- | --- | --- | --- |
| D3 原始收据 | /lfshome/zixiao/data_v1_20261025/D3_pilot_provisional_lustre_v1/day10_parallel_keys_closed55k_cpu_r4/receipt.json | 864648 | 8d4dbc30f0f00e1e279cb66cfc7975ecaf239c881f0625748a7a7f1faed8798c |
| D3 唯一导出清单 | /lfshome/zixiao/data_v1_20261025/D3_pilot_provisional_lustre_v1/day10_parallel_keys_closed55k_cpu_r4/export_manifest.json | 3427480 | 5e88e9242ff8c6dfa1ac3dfaaa6aca617e424b221e2f9673e6e68ca69f93d7b8 |
| D3 实际计划 | /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/D3_local_store_export_20261105_v6b/execution/plan.json | 336891 | 53efeada53d00026d3834fe4bb042d847d4cd61c970009d06ac98c1618a63785 |
| 试点人口/组件入口 | /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/D3_parallel_guide_after_MAD_20261103_v6/D4_local_root_limited_acceptance.json | 5289 | de25f7753775f6aaddbed1e4d4a5e97b5a523cdcc106cc801be860344665ab42 |
| 原闭合投影分片目录 | /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/D3_lustre_cpu_export_20261104_v6/closed_projection_groups_direct_read_candidate.jsonl | 96219 | c4dbbf26b53c119a058a340e0b4845edef022219126ed8587769f26ddc46e317 |
| 同父绑定 D5 | /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/v1-pilot-provisional/D5_diagnostic_payload_D3_job4525880_bound.json | 28019 | 986b62d24cb0fd3b6e3ab4923a077b7bb3172ebdb78a7407f55417a3bdd1b516 |
| D5 原始交付组件 | /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/v1-pilot-provisional/D5_diagnostic_payload.json | 26882 | 40e5ad2f018ced1220c6ce3b2f36058eeb16af011a8dce5c634153d90ea1530e |
| D5 唯一校验结果 | /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/source_status_v1/pilot_D5_parallel_guide_v1/day09_parallel_frozen_pilot_v1_provisional/actual_diagnostic_Source_QA.json | 225352 | 81ac43cd98f96f7efc320f0b43734de1fecfc0d151e9fbd1652d18800c9d2b21 |
| mapping_reference | /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/source_status_v1/pilot_family_D3_census_resume_v3/day01_parallel_guide_frozen55k_v6/actual_bounded_configurations/mapping.json | 109596 | 61cc6d3906ab8dfe8ef36f94a0595559d408fd0fdcb8a7e151026a61d062f9a5 |
| projection_recipe_reference | /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/source_status_v1/pilot_family_D3_census_resume_v3/day01_parallel_guide_frozen55k_v6/actual_bounded_configurations/projection_recipe.json | 85864 | 18320084c32bd33cb758ce24a1c1050237f4f97f8169ab9ae5b6f5cd4c980354 |
| registry_reference | /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/source_status_v1/pilot_family_D3_census_resume_v3/day01_parallel_guide_frozen55k_v6/actual_bounded_configurations/registry.json | 1530797 | 5fb11fc5dd1f4be3f491b9c74f18c2725bb64d29005e08c5aeef9be19693796d |
| target_policy_reference | /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/source_status_v1/pilot_family_D3_census_resume_v3/day01_parallel_guide_frozen55k_v6/actual_bounded_configurations/target_policy.json | 269884 | 7c876e3e3af76245af26afac7d12f0a757fd0a346507eea125ee787bb0e68861 |
| 原始序列尺寸相关性 | /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/source_status_v1/pilot_family_D3_census_resume_v3/day01_parallel_guide_frozen55k_v6/required_molecule_size_rho/original_series_weighted_size_rho.json | 350634 | b372aabbfa86009679f5a49428bb9af3418b05840a13a9c8fac93ed37387f993 |

## 3. 规则和参数

按家族拆分 float32 LMDB，几何与标签分库，使用原 MFM3 数组编码及原 mask/原因域，不使用 pickle。本试点包含 PM7 几何 S、D/P 标签及已有 UFF S′ 几何；不包含 UFF D′/P′ 标签。固定 TRAIN/ROUTINE VAL 人口，D5 为 TRAIN_UNSEEN_CONFORMATION，排除于训练。永久 F64 权威与完整来源 metadata 保留在共享存储；训练连续值仅做原编码器的一次 F32 转换。r73 保持完整有序条目，r674 保持 LOSS_DISABLED，原值和 mask 保留。

本次复用已闭合源分片 `171` 组；本父新增 QM/UFF 调用 `0`；writer 数 `15`。可用构象顺序 `["fixed_random"]`；不可用顺序 `["energy", "diversity"]`。

验收按用户最终简化规则：末尾一次计数与随机 1000 条原 Parquet 逐字段对照、一次总清单 SHA；不执行独立重放、16-reader 复核或全量 F64 二次扫描。分发只用一次 `rsync --checksum`，不追加复制后哈希；读取测量只有一次，目标窗口不超过五分钟，不重试。

## 4. 统计结果

| 项目 | 正式元数据值 |
| --- | --- |
| TRAIN 分子 | 50000 |
| ROUTINE VAL 分子 | 5000 |
| 关闭子库 | 2915 |
| 几何记录（含输入视图/子几何） | 7116214 |
| 标签家族记录 | 24906749 |
| 全部导出记录 | 32022963 |
| 训练 LMDB 字节 | 575151706112 |
| 共享永久 F64 字节 | 398342180864 |
| 子库清单字节 | 1865575 |
| 清单定义的总 payload 字节 | 973495752551 |
| 原 Parquet 抽样记录 | 1000 |
| D5 已见 TRAIN 分子/未见构象诊断 | 893 |
| D5 几何记录 | 12502 |
| D5 标签记录 | 43757 |
| D5 关闭子库 | 53 |

全部数字来自正式清单/收据。几何记录包括实际输入视图及子几何，不能当作去重后的普通构象数。总 payload 为原清单口径，不包含历史源缓存、临时路由、目录块和复制副本，不等于账户总占用。

| 项目 | 正式元数据值 |
| --- | --- |
| 复制状态 | COPIED_WITH_RSYNC_CHECKSUM |
| 目标节点 | compute-0-21 |
| 目标目录 | /tmp/dv1_pilot55k_20261103_9b66baf693 |
| 实际复制字节 | 575161700855 |
| 复制文件数 | 5833 |
| 复制前 /tmp 可用字节 | 922355494912 |
| 复制所需字节 | 575161700855 |
| 保留余量字节 | 100000000000 |
| 单次 benchmark 状态 | COMPLETE |
| 请求测量秒数 | 180 |
| 实际测量秒数 | 180.0332307787612 |
| CPU reader workers | 4 |
| 分子/秒 | 11.981121433357428 |
| 记录/秒 | 6994.719777858696 |
| 随机 MID 窗口 | 64 |
| 重试次数 | 0 |
| cache 状态 | AFTER_SINGLE_RSYNC_CHECKSUM_NO_CACHE_FLUSH |
| GPU 计算 | false |

唯一 export manifest SHA256：`5e88e9242ff8c6dfa1ac3dfaaa6aca617e424b221e2f9673e6e68ca69f93d7b8`。单次 F32 抽样比较摘要：`0e00daf6ba1c815bbfd58a1bc18f958eb3fe2e0dec41e90a5da35ee55766663d`。训练 LMDB 与清单复制到节点本地；F64 是否复制：`false`，范围 `TRAINING_LMDB_AND_MANIFESTS_ONLY`。共享 F64 路径/引用保持原值。

## 5. 异常情况及处理方式

- 正式收据未记录导出错误；此前作业失败不在本次元数据中推算或计为成功。

benchmark 失败/超时时保留原状态与空缺吞吐，不补跑，不替代已完成的导出、原 Parquet QA 和 checksum 分发。

## 6. 已知限制

`Model_ACK=false`，`Model_payload_ACK=false`。实际 Model loader 与逐 head overfit 是后续真正模型验收；本报告及数据父作业 C0 不代填该 ACK。D-6 未放行，最终 Common、完整三种构象顺序及全量统计不由本试点冒充。归一化仅沿用当前试点版本，无新拟合。读测仅为单节点有限随机 MID 窗口，且在单次 rsync 后运行，不能解释为冷缓存、全库或多节点吞吐。共享 F64 权威读取仍依赖其原共享路径。
