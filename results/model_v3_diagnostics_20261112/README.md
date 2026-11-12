# 2026-11-12 模型线只读诊断导出

交付状态：六项诊断导出、独立曲线重跑和既有随机 z 对照均已完成并上传。

本目录按用户六项清单导出。原始训练、分数、面板、判定规则和选择逻辑保持；全部新增诊断数据 selection_use=false。仅使用下游 TRAIN 的原优化子集及内层验证子集，不读取 TEST。不重新预训练，不对导出进行复核或二次读回。

- `summaries/*.json`：完整原 summary、逐读出 summary、原 bootstrap、ridge α 和五折误差，以及原预测文件中的探针详情（不包含权重 state_dict）。随机对照保留既有三个架构匹配配置，作为一个逻辑对照组。
- `predictions/*.parquet`：原内层验证预测、真值、分子完整组 ID、源记录 ID、原子数、SoM 源原子 ID 和有效掩码。旧版未持久化的 R1 预测仅在缓存上按原记录 α 重建，不重做 CV 或重新计算原分数；provenance 列明确区分。R0 原 summary 保留；旧逐记录预测未持久化，另按原配方重建并标明来源。
- `curves/*.parquet`：C1 六个检查点、随机对照以及 T0 四组的 R2/R3/R2z 每轮诊断曲线和独立终点预测。严格沿用原探针超参数、种子、30 轮、有效批 32 和最后一轮规则；每轮额外推理不影响训练 RNG/优化器。诊断使用 compute-0-20 CPU，原执行设备为 CUDA，设备差异在元数据中说明；不以诊断结果替换原结果。无 z 的 C1 标为不可用，SoM 的 R3/R2z 为既定 R2 别名。
- `features/*.parquet`：每个任务原优化特征人群的逐维 mean/std/min/max 与低方差计数，阈值 `max(1e-12,1e-4*median(std))`，std 使用总体定义。缓存字段 `h0` 实为原模型最终逐原子 X；`H0_mean/H0_sum` 为其均值/求和池化，`X_atom` 为逐原子统计，`X_R2` 为 concat(mean,sum/N_ref)，`z` 只对缓存中确实存在的分子潜变量输出。
- `u0/`：原优化和内层验证的 U0/原子数分布、分位数、原子数直方图及逐分子表；单位按冻结面板为 Ha。
- `native_s_logs/`：C1-0/a/b 原生 S seed0 的原逐步 losses.csv，tar+gzip 直接流式压缩为 3 MiB 分段，无载荷临时副本。拼接/解压命令及成员源路径、大小写在 manifest 中。

T1 仅纳入本次导出开始时已完成评价且有 producer_complete.json 的各组；正在进行的组保持运行。不存在的原生参考区间不会补造。原结果与诊断结果分别保存，诊断差异不进入采用决策。

`STATIC_MANIFEST.json` 列出已完成的静态导出；最终 `MANIFEST.json` 列出全部文件路径和生产时记录的字节数。GitHub 上传仅顺序传输生产文件，不增加内容验证、哈希复核或数值读回。

`reference_z_controls/` 额外保留既有 PMA/Lite 的两组匹配随机 z 对照：原 R1z/R2z 预测及详情、特征统计和独立 R2z 逐轮曲线。它们复用已有缓存，不生成新编码器特征，不重复 S 日志或 U0 导出。

`READOUT_ALIASES.json` 明列未重复物化的既定别名：T0 的 SoM/R1z 对应同格 R1；随机 z 对照的 SoM 对应 C1-0 随机 X 对照。源预测值已在 parquet 中提供，通过源记录 ID/原子 ID 对应，不产生新分数。

总体特征统计沿用原神经读出的全部冻结 TRAIN 特征人群；`reference_z_controls/features_observed/` 另列每个任务实际有观测标签的优化记录，SoM 同时提供仅候选且有监督原子的 `X_observed_atom`。`molecule_count` 计缓存中的原生分子记录，未合并同一完整分子组的多个源记录。两类人群分别标注，不改变原归一化或优化规则。

`reference_z_controls/` 同时导出 T1 实际保存的 `base_reference_R1` 原预测和 α/五折详情，文件名为 `random_C1-0_R1_v2_reference`；它与 C1/T0 的旧 R1 重建预测分别保留。SoM 参考的别名按 T0/T1 原上下文区分。`X_R2` 是图读出的拼接特征，SoM 实际使用 `X_atom`，无读出切换。

`r0_reconstruction/` 补齐旧 R0 未持久化的逐分子/逐原子预测：C1 六检查点和三个既有匹配随机配置，使用原 `nonlinear_probe`（20轮、Linear64/ReLU、B32、seed0），只在既有缓存上重建预测，不计算验证误差/CV/bootstrap，不重写原 R0 分数。原设备 CUDA、本次 CPU，均标记 reconstructed。T0 的既有冻结 X/R0 通过别名复用对应 C1-0/S 或 P 预测，T1 未做过的 R0 不补造原分数。
