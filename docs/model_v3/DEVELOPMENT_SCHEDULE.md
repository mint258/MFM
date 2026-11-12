# 模型线 v3 开发日程

2026-11-11首次排程；以任务书v3为科学依据。当前在0/5/6各使用一张3090；node0获准清理旧试点副本并重新准入，其他作业不动。GPU时为任务书估计，不是实际已花费。训练/评价优先于selection_use=false的只报告工作。表中条件未满足不提前选择或虚构运行。

| 步骤 | 前置条件 | 工作 / GPU时估计 | 预计完成日期 |
| --- | --- | --- | --- |
| 1 | 无 | 取消8个补种子/开发；提交规则与v2面板 / 0 | 2026-11-11 |
| 2 | 1 | R2/R3；6已有C1检查点+1匹配参考作业组；选C1 / 10 | 2026-11-11已完成：实际1.0156GPU时，C1-0 |
| 3 | 1；与2并行 | Lite核心及指定3项数学验收 / 0 | 2026-11-11已完成；训练接入继续 |
| 4 | 2、3 | 第0层；4组训练与评价全部C0 / 10 | 2026-11-11已闭合4组；T0-2因node20缺16核，调度器暂估2026-11-19运行（动态预估，11月12日06:39更新） |
| 5 | 2、3；与4并行 | 第1层10次1.5M配对续训（A0/S、A1/S续训已C0，评价后接P）及机制分析 / 60 | 2026-11-13 main comparison; mechanism report awaits canonical inputs |
| 6 | 5且A3采用 | λ=.3、k=16各S/P，共4次 / 24 | 2026-11-15（条件成立时） |
| 7 | 5–6且A3/A1采用 | 两次从头6M确认+6次只报告微调 / 42 | 2026-11-17（条件成立时） |
| 8 | 模块结论 | 两/三视图S/SDP，精确复用相同运行 / 50 | 2026-11-19 |
| 9 | 8 | H1/2/3及仅none时池化 / 115 | 2026-11-22 |
| 10 | 9 | M4五LR、前二B64、cosine/WSD、p99/SDP / 280 | 2026-11-28 |
| 11 | 10 | 全量S/P、64M调度分段、按新规则B* / 380 | 2026-12-06 |
| 12 | 11 | 两份FROZEN配置、代码标签、PREREG/HANDOFF / 0 | 2026-12-07 |

任务书总估计约970 GPU时。每个完成组当天更新分数和本表；比此计划迟超过1天，日报第二行写实际原因。每周一汇总实际GPU时；>1.5倍报告继续，>3倍停下询问。诊断/修复累计4小时或连续2次失败记未解决并按原路径/原架构继续。正式E2按研究主线至少3种子，D6的3/5种子取舍待用户届时决定，当前不启动。


2026-11-12 execution update: original closed P/C1-b independent validation4529709 is now published. Four closed SDK archives completed with1CPU each and were uploaded:21sessions,249files,40parts. T0-2 four-statistics16CPU work still waits on node20; its scheduling delay does not block the T1 main comparison or adoption decisions.

2026-11-12 02:02 CST: T1 A0/S and A1/S continuation training completed1.5M each in8:22:03 and8:23:05. Frozen evaluations were running, followed automatically by paired P continuations. The full10-case group and adoption comparisons remain pending; Nov14 estimate retained. Their two closed training SDKs are delivered in7 additional archive parts.

2026-11-12 04:36 CST queue estimate: T0-2 job4529737 remains PENDING Resources,16CPU/node20; scheduler UTC2026-11-18T19:59:59 (=Nov19 03:59 CST). This dynamic scheduling estimate replaces the previous Nov18 evening expectation. T1 decisions continue independently.

2026-11-12 08:03 CST：获准仅删除node0旧试点本地副本34.94GB，根盘恢复38.62GB。相同A2科学配置迁移到第三张3090，4530010→4530011→4530012→4530013；首组已真实更新272步。原四个零运行任务已取消，A4/S改接4529748。T1主比较暂估Nov13；T0-2排队估计保持动态。

