# C4 等变性 v3 正式报告

C4：**PASS**。按用户 2026-10-29 v3 规则，唯一硬门为 FP64 相对误差 ≤ 1e-9。既有纯 FP64 数学验收 CPU4524734 已完成 48/48 PASS、192 次 FP64 完整 encoder 前向、0 数学失败/0 错误；零参考要求精确零差，不加入 epsilon。新规则取代旧 C4 HOLD，FP32 诊断不再产生 PASS/FAIL 或阻塞主线。

本次保存输出报告 CPU4525166 实际 C0、11 秒、16CPU、compute-0-13。仅消费原未补偿 baseline GPU4521160 已保存的完整 48 case/52 终端数组；没有新 forward、拟合、bootstrap，也没有重跑旧 v1/v2 或补偿候选。同父正常仓库检查 PASS（3707 文件、1762 Python、1309 引用）。旧失败和旧规则证据保留；全部 FP32 补偿停止且不采用。

## FP32 诊断定义与覆盖

矢量/坐标字段按每分子每字段计算 `||actual-reference||₂ / ||reference||₂`，节点向量以 Frobenius 范数合并；原物理 views 属于同一分子，合并取一次范数。标量按 `abs(delta)/(abs(reference)+该字段真实 TRAINstd)`。本批没有可绑定的真实逐字段 TRAINstd，故所有标量诊断为 NA；没有代入 1、epsilon、normalizer scale 或合成 fixture 标准差。该缺失不阻塞 C4。

完整人口为 48 case × 3 原变换 × 13 字段 × 3 原 fixture 分子 = **5616** 逐分子字段行。39 个 field×transform 组各含 144 个分子字段；其中 12 个矢量/坐标组共 **1728** 个可定义比值，27 个标量组的 **3888** 个分子字段没有比值，合计 **1,928,880** 个标量条目缺 TRAINstd。报告没有非有限分量或零分母样本（均 0）；若遇到这类样本，应单列计数而不加入未经批准的近零阈值。小而非零分母照原式报告，不据较大比值启动修复或改 API。

参考值沿原保存 base 和记录的 R64/t64 生成：不变字段用 base，矢量用 base@R，坐标再加 t。原 fixture 为 3/9/32 atom 的三个分子；没有新的 tensor6/r674 结果。r674 仍为 LOSS_DISABLED、保留 head，不追加任务。

## 39 组统计

p50/p99 是原报告的 linear quantile；表内有限数值显示 7 位有效数字，精确值保留于原 JSON/CSV。NA 表示真实 TRAINstd 不可得，不表示零或通过。以下数值只用于报告。

