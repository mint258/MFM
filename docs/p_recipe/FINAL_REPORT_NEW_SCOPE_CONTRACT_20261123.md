# 11-22B/22C 最终报告输入与 I1 后续衔接

## 2026-11-25执行状态与覆盖规则

本页下文的11-23接口设计保留；当前状态以[11-25日报](daily/2026-11-25.md)和闭合主统计为准。I1判定、12项full及组成补充已完成，F.csv现有116行；冻结配方仍为A1+B3+B4+F2，I1采纳留用户。E1三个新候选及39项下游GPU已完成，8项原CPU统计/判定仍排队。

[用户11-25补充指示](USER_DIRECTIVE_20261125.md)撤销A5的工程失败UNRESOLVED，CPU4540060已提交，原目录匹配/失败输出/成本保留；尚无共同UFF主结果。最终报告消费者已拒绝旧工程失败豁免。后续表格并列ExpansionRx三项及三任务均值的原几何/共同UFF T2−T4 Δ和95%CI，只消费原闭合主统计。

最终REPORT、最终权重SHA及PR7合并仍须E1、A5和D第5节A4全部闭合。全部27项范围保持；不以旧A5跳过记录提前结项。

状态：2026-11-23，原注册范围未完成，最终 REPORT 尚未生成。此文记录现有执行入口，不增加科学任务、种子、bootstrap 或训练预算。

## 已闭合输入

原任务的 22 个预算读出和五个原 9M 端点、486 行逐任务表、原 26 项确认比较已闭合。F 第一批 120 次、第二批原 60 次及原配对主统计已完成，F.csv 共 108 行。A1、A2 初始四来源、A3、H-comp 八断点和 A6 已完成。原子级只报告 EEV；mean(H) 保留原 CEV、CEV_size、CVF、CVF_res、PR 定义，H-comp/H-B4 只由 mean(H) CEV 判定。

A5 的11-23旧跳过决定已由11-25补充指示撤销，当前恢复补做；原输出、失败与成本保留。完整键目录匹配不等于 UFF 可用人群或原子映射验证。I2 的触发比为 1.1136516854，小于 2，不运行 I2。

## I1 源与判定

I1 正在完成自身预算 3M，只有关闭 B4 这一项配方变化。基线必须为原 round4_F2 的自身预算 3M；9M 运行的中间 3M 不可代替。B32、FP32/TF32 关闭、无梯度累积/逐层重算、原 11-07 全 TRAIN 归一化不变；每臂自己的原始 clip_calibration.json 只读取和报告，不重算、不调整。

I1_decision_draft.json 当前 ready=false。真实完整 3M 断点、原 R1/R3 与 CPU 主统计完成后，绑定真实配置并启用 i1_decision_entry.py。GPU 入口只执行原 H0/R3；缓存 H0 后，原 R1 和全部 bootstrap 在 CPU 节点完成。

判定直接调用原 p_recipe_seed_policy.combined_seed_decision，复用已配对的 1,000 个分子 bootstrap 值，不生成新 draw。只有 R3 seed0 WIN 触发注册的条件 seed1；R1 不触发。seed0 比较保存后条件确认直接复用。两种子确认 WIN 建议 DROP；TIE 且 CI 跨 0 建议 DROP；TIE 且 CI 整体负或 LOSS 建议 RETAIN。11-19 第 2 节规定平局时只有 CI 跨 0 才采纳删项，11-22B 保留现行判定规则。因此 CI 整体正但幅度未达到 WIN 的 TIE，也按该限制保留 B4。配方是否采纳留用户决定，不自行修改冻结配方。

公开的 I1_decision.json 由闭合的私有 I1_decision/primary.json 转录，包含候选/基线实际自身训练预算、原判定、条件种子闭合、建议、来源身份和原始裁剪报告。WAITING 状态不能写成 COMPLETE。

## I1 微调与组成

I1_F_drafts 下 12 份配置仅在实际完整 3M 源闭合并重新登记资源后启用：四任务 × 微调种子 0、1、2，原 full 协议不变。不另外新增基线预训练或未注册的基线 12 次 full。原冻结 R3 与已经闭合的共同 scratch/E_ref 复用。

公开 I1_F_primary.json 的 status=COMPLETE、source_training_budget=3000000；rows 含四个 full_I1_3M（三种子）和四个 frozen_I1_3M（原读出种子 0），同时追加 F.csv。均值、标准差与三种子平均预测的 CI 保持原 F 定义。

F2_3M 的组成前向已完成并保留物理数组，I1 完成后只新增 I1 的原固定 5000 VAL/L6/H0 前向。合并 summary 仅引用两份原数组，不复制或重复推断基线。composition_I1_mean_entry.py 与 composition_I1_descriptive_entry.py 复用原公式和原 1,000 次配对权重；草稿仍 ready=false。

公开 I1_composition_primary.json 的 status=COMPLETE、atomic_metrics=["EEV"]，含 F2_3M、I1_3M 各自 mean(H)/atomic(H) 四行，以及 mean(H) CEV 原配对对比。mean 行为原五指标，atomic 行仅 EEV，其他指标只作描述。后续结果同时补入 A2.csv。

## A4 外部交付

只消费 D 线第 5 节已闭合结果，不在 P 线重拟合直接描述符或组成对照。公开 A4_descriptor_upper_controls.json 的 status=COMPLETE、source_delivery 非空、rows 非空、new_computation_performed=false；逐任务并列 T2 R3、直接描述符、组成参照及 R3 落后标记。原面板覆盖或协议不可比处按交付明确标记，不能补造数字。

## 最终生成条件

final_report_22B.require_closed 在旧报告入口读取权重或计算 SHA 前执行。除已闭合输入，还须具备 I1_decision.json、I1_F_primary.json、I1_composition_primary.json 与 A4_descriptor_upper_controls.json。条件 seed1 未完成、9M 中间点冒充 3M、原子指标误名或 F 行未导出均不通过。

11-25共享时间盒规则覆盖旧条款：工程失败修复续接，不计次数且不能标UNRESOLVED。只计同一根因的科学/方法失败：修复两次后仍失败，或诊断修复本身累计4小时，才按保守默认处理；排队和正常计算不计时。旧工程失败豁免不能满足最终报告关卡。

全部输入真正闭合后才生成一次最终 REPORT，加“微调与冻结读出”“读出噪声与 B4 机制”“P 与 P′ 的几何对照”三节。渲染仅消费闭合主统计，不重做拟合、读出、bootstrap 或归一化。当前预检只验证入口与缺项，不生成 REPORT，也不计算最终权重 SHA。
