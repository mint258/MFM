# 单日打包进度：实际结果与待续项

2026-10-28 08:54（Asia/Shanghai）。全指南仍在执行，D1–D7 和扩充第一批完整交付尚未完成。

任务已按约一天的 Slurm allocation 合并：分子和小分片仅作为作业内检查点，复用持久进程池及已完成成果。工作提前完成时立即结束，不为凑一天增加计算。本机及服务器 HPC skill 已同步为 1.0.123；CPU-only、至少16CPU、无 SBATCH 内存大小申请、全部质量阈值及存储200GB余量保持。

| 工作 | 真实状态 |
| --- | --- |
| S′ 剩余构象 | 单一4524556，64CPU、compute-0-13、24小时上限，仍运行。08:41操作元数据为24338已派发、24320结果包、错误文件0；最终科学成功率未据此宣称。08:50只读进程采样有12个运行进程、约11.96核实际CPU活动；没有终止任务或打开活动SQLite。 |
| 七来源身份审计 | 4524598实际COMPLETED/0:0，638秒、16CPU14、10208分配核秒。复用旧404投影单元和12份严格导出，逐旧文件/来源/角色/身份及SQLite双向集合读回后完成TDC与407项留存物理证据汇总。未重投影旧Parquet，未复制旧严格导出，新增图/键/UFF/QM调用均0。 |
| 去污染来源登记 | 七来源11469344条身份已分别接纳，与此前Drugs/Kraken合成9/11 READY的独立部分清单；MoleculeNet17全来源和COCONUT仍待闭合。没有放行全来源去污染、排名或新数据池。 |
| 标签数值缓存 | 单一4524575以64CPU运行9428秒后FAILED/1:0：收尾导入不存在的day包bindings。原64worker均已返回；冻结115656文件、471171617813字节，无.partial或SQLite sidecar。将修复包装入口，并在同一新日级Parent内只读核对旧ledger/window/part后继续未读游标及coverage，保留原FAILED及603392核秒。缓存不等于最终Common TRAIN归一化D4。 |
| P′ | 已批准1200次限定诊断及留存只读核验完成。已定义向量500、张量100、梯度/力100项通过既有门槛。七来源同Parent已核对407份留存事实；MOPAC及扰动梯度坐标可核，另六类xTB的192项缺独立native坐标块仍UNKNOWN。D1物理定义综合审阅、Model policy、正式2000及full未放行，无新QM。 |
| N=1额外构象 | 原32试点及三批64的224个第二构象是已有小receipt候选；必须在CPU逐包核对、反核全旧once与真实Common后复用，不作为已接受Common数量。 |
| Alpha | COCONUT按原48小时任务继续。两份32CPU/24h PubChem日级代码及资源/存储准备就绪；等待原有限协调器和提交锁自然结束后，按真实注册/once/intent清点剩余集合，提交互斥的两份日级任务。未猜测索引、改旧deadline或重启旧小分片链。 |

七来源恢复前的两次失败也保留：4524583因把大型SQLite误当小元数据而FAILED，1351秒/21616核秒；4524596在Source3通过后因预留总账未刷新而被存储保护拦下，31秒/496核秒。后者尚未读取科学数据。Root核对实际已落地的标签文件，保守去掉未来预留中重复计入的64GiB，保持原输出cap、逻辑UNKNOWN及实际占用不变，重新提交后成功。没有删除旧文件或用外部步骤C0升级失败父任务。

独立部分来源清单：`control/decontamination_sources_partial_ready9_primary7_drugs_kraken_v1.json`，159584字节，SHA256 `9ce80622abc10eeeeddc61bed072c7104e7a0cce867dbb6d683d165eceff0f214`。七来源实际接纳链：`control/primary7_r3_actual_C0_acceptance_v1/`。标签实际失败会计：`control/accounting/labels_numeric_day01_4524575_actual_terminal_v1.json`；其Source14完整归档及纯lstat分块清单位于 `control/labels_failed4524575_*`。原文件、旧Source、全部失败成本与UNKNOWN均保留。

最终pilot的VAL候选遵守指南1.2的共同人群：Common∩effective VAL；ROUTINE整分子的VAL角色权威保持，不向Common外扩展，也不把原Source角色误作最终训练角色。

下一步继续完成标签恢复与未读部分、S′自然收尾和真实Common/PM7/D7、D5及最终D4、真实格式导出和模型加载验收，以及扩充全流程。最终源合同和P′精度例外仍各守实际授权边界，不以源代码完成、排队、单Parent C0或部分READY替代全指南交付。