| transform | field | 可定义比值数 | p50 | p99 | max | 缺 TRAINstd 条目数 |
|---|---|---:|---:|---:|---:|---:|
| general_rotation | PD/d_atom | 0 | NA | NA | NA | 2112 |
| general_rotation | PD/d_binary | 0 | NA | NA | NA | 144 |
| general_rotation | PD/d_intensive | 0 | NA | NA | NA | 144 |
| general_rotation | PD/p_dipole | 144 | 4.203290E-6 | 4.876926E-4 | 5.570281E-4 | 0 |
| general_rotation | PD/p_dipole_magnitude | 0 | NA | NA | NA | 144 |
| general_rotation | PD/p_extensive | 0 | NA | NA | NA | 144 |
| general_rotation | PD/p_gradient | 144 | 5.538845E-7 | 5.124528E-6 | 6.411993E-6 | 0 |
| general_rotation | PD/p_intensive | 0 | NA | NA | NA | 144 |
| general_rotation | PD/p_pair | 0 | NA | NA | NA | 1968 |
| general_rotation | S/clean_bond_logits | 0 | NA | NA | NA | 9840 |
| general_rotation | S/coordinate | 144 | 4.318670E-8 | 4.963562E-8 | 4.963575E-8 | 0 |
| general_rotation | S/element_logits | 0 | NA | NA | NA | 628320 |
| general_rotation | S/noise | 144 | 7.001848E-7 | 2.443493E-6 | 2.447940E-6 | 0 |
| other_rotation_and_translation | PD/d_atom | 0 | NA | NA | NA | 2112 |
| other_rotation_and_translation | PD/d_binary | 0 | NA | NA | NA | 144 |
| other_rotation_and_translation | PD/d_intensive | 0 | NA | NA | NA | 144 |
| other_rotation_and_translation | PD/p_dipole | 144 | 4.466428E-6 | 5.292353E-4 | 9.060388E-4 | 0 |
| other_rotation_and_translation | PD/p_dipole_magnitude | 0 | NA | NA | NA | 144 |
| other_rotation_and_translation | PD/p_extensive | 0 | NA | NA | NA | 144 |
| other_rotation_and_translation | PD/p_gradient | 144 | 6.201996E-7 | 3.177750E-6 | 6.668254E-6 | 0 |
| other_rotation_and_translation | PD/p_intensive | 0 | NA | NA | NA | 144 |
| other_rotation_and_translation | PD/p_pair | 0 | NA | NA | NA | 1968 |
| other_rotation_and_translation | S/clean_bond_logits | 0 | NA | NA | NA | 9840 |
| other_rotation_and_translation | S/coordinate | 144 | 4.160550E-8 | 5.145122E-8 | 5.145151E-8 | 0 |
| other_rotation_and_translation | S/element_logits | 0 | NA | NA | NA | 628320 |
| other_rotation_and_translation | S/noise | 144 | 5.864454E-7 | 2.160211E-6 | 2.173344E-6 | 0 |
| translation_only | PD/d_atom | 0 | NA | NA | NA | 2112 |
| translation_only | PD/d_binary | 0 | NA | NA | NA | 144 |
| translation_only | PD/d_intensive | 0 | NA | NA | NA | 144 |
| translation_only | PD/p_dipole | 144 | 4.291783E-6 | 7.250623E-4 | 8.412857E-4 | 0 |
| translation_only | PD/p_dipole_magnitude | 0 | NA | NA | NA | 144 |
| translation_only | PD/p_extensive | 0 | NA | NA | NA | 144 |
| translation_only | PD/p_gradient | 144 | 5.609967E-7 | 4.503559E-6 | 4.909353E-6 | 0 |
| translation_only | PD/p_intensive | 0 | NA | NA | NA | 144 |
| translation_only | PD/p_pair | 0 | NA | NA | NA | 1968 |
| translation_only | S/clean_bond_logits | 0 | NA | NA | NA | 9840 |
| translation_only | S/coordinate | 144 | 3.364999E-8 | 5.946850E-8 | 5.946850E-8 | 0 |
| translation_only | S/element_logits | 0 | NA | NA | NA | 628320 |
| translation_only | S/noise | 144 | 7.569286E-7 | 2.380475E-6 | 2.395626E-6 | 0 |

## 原产物与下载、复算

正式决策：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/C4_equivariance_v3_actual_v1/C4_DECISION.json`。汇总及精确 39 组数据：同目录 `summary.json` 与 `fp32_field_summary.csv`。逐分子完整表：同目录 **`fp32_per_molecule_field.csv`，5616 行、1,264,014 字节**。完整表保留在 N，不加入 Git CSV checker；本文可直接归档为公开 Markdown。

逐分子表可从持久 X 盘复制，或由已配置密钥的别名下载：

```powershell
scp descriptor-analysis-remote:/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/C4_equivariance_v3_actual_v1/fp32_per_molecule_field.csv .
```

复算无需打开 NPZ 或运行模型：按 `transform,field` 分组，取该组 `defined_values=1` 行的有限 `max` 列（每行只有一个分子范数比，故本行 p50=p99=max）；每个可定义组应有 144 行。排序为 x₀…xₙ₋₁，分位 q 的位置 h=(n−1)q，取相邻两项线性插值；max 取最后一项。标量组 `defined_values=0`、p50/p99/max 留空；按原列累计 `unavailable_TRAIN_std`、`undefined_denominator`、`nonfinite_components`，不能把空值转为 0。逐行 `norm_delta`、`norm_y` 供直接核对比值，case 四因子、分子索引、字段、变换及单位均保留。

FP64 原证据：`N/equivariance_v2_FP64_math_20261029/math_parent_4524734/math/summary.json`，实际 48/48、epsilon=0；规则：`MFM_model_v3_delivery_integration_v2/docs/model_v3/USER_MAINLINE_AMENDMENT_V3_20261029.md`，生效记录：`N/MODEL_LINE_USER_AMENDMENT_V3_effective_20261029.json`。本次 decision 中两份关键元数据 current_read 均 true、metadata issues 为空。

本次诊断既有累计 1053.861213 秒、连续失败 0；worker 诊断计时 2.004915699 秒。遵循累计 4 小时或连续失败 2 次即未解决、保守旧路径继续的规则，不据本报告增加诊断/修复。C4 PASS 不等于整份指南完成，不代替真实 Data 发行、TRAIN 统计、D5/B*、正式 TEST 或其它阶段验收；科学选择 DECISION_RULES、TRAIN-only/no-TEST 边界不变。