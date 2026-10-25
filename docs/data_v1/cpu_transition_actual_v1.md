# CPU节点调整与实际试点结果

观测：2026-10-25T18:45:27.343320+08:00。本报告由control/record_cpu_transition_v1.py按实际sacct、已闭合receipt和小metadata生成，不读取大科学正文。

用户明确CPU任务从可用CPU节点运行；站点cpu分区为2、8–19，当前选17。run_decisions_v4与有限scope policy记录本轮小分析试点的资源解释；正式生成仍原16CPU64GiB/全部用户声明内存85%，UFF/QM14–19，未获正式资源放宽。

| 实际父作业 | 结果 | 分配核秒 |
| --- | --- | ---: |
| 4520364 | TIMEOUT / 0:0 / 14425s / 16CPU | 230800 |
| 4520476 | COMPLETED / 0:0 / 1s / 16CPU | 16 |
| 4520484 | COMPLETED / 0:0 / 195s / 16CPU | 3120 |
| 4520496 | COMPLETED / 0:0 / 0s / 16CPU | 0 |
| 4520497 | FAILED / 1:0 / 28s / 16CPU | 448 |

4520476的8项新资源边界通过；4520496原6闭合fixture+2新CPU边界通过（ElapsedRaw=0是整秒取整，不能称无执行成本）。3CID4520484的中央monitor闭合无denial。原X均通过；三个旧features失败均精确复现于环片段SanitizeMol：['ring_system.fragment_2.Chem.SanitizeMol_exact_old_call', 'ring_system.fragment_34.Chem.SanitizeMol_exact_old_call', 'ring_system.fragment_34.Chem.SanitizeMol_exact_old_call']。修复只在新候选helper评估，旧screen/X与427失败证据不改。

MAD0 job4520497的4项新增边界通过，但源扫描被CPU_MEMORY_HEARTBEAT_STALE拒绝，不能接受partial或推进MAD。monitor自身全ALLOW/no内存拒绝；Root新v2监控改本地/tmp及boot monotonic时间，1秒采样/5秒新鲜度/75%自身RSS/85%节点包络保持，科学子进程自然结束后才SHA导出持久证据；当前v2实际验证仍待完成，旧源不改。

S′原336试点实际为TIMEOUT，尽管父ExitCode为0:0也不是C0完成。最后进度334/336，包CRC/SHA/身份仍待CPU部分审计；无最终receipt，不开正式放行。延期至6h的单次请求被Slurm权限拒绝，原4h截止后调度器终止；Root未强停任何任务。原父分配成本为230800核秒，不能丢失。候选级中间状态未落盘，若恢复需独立Root审查、准确缺包集合及同输入/同seed整分子重执行来源，完整包不重算；当前尚未授权或提交恢复生成。

限制：common/最终D2/D4/D3/D5/D6/D7、真实P′、全来源全部划分去污染及扩充生成均未完成。Se与ROUTINE决定不变；任何字段新增mask>1%等科学停止阈值不变。大规模正式作业仍受无明确内存上限的其他作业约束。
