# 每步CPU开销提速：原始证据索引

工作树：`/share/home/zixiao/descriptor_analysis/MFM_step_overhead_20261114`；最终报告：`docs/perf/STEP_OVERHEAD_20261114.md`。

- `timing3090_4532627/timing_runs.json`：四个累计版本各100步预热、1000步计时。52.2517→59.0791→60.3907→71.5957样本/秒，最终1.37021×；同一空闲3090 UUID及每版选项均在记录内。
- `timing3090_4532627/profile_old/flame.svg`、`profile_new/flame.svg`及`flame_comparison.json`：新旧原生采样；采样数据单独采集，未用于测速表。
- `numerical_final_4532640/numerical.json`：最终随机0/G1的3M两组权重各20批，同卡旧1/旧2/新；全部逐字段损失和完整梯度通过噪声底容差，未用参数集合相同。原始三遍逐字段值在同目录`field_losses.csv`；120份完整FP32梯度在`gradients/`，每份24,755,300分量，布局在`gradient_layout.json`，总文件字节11,882,731,320。
- `input_pipelined_4532628/input_equivalence.json`：最终四批预取的1000批分子/构象序列及提交RNG一致，20批全部GPU输入、目标、掩码、配对/补齐索引精确相等。
- `capacity_policy.json`、`capacity3090_4532620/capacity.json`、`capacity_tiled_4532623/`：不分块在首重批OOM；保留分块、只关向量头重算，8重批完成，峰值6,143,677,440字节。fallback原记录的`execution`为真实配置，`options`曾误按fallback峰值派生，最终采用`capacity_policy.json`的决策。
- `regression_4532639/summary.json`：一次全量回归的最终合并结果，复用`regression_4532629/`完成模块；3592通过、24跳过，1项既有失败为`test_p_recipe_exclusion`引用已删除的`refit_d4.py`。本次引入的冻结来源校验问题均已修复并通过补测。
- `repository_check_final_delivery.json`：仓库检查PASS；`runtime.json`为共同环境与固定配方。

原始梯度PT、计时CSV、逐字段CSV及完整JUnit XML保留服务器上述results路径；Git保存测量/数值JSON、原生图及必要日志。早期未落盘梯度的对照在`numerical_4532624/`保留，以最终记录为准。所有旧失败/中止记录均保留。数据LMDB、G1检查点和P研究正在运行的卡、作业及输出未改动。资源预留与磁盘保护通知在共享STATUS中，临时文件未作人工清理。
