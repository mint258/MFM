# S0：资源检查（无合格空闲卡，未剖析）

2026-11-17，基线 p-recipe@1237304，任务分支 perf/sync-free-20261117。

本次 S0 三种卡型均按任务书“无空闲卡就跳过，不等待”跳过，未启动计算。

| 卡型 | 现场证据 | 结果 |
|---|---|---|
| 5090 | compute-0-22 唯一允许的卡 GPU-9b6008d0-35dd-4bff-f69a-0927b04b7eef：12,235/32,607 MiB，主线在用；node21 禁用 | SKIPPED_NO_FREE_GPU |
| 4090 | compute-0-20 两张卡占用18,184/49,140及22,738/49,140 MiB，主线/侧线正在运行 | SKIPPED_NO_FREE_GPU |
| 3090 | node0 p-heads在用并有已排定后续任务；node1/2 CPU全分配；node3/4有其他用户gmx/MPS上下文；node5/6/7主线在用 | SKIPPED_NO_FREE_GPU |

不取消、不抢占现有任务，不占用其排定的新卡。以上仅为现场资源观测，不能推断这些卡永久不可用。

GPU忙碌比例、kernel数、每步同步、发射耗时、H2D次数/字节和ε_loss/ε_grad均为 **未测量（null）**；没有trace文件。不能引用PR8/PR10旧测量填充新的基线，也不能据此宣称S1达到零同步或某项提速有效。

基准配置复制到 configs/perf_sync/M2.json，保留B32、A1+B3+B4、原科学预算和LR定义、14读进程、FP32/TF32关闭；仅替换独立输出/运行名并移除主线resume。实际短测上限由工具限制，绝不把原3M预算当作执行许可。

后续继续实现默认关闭的开关和新逻辑单测；本次未通过GPU验收的开关不得建议开启。测速100预热+1000计时与禁止超过1000更新的冲突已向用户提出，未确认前不启动1100更新测速。

后续只读复查（06:30 UTC附近）：node0旧p-heads任务4535405已FAILED，后续训练已改排node20；node0的3090虽无GPU进程（8MiB），但CPUAlloc33/48，仅15核可分配，仍不满足本基线与主线相同的16CPU/14reader配置，因此不为测速缩减协议或等待资源。node20/22目标GPU仍在用；node3/4仍有他人gmx/MPS上下文。

## 2026-11-18：补充指示下的首次GPU实测

4535718/node5/16CPU，固定3090 UUID GPU-dac07d74-6269-c7db-8832-340dd3c0b377，M2/B32/FP32/TF32关闭/14读进程；无其他GPU计算进程。原SKIPPED记录保留为前轮历史。

100步预热+100步CPU/CUDA时间线：GPU忙碌/墙钟71.25%，每步4899.66 kernel；同步API166.02次/步（含采样边界2次device同步；其余16600次stream同步）；主线程发射kernel 42.58毫秒/步；H2D 88次/步、4736603.28字节/步。以上包含profiler开销；吞吐另用不带profiler的1000更新测试。同期仍在clip校准前期，norm即时取回是保留行为。

两组权重各20批的噪声底：epsilon_loss=5.857070254547035e-7，epsilon_grad=1.154455482350726e-6。实际代码位置与API计数见results/perf_sync/gpu_20261118/S0_profile_summary.json；to_dense_batch、PyG Data传输等同步已观测。原始trace与完整警告位于/share/home/zixiao/descriptor_analysis/.perf_sync_scratch_20261117/gpu_20261118/S0_trace.json及S0_sync_warnings.txt，不进入Git。
