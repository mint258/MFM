# Native B 资源等待 v5：已证实 foreign job 终态与一次显式首段重试

v4 及其实际失败全部保留。v4 在 NVML 短暂无 compute 进程时提交
slot031 / GPU4525157，worker 随后在原资源门拒绝 foreign GPU 进程；
实际 FAILED1:0 / 0秒 / 16CPU / node21。原 FAILED_OR_STORAGE_HOLD 和
process_private_closed=false 不覆盖。Root 真实 reconciliation 已核该拒绝发生在
snapshot/QA/supervisor/model 之前，child、supervisor、member、SDK、CP和
/tmp/mv3n_4525157 均无；原 slot030/update9000 的有效 CP 保留。

## 只增加两项

1. 原 CPU/MemAvailable 等待通过后，只等待已证实占用22e的
   job4525142 / guangyuan(uid1275) / compute-0-21。
   原 gmx PID882712 的实际 cgroup 已由 Root 绑定
   /slurm/uid_1275/job_4525142/step_0。
   新源读取 guangyuan 队列并只筛精确4525142；5143/C35及其他任务不阻塞此条件。
   即使目标 NVML 暂时空白，只要4525142仍 live 就等待。
   队列消失后还须原5字段 sacct parent 精确 job/user/node、
   确切终态与再次队列确认；缺失、传输失败、重复或未知字段均不能放行。
   不发 signal，不改/kill/cancel foreign，不持GPU锁等待。
2. 仅 finite_index=0 根据 Root 实际 reconciliation，使用原
   next_member(..., allow_failed=True) 并核唯一新首段
   slot32 / seed0 / bf16 / update9000→10000。
   previous 与 resume_checkpoint 必须仍是 Root 绑定的原030有效CP。
   只有这一次原 submit-next argv 追加 --retry-failed。
   此后使用原默认无retry；任何新child失败或未知，立即STOP，不循环重试。
   观测结束后调用前再核 next_member 没有变化。

原真实证明：
Native_B_slot031_actual_failed_pre_model_reconciliation_v1.json，
schema NATIVE_B_ROOT_ACTUAL_FAILED_PRE_MODEL_RECONCILIATION_V1。
源码内绑定其真实rawref，并严格核实际首段/失败/阻塞任务/授权字段。
不是把031失败改为成功、删除记录或恢复失败031；新实际job尚不存在。

## 原规则保持

原 v8、3d9科学代码、4成员20k计划、500步验证、seed、采样、初始化、优化器、
CP/数据、登记/hold/ledger均不改。原7天绝对终点仍取最初
native_B_remaining_20261029/identity.json，而不是v5启动时重新延长；
81有限循环、原6900秒/2小时、自动Slurm内存、software32GiB/RSS28GiB、
85% GPU与15% MemAvailable、双2GiB和全部原GPU/UUID/锁/quota最终门保持。
原观测后及 Popen 前deadline检查保留。预等待不是容量或锁定保证；
最终资源竞争失败仍STOP，由Root判断，不能自动重试。

仅新增 v5 source/control namespace。Root审核pins和实际公开字节、核v4已退出、
无32 intent/submitted/layout/SB和其他controller后，建立独立空control并启动一次。
没有新manager、dispatcher、monitor或Slurm QA父；作者未执行源码、AST、
SSH、Slurm、科学或SDK。

## 固定 metadata 反例说明（未执行）

| 情况 | 行为 |
| --- | --- |
| 4525142仍RUNNING，而NVML恰无进程 | 等待，不启动新段 |
| 只有5143/C35仍live，5142确切终态且消失 | 只通过该job条件，仍重验原CPU/内存/22e全部门 |
| 5142 owner/node改变、状态未知、sacct缺失/重复、查询非0 | STOP，不视为终态 |
| 终态后第二次队列又出现5142 | 继续等待，不准备提交 |
| 新首段不是32或不是原030有效CP | STOP，无提交 |
| 首段32新失败/不明确 | 原失败保留，STOP，不发第二次retry |
| 原7天deadline在观测中耗尽 | STOP，不新建child |

实际GPU新job、SDK、训练结果、科学接受均为未产生；不写未来SHA或成功记录。
