# Native B 原计划资源等待 v4

仅修正已公开 v3 的资源预等待范围。v3 已完成 slot030 / GPU4525129
（Root 报告 C0、2474秒、bf16 seed0 update9000），随后原 v8 的 GPU 门因目标22e上
存在外部 gmx 而拒绝 slot031。原失败、v3 stop、030证据均保留，不改成科学失败或成功。

Root 已实际 reconciliation：
Native_B_slot031_pre_submission_resource_reconciliation_actual_v1.json。
其确认30份 submitted 均有 closure、旧v3 PID消失、没有031 intent/submitted/slot/SB，
仅释放 exact PRE_SUBMISSION 登记；storage、Native principal、counters及其他记录不变。
v4 不执行此清理。新首段仍 slot31 / seed0 / bf16 / update9000→10000。

## 唯一资源增量

在原16空闲CPU及32GiB+15% MemAvailable只读等待成功后，沿原
compute21_known_hosts_v1 严格SSH，只查询原节点：

- nvidia-smi GPU uuid/name/driver_version/memory.total/memory.free
- nvidia-smi compute-apps gpu_uuid/pid/process_name/used_gpu_memory

直接复用冻结 native_S_long_operational_v8/native_resources.selected_gpu
核原 GPU-22e21021-e572-4562-fc51-cd8c83e74141、5090、driver590.44.01。
先核身份，再按同源 normalized_uuid/首字段规则识别目标 compute 进程：
存在则等待；没有则再调用原完整 selected_gpu(gpus, apps)。
查询失败或身份不符停止，绝不改卡、杀进程、取消任务、申请外部任务或持GPU锁等空闲。
等待中仅持原本独立 controller.lock，不持 dispatch、registry 或公共GPU锁。

原 v8 随后仍重新登记并验证实际CPU、内存/85%、GPU、UUID公共锁、quota等全部门。
预等待不是容量保证或资源预留。预等待后发生竞争，原 submit-next 仍失败即停止，
不自动重试、不删除新 PRE 行或猜测提交结果。

## 不变与固定 metadata 示例

保留原7天绝对终点（从 native_B_remaining_20261029/identity.json 的原 started_unix 算），
不是从v4重开7天。保留81有限循环、原500步验证/20k科学计划、原3d9 producer、
CP/seed/sampler/环境/原 submit-next 参数、6900秒/2小时、software32GiB/RSS28GiB、
自动Slurm内存及双2GiB。新增GPU查询计入原观测耗时；
原v3观测完成后、Popen前的deadline断言原样保留。

下列是源逻辑说明，尚未执行metadata测试或Slurm QA：

| 固定输入情况 | 预等待结果 |
| --- | --- |
| 原UUID/5090/590.44.01，目标有gmx或其他compute行 | 等待，不持GPU锁、不触进程 |
| 原身份且仅其他UUID有compute行 | 不拦他人，交原Root门重新验证 |
| 原UUID缺失/重复、型号或driver错误 | 原selected_gpu拒绝，STOP |
| GPU或apps查询returncode非0 | STOP，不调用提交器 |
| CPU不足或原MemAvailable reserve不足 | 原只读等待 |
| idle查询返回时已超过原绝对截止 | 原deadline断言拒绝新child |

## Root启动条件

新source namespace为native_B_remaining_GPU_auto_resource_wait_20261029_v4_source，
独立control为native_B_remaining_GPU_auto_resource_wait_20261029_v4。
Root先核pins、原reconciliation、无其他controller、实际公开字节，建立新空control目录，
再按handoff argv启动一次；本源码包没有发起进程或生成actual job/SDK证据。
Root保留唯一SSH/调度权限。原v3、v8、登记、hold、030与031均未修改。
