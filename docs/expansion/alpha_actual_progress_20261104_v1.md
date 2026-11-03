# Alpha 实际处理结果（2026-11-04）

计算已迁回 Alpha CPU，完整 Common 参考已验收。全来源去污染及250万分子批次仍在推进。

## 已完成子项

原始124,857,440条 PubChem 记录已有完整初筛产物；内部 min-CID/full-key 去重候选109,871,959个，仍为去污染前池。[固定100万基线统计](pubchem_baseline_statistics_actual_20261103_v1.md)已完成11个数值字段和28类官能团统计，完整Common已验收，分布统计及最近邻对照待完成。

[十来源字节验收](all10_replicas_1885168_root_actual_v1.json)：1885168实际C0/47秒/16CPU，511条逻辑引用共4,004,318,487字节全SHA通过，2项边界测试通过。[V3语义检查](all11_native_fixture4_1885170_root_actual_v1.json)：1885170实际C0/6秒/16CPU，4项合成测试通过；没有生成真实all11清单或索引。

## Common 完整扫描与119例异常

[1885153实际终态](common_1885153_actual_terminal_HOLD_v2.json)为C0，16CPU、18,275秒。完整扫描1196122个MID：TRAIN1188592、VAL7530；原生记录分别10973084、71884。33份输入全SHA、4份输出读回、16个真实工作进程、6+3项源/IO测试均齐全。原母体1214218、排除18096、UNKNOWN3436保留。

特征阶段119个TRAIN MID（352原生记录）进入HOLD，strict5只有1196003行，原SOURCE_GRAPH_HOLD_NOT_A_SUBSET_REFERENCE状态保留，未被验收为完整参考。

[元数据审计1885169](common_hold119_audit_1885169_root_actual_v1.json)实际C0/37秒：119例各只有一个Creator变体，全部FEATURE_COMPUTE_UNRESOLVED/AtomValenceException，无多图冲突；保留全部352条来源及事件定位。

[原生分步诊断1885171](common_hold119_native_1885171_root_actual_v1.json)实际C0/13秒，16真实进程、2项元数据测试、8项普通分子对照通过。119例原X筛选、原图解析、InChIKey和ECFP4均通过；其骨架含216个五配位磷。官方泛化将其换成碳后，末尾Chem.RemoveHs的默认价态检查报错。traceback定位原screen.features及[固定官方RDKit实现](https://github.com/rdkit/rdkit/blob/Release_2025_09_5/rdkit/Chem/Scaffolds/MurckoScaffold.py)，安装源码SHA、官方Git blob及转换AST均匹配。

[独立完整特征验证1885175](generic_repair_validation_1885175_root_actual_v1.json)实际C0/23秒/16CPU：119例全部24字段、字段集合及canonical值精确一致，352原生记录来源保留；8个普通分子的完整原kernel特征字节不变，2项元数据测试、16个实际进程的原AST逆变换证明通过。此前1885172和1885174失败记录保留；差异只涉及对照程序错误地混用逐片段路径，已按原兼容函数的全函数Kekulize回退修正对照证据路由，严格比较条件及生产修复库字节未变。修复仅处理临时泛化表示，旧kernel、安装库、原图、化学筛选、坐标、种子及历史HOLD均保留。[独立合并1885176](fullCommon_repaired_1885176_root_actual_v1.json)实际C0/208秒/16CPU，并已完成Root验收：[完整参考清单](fullCommon_repaired_manifest_1885176.json)为1196122行、当前HOLD为0。1196003条旧成功行的原始字节全部保留，仅加入119条；16份完整membership、2份旧成功数据全SHA读取，2份新完整输出全SHA读回与完整MID/role/native-record摘要32b1c446…8c9d96一致。Root在实际sonmi1核对当前FD元数据，保留Main历史STOPPED快照与当前FAILED账本，不声称Main C0。100万原基线与完整Common的统计对照作业1885178已在Alpha CPU启动，原基线不重算。

## PubChem 技术待核审计

[1885173实际审计](technical_unknown_audit_1885173_root_actual_v1.json)为C0/532秒/16CPU，完整502物理片、124857440行category计数一致，46201条技术UNKNOWN全部保留。42502条原PARSE_FAILED；3642条trace精确定位官方泛化RemoveHs的AtomValenceException，56条KekulizeException定位原MolToInchiKey，1条ValueError定位原wp5_key完整键校验。化学调用为0，没有改动候选池、minCID或基线；[逐条原生诊断1885177](generic3642_1885177_root_actual_v1.json)随后实际C0/38秒/16CPU：3642条全部达到REPAIRED_CANDIDATE_NON_GENERIC_EXACT，原X、键、FP及全部非泛化字段精确一致，原异常、图及来源保持；502份既有诊断DATA重新全SHA读取、2项边界测试和16个真实进程的原AST证明通过。当前只验收技术诊断，候选池、minCID和旧100万基线尚未修改。此次复用了既有完整源SHA证据，没有重新声称读取93GB原片全SHA。

## 保留的范围与依赖

Main4525659传输时的STOPPED是历史快照，新鲜账本为FAILED1:0；失败在已写出的membership组件之后的graph quota检查。没有声称Main C0。Alpha的33份实际输入是16 membership、16 role和正式population索引，未重读旧坐标、32 geometry maps或16 UFF identity大体。

COCONUT732条范围提案尚未应用，等待真实用户答复。1000万固定队列、首批250万正式UFF/D尚未生成；max3、固定种子/顺序、不补足、不重试、追加构象保留已有坐标位的要求继续执行。
