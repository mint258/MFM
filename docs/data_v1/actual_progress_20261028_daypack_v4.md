# 2026-10-28 日级任务实际进展 v4

正式数据任务按约24小时合并，500分子小批次仅作同一父作业内的检查点，不再单独sbatch。规则已记录并同步HPC skill1.0.123。

| 端点 | 真实作业 | 资源 | 本次观察 |
| --- | --- | --- | --- |
| Main | 4524658 S′剩余续接 | compute-0-18 /16CPU /24h | RUNNING；同父9项preflight全部通过，正在核对原成果 |
| Alpha | 1885075 PubChem A | compute-0-1 /32CPU /24h | RUNNING |
| Alpha | 1885076 PubChem B | compute-0-6 /32CPU /24h | RUNNING |
| Alpha | 1884790 Coconut | compute-0-1 /16CPU /48h | RUNNING；沿用原作业，不中断或重算 |

Main上一S′父4524556实际COMPLETED0:0/23208秒/64CPU；24,338份逐分子派发结果已保留。下一作业从真实终态、原始once记录和全部已完成几何核对剩余任务，不能把派发数冒充质量通过数或最终Common。

标签汇总4524608实际COMPLETED0:0/3959秒/64CPU，业务状态为资源观察STOP，尚未完成typed读回/归一化/投影。已保留116份完整whole-SHA哈希分块与关闭目录；Root已签只读复用授权。下一父须先在CPU内验证当前文件帧及完整目录，再复用哈希阶段，继续原质量检查，不能据此提前宣称D4完成。STOP记录为时间有效性校验失败，现有证据不能精确判定它当时读到哪一份snapshot；不归因为内存不足。

MoleculeNet两次实际启动均在同父3项Source核验中失败，尚未读取科学输入或访问新官方数据：4524614为Q名称缺失（31秒/16CPU），4524627为hashlib缺失（61秒/16CPU）。当前源码已修复这两个模块依赖并保留原版本及费用；正在逐文件核对实际外部API并接入原资源观察保护，再在下一日级父中一次核验执行。

新S′资源适配仅将新父绑定实际16CPU/compute-0-18；原64CPU/compute-0-13作业证据、科学函数、种子、阈值和claim命名空间不变。新独立25h配额发布器PID3072364真实启动，旧发布器不修改。全部future allowance合计1,121,587,921,920字节，包括新旧发布器各自64MiB；释放前实测扣除全部future后约278.59GB，保留200GB要求。无需SBATCH内存请求。

D1–D7及250万扩充仍未全部完成。九个来源的去污染输入已就绪，MoleculeNet17和Coconut尚未整体放行；Common最终验收、CommonTRAIN统计、最终子集/导出/本地盘吞吐和正式P′试点仍按原依赖继续。精度例外仅限既有15+1200诊断，不据此启动正式全量。

证据：本run的control/active_checkpoint_v52.json、owned_accounting_checkpoint54_cpu_daypack_20261028_v1.json，以及cpu_packed_day_v2/dv1_pack_sprime_day02_r4_cpu18_20261028_v1内真实submission/proof。最新记录覆盖v3的运行状态描述，历史记录保留。
