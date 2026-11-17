# S0：3090 时间线、同步与噪声底（2026-11-18）

按USER_DIRECTIVE_20261117完成必做GPU实测。固定M2/A1+B3+B4、B32、FP32、TF32关闭、14读进程；node5、16CPU，3090 UUID GPU-dac07d74-6269-c7db-8832-340dd3c0b377，原作业4535718。5090/4090可选补测未执行。此前无卡跳过的历史记录已由补充指示覆盖，不能作为本次完成证据。

|指标|实测值|
|---|---:|
|GPU忙碌区间并集/墙钟|71.2501%|
|kernel/步|4899.66|
|同步API/步|166.02|
|主线程kernel发射API时间/步|42.5807 ms|
|H2D拷贝/步|88|
|H2D字节/步|4736603.28|
|ε_loss（PR8相对定义）|7.278473238064165e-5|
|ε_grad（完整梯度相对L2）|1.154455482350726e-6|

CPU与CUDA activity同时采集，100步预热后采100步。同步API含边界2次device同步和16600次stream同步。原始trace、调用栈和同步警告保留本线scratch，汇总附全部实际源位置与计数，见results/perf_sync/gpu_20261118/S0_profile_summary.json。实测包括PyG dense/数据传输、头部运行时检查与batch.max、成对索引、bincount、分组损失以及校准期梯度norm取回；CPU100%本身不构成CPU瓶颈证据。

原始路径：/share/home/zixiao/descriptor_analysis/.perf_sync_scratch_20261117/gpu_20261118/S0_trace.json.gz、S0_sync_warnings.txt、S0_field_losses.csv。trace/完整梯度不进Git。剖析包含profiler开销，吞吐另测，不把71.25%推算为可兑现提速。

随机seed0及B3的3M检查点各20批、基线两遍，固定RNG；两遍本身存在CUDA非逐位噪声。ε_loss按PR8的abs差/max(abs(loss),1e-30)定义；早期abs差/(1+abs(loss))统计已直接用保留CSV更正，没有GPU重跑。原结果归档S0_noise_original_combined_norm.json，更正见noise_reanalysis.json；各项整体单步结论不变。

不带profiler的M2基线1000更新：68.620173样本/秒，主进程CPU97.15%，整卡307.15W，CUDA分配峰值6510372352字节，末200均损失0.4524085382。测速预热采用首批100次前反向、不更新优化器、恢复RNG后计时1000次实际更新；科学预算/LR分母保留M2原样。每条不超过1000更新，不改标签、mask、归一化、采样或任何既有FP64数据处理。

存储更新：S0/S1原始trace已无损gzip保留为S0_trace.json.gz（473384378字节）、S1_trace.json.gz（476156940字节）；原runtime/summary中的trace保留运行时原路径，实际归档路径以此为准。4535744的S8导出临时副本触发20GiB保护后，仅在本线scratch内归档，原梯度与CSV均保留。
