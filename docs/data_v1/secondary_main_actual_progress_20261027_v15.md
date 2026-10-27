# 数据线实际进度 v15（2026-10-27）

## 目的与当前边界

继续完成指南第一部分D1–D7，并独立获取扩充数据。该报告是实际执行快照；不是最终v1、共同人群、P′或扩充候选池的交付验收。原始数据与历史失败保持，未开最终PR。

## 输入、规则与可追溯清单

原指南仍适用；用户授权的Se排除例外、ROUTINE整分子VAL、免费集群、CPU11–13、无SBATCH内存申请以及核时超标报告后继续均保留，全部质量门槛不变。Main与Alpha分别按endpoint/UID1278、1264绑定，不混用同名节点或job ID。

源代码执行版v21为`5b9a00a341b920cc09fc421d46d399b21c7fa9fb`，公开data-v1提交`425bd73f4ae202b4fad8685f91e0453c0b335139`，相同Git tree `86faf1b140aabae3cbffb68cb2565e349788d60c`。这是检查后的66件源码/文档，不是科学放行。Source27的3340文件、35510011字节源归档SHA256为`a4fc52253a156da2711b014231dc1ac6032193dbc38ce4ffbc91b2495768cbfa`；完整逐文件来源及SHA在外部`control/source_snapshot_alpha27_v1/`。

跨集群实际小回执的原路径、复制路径及逐件SHA见`control/alpha40_source27_qm7bformat_small_metadata_transfer_verified_v1.json`；原数据、二进制源归档之外的科学DATA没有为此传回或在登录节点解析。

## 实际结果

| 项目 | 已观察事实 | 仍需完成 |
| --- | --- | --- |
| P′独立精度15次 | 4523473，CPU13/16CPU，C0/45s/720核秒；恰好15调用，25向量比较和5同几何伴随检查全通过原容差，无重试 | 科学原因仍UNKNOWN，下一NEW20唯一分子×全12项QA需具体提案/新授权；2000及full HOLD |
| S′94–96闭合 | 原94批47000包保留；95晚收尾4522547 C0/33s，96新运行4523537 C0/1423s，独立close4523598 C0/32s；95、96各500有效包/500 consumed，无未决、未启动或错误 | 剩余97–179，实际新有限CPU13资源epoch；不得自动续期或重算原96 |
| 资源源码门 | Main4523531 C0/31s，原recovery3+epoch3通过；实际原Budget CPU13探针4523533 C0/31s | 不替代完整科学质量门 |
| 原生字段位置 | 旧3474被原catalog符号链接校验拒绝；显式同内容literal target视图后，3532 C0/44s；3538 C0/33s，384/384键、缺失0/错误0，160次SQLite打开与关闭相等 | 未读取科学BLOB，尚未证明basis/张量/单位/符号/轴；新两stage原生证据读取待实际CPU |
| 标签超时恢复 | 1904原TIMEOUT与全部成本保留；新CPU13 inventory/book bridge及Common runtime接口的9测试，4523589 C0/61s，全PASS | 独立readonly inventory实际完备性→新book/adoption→全数值覆盖→最终mask；不把旧1904/2748冒C0 |
| TRAIN缓存首轮 | 4523548，CPU18/16CPU，C0/164s，4251记录/512分子首轮通过 | 后续median/MAD轮与完整TRAIN、最终Common、独立P′D4仍未完成 |
| Drugs原生图试点 | 4523547，CPU13/16CPU，C0/254s；1000原生图成功、unknown0、来源键差异0、比较未知0；全633101物理行上下文已闭合，75099原名称、290多SMILES组保留 | 558002个SDF中仍557002未做本轮原生图检查；不以试点或名称union充全量图验收 |
| QM7b补充来源 | 官方2013 ZIP已实际获取；Alpha1884926 C0/43s/16CPU，4个成员全EOF/CRC/SHA，3个文本和1个XYZ | 未接受图或MAT行映射；不能从名字、次序或7211数量推对应 |
| PubChem | Alpha40所存点10:36:49 UTC：106分片/26500000原始行闭合；24617000 accepted、1880812规则拒绝、2188技术未决，合计守恒；6片仍跑 | 完整500片、全来源去污染、1M精确NN、ordered10M与首2.5M UFF+D未放行 |
| 源代码检查 | Alpha1884927 C0/320s/16CPU；原checker PASS、1311冻结服务端源匹配、27指定原测试+3资源测试通过，所有源SHA前后相等 | Alpha不代替Main物理engine/D1/native/QC；新的Main-dependent测试在Main实际跑 |

P′详细结果、输入协议SHA和残差见[pprime_strict15_precision_diagnostic_20261027_v1.md](pprime_strict15_precision_diagnostic_20261027_v1.md)。本次P90是坐标轴变换，原子顺序没有打乱；不是原子重排测试。

## 异常、资源与费用

Main节点12、13、18出现空闲时，Root只将已确认PENDING/零运行且无proof的本任务移到新名、新请求；保留旧取消回执与实际0核秒。运行任务和其他用户/模型任务未被终止。新sbatch没有内存、exclusive或GPU申请。

标签inventory的第一个额外64GiB保守预留草案没有提交；现场账户剩余不足该保守合计时，改为有明确范围的旧其他任务上界+新增32GiB、另加本任务2GiB和200GB，独立Root审核。科学输入、数量、算法和质量均未改变。另有模板父引用插入序与canonical JSON排序不同，Root独立审查同一组精确引用后按实际plan顺序重排，未改旧回执或绕开父链。

Main checkpoint42为505个去重实际父作业、观察分配核时461.066667；Alpha checkpoint40为161父作业、1179.173333核时。两者均是各自时点的部分累计，包含失败/超时/启动以及仍运行作业的已观察成本，不是最终成本；不能相加历史checkpoint。当前免费意味着不产生本轮金钱费用，不意味着CPU核时为零。

## 已知限制与下一步

D1当前权威仍draft3，draft4待模型线共同审阅；r73双端native basis/同原子多条目、r674原六分量、单位/符号/轴尚需真实原生证据。新native32分别保留四个历史复现包的288/60/12/24键身份，其五份科学源码逐包字节一致；不能用新包覆盖历史来源。

N1新domain接口与typed-cache候选已实际通过相应源测试，完整Common冻结、N1额外几何全量、D2异常与相关性、D4精确重算、D5诊断anti-join、D3/D6真实加载与全量导出仍待完成。Common结构特征的新Main runtime已有完整入口，但必须等真正最终父人口和Root图审查，不能把接口检查当真实指纹或NN产物。

下一步恢复有限S′队列、完成旧标签只读inventory及新book、运行原生证据两stage，同时继续PubChem和外部源覆盖。P′后续QA的选择单位必须是20个唯一MID，不能把原2000构象的1%审计20条记录冒作20个分子；尚无现成已执行QA20来源清单，需明确新提案后再批准精度协议调用。