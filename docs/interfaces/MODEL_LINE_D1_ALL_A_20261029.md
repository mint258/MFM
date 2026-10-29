# 模型线已收到 D1 五项全部 A 的用户决定

2026-10-29（Asia/Shanghai），用户在本模型线对已列明五项政策的提问中明确回答：“全部采用推荐项 A”。

决定原文来自数据线 `runs/data_v1_20261025/repository/docs/interfaces/D1_user_decisions_20261029_v1.md`。本文件记录真实用户选择；consumer 实现、逐 target 物理映射、joint v3.0 ACK 与真实数据验收继续分别执行。

- 1A：r73 原 F64 sidecar 为权威，训练 wire 恰一次转 F32；双端 atom/channel 独立，保留 onsite、方向、重复、retained-list ordinal，ordinal 不作学习特征。
- 2A：r674 仅完整六项有效且绑定同一 actual geometry 才进 tensor loss；原 partial 值、component masks/reasons 及审计分母保留，不补零。
- 3A：Q/s，不减中心；s 为实际 TRAIN Frobenius 序列 0.1%/99.9% winsorized std_ddof0，逐登记 target/condition 拟合。使用实际 D4 population/series/value/rawref，退化或未发布尺度不启 loss。
- 4A：Frobenius 径向 Huber，d=9、delta=1，一个 tensor 计一个 target，权重1。六项权重为 (1,2,1,2,2,1)，不能用逐分量 Huber 替代。
- 5A：接受注明假设的源程序 frame provenance 作为本版物理审阅依据；192 项无独立坐标观测仍记 UNKNOWN。假设可信 FS/时钟、同目录路径未被替换/恢复、无特权时间戳操纵；unit/sign/atom-order/input-hash 问题仍须审阅。

原模型651a关于 median(Frobenius)/sqrt(6) 和 d6 的候选保留为历史，由本次用户决定取代。政策授权、数据发布、实际consumer通过和双方ACK是分别记录的状态。

[机读政策](MODEL_LINE_D1_ALL_A_20261029.json)。数据线仓库继续只读，模型线将此确认公开到 model-v3 的共享接口文档。
