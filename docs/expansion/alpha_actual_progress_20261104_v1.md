# Alpha 实际处理结果（2026-11-04）

计算已迁回 Alpha CPU，完整 Common 参考已验收。全来源去污染及250万分子批次仍在推进。

## 已完成子项

原始124,857,440条 PubChem 记录已有完整初筛产物；原内部 min-CID/full-key 去重候选109,871,959个；技术修复后当前候选109,875,599个，仍为去污染前池。[固定100万基线统计](pubchem_baseline_statistics_actual_20261103_v1.md)已完成11个数值字段和28类官能团统计，完整Common及其基础分布统计已验收；当前新基线统计和最近邻对照仍待完成。

[十来源字节验收](all10_replicas_1885168_root_actual_v1.json)：1885168实际C0/47秒/16CPU，511条逻辑引用共4,004,318,487字节全SHA通过，2项边界测试通过。[V3语义检查](all11_native_fixture4_1885170_root_actual_v1.json)：1885170实际C0/6秒/16CPU，4项合成测试通过；没有生成真实all11清单或索引。

## Common 完整扫描与119例异常

[1885153实际终态](common_1885153_actual_terminal_HOLD_v2.json)为C0，16CPU、18,275秒。完整扫描1196122个MID：TRAIN1188592、VAL7530；原生记录分别10973084、71884。33份输入全SHA、4份输出读回、16个真实工作进程、6+3项源/IO测试均齐全。原母体1214218、排除18096、UNKNOWN3436保留。

特征阶段119个TRAIN MID（352原生记录）进入HOLD，strict5只有1196003行，原SOURCE_GRAPH_HOLD_NOT_A_SUBSET_REFERENCE状态保留，未被验收为完整参考。

[元数据审计1885169](common_hold119_audit_1885169_root_actual_v1.json)实际C0/37秒：119例各只有一个Creator变体，全部FEATURE_COMPUTE_UNRESOLVED/AtomValenceException，无多图冲突；保留全部352条来源及事件定位。

