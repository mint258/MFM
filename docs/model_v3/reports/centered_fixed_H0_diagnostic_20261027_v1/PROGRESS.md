# 当前centered固定H0诊断：实际结果与限制

2026-10-27。[执行前协议](../../C4_centered_fixed_H0_diagnostic_prereg_20261027_v1.md)已在[7b290606b776ba74d38a6976c0730360cc7a718e](https://github.com/mint258/MFM/commit/7b290606b776ba74d38a6976c0730360cc7a718e)公开后执行；[公开读回](PREREG_PUBLICATION_ACTUAL_v14.json)保留精确树。候选仍为独立cf8/f841、全六层centered+COMP，模型、参数、512维H0 API和1e-5/rtol0未改。C4仍21PASS/27FAIL、HOLD，无adoption。

## 测量闭合与物理门分别记录

| 实际作业 | 已完成范围 | 终态 |
| --- | --- | --- |
| GPU4521838 | 全48 fresh case、192 FP32 encoder前向、0 F64 encoder；1776全部2496个外部终端数组逐位相等，逐case物理passmatrix仍21/27 | C0/66秒/16CPU |
| CPU4521842 | 冻结1503函数数学，48case共432项观察；无encoder前向 | C0/32秒/16CPU，compute-0-17 |

[GPU Root闭合](GPU_ROOT_CLOSURE.json)、[捕获manifest](GPU_CAPTURE_MANIFEST.json)、[CPU Root闭合](CPU_ROOT_CLOSURE.json)、[原始结果](CPU_RESULT.json)、[完成标记](CPU_COMPLETE.json)和两份[GPU](GPU_SUPERVISOR.json)/[CPU](CPU_SUPERVISOR.json)监督记录保留成功终态、源前后相同及1290项当前raw source refs核验。C0说明捕获对照与诊断执行闭合，不表示物理门通过。新H0来自1838的同次前向，没有1776隐藏H0声明。捕获目录stat共88719308字节，其中NPZ stat为74718432字节；Root未独立读取NPZ/tensor，本报告不含NPZ/XML/SDK/权重。

## 固定H0下的精度分解

[V2完整分析](ANALYSIS.md)、[标量](SCALAR_SUMMARY.json)及[来源/分组补正链](ANALYSIS_SOURCE_REFS_v2.json)覆盖全48case/432项。每个P字段有144项，functional F64头的D仍有50项、30个case超1e-5，最大约3.08038e-5：

| 字段 | F64 D超门项 / 144 | F64 D最大绝对值（约） |
| --- | ---: | ---: |
| extensive | 2 | 1.10828e-5 |
| dipole | 28 | 3.08038e-5 |
| magnitude | 20 | 1.84588e-5 |

H亦有50项超门；G最大约2.55098e-7，I最大约3.38054e-11。在GPU原71项失败的各自argmax同一分量上，最大源项为H的有52项、head arithmetic delta的有19项；不是把不同分量的max相加。F64头使42项原GPU失败降到阈下，同时使21项原GPU阈下观察超门，29项两者均失败。由此失败观察数71→50、涉及case27→30，不能称高精度头解决C4。

CPU FP32实现也不是GPU舍入路径的oracle；其87项/37case超门与GPU/F64各有明确分母。实际CPU环境与旧1503未被宣称等价。旧1492/1503使用不同、未centered的H0，只能作描述性不同cohort对照，不是重复样本或架构选择。

当前结果支持继续分辨精度作用位置，不能据F64残差自动定位encoder/LayerNorm/GEMM。下一步仅是待Root审阅、尚未执行/公开预注册的历史1561参考H64接口量化CPU反事实：严格全48参数/case/source/实际pos-batch-transform谱系相等后，再比较参考H64、一次F32量化后接同functional64头、同量化H0接普通CPU F32 bank。它是不同数学参考，不替代当前1838 H0；一次量化失败不证明通用FP32下界，CPU F64/F32 bank对照也包含实现/backend差异，不据此改H0 API或提出新候选。

## 更正链与旁线进度

已公开1776 V2 scalar的单一old_new_case_patterns派生分组字段有误；原48paired case、MD15改善/4回退/6共同PASS/23共同FAIL及全部测量值均正确。[V3 corrected scalar](../attention_centered_e2e_20261027_v1/SCALAR_SUMMARY_CORRECTED_v3.json)和[机器更正记录](../attention_centered_e2e_20261027_v1/GROUPING_CORRECTION_v3.json)另存，公开V2原件未覆盖。当前1842分析只采用最终V2的真实11组；未公开V1保留在原路径，没有冒作科学重跑。分组更正是派生报告问题，未改变原始科学结果、源码或21/27。 [Root独立核对](ROOT_DERIVED_GROUP_VERIFICATION.json)从144份原始case JSON及闭合结果重算，确认15/23/6/4配对分组和全部11个cohort分组完全相同，1776其余scalar字段与公开V2规范化后相等；未运行新模型或QA。

S首成员1773实际C0/2507秒，安全累计9000更新/3665920次基础记录消费；[续跑核对](SLOT010_CONTINUATION_REVIEW.json)保留证据。1830在本次快照时正向10000更新运行，四成员各20k的首成员仍未完成，非D5或B验收。slot10 SDK待下一批次，online保持61而非62，原不完整记录继续保留。

[成本快照v19](ACTUAL_COST_SNAPSHOT_v19.json)固定于2026-10-27 00:47:12 UTC（北京时间08:47:12）：459父、1210864 allocated CPU核秒、55161 GPU作业分配秒，捕获时1338 PENDING/1830运行。后续活动时间不在本快照，不是最终成本、利用率或费用金额。最终数据交付与完整指南验收仍进行中，没有模型采用、最终recipe/B*/tag/HANDOFF/PR或main变更。

