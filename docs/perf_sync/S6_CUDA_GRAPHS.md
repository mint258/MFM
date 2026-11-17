# S6：CUDA Graphs 不适用（2026-11-18）

开关step_overhead.cuda_graphs=false；没有合格capture时显式拒绝开启。

**NOT_APPLICABLE_PREREQUISITE_UNMET。** 同一3090上S1以S0方法复测仍有126.03次同步/步，基线166.02次/步，未满足每步0次同步的启动条件。源证据：results/perf_sync/gpu_20261118/S1_profile_summary.json、S6.json。

按任务书不捕获、不实现补齐桶，不修改B4、PMA或任何mask来凑条件。CUDA Graphs吞吐、倍率及B类/无padding逐位验收均不适用；5090/4090未补测。此前“没有空闲卡”的历史解释已由实际同步测量替代。