[原生分步诊断1885171](common_hold119_native_1885171_root_actual_v1.json)实际C0/13秒，16真实进程、2项元数据测试、8项普通分子对照通过。119例原X筛选、原图解析、InChIKey和ECFP4均通过；其骨架含216个五配位磷。官方泛化将其换成碳后，末尾Chem.RemoveHs的默认价态检查报错。traceback定位原screen.features及[固定官方RDKit实现](https://github.com/rdkit/rdkit/blob/Release_2025_09_5/rdkit/Chem/Scaffolds/MurckoScaffold.py)，安装源码SHA、官方Git blob及转换AST均匹配。

[独立完整特征验证1885175](generic_repair_validation_1885175_root_actual_v1.json)实际C0/23秒/16CPU：119例全部24字段、字段集合及canonical值精确一致，352原生记录来源保留；8个普通分子的完整原kernel特征字节不变，2项元数据测试、16个实际进程的原AST逆变换证明通过。此前1885172和1885174失败记录保留；差异只涉及对照程序错误地混用逐片段路径，已按原兼容函数的全函数Kekulize回退修正对照证据路由，严格比较条件及生产修复库字节未变。修复仅处理临时泛化表示，旧kernel、安装库、原图、化学筛选、坐标、种子及历史HOLD均保留。[独立合并1885176](fullCommon_repaired_1885176_root_actual_v1.json)实际C0/208秒/16CPU，并已完成Root验收：[完整参考清单](fullCommon_repaired_manifest_1885176.json)为1196122行、当前HOLD为0。1196003条旧成功行的原始字节全部保留，仅加入119条；16份完整membership、2份旧成功数据全SHA读取，2份新完整输出全SHA读回与完整MID/role/native-record摘要32b1c446…8c9d96一致。Root在实际sonmi1核对当前FD元数据，保留Main历史STOPPED快照与当前FAILED账本，不声称Main C0。100万历史基线与完整Common的分布统计作业1885178已实际C0，16CPU、4526秒；Common全1196122个成员的11项数值分布、28类官能团及骨架长尾统计齐全，旧基线逻辑行摘要不变。

## PubChem 技术待核审计

[1885173实际审计](technical_unknown_audit_1885173_root_actual_v1.json)为C0/532秒/16CPU，完整502物理片、124857440行category计数一致，46201条技术UNKNOWN全部保留。42502条原PARSE_FAILED；3642条trace精确定位官方泛化RemoveHs的AtomValenceException，56条KekulizeException定位原MolToInchiKey，1条ValueError定位原wp5_key完整键校验。化学调用为0，没有改动候选池、minCID或基线；[逐条原生诊断1885177](generic3642_1885177_root_actual_v1.json)随后实际C0/38秒/16CPU：3642条全部达到REPAIRED_CANDIDATE_NON_GENERIC_EXACT，原X、键、FP及全部非泛化字段精确一致，原异常、图及来源保持；502份既有诊断DATA重新全SHA读取、2项边界测试和16个真实进程的原AST证明通过。该作业只验收技术诊断；后续1885179/180独立产出了3642条恢复记录及新候选池覆盖层，旧候选池和旧100万基线保留。此次复用了既有完整源SHA证据，没有重新声称读取93GB原片全SHA。

## 保留的范围与依赖

Main4525659传输时的STOPPED是历史快照，新鲜账本为FAILED1:0；失败在已写出的membership组件之后的graph quota检查。没有声称Main C0。Alpha的33份实际输入是16 membership、16 role和正式population索引，未重读旧坐标、32 geometry maps或16 UFF identity大体。

[732条具体范围提案已获用户明确批准](coconut732_actual_user_approval_20261104_v1.json)：只隔离729条提供结构未指定及3条官方抽象类/非分子条目，保留全部原文及逐条审计；恢复的3条具体分子和其余COCONUT继续完整去污染。实际1885181已闭合完整735条处置账本；1885184已完成三条恢复分子的严格组成排除影响统计。all11索引及全池过滤仍须完成，不以范围批准或单项影响统计代替。1000万固定队列、首批250万正式UFF/D尚未生成；max3、固定种子/顺序、不补足、不重试、追加构象保留已有坐标位的要求继续执行。

## 当前候选池和固定100万基线

[候选恢复1885179](generic_recovery_delta_1885179_root_actual_v1.json)实际C0/55秒/16CPU，3642条完整字段、原生比较及读回通过；[精确minCID覆盖层1885180](generic_overlay_1885180_root_actual_v1.json)实际C0/31秒/16CPU，形成3640个新增唯一完整键、2条内部重复别名，旧代表CID变更0。[当前池权威](corrected_pool_authority.json)明确版本alpha-original502-generic3642-recovery-v1：唯一分子109875599、别名110050006、内部重复174407；原始124857440条及原UNKNOWN审计全部保留。有效技术待核42559条，此处不声称全部原始记录均可恢复。

[同规则固定100万基线1885183](corrected_baseline1m_1885183_root_actual_v1.json)实际C0/74秒/16CPU，种子20261025和PubChem-baseline-uniform域保持；严格topK增量等价证明及全读回通过。新增31个成员并移出31个旧成员，代表CID变化0。[新基线清单](corrected_baseline1m_receipt_1885183.json)单独记录新池版本与旧基线历史，旧100万结果未重命名。当前新基线的11项数值、28类官能团和骨架统计由1885190在sonmi1/16CPU重算；原生1项副本隔离测试已通过，Common关闭结果在新副本中完整复用，尚未验收新统计终态。

[Common统计1885178](fullCommon_population_statistics_1885178_root_actual_v1.json)已完成，但其附带的100万部分对应历史基线。它不能充当更新31个成员后的当前基线统计，也不能代替最近邻分布对照。

## 732条批准的实际应用与全来源进度

[实际735处置账本1885181](coconut735_scope_1885181_root_actual_v1.json)为C0/21秒/16CPU，保留全部735条原始记录，732条仅作已批准的来源范围隔离；另外3条继续以严格元素组成覆盖，不将诊断观察的键升级为原始图修复。

[1885184实际组成影响与覆盖验收](coconut735_1885184_root_coverage_acceptance_v1.json)为C0/24秒/16CPU。对当前109875599个候选完整扫描后，三条组成分别排除177、325、6229个候选，共6731个。仅实施这735条对应规则后余109868868个；这不是全11来源过滤后的可用数量。未生成新化学图、未猜测新键，原UNKNOWN及逐条证据保留。

[全11来源清单1885186](all11_source_manifest_1885186_root_actual_v1.json)实际C0/15秒/16CPU，[机器清单](all11_source_manifest_1885186.json)已成形。原compose代码对象保持，原生依赖边界测试通过，原历史错误字面量只保留为审计、不当作当前数据引用。实际排除索引1885187在Alpha compute-0-1/16CPU运行；截至本次发布未闭合索引，也未完成全池过滤及回归SQL绑定，不能据此放行R/N队列。

## 完整Common TRAIN质量参考

[实际传运验收1885185](d27_transport_1885185_root_actual_v1.json)为C0/174秒/16CPU，11488个唯一物理文件共12475282830字节全部按原引用全SHA验证，11490条逻辑引用保留；不重新生成旧几何。完整Common TRAIN校准1885189在Alpha compute-0-1/16CPU运行，使用10973084条原生TRAIN记录，并按原规则排除20000条D5PM7保留记录；完成数量仍须实际终态核验。1885188在数据计算前被合成测试路径上下文误判拦下，失败保留；新不可变入口仅在合成测试期间隔离实际路径绑定，4项测试全通过后恢复正式数据绑定。原科学函数、筛选与掩码规则不变。

250万首批R/N、1000万固定队列、正式UFF/D以及完整最近邻对照尚未完成。本报告和GitHub源码同步不等于扩充全任务完成。
