# 历史H64接口量化：1917实际结果

2026-10-27。纯CPU4521917在[执行前协议](../../C4_H0_interface_quantization_CPU_prereg_20261027_v1.md)公开后实际C0/11秒，16CPU、compute-0-15。[公开读回](PREREG_PUBLICATION_ACTUAL_v16.json)保留7dd1cfc09b6c85cd683ae30fb271a71cb00c3be3及精确树。[Root闭合](ROOT_CLOSURE.json)、[原结果](RESULT.json)、[COMPLETE](COMPLETE.json)和[supervisor](SUPERVISOR.json)确认48case、三个arm各192次head调用/432项观察、155项当前raw source核验和源前后相同。0 encoder前向、0 GPU工作；Root未读取NPZ/tensor。

## 全部有限cohort结果

A为历史1561 H64接functional64；B只将同H64一次量化FP32后无损提升再接同functional64；C将同一次量化FP32值接原FP32 CPU bank。历史H64不是当前1838全六层centered H0，也不是未保存的1776隐藏H0。

| arm | >1e-5观察 / 432 | 失败case / 48 | 最大绝对D |
| --- | ---: | ---: | ---: |
| A | 0 | 0 | 1.2230009710928469e-6 |
| B | 0 | 0 | 2.0317572508865567e-6 |
| C | 0 | 0 | 7.897615432739258e-6 |

[完整分析](ANALYSIS.md)、[标量汇总](SCALAR_SUMMARY.json)及[来源refs](ANALYSIS_SOURCE_REFS_v1.json)保留三个字段与全部11个分组，未选择层、head policy或seed。A全部432×3=1296个已存标量控制通过，最大误差9.2370555648813024e-14，小于原1e-10诊断界；不是完整终端bitwise重放。物理报告仍absolute1e-5/rtol0，三个P字段的CPU对照不替代原13字段CUDA test及其完整finite/nonzero/domain条件。

B−A最大1.4151571376963545e-6，C−B最大8.18786855044662e-6；1296个argmax与同分量tuple检查全部相符，不相加不同位置的max。全部192次role量化非零，最大H64→F32差约1.19206e-7。C/extensive有16个exact maximum ties，其中10项D全零，按first flat index保留；零残差不说明模型输出全零，本次未导出terminal norm，不能新增nonzero或norm-floor证明。

实际唯一输入125739933B低于固定134217728B，余8477795B。原tiny controls通过，CPU环境在结果中记录；未声称CPU/CUDA舍入等价。原metrics.csv继续留实际输出，本Git快照不复制该逐case CSV；全部case refs及数值由原结果与标量保留。

## 决策与边界

这组固定历史值的最终512维F32接口量化没有阻挡三字段阈值，原CPU F32 bank在同受控表示上也满足阈值。这是有限cohort证据，不是普遍FP32下界、一般head结论、当前CUDA接受或API变更依据；B/C同时包含implementation、dtype、CPU backend差异。当前1838 H0在1842 F64头下仍50项/30case超门；1776/1838仍21PASS/27FAIL、C4 HOLD，无adoption、无生产改变。

下一步仅在准备当前encoder的局部module研究：native F32同输入重放先逐位相等，再以相同输入做独立F64 real-formula参考，保留同一分量原drift/reference drift/local arithmetic delta。旧F64参考算法与当前centered算法不同，须明示precision+algorithm contrast，不能冒作instruction-identical dtype substitution或跨module量纲排名来定位整模原因。新研究尚未执行、尚未公开预注册；不向model注入输出，不选新算子、层、seed或候选。

## 训练与成本的固定时间快照

[slot011续跑核对](SLOT011_CONTINUATION_REVIEW.json)记录1830实际C0/2497秒，首成员安全10000更新/4076032基础记录消费；1906在v20捕获时续向11000。四成员各20k首成员仍未完成，slot10/11 SDK待下一3段批次，online61，非D5或B验收。

[v20账本](ACTUAL_COST_SNAPSHOT_v20.json)固定2026-10-27 01:56:54.187994 UTC（北京时间09:56:54）：463父、1274464 allocated CPU核秒、59116 GPU作业分配秒，捕获时1338 PENDING/1906运行；不是最终成本、利用率或金额。全部剩余指南工作仍在范围内，最终D交付、B*、最终recipe/tag/HANDOFF/PR未完成；本诊断不缩减原验收要求。
