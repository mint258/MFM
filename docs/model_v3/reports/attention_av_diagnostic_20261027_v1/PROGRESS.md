# Attention AV 局部诊断与后续工作

2026-10-27。执行前预注册已在公开版本[99788277501ceff4a8adf37f7d9ee01498b9dbf1](https://github.com/mint258/MFM/commit/99788277501ceff4a8adf37f7d9ee01498b9dbf1)发布。4521641实际COMPLETED/0:0、75秒；[Root元数据闭合](ROOT_METADATA_CLOSURE.json)、[完整分析](ANALYSIS.md)和[全部标量汇总](SCALAR_SUMMARY.json)保留人口、分母及负结果。原始数据、SDK、科学journal、权重和截图未作为本报告附件。

## 诊断结果与边界

48组合×4次原H0捕获前向共192次逐位门全部通过；六层×四role×48组合共1152项原AV重放全部逐位相等。中心表达式仅在固定已存operands上计算，没有替换全网络执行，也没有获得新的物理等变性通过。

中心化C32相对Rnorm的聚合RMS误差约下降11.3%，但第0层192/192局部项的RMS均变差，相对Rraw的总体误差也更大。Rnorm是同一存储masked logits的高精度softmax参照；Rraw是同一存储p32/V32的高精度乘积参照。两者不混称准确率，也不按层筛选采用。全部定义、完整人口和不同参考下的变化见[分析](ANALYSIS.md)；原FP32物理门仍10PASS/38FAIL，1e-5未改。

统一六层FP32候选的源码与完整CPU证据现已冻结，并在独立实验分支[model-v3-attention-centering-20261027-v1](https://github.com/mint258/MFM/tree/model-v3-attention-centering-20261027-v1)发布，公开提交[f8417157dc23326d1beca8e19e4725755d9f13c6](https://github.com/mint258/MFM/commit/f8417157dc23326d1beca8e19e4725755d9f13c6)对应本地cf8ce66d97cd518ebf279b40ee20294919bb95e1、树2389ab046ee23f2ba92fcb61179d853dfdee8357。[源码冻结](CANDIDATE_SOURCE_FREEZE.json)、[公开读回](CANDIDATE_PUBLICATION.json)与[普通检查闭合](CHECKER_ROOT_CLOSURE.json)分别记录来源和实际1699 C0/4秒。此前1694因Root wrapper漏GitPATH失败，补PATH后的1699成功，原失败收据保留。

单CPU父4521707实际C0/132秒、16CPU/compute-0-13，四pytest完整采集2712项：2709PASS、3SKIP、0失败/错误。新候选73项及原numeric47项全部PASS/0skip；与1421相同的三项可选skip身份已独立核对。[Root闭合](CPU_ROOT_CLOSURE.json)、[原完整汇总](CPU_FULL_SUMMARY.json)及[监督记录](CPU_SUPERVISOR.json)保留114模块覆盖、实际JUnit合计、完整来源前后及进程清理；114是模块数，73是本次实际新测试数。

完整GPU协议及运行器已在执行前公开为[63ae209b27acabaadafa15cf4ebd8f64f8a98e06](https://github.com/mint258/MFM/commit/63ae209b27acabaadafa15cf4ebd8f64f8a98e06)。4521776现实际FAILED、退出1/42秒；完整48项为21PASS、27FAIL，0error/skip。原1e-5/rtol0不变，C4仍HOLD，不采用候选。tiny CUDA控制通过，来源前后相同；记录192次encoder前向形状、1872项字段观察，其中71项超门，48个domain控制全部通过，F64 encoder报告数为0。[Root元数据闭合](../attention_centered_e2e_20261027_v1/ROOT_METADATA_CLOSURE.json)核对1227项当前源ref；NPZ仅stat，不宣称Root独立重读数组内容。

[V2完整分析](../attention_centered_e2e_20261027_v1/ANALYSIS.md)及[标量汇总](../attention_centered_e2e_20261027_v1/SCALAR_SUMMARY.json)配对原1435全部48 case：15个旧FAIL转PASS，4个旧PASS退化，6个两次均PASS、23个两次均FAIL，整体并非单调改善。四个退化case全部保留：

| case | 本次失败字段 |
| --- | --- |
| C1-a / three / H2_fixed / seed20261026 | dipole、extensive |
| C1-b / two / H1_learned / seed20261026 | magnitude |
| C1-b / three / H3_fixed / seed20261026 | dipole、magnitude |
| C1-b / three / H3_fixed / seed20261027 | dipole |

71项字段失败分为extensive10、dipole36、magnitude25；每字段原分母144项，全部失败argmax指向row2的32-atom图。全部48配对的参数、fixture/view/registry身份相同，但全局H0误差max两次均为1.9073486328125e-6；这些最大值与32-atom模式不能定位机制，也不能当作下游敏感度比值。不能选择层、seed或head采用。

唯一下一测量是当前centered候选的全48 fresh same-forward固定H0捕获与CPU函数头分解，方案准备中，尚未执行或预注册。1776没有保存内部bankH0，旧1492/1503不能代替当前内部H0。即使同一H0下F64头仍有残差，也只表明head-arithmetic-only精度提高不足；须先看同一失败分量H/G/I，再选择表征、几何或相互作用干预。当前没有定位LayerNorm/GEMM或确定新候选。[V2来源与措辞补正](../attention_centered_e2e_20261027_v1/ANALYSIS_SOURCE_REFS_v2.json)保留V1原件及数值未变证明。

[最终公开证明](../attention_centered_e2e_20261027_v1/PREREG_PUBLICATION_ACTUAL_FINAL.json)补正了初始PS5路径处理产生的null refs，原[部分收据](../attention_centered_e2e_20261027_v1/SUPERSEDED_PARTIAL_PUBLICATION_RECEIPT.json)保留；实际公开提交/树未变化。原[AV局部预注册](../../C4_attention_AV_centering_prereg_20261027_v1.md)仍对应1641诊断，其局部改善和CPU通过不能替代本次完整网络门。

## S长段与日志归档

S首成员已安全闭合8000更新、3258368次基础记录消费，4521773在本次快照时正续8000→9000更新，首个20k成员尚未完成，8000不表示B通过。slot7/8/9批量SDK审计4521777实际C0/15秒、28QA，3006条history全部typed匹配；同步4521778实际C0/32秒，三条新增日志已由Root在线闭合。现有S后备路线不能代替D5或B验收。

61条完整run日志已在线同步、读回并由Root闭合：固定50条、随后6条、slot5/6两条及slot7/8/9三条。原7条不完整SDK继续保留。七项集中本地归档4521639实际C0/11秒，已Root闭合、审阅并接入统一入口；新增slot5/6归档4521649实际C0/3秒、原4项导出QA通过，两段共2004条科学history，现亦已Root闭合并接入入口。[本地归档闭合](SLOTS005_006_ARCHIVE_ROOT_CLOSURE.json)和[入口追加证明](SLOTS005_006_ARCHIVE_ENTRY_APPEND.json)保留旧入口完整备份、原前缀及旧索引。两页默认训练曲线各1000点，history各1002条包含非训练事件；视觉审阅范围没有升级为全部字段交互或科学验收。远端项目根W&B_训练记录.html提供统一入口，旧offline快照的真假状态未重写。

新增slot7/8/9本地归档4521780实际C0/3秒，3006条history、原4项导出QA通过；三页已由Root实际Chrome检查，各1000训练点与1002完整history的分母分别保留。[在线闭合](../attention_centered_e2e_20261027_v1/SLOTS007_009_SYNC_ROOT_CLOSURE.json)、[在线入口追加](../attention_centered_e2e_20261027_v1/SLOTS007_009_ONLINE_ENTRY.json)、[本地闭合](../attention_centered_e2e_20261027_v1/SLOTS007_009_ARCHIVE_ROOT_CLOSURE.json)及[本地入口追加](../attention_centered_e2e_20261027_v1/SLOTS007_009_ARCHIVE_ENTRY_APPEND.json)保留旧索引、完整旧前缀/inode与单marker；线上/本地状态分别核证。

## 时间点成本与剩余

[成本快照v18](../attention_centered_e2e_20261027_v1/ACTUAL_COST_SNAPSHOT_v18.json)捕获于2026-10-27 00:06:41 UTC，即北京时间08:06:41：454个父任务、1171344 allocated CPU核秒（325.3733小时）、52741 GPU作业分配秒（14.65028小时），捕获时1338仍PENDING、1773运行中。捕获后的任务与活动任务后续时间不在本快照内；它不是最终成本、利用率或费用金额。旧v17快照原件保留，A01尚无独立ABBA结果。

v11 payload SHA的65字符抄录错误保留在原收据，并由机器摘要[补正](PUBLICATION_PAYLOAD_SHA_CORRECTION.json)另行记录；Git树、执行代码和执行前公开预注册没有因此变化。[排队归档1638失败](QUEUED_ARCHIVE_1638_FAILURE.md)及[挂载恢复](MOUNT_RECOVERY_ACTUAL.json)作为操作历史保留，不计为模型数值失败。

[归档工具快照](../../../../tools/model_v3/analysis_sources/native_long_archive_v1/README.md)和[Root闭合工具快照](../../../../tools/model_v3/analysis_sources/native_long_archive_metadata_v1/README.md)保留原始源码字节；实际执行仍使用远端runs/model_v3_20261026原目录。[完整CPU薄层快照](../../../../tools/model_v3/analysis_sources/attention_centering_CPU_v1/README.md)保留此次实际回归源与生成请求；快照本身不代替GPU验收或最终配方冻结。

数据线持续有实际处理进度，最终D1–D7与扩充交付仍在进行；这里记录最终交付状态。D3–D6最终交付仍缺，D1 draft.3未共同冻结。真实SDP与代理/架构/配方矩阵、种子噪声与B*验收、用户确认及最终recipe/tag/HANDOFF/PR均未闭合。没有main合并、最终冻结或学校正式预训练。

