# 模型 v3：组合回归、真实容量观察与下一步接线（v2）

三项候选已整合到同一独立运行树，并通过完整回归。最终模型、配方和真实数据验收仍未完成。旧v1报告保留其当时状态，本页追加后续实际证据。

## 已闭合的代码与实际验证

| 范围 | 实际作业 | 结果 |
| --- | --- | --- |
| Native bridge独立full | 4524142 | 2635通过、3可选跳过 |
| recipe独立full | 4524143 | 2638通过、3可选跳过 |
| performance独立full | 4524145 | 2639通过、3可选跳过 |
| bridge+recipe合并后full | 4524370 | 2684通过、3可选跳过，114模块 |
| 三项全部合并后full | 4524376 | 2734通过、3可选跳过，116模块 |
| manual R2实际GPU | 4523976 | 原20批前向/全参数梯度与500步轨迹门均通过 |
| R2真实记录CPU consumer | 4524211 | 原训练资源记录及305源解释通过 |
| Native S10000完整面板CPU准备 | 4524415 | 实际请求与原packing计划准备通过，未执行GPU评估 |

各full均零失败/错误，四XML、实际父C0、源前后/当前、进程和私有存储已由Root核验。测试有重叠，不相加为唯一测试数。三个skip仍是原CPU可选项，不授权CUDA/真实D3。

[组合分支](https://github.com/mint258/MFM/tree/model-v3-runtime-integration-20261027-v1)：
local81948e457c29fbc51687066a4f944ff5bcd5bad5；
public57d95b5c79fbd33e916330a455a7c3d4178c2284；
同一tree ebf5a63c7ac66b9d8b15a8f19a01b8aa2946e577。
发布后实际读回了分支与Git树。main未改。合并前的测试暂存竞态失败及原源均保留。

R2仅对应原paired双驻留/原Native-S工作负载，不是auto GPU、单驻留R1或ABBA速度资格。Root闭合后释放其独立2GiB逻辑hold，其余Native预留、principal和计数未改。

## 预注册与模型接口反馈

归档[Core64完整48案例方法](../pre_registered_methods/attention_core64_full48_v1/METHOD.md)与[Native完整开发面板方法v2](../pre_registered_methods/native_S_closed_panel_v2/METHOD.md)，对应源码逐字节保存。两者均没有在本报告宣称GPU结果；必须另经最终运行绑定和现场资源准入。

[D1 draft5模型反馈](../../interfaces/training_format_v3_draft5_model_feedback_DRAFT_v1.md)及其[原始来源](../../interfaces/training_format_v3_draft5_model_feedback_refs_DRAFT_v1.json)确认draft5已吸收先前意见。Root当前核验23份明确输入。unit/sign/origin/frame、新消费者及D3–D6仍分别待闭合，不能签为joint v3.0或真实新标签可训练。

## 剩余的实际工作

三项组合通过不等于真实proxy/full训练已消费A1/A5。新的隔离实现正将同一执行合同接到完整模型optimizer、TRAIN/probe/两验证人口、严格save/resume、CP→独立FP32 H0/random/cache/outbox/ACK，以及显式grid消费scope。旧Native继续原17f独立读取路径。新的6x512工程链将用两fresh CLI进程覆盖，不以1层链或分开不相交的测试代替。

FP32物理检查仍21通过/27未通过；Core64混合算术不能抵扣此门。S fallback仍安全保存17000步。真实D1–D7、三卡数值/速度与SDP、D5架构/头及配方矩阵、D6全量收敛与B*、真实120k/k2/1M端到端、冻结配置/tag/HANDOFF/最终PR仍待完成。正式预训练未启动。

机器证据见[本页证据表](pretraining_preparation_compact_evidence_20261027_v2.json)。全部失败作业计入实际账本；统计是明确时点的分配核时，GPU节点作业秒不是利用率或付费金额。
