# 服务器空间与清理记录
更新：2026-11-25 15:01:55 CST。状态：目标尚未达成，清理进行中。

完整基线：102个主目录、1042个重要子目录；3,060.713 GiB。基线扣已知清理：3,050.122 GiB，未计活动及新增写入。

|账号|限额 GiB|最新可用 GiB|目标 GiB|尚缺 GiB|
|---|---:|---:|---:|---:|
|/share/home/zixiao|4,096.000|283.157|2,048.000|1,764.843|
|/lfshome/zixiao|2,048.000|3.457|500.000|496.543|

## 当前保留与删除规则

KEEP：数据与标签、几何、split/子集索引、下游预生成构象、指标/配置/日志及仓库；保留各 label-family、采用配方、250k/500k 子集与 E1 终点、9M scaling 需要的中间点及任何已引用 checkpoint。COMPRESS：仅结束且不需完整续训状态的保留 checkpoint 去 optimizer/scheduler，真实模型加载成功才替换。DELETE：未受保护的其他 checkpoint；原始计算输出须先通过字段与成功 ID/缺失值检查。未知旧 DELETE/ASK 项不扩权。

## 执行与待核实事项

- 已删除277个模型 checkpoint，文件分配块净减少13.054 GiB；配额快照另计。
- 已检查79个有效 Git 仓库，另3个历史源码目录用当前文件补查；明确引用的 checkpoint 保留。
- 模型 checkpoint 与特征/预测张量分开；仅扩展名不能作为删除依据。
- WP5原始档案396个，126.844 GiB。大型 Parquet 标签/几何保留。
- 原始输出的字段、成功 ID 与缺失值检查尚未完成，不删除；旧 DELETE/ASK 索引位置仍待补充。
- 四条研究线的精确字段清单见 `raw_required_fields.json`。清单已建立，不代表分子 ID/数值完整性已通过。
- S_checkpoint_compression：Slurm 4540054，PENDING||(Priority)。

## 完整主目录总表

目录量为今日完整基线扣已知清理，不能等同当前精确占用。重要子目录、样本、GitHub核实状态和用途见同目录 `storage_inventory.html`。

