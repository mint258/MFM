# Attention AV 局部诊断与后续工作

2026-10-27。执行前预注册已在公开版本[99788277501ceff4a8adf37f7d9ee01498b9dbf1](https://github.com/mint258/MFM/commit/99788277501ceff4a8adf37f7d9ee01498b9dbf1)发布。4521641实际COMPLETED/0:0、75秒；[Root元数据闭合](ROOT_METADATA_CLOSURE.json)、[完整分析](ANALYSIS.md)和[全部标量汇总](SCALAR_SUMMARY.json)保留人口、分母及负结果。原始数据、SDK、科学journal、权重和截图未作为本报告附件。

## 诊断结果与边界

48组合×4次原H0捕获前向共192次逐位门全部通过；六层×四role×48组合共1152项原AV重放全部逐位相等。中心表达式仅在固定已存operands上计算，没有替换全网络执行，也没有获得新的物理等变性通过。

中心化C32相对Rnorm的聚合RMS误差约下降11.3%，但第0层192/192局部项的RMS均变差，相对Rraw的总体误差也更大。Rnorm是同一存储masked logits的高精度softmax参照；Rraw是同一存储p32/V32的高精度乘积参照。两者不混称准确率，也不按层筛选采用。全部定义、完整人口和不同参考下的变化见[分析](ANALYSIS.md)；原FP32物理门仍10PASS/38FAIL，1e-5未改。

统一六层FP32候选的源码与完整CPU证据现已冻结，并在独立实验分支[model-v3-attention-centering-20261027-v1](https://github.com/mint258/MFM/tree/model-v3-attention-centering-20261027-v1)发布，公开提交[f8417157dc23326d1beca8e19e4725755d9f13c6](https://github.com/mint258/MFM/commit/f8417157dc23326d1beca8e19e4725755d9f13c6)对应本地cf8ce66d97cd518ebf279b40ee20294919bb95e1、树2389ab046ee23f2ba92fcb61179d853dfdee8357。[源码冻结](CANDIDATE_SOURCE_FREEZE.json)、[公开读回](CANDIDATE_PUBLICATION.json)与[普通检查闭合](CHECKER_ROOT_CLOSURE.json)分别记录来源和实际1699 C0/4秒。此前1694因Root wrapper漏GitPATH失败，补PATH后的1699成功，原失败收据保留。

单CPU父4521707实际C0/132秒、16CPU/compute-0-13，四pytest完整采集2712项：2709PASS、3SKIP、0失败/错误。新候选73项及原numeric47项全部PASS/0skip；与1421相同的三项可选skip身份已独立核对。[Root闭合](CPU_ROOT_CLOSURE.json)、[原完整汇总](CPU_FULL_SUMMARY.json)及[监督记录](CPU_SUPERVISOR.json)保留114模块覆盖、实际JUnit合计、完整来源前后及进程清理；114是模块数，73是本次实际新测试数。

最终metadata绑定已由Root实际完成，execution request/pins与实际CPU、公有候选同树精确关联；[绑定结果](../../../../tools/model_v3/analysis_sources/attention_centered_e2e_v1/FINAL_BINDING_RESULT.json)保留无GPU/无提交状态。metadata-only启动audit已通过1213项runtime refs和15项自身源；[正式GPU协议](../../C4_centered_attention_e2e_prereg_20261027_v1.md)及运行器源快照待Root检查、公开读回后才唯一提交。完整GPU48矩阵尚未运行，当前没有新的物理验收、架构/dtype/训练采用。原[AV局部预注册](../../C4_attention_AV_centering_prereg_20261027_v1.md)仍对应已执行的1641诊断，不能用局部改善或CPU通过替代完整网络科学结果。

## S长段与日志归档

slot8/4521644现已实际C0，安全累计7000更新、2851328次基础记录消费；slot9/4521686已从7000续至8000更新区间运行。四成员各20k更新的计划中，第一个成员尚未完成，7000更新不表示B通过。slot7/8日志暂待与slot9批量独立SDK审计，未新增在线记录；现有S后备路线不能代替D5或B验收。

58条完整run已在线同步、读回并由Root闭合：固定50条、随后6条及slot5/6两条。原7条不完整SDK继续保留。七项集中本地归档4521639实际C0/11秒，已Root闭合、审阅并接入统一入口；新增slot5/6归档4521649实际C0/3秒、原4项导出QA通过，两段共2004条科学history，现亦已Root闭合并接入入口。[本地归档闭合](SLOTS005_006_ARCHIVE_ROOT_CLOSURE.json)和[入口追加证明](SLOTS005_006_ARCHIVE_ENTRY_APPEND.json)保留旧入口完整备份、原前缀及旧索引。两页默认训练曲线各1000点，history各1002条包含非训练事件；视觉审阅范围没有升级为全部字段交互或科学验收。远端项目根W&B_训练记录.html提供统一入口，旧offline快照的真假状态未重写。

## 时间点成本与剩余

[成本快照v17](ACTUAL_COST_SNAPSHOT_v17.json)捕获于2026-10-26 22:17:38 UTC，即北京时间2026-10-27 06:17:38：443个父任务、1076112 allocated CPU核秒、46983 GPU分配秒，捕获时活动任务1338/1644。1649等随后任务不在该快照内；这是点时累计，不是最终成本或GPU利用率。A01/4521338仍PENDING，最近节点20资源帧CPUTot/CPUAlloc为104/104，尚无独立ABBA结果。

v11 payload SHA的65字符抄录错误保留在原收据，并由机器摘要[补正](PUBLICATION_PAYLOAD_SHA_CORRECTION.json)另行记录；Git树、执行代码和执行前公开预注册没有因此变化。[排队归档1638失败](QUEUED_ARCHIVE_1638_FAILURE.md)及[挂载恢复](MOUNT_RECOVERY_ACTUAL.json)作为操作历史保留，不计为模型数值失败。

[归档工具快照](../../../../tools/model_v3/analysis_sources/native_long_archive_v1/README.md)和[Root闭合工具快照](../../../../tools/model_v3/analysis_sources/native_long_archive_metadata_v1/README.md)保留原始源码字节；实际执行仍使用远端runs/model_v3_20261026原目录。[完整CPU薄层快照](../../../../tools/model_v3/analysis_sources/attention_centering_CPU_v1/README.md)保留此次实际回归源与生成请求；快照本身不代替GPU验收或最终配方冻结。

数据线v7记录了实际处理进度，全部D1–D7与扩充交付仍在进行；这里记录最终交付状态。D3–D6最终交付仍缺，D1 draft.3未共同冻结。真实SDP与代理/架构/配方矩阵、种子噪声与B*验收、用户确认及最终recipe/tag/HANDOFF/PR均未闭合。没有main合并、最终冻结或学校正式预训练。

