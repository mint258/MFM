# 分批 profiler 采集协议 v2

问题：f9245bd 的真实S作业352/353都完成了2个warmup与20个测量批次，但未闭合。
352在汇总期间触发56GiB进程树RSS上限；353导出trace触及2GiB输出预算并非零退出。
这些是测量工具的资源失败，不是模型数值或等价性通过；原作业、SDK、trace、监督记录保留。
354仍按其原始实现独立记录终态，不追改旧运行源码。

本修订在任何v2 GPU实验前提交。模型、原S目标/损失/optimizer/批次顺序、seed、
max512/65536原子/8M填充代价、8个spawn worker、warmup2与测量更新20均保持原定义。
原snapshot rawSHA与所有资源/进程边界沿用350已测实现；资源上限保持原定义。
这项工具修复不改变A/B验收阈值或任何模型选择规则。

固定采集相对测量序号0、10、19，三类GPU相同。每个样本使用独立torch.profiler上下文，
保留CPU/CUDA、shape和memory事件，单步结束后立即导出其trace与operator表，再释放
profiler对象。输出文件名含实际update ordinal。三次采集不把所有20步事件同时留在主存。
全20步的loss/count/ID/padding/GPU峰值记录仍保留；steps.jsonl明确profiled标记。

吞吐主值来自其余17步的实际完整step墙钟，包含数据、监控、W&B及逐步记录，排除
诊断采集和独立trace汇总/导出。step_timings.json保存实际计时序号与秒数；summary
另列包含采集/导出的完整测量循环时长。三个样本仅用于组件/内存诊断，不能以它们的
profile耗时作等价提速倍数。若小合成smoke所有步都采集，明确标profiled_smoke_only。

每一步单独重置CUDA峰值计数，并分别报告20步总峰值与17个非采集步的峰值。
三份trace分别做唯一kernel区间并集归因，保留unknown和各自的原始来源SHA；不把
重叠inclusive CPU区段与完整反向时间相加。真实三卡闭合且报告审核后才接受阶段1。
