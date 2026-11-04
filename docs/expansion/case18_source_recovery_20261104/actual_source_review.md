# PDBbind case18 的实际来源复核

Alpha 独立作业 **1885203 已 COMPLETED / 0:0**：sonmi1、16 CPU、37 秒，无 GPU。4 个原生测试通过；28 次完整同 FD SHA 读取共 1,067,297,161 字节（含重复的小元数据），Root 随后在同一节点复核全部 28 个文件 frame 一致。首次 1885202 因漏列原 `native_composition` 源码引用在读取化学数据之前退出，失败账本与产物保留；补齐引用后独立运行 1885203，原函数未修改。

## 来源结论

[Root 正式审查](molnet_case18_1885203_root_source_acceptance_v1.json)接受原 case18 的来源组成对应，依据是原始 PDBbind 1slg 的完整 SDF formula、SDF/MOL2 原子表、官方 1PTS/1SLG 的相同七残基标准肽实体声明，以及 1995 年原研究对同一线性肽复合物的重新测定关联。该研究的摘要可在 [1SLG 官方条目](https://www.rcsb.org/structure/1SLG)核对，PMID 7492542，DOI 10.1021/bi00047a005。

原始 1slg SDF 完整 formula 为 C36H51N11O12；两份原始原子表分别给出非 H 组成 C36N11O12。其两条既有 composition-only 身份行已在原 187 索引中，不需要新增推测图或键。官方 1SLG chainD 的 A/B 两个替代分别包含 59 个非 H 位点；共享位点各计一次，不能把 A/B 相加。原始 MOL2 残基首见顺序也确为 PHE/SER/HIS/PRO/GLN/ASN/THR。

Root 已明确审查终端化学对应：原研究的同一复合物关联、标准实体定义、原始完整 formula/原子表和 1SLG 实际 N/H1/H2/H3、OXT 记录共同支持元素组成来源对应。1PTS 自身仍只观测到三个 C-alpha，终端并未在该模型中直接观测。未给 1PTS 补原子、替换坐标或声称恢复其 graph/charge/stereo。1SLG 自由文本 FCHPQNT 与实体序列及实际 SER 的冲突原样保留；字典 no-nstd 标志、未列 modification 本身均不当作充分证明。

## 变更边界及下一步

这是单条有限分子记录的来源组成复核，不是新增隔离或扩大 COCONUT 732 条批准。全部 MolNet 来源记录仍保留，ClinTox case00 及其余 20 个旧 case 不变；原 1PTS UNKNOWN、旧 C3 下界、旧索引与审计全部保留。

**当前尚未生成或验收新的索引，也尚未运行新的完整过滤。** 后续独立生产者必须只在新副本中替换 case18 的旧 C3 约束为既有精确组成覆盖，证明 excluded 全 PK 集合、计数及摘要完全一致，所有其他约束不变，并诚实继承 187 的 577 项完整来源读取证据。通过新索引验收及全量重筛后才能报告新的可用候选数。旧筛选的 52,859 个结果仍作为该旧策略的真实结果保留。

100 万基准完整精确近邻作业 1885201 继续原样运行。1000 万 R/N 固定队列、首批 250 万分子的正式 UFF/D 和最终扩充报告尚未完成。

实际证据：[生产收据](case18_1885203_receipt.json)、[来源观测](case18_1885203_case18_source_observations.DATA.json)、[同 FD 读取记录](case18_1885203_actual_source_reads.json)、[原生测试](case18_1885203_source_tests.json)、[实际账本](molnet_case18_1885203_actual_accounting_v1.json)、[新 Root 来源政策](molnet_case18_source_correspondence_root_policy_v2.json)。新存储预算 [revision3](all_future_storage_budget_v3_20261104.json)仅核销已关闭产物的实际物理块，不改 scope caps、200GB 账户余量或活跃 1885201 的原计划。
