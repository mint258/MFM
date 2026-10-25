# 数据线与模型线接口状态

更新：2026-10-25。data-v1 仍在进行，最终真实数据未交付。最新可复算结果与全部父任务成本见 [CPU 实际报告](../data_v1/cpu_actual_cpu_v13.md)；报告生成入口为 workflows/data_v1_final/execution/cpu_analysis_v1/write_actual_report_v2.py。此前 [CPU 转移记录](../data_v1/cpu_transition_actual_v1.md) 保留原时间点结论。

- CPU 任务使用实际 cpu 分区2、8–19，本轮小试点在17。正式 S′/UFF/QM 仍限14–19、16CPU/64GiB、全部用户申报内存合计85%。最新六节点声明核验无合格节点（control/formal_resources_cpu_v10.json）：其他作业内存0记为无明确上限，未放宽规则或修改他人任务。
- Se 单元素例外及 ROUTINE VAL 7610分子/72525 PM7记录保持；其余科学阈值不变。
- D-1 仍为 [draft.3](training_format_v3.md)，未共同签为v3.0。模型需求清单不是正式签署；源码适配仍待对齐：r674 对称 tensor 六分量、PM7/UFF各自独立顺序与身份、诊断排除后最低能训练构象ID，以及mask理由粒度。未收到正式反对或契约意见冲突。
- 标签512分子4251记录、16源组、146分量的精确median/MAD/mask已实际闭合（最终reducer4520564）；各字段新增mask均0。拟合TRAIN4211，应用VAL20/FULL20。它仍是原source人口小试点，最终共同人群、geometry/order/diagnostic冻结后才计算D4。
- 尺寸相关性4520541实际完成：129物理目标/146分量，TRAIN元素参考与逐目标rho已保存。sigma/pi的物理不变性、部分单位/原生精度仍待证据，未据此冻结最终注册表。
- S′原336试点4520364为TIMEOUT/14425s/64.111111分配核时；没有final receipt。只读审计4520527确认334完整可复用包、2缺包、0损坏；完整包中SUCCESS102，其余科学失败保留。新的 [恢复提案](../../workflows/data_v1_final/conformers/recovery_v1/README.md) 只准备源码与待决模板，保留334旧包、2原task/seed重放及14独立复现控制；未运行测试或恢复生成，预算与资源批准未冻结。
- P′1000分子/2000 UFF原准备保持。三项CPU增量边界通过；4520552完成72组frame审计输入准备，实际16渲染TID。尚无QM/frame科学验收或2000构象成功率/成本结果，不放行P′全量。
- [EA七例原生诊断](../data_v1/ea_known_seven_cpu_v1.md)已由4520570实际C0/20秒完成：7例、14上下文、16worker。复用同文件Parquet句柄并关闭旧句柄后，最高worker RSS为385368064B；96次打开/关闭、5560次复用，预算保持1280MiB/worker和全局32GiB/75%。14份canonical原始输出均未保留或不存在，根因仍UNKNOWN，未从NULL/缺失或跨方法能量推断SCF失败，未改标签或新增mask；约390条全人口计数仍待重建。
- PubChem官方raw SHA/CRC已通过；全X15879477记录回放一致率100%、未解释0，共同人群范围待最终绑定。原前10000行8197去重features/8198 aliases/753特征失败证据保持。四项新边界通过，4520555的3CID候选generic-first修复评估通过，未改pool；[配对10k回放](../expansion/paired_prefix_candidate_replay_v1.md) 已准备NOT_READY源码，独立有限范围正在登记，实际回放尚未运行。
- 76个来源current pin已由4520547实际完成；这不等于全部身份导出、全划分去污染或候选池放行。下游清单仍按指南默认。
- D3/D4/D5/D6/D7最终交付、正式S′/P′与扩充第一批尚未完成，未开最终PR。负面结果、所有失败和超时的父成本已保留；0整秒会计值不解释为真实零耗时。