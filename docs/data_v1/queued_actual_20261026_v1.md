# 实际排队与持续观察

目的：按用户持续提交指令，将已具备输入与审查的步骤交给Slurm等待资源。以下为当前真实作业，不代表计算或整轮验收完成。

|任务ID|步骤|当前状态|原因|CPU|GiB|
|---|---|---|---|---:|---:|
|4520959|22项新边界检查|PENDING|Resources|16|64|
|4520960|2缺包恢复+14复现控制|PENDING|Dependency|16|64|
|4520961|72次真实帧控制计算与验收|PENDING|Dependency|16|64|
|4520962|2000UFF输入的retention准备，无QM|PENDING|Dependency|16|64|

所有任务经实际readback核实exclusive=user、16CPU/64GiB、禁自动重排。观察进程启动后已release到资源队列；后继任务依赖检查任务实际C0。计算启动前还必须取得120秒内、目标节点时钟的Root执行证明，重算全用户声明85%、真实内存、quota200GB和前置任务结果。零/缺失内存声明不作豁免。

用户级隔离等待规则见[Slurm官方文档](https://slurm.schedmd.com/sbatch.html#OPT_exclusive)。它阻止与其他用户同节点；初始held后readback确认再release，未修改其他作业。

S′保留334旧包和原TIMEOUT，新物理重放只含2缺包与14控制。6900秒×16CPU的追加分配上限加原成本为94.777778核时，低于原96核时门槛；这是上限，不是完成耗时预测。

72帧控制只验证规定的软件/字段与变换范围，不冒充2000构象12任务试点。2000QM仍须等待实际frame PASS和retention manifest真实闭合后冻结提交。

已验证观察进程PID 2054694 的UID、boot/start_ticks和源文件；当前心跳年龄16.157秒。它每20秒观察已注册作业，有效期24小时，期满须对同一真实作业重新核对并续接观察，不能重提作业。

本run实际父任务78个，已观测分配核时76.55555555555556，含所有失败/超时；完整sacct在/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/owned_accounting_cpu_queue_20261026_v1.json。

D1–D7最终交付、正式全量S′/P′及扩充第一批仍未完成。目标保持active；不能用本排队记录或源码测试替代真实结果。

输入与完整path/bytes/SHA、实际scontrol和父会计见 /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/queued_actual_20261026_v1.json。报告时间：2026-10-26T03:28:33.715550+08:00。