|主目录|基线 GiB|扣已知清理 GiB|内容|处理方向|
|---|---:|---:|---|---|
|`runs`|2,774.289|2,764.929|数据生产与模型实验的总入口：数据线 v1、WP5、历史模型/修复/筛查，以及当前 P/S/D、头部与后续研究。|混合目录按子项处理；未知项 ASK|
|`docs`|236.169|236.169|文档之外还包含历史几何帧暂存、Stage61 数据审计候选/统计分块、运行环境；最大载荷为 staged_geom_frames 和 Stage61 scan_v2。|混合目录按子项处理；未知项 ASK|
|`results`|11.964|11.964|旧竞赛/模型结果入口；下级按项目与实验阶段保存预测、指标和模型产物。|混合目录按子项处理；未知项 ASK|
|`MFM_step_overhead_20261114`|11.167|11.167|每步开销/数值一致性源码工作树；主要载荷是 numerical_final_4532640 下 random_seed0 与 G1_3M 的梯度对照数组。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`.perf_sync_scratch_20261117`|9.852|9.852|性能验证暂存：baseline_gradients、测试输入、TorchInductor/Triton 编译缓存和临时 W&B 等。|ASK：等待旧 DELETE/ASK 索引或具体用途核实，不整目录删除|
|`MFM_precision_20261115`|6.649|5.418|历史精度研究源码工作树；大头为 school_wheels 离线安装包和 TF32/BF16 对照实验产物。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`ckpt`|3.070|3.070|公开 CheMeleon/UniMol/MACE 权重、自训 MFM 权重和 waste 下的实验权重混合。|按 checkpoint 明细分 KEEP / COMPRESS / DELETE / ASK；指标、配置、日志保留|
|`MFM_p_followup_20261117`|0.971|0.971|P/S/D 及头部/后续研究：训练、检查点、读出模型、预测、bootstrap、测试与报告混合。|按 checkpoint 明细分 KEEP / COMPRESS / DELETE / ASK；指标、配置、日志保留|
|`MFM_p_heads_20261117`|0.815|0.815|P/S/D 及头部/后续研究：训练、检查点、读出模型、预测、bootstrap、测试与报告混合。|按 checkpoint 明细分 KEEP / COMPRESS / DELETE / ASK；指标、配置、日志保留|
|`MFM_d_recipe`|0.805|0.805|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_s_recipe`|0.801|0.801|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`xyz_pool`|0.528|0.528|按分子组织的结构/构象池；查看 XYZ 等样本而非遍历每个结构内容。|KEEP：科学数据、标签、几何或索引|
|`MFM_model_v3`|0.496|0.496|主源码工作树及共享 Git 管理目录，同时含 results、配置和运行工具。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_perf_sync_20261117`|0.106|0.106|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_p_recipe`|0.102|0.102|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`reports`|0.086|0.086|空间审计、迁移、故障等报告与证据；本轮统计文件也在此。|混合目录按子项处理；未知项 ASK|
|`MFM_precision_rebased_20261116`|0.085|0.085|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`data`|0.079|0.079|本项目数据输入、划分与处理用小型数据目录；具体以当前样本为准。|混合目录按子项处理；未知项 ASK|
|`MFM_model_v3_cpu_perf_20261112`|0.076|0.076|CPU 性能改进、回归与等价性验证的独立输出，可能含合成模型/数据和 benchmark。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_d_descriptors_20261120`|0.071|0.071|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_cpu_reference_20261112`|0.071|0.071|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_delivery_integration_v2`|0.066|0.066|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_C1a_three_GPU_checkpoint_off_runtime_v1`|0.065|0.065|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_C_resolve_cli_v1`|0.062|0.062|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_pilot_entry_v1`|0.061|0.061|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_reporting_v3`|0.059|0.059|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_delivery_integration_v1`|0.058|0.058|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`logs`|0.048|0.048|运行日志或 W&B 事件/配置/调试记录。|KEEP：指标、配置、日志和离线事件|
|`MFM_p_data_information`|0.041|0.041|P 数据信息研究：本地来源权威 SQLite、数据校准/抽样输入、描述统计与报告。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_physical_policy_v1`|0.031|0.031|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_clean_integration_v1`|0.031|0.031|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_runtime_integration_v1`|0.031|0.031|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_training_chain_candidate_v1`|0.031|0.031|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|按 checkpoint 明细分 KEEP / COMPRESS / DELETE / ASK；指标、配置、日志保留|
|`MFM_model_v3_training_execution_v1`|0.030|0.030|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|按 checkpoint 明细分 KEEP / COMPRESS / DELETE / ASK；指标、配置、日志保留|
|`MFM_model_v3_training_entry_v1`|0.030|0.030|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|按 checkpoint 明细分 KEEP / COMPRESS / DELETE / ASK；指标、配置、日志保留|
|`MFM_model_v3_execution_H0_bridge_v1`|0.030|0.030|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_performance_integration_v1`|0.030|0.030|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_A_acceptance_v2_candidate_v1`|0.030|0.030|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_dipole_moment_fp32_candidate_v1`|0.030|0.030|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_tensor_math_candidate_v1`|0.030|0.030|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_C_bias_free_candidate_v1`|0.030|0.030|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_residual_fp32_candidate_v1`|0.030|0.030|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_ffn_fp32_candidate_v1`|0.030|0.030|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_geometry_fp32_candidate_v1`|0.030|0.030|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_projection_fp32_candidate_v1`|0.030|0.030|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|ASK：等待旧 DELETE/ASK 索引或具体用途核实，不整目录删除|
|`MFM_model_v3_attention_core64_diagnostic_v1`|0.030|0.030|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_attention_centering_v1`|0.030|0.030|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_recipe_readiness_v1`|0.030|0.030|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_numeric_stability_v1`|0.030|0.030|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_native_checkpoint_bridge_v1`|0.029|0.029|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_native_s_runtime_v1`|0.029|0.029|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_native_s_precision`|0.029|0.029|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_long_run_storage`|0.027|0.027|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_long_run_storage_rev2`|0.027|0.027|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_wsd_fork`|0.027|0.027|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_sampling_cache`|0.027|0.027|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_composed_equivariance_runtime_v3`|0.027|0.027|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_proxy_runner`|0.027|0.027|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_composed_equivariance_runtime_v2`|0.027|0.027|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_wire_provider_rev2`|0.027|0.027|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_wire_provider`|0.027|0.027|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_composed_equivariance`|0.027|0.027|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_sampling_bridge`|0.027|0.027|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_s_bond`|0.026|0.026|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_sample_budget`|0.024|0.024|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_decisions`|0.024|0.024|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_b_precision`|0.024|0.024|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_proxy_plans`|0.024|0.024|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_a_checkpoint`|0.023|0.023|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_sa1_a`|0.023|0.023|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_c2`|0.023|0.023|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_sa4`|0.023|0.023|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_sa3`|0.022|0.022|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_sa1`|0.022|0.022|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_profiler_v2`|0.022|0.022|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_model_v3_sa2`|0.022|0.022|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`MFM_portable_context_20261105`|0.022|0.022|模型/数据开发源码工作树；包含源码、configs、tests、docs 等；若存在 results、环境或大二进制，下面另列重要子目录。|KEEP 仓库；仓库内运行产物继续按类拆分|
|`references`|0.009|0.009|参考资料/文献。|混合目录按子项处理；未知项 ASK|
|`modern_ML_representation`|0.005|0.005|旧机器学习表示/实验代码。|混合目录按子项处理；未知项 ASK|
|`scripts`|0.000|0.000|项目脚本与运行工具。|混合目录按子项处理；未知项 ASK|
|`catboost_info`|0.000|0.000|CatBoost 学习曲线、模型训练记录及辅助输出。|KEEP：指标、配置、日志和离线事件|
|`wandb`|0.000|0.000|运行日志或 W&B 事件/配置/调试记录。|KEEP：指标、配置、日志和离线事件|
|`.st_4532622`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.st_4532627`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.st_4532623`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.st_4532624`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.st_4532626`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.st_4532628`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.st_4532640`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.pr_4532643`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.pq_3690575`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.pq_3690989`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.pr_4532646`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.pq_3692189`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.pq_1874339`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.pq_3394967`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.pr_4532717`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.pq_1613477`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.pq_1613617`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.pq_1614545`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.pq_1614634`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
|`.pq_1652602`|0.000|0.000|隔离测试/性能/任务运行的临时工作目录；以本次样本核对具体配置、环境、日志与二进制。|混合目录按子项处理；未知项 ASK|
