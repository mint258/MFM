# 模型线资源观测

2026-11-11；描述性记录，不作为模型采用分数。原始W&B保持不变。

- 18:04 CST：T1 A0/S（node5）续训102400，A1/S（node6）续训108800，损失有限；进程分配峰值8.93/9.32GB。GPU驱动显存含缓存和CUDA工作区，不能与torch分配峰值混为一项。
- 18:20 CST附近：node5观测到本训练之外的lmp CUDA上下文（344MiB）。原生W&B的整卡功率、利用率和驱动显存可能包含它；此观测不回填为10万样本边界状态，也不推断其启动时间。node6当次仅见本训练上下文。运行时GPU共享按已有授权记录风险，不改变科学指标，不处理其他用户进程。
- node0虽有空闲3090，但实际根盘仅3,684,593,664B，低于10,737,418,240B底线；本次没有提交或迁移任务到该节点。Lustre/NFS空间不能绕过根盘保护。
- node20两项旧v2记录服务的24个真实SDK均已闭合，4529106/4529240已按精确作业/UID/命令退休，原文件保留，释放8个CPU核。两项GPU训练使用自己的原生SDK；18:04巡检时CPU16核作业等待资源，后续以实际调度为准。
- node20/21/22已观察到其他用户GPU任务；node2驱动不可用。本次不在这些已占用或未准入的卡上新增运行。新任务继续执行实际节点字节/inode/native quota、公共UUID锁和启动时foreign-context检查。

来源：仓库外MODEL_V3_GPU_inventory_20261111T1015.json、MODEL_V3_NODE0_capacity_before_A2_20261111.txt、MODEL_V3_legacy_recorders_retirement_20261111.json及原生W&B。观测是点时状态，后续按半小时巡检更新。

- 23:28 CST巡检：node0空闲3090的根盘余量3,684,495,360B，仍低于10GiB底线，未新增任务或传输。node1/21仍有其他任务CUDA上下文；node20分配96/104核，剩余8核不足本任务16核请求，四统计量与SDK归档继续等待，节点本身为MIXED。5/6磁盘守护均OBSERVING且记录新鲜，模型所有根目录合计24,714,448,896B，统一剩余峰值预算75,285,551,104B；Lustre/NFS实际账户余量分别约210.30/153.88GB，均覆盖当前已登记并发需求。

- 23:58–23:59 CST巡检：T1 A0/S、A1/S各1,166,080/1,500,000阶段样本，实际两作业均RUNNING，磁盘守护OBSERVING且观察年龄<4秒。node5/6当次仅见本训练CUDA上下文，不撤销node5历史共享时段。node0根盘余量仍3,684,495,360B，未迁移任务；node1/21仍见其他上下文。`TZ=UTC squeue --start`给CPU4529737的当前预估为2026-11-18T12:44:40Z（20:44 CST），其余归档作业同时段；这是调度器估计，不是已运行或完成。

- 2026-11-12 00:07 CST: four zero-work pending single-thread SDK archive jobs changed NumCPUs/CPUsPerTask/MinCPUsNode to1. Actual4529839/4529840/4529986/4529987 completed0:0 on node20,1CPU each,28/17/15/17seconds. The previously estimated Nov18 archive start is superseded by these completions; the16CPU four-statistics readout still waits. Node20 actual root headroom was about275GB with sufficient inodes; native Lustre/NFS quota covered registered concurrency. Upload read shared Lustre directly without extra node/tmp/NFS archive copies.
- 00:29 CST: both T1 S jobs RUNNING at1256256 stage samples, disk guards OBSERVING with age<4seconds. Node0 root available3684335616B remains below10GiB; no new work/writes there. Node1/21 have other CUDA contexts; node5/6 showed only own training contexts at this observation.

2026-11-12 08:03 CST actual update: user-approved node0 /tmp/D3_v31_pilot_20261105_v1 cleanup deleted exactly7 files and3 empty directories, freed34937044992B, root free38621130752B (floor10737418240B). Shared originals and current D6 retained. Fresh filesystem/inode/native-quota/concurrent-output admission passed; UUID GPU-a967b766-fb5e-8db3-b09c-4ddc6c02b332 now runs existing A2 chain4530010/11/12/13. A2/S first272 real updates accepted, rec0, diskguard OBSERVING. Node5 A0/P1123808 and node6 A1/P1104704 samples continue; no training restarted. Recovery configuration41 entries. All original four moved tasks were PENDING with zero runtime before cancellation. Diagnostic export newly authorized: cached-input-only, report-only curve replay; running jobs/science untouched.

