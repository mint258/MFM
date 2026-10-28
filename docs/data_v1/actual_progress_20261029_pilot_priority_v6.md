# 2026-10-29：日级作业与试点优先的实际进度

正式扫描、缓存和构象任务按约24小时的单个sbatch执行，内部使用持久进程池和检查点。HPC技能当前1.0.124的本机、服务器两份字节相同；其中10月28日单日打包、11–19构象节点及CPU不申请SBATCH内存的规则继续有效。

D1剩余设计已收敛为[五项一次决议](../interfaces/D1_user_decisions_20261029_v1.md)，已交用户选择；Model已有条件式反馈，尚无joint v3.0 ACK。r73有序条目/F64、r674完整六分量/尺度/损失、192项独立坐标UNKNOWN的证据接受政策按该表一次定案。不会把用户决议、源码检查或小样本诊断写成消费者已实现。

| 工作 | 真实作业与实际状态 | 仍待完成 |
| --- | --- | --- |
| S′补齐 | 4524666，16CPU/compute-0-14/24h，持续运行；原成果和once记录复用 | 剩余补齐、最终共同人群和D6 |
| 标签覆盖 | 4524729，16CPU/compute-0-18/24h，启动9项预检和原整库检查PASS，正在原数值覆盖验证 | 完整覆盖和后续统计，不冒称D4完成 |
| PM7缓存与试点选人 | 4524738，16CPU/compute-0-14/24h，同父20项预检全部PASS；先旧完整S′母表/原嵌套名单/55k优先，再继续全部原人口 | 实际55k缓存闭合与独立试点geometry/order/heldout/统计/导出 |
| MoleculeNet | 4524733，16CPU/compute-0-18，实际C0/35秒；3项Source测试PASS，全部21案例保守排除覆盖已独立接纳 | all11索引与完整候选池筛选仍未放行 |
| P′原2000输入 | 4524740实际FAILED/168秒/16CPU；3项预检通过，软件asset读取路径门拒绝，0初始化/0Native调用 | 完整执行器、实际输入闭合、精度选择及原试点质量/成本门 |
| COCONUT | Alpha1884790实际C0/142709秒/16CPU；2939137物理行、46闭合分块 | strict5及全部变体/孤儿身份的去污染投影 |
| PubChem | Alpha1885075、1885076，各32CPU/24h，实际仍运行 | 全源筛选与后续去污染/排序/新构象 |

标签旧4524665实际FAILED/20587秒/16CPU：全部剩余数值投影已经写完，原146字段质量报告无新增1%HOLD，随后覆盖SQLite触及16GiB软件页上限。现父只复用闭合投影、重做原覆盖验证；新预算336GiB中覆盖304GiB、投影/管理保守保留32GiB，统计未启用。没有重新解析原WP5或LMDB数值。旧部分SQLite、原FAILED和329392分配核秒完整保留。

恢复启动的4524728因Source逆向验证将物理CRLF规范化而FAILED/31秒；已修为按原字节比较，旧Source17完整归档。PM7首父4524730在DATA、once和输出开始前因三件原schema定义被误分类为DATA而FAILED/32秒；明确Source清单修正已用于4524738。两次启动失败保留，共1008分配核秒。4739是必要的修后Family与整库源码校验，实际C0/10秒/16CPU，两阶段PASS；原已通过的D4/D5/N1测试没有再次重复。

MoleculeNet新增只做3次官方GET、214232字节，保留原21项图身份UNKNOWN：15项原作者FAIL占位逐项保留、3项离子与原X02域不相交、2项原生原子计数下界、1项ARG与当前组分并集。6条strict5补充和2条typed下界已在CPU逐项读回。新V2消费者按每个候选的真实元素/组成执行约束，旧消费者拒绝V2。当前10/11来源具备对应排除依据；COCONUT仍待完成，不能把这份部分状态当完整池READY。

D2注册表仍待实际尺寸家族/归一化及同版本政策接合；D3、暂定D4和D5尚未交付。当前试点独立使用已完整S′的分子，保留原12万⊂24万⊂60万和5万TRAIN＋5000 ROUTINE VAL计数，不把55k冒充全人口。原2万诊断MID候选必须进一步绑定真实heldout构象及所有直接children；数值统计必须反连接这些真实几何。全量共同人口和D6留到补齐完成后更新。P′、MoleculeNet、PubChem和COCONUT后台继续，P′原15＋1200精度例外不自动延伸至2000或全量。2000准备的当前阻碍为软件库/.conda/原件与科学DATA路径域不同，正在本准备namespace作限定软件读取适配，原全局DATA路径守卫不放宽。

真实证据均在同run的control下：active_checkpoint_v56.json、owned_accounting_checkpoint57_actual_progress_20261029_v1.json、molnet21_4524733_actual_root_adoption_readback_v1.json、decontamination_sources_partial_ready10_molnet_conservative_V2_v1.json、pm7_priority_r2_cpu14_20261029_v1_actual_prepared_summary.json、pprime_original2000_prepare18_actual_prepared_summary_v1.json。本文为点时进度；运行状态、计数与后续收尾由新的实际会计更新。