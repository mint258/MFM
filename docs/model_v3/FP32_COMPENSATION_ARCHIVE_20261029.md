# FP32 补偿候选归档

生效日期：2026-10-29（Asia/Shanghai）。依据用户最新明确指令，以下候选全部**不采用**，停止实现、测试、拟合、性能测量和误差诊断。旧源码、提交、运行结果与失败记录就地保留；不删除、不重写历史结论。新等变性规则的历史复判只形成独立附加结果，即使通过也不恢复这些候选。

| 候选 | 保留的服务器工作树 | 当前决定 |
| --- | --- | --- |
| 注意力中心化 | `MFM_model_v3_attention_centering_v1` | 不采用，停止 |
| FFN FP32 补偿 | `MFM_model_v3_ffn_fp32_candidate_v1` | 不采用，停止 |
| 投影 FP32 补偿 | `MFM_model_v3_projection_fp32_candidate_v1` | 不采用，停止 |
| 残差 FP32 补偿 | `MFM_model_v3_residual_fp32_candidate_v1` | 不采用，停止 |
| 几何 FP32 补偿 | `MFM_model_v3_geometry_fp32_candidate_v1` | 不采用，停止 |
| 新偶极矩 FP32 补偿 | `MFM_model_v3_dipole_moment_fp32_candidate_v1` | 不采用，停止；不再运行拟议的 full119/full48 |

以上路径均相对 `/share/home/zixiao/descriptor_analysis`，对应 live `X:\`。
派生的中心化/投影/残差局部诊断及新偶极端到端运行包一并停止，不再新增诊断。

原始证据索引位于 `runs/model_v3_20261026/`：

- 中心化：`attention_centered_e2e_4521776_Root_metadata_closure_v1.json`。
- FFN：`FFN_fp32_GPU_4524610_Root_negative_closure_v1.json`。
- 投影：`projection_FP32_GPU_4524550_Root_scientific_failure_closure_v1.json`。
- 残差：`residual_fp32_GPU4701_Root_negative_closure_actual_v1.json`。
- 几何：`geometry_FP32_GPU_4524579_Root_closure_v1.json`。
- 偶极：`dipole_moment_fp32_targeted_CPU4726_Root_closure_actual_v1.json`；已有47项定向测试通过不构成采用，未完成的 full119/full48 不再执行。

停止时实际 Slurm 队列没有这些 FP32 补偿作业；没有取消他人任务或无关 Native S 精度曲线。历史隔离分支保留，生产默认实现不切换到补偿候选。

旧的通用 FP32 数值补偿（1435及其1492捕获）和 `MFM_model_v3_attention_core64_diagnostic_v1` 的 FP64→FP32 roundback 分析也归档为**不采用**，不再诊断或恢复执行。只允许按新规则读取其已保存结果。新运行的纯FP64数学验收使用原未补偿模型，仅用于检验数学正确性，不构成数值补偿候选。
