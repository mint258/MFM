# 按来源采样桥接的实际边界验证

目的：分别投影 PM7/UFF 的构象身份与采样顺序，并阻止诊断构象进入训练清单。输入仅为新增合成fixture，没有读取真实语料。

实际 CPU 父任务 4520608，节点 compute-0-17，16CPU/4GiB；6项新增测试均PASS，日志测试耗时0.001秒，监控闭合无内存拒绝。

验证覆盖：两来源独立ID及三种顺序；诊断base和child排除；保留energy training_rank=0作为最低能ID；跨来源碰撞与引用拒绝；重复物理身份拒绝；view不作基础构象；原子数、角色、布尔exposure与单分子内存边界。

实际父ElapsedRaw=1秒，分配核秒=16，分配核时=0.0044444444444444444。成本从实际sacct父记录计算；整秒0不表示真实零耗时，steps不重复计入。

限制：这是候选桥接的合成数据边界验证。D1仍draft.3，tensor参考系/模型tensor消费、审计原因sidecar、真实provider及最终共同人群/D5/export均未验收；没有改模型文件，没有宣称D3/D5完成。

来源与完整path/bytes/SHA见外部 /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/export/sampling_projection_fixtures_cpu_v1/actual_closure.json；本报告由 /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/export/wire_v1/write_sampling_actual_v1.py 从已闭合小型元数据重建。

生成时间：2026-10-25T21:34:02.073125+08:00。
