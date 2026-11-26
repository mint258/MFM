# P 独立交付：D线交付前已完成的部分（2026-11-26）

按用户“先完成不依赖D线的剩余工作”执行。P的独立计算、结果章节、方法与完整精度参数、最终权重SHA、全27项证据索引均已就绪。完整研究仍缺D第5节A4，PR7暂为草稿。

- [已封存P章节](REPORT_P_SECTIONS.md)：约55KB，包含四轮筛选、五条9M确认、预算/分子数曲线、F、A1/A2/A3/A5/A6、H-comp、I1、E1、方法与资源。该文件是等待拼接的正文部件，保留最终章节排版标题，**不是最终REPORT**；唯一A4插入标记明确保留。
- [最终检查点SHA256](../../results/p_recipe/final_checkpoint_sha256.json)：只计算T2/T4原9M终点，未反序列化权重。后续最终报告直接复用，若文件身份变化则报错，不默默重算。
- [封存与输入绑定](../../results/p_recipe/independent_delivery_20261126.json)：48份原始标量输入的路径/大小/mtime/inode绑定，零新拟合、零新bootstrap、零重画曲线。
- [全27项原始证据索引](../../results/p_recipe/independent_delivery_evidence_20261126.json)：只盘点原文件元数据，不对已闭合科学结果重新QA。

## 全范围交付清单

|任务项|当前交付状态|证据|
|---|---|---|
|protocol_and_legacy_rescore|existing_evidence_located|[原文件](../../configs/p_recipe/protocol.json)|
|P0|existing_artifacts_read|[原文件](../../docs/p_recipe/P0_SUMMARY.md)|
|required_regression|verified_existing_scope|[原文件](../../docs/p_recipe/LOG.md)|
|R1_to_R3_screening|COMPLETE_VERIFIED|[原文件](../../configs/p_recipe/fixed_20261115/round1_decision.json)|
|side_lines_and_freeze|COMPLETE_VERIFIED|[原文件](../../configs/p_recipe/fixed_20261115/external_line_decisions.json)|
|five9M_runs|FIVE_GPU_AND_CPU_COMPLETE_VERIFIED|[原文件](../../tools/p_recipe/prepare_confirmation.py)|
|final_tables|ORIGINAL_PRIMARY_26COMPARISONS_AND_3POINT_SCALING_COMPLETE|[原文件](../../tools/p_recipe/final_comparisons.py)|
|final_recipe_parameters_methods|P_METHODS_FULLPRECISION_PARAMETERS_AND_BODY_SEALED|[原文件](../../configs/p_recipe/label_parameters/PM7_A1.json)|
|accounting_hardware|CURRENT_COST_AND_E1_ORIGINAL_TELEMETRY_COMPLETE|[原文件](../../docs/p_recipe/daily/2026-11-20.md)|
|REPORT_and_SHA|FINAL_ENDPOINT_SHA_COMPLETE_P_SECTIONS_SEALED_FINAL_JOIN_WAIT_A4|[原文件](../../tools/p_recipe/render_report.py)|
|GitHub_and_close|INDEPENDENT_DELIVERY_PUBLICATION_IN_PROGRESS_FINAL_MERGE_WAIT_A4|[原文件](../../docs/p_recipe/LOG.md)|
|training_family_CSV_final|FIVE_CANONICAL_FAMILY_CSV_AVAILABLE_PUBLISHED|[原文件](../../configs/p_recipe/fixed_20261115/confirmation/plan.json)|
|confirmation_budget_curve_22_readouts|COMPLETE_22_NEW_READOUTS_AND_5_ENDPOINTS|[原文件](../../docs/p_recipe/USER_DIRECTIVE_20261121.md)|
|budget_curve_task_scores_27points|COMPLETE_27_POINTS_486_ROWS|[原文件](../../results/p_recipe/fixed_20261115/confirmation/budget_curve_tasks.csv)|
|Hcomp_composition_8checkpoints|COMPLETE_ALL22C_METRICS_HCOMP_NOT_SUPPORT|[原文件](../../docs/p_recipe/USER_DIRECTIVE_20261122.md)|
|Nov22_shared_guard_migration_and_exit_entry|CANONICAL_UID_QUOTA_GUARD19_TESTS_PASS_NFS_RESUMES_ACTIVE|[原文件](../../docs/interfaces/STORAGE_GUARD_20261122.md)|
|F1_finetuning_120|COMPLETE_TABLE68_AND_FIRST_INTERPRETATION|[原文件](../../docs/p_recipe/USER_DIRECTIVE_20261122B.md)|
|F2_finetuning_60_and_interventions|COMPLETE_BASE60_PLUS_I1_FULL12_AND_F116|[原文件](../../docs/p_recipe/USER_DIRECTIVE_20261122B.md)|
|A1_readout_noise_16|COMPLETE|[原文件](../../docs/p_recipe/USER_DIRECTIVE_20261122B.md)|
|A2_B4_composition|COMPLETE_INITIAL4_AND_I1_OWN3M_ALL22C_METRICS|[原文件](../../docs/p_recipe/USER_DIRECTIVE_20261122B.md)|
|A3_B4_penalty_size|COMPLETE|[原文件](../../docs/p_recipe/USER_DIRECTIVE_20261122B.md)|
|A4_descriptor_upper_controls|WAITING_EXTERNAL_D_SECTION5|[原文件](../../docs/p_recipe/USER_DIRECTIVE_20261122B.md)|
|A5_common_UFF_geometry|COMPLETE_5106_COMMON_COHORT_8_ORIGINAL_ROWS|[原文件](../../docs/p_recipe/USER_DIRECTIVE_20261122B.md)|
|A6_QM9_30000_TRAIN_groups|COMPLETE_16R3_CELLS_32ROWS_16_WITHIN_COUNT_CONTRASTS|[原文件](../../docs/p_recipe/USER_DIRECTIVE_20261122B.md)|
|I1_disable_B4_3M|COMPLETE_ORIGINAL3M_R1_R3_TIE_NO_SEED1_ALL_FOLLOWUPS|[原文件](../../docs/p_recipe/USER_DIRECTIVE_20261122B.md)|
|I2_dynamic_B4_3M_conditional|CLOSED_NOT_TRIGGERED|[原文件](../../docs/p_recipe/USER_DIRECTIVE_20261122B.md)|
|E1_conformer_k_star|COMPLETE_K_STAR_1_NO_SEED1|[原文件](../../configs/p_recipe/E1_k_star.json)|

## 执行与验证

CPU11/core63，5秒实测idle=1.0，1CPU、8GiB RAM、30分钟硬上限及180秒收尾；实际两次自有树均退出。4项新边界控制通过（缺A4不能生成最终报告、跳过A4不能跳过P关卡、最终权重不重复hash且变化拒绝、收尾不启动新hash）。首次报告引用不存在SVG，修正为原闭合PNG后续接，测试结果直接复用，没有重新科学计算。两次真实CPU成本均计入。

## A4到齐后的单次收尾

1. 消费D所选冷9M、七任务开发A/B/C/组成的原COMPLETE与scores交付，保持来源/人群绑定；P侧不重拟合。
2. 生成 `A4_descriptor_upper_controls.json` 原结果转录。
3. 原 `render_report.py` 自动检测封存清单，只将A4原始表插入一次；复用P正文/现有曲线/最终SHA，不重新render P或读取权重。
4. 最终精确head源码CI后完成PR7合并。旧科学回归沿用，不重跑。

最终REPORT尚未生成，不能将本次独立交付记为全研究完成。
