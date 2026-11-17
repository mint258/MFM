# S6：CUDA Graphs

开关预留为step_overhead.cuda_graphs=false；无合格capture时显式拒绝开启。

状态：NOT_APPLICABLE_PREREQUISITE_UNMET。S1后没有S0方式的实际零同步剖析证据（三种卡型均无空闲卡），因此严格按启动条件跳过。不实现/运行不超过8桶的补齐捕获，不为凑条件改动B4、PMA或任何mask，不新增GPU尝试。未花费GPU小时。

5090/4090/3090：未测，样本/秒及倍数均null；B类及无padding逐位对照不适用。不能将“未测”写成“实测零同步”，也不能写成CUDA Graphs已通过或有效。

2026-11-18 实测判定：3090/4535718的S1同步复测为126.03次/步（基线166.02），没有达到每步0次的启动条件，S6记NOT_APPLICABLE。不捕获CUDA Graphs，不修改其他项来强行满足条件；详细源见results/perf_sync/gpu_20261118/S1_profile_summary.json和S6.json。
