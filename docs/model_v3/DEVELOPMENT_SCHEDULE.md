# 模型线 v3 开发日程

2026-11-11首次排程；以任务书v3为科学依据。当前准入计划覆盖0/5/6各一张3090；11月12日12:29实际在0/6训练、node5进行A0/P冻结评价。node0获准清理旧试点副本并重新准入，其他作业不动。GPU时为任务书估计，不是实际已花费。训练/评价优先于selection_use=false的只报告工作。表中条件未满足不提前选择或虚构运行。

| 步骤 | 前置条件 | 工作 / GPU时估计 | 预计完成日期 |
| --- | --- | --- | --- |
| 1 | 无 | 取消8个补种子/开发；提交规则与v2面板 / 0 | 2026-11-11 |
| 2 | 1 | R2/R3；6已有C1检查点+1匹配参考作业组；选C1 / 10 | 2026-11-11已完成：实际1.0156GPU时，C1-0 |
| 3 | 1；与2并行 | Lite核心及指定3项数学验收 / 0 | 2026-11-11已完成；训练接入继续 |
| 4 | 2、3 | 第0层；4组训练与评价全部C0 / 10 | 2026-11-11已闭合4组；T0-2已于11月12日完成0:0，8核/22分37秒；第0层全部闭合 |
| 5 | 2、3；与4并行 | 第1层10次1.5M配对续训（A0/S、A1/S、A0/P、A1/P训练C0；前三个完成评价为A0/S、A1/S、A1/P）及机制分析 / 60 | 2026-11-13暂估，取决于node5排队；机制报告待canonical输入 |
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

2026-11-12 11:59 CST：A2/S4530010在node0续训775072/150万，A3/S4529728在node6续训316224/150万，守护正常。A1/P评价4529749完成，原值已入M3_T1_RESULTS.md。A0/P首次评价启动安全门失败且原生工作为零；同配置4530187在node5等待16CPU，当前该节点48CPU由他人4530188占用，未干预。A4/S4529729及评价归档4530009仅改接恢复评价依赖，训练配方/输出不变。T0-2仍保持原16核排队，未应用8核提议。诊断162文件78623911字节已发布，T1前两组P训练SDK另完成7分段交付。

2026-11-12 12:22 CST：按任务书“其他情况一律记一行日志并继续”的执行调整权限，T0-2原作业4529737在核实本UID/PENDING/零运行后，仅将CPU请求16改8并令Torch线程跟随实际Slurm分配（上限/默认16）。node20现场96/104核已分配、8核空闲；保持原任务号、科学配置和输出，实际已RUNNING，8CPU/CPU-task8，离线SDK启动。旧16核等待记录保留，11月19日估时已由实际启动取代。参与选择的训练、评价和完整回归不因本项变更调整。node21现场两张卡均有其他计算进程，不启动额外实验、不干预他人。

2026-11-12 12:29 CST：node5恢复评价4530187已实际RUNNING/16CPU/5:19；node0/6分别A2/S874464与A3/S415328/150万，均OBSERVING。三张3090已全部承担原T1训练/评价；A4将按既有链自动继续。原十万边界新增2点，累计279。T0-2实际产出说明8核接线已经进入真实读出，无额外测试/复核。

2026-11-12：T0-2实际22:37完成0:0，四统计量S/P×R1/R2原summary已登记；第0层全部闭合。A0/P恢复评价4530187实际9:58完成0:0，T1现有四组评价入表，尚余六组。T0-2和前两组P评价SDK归档4530189/4530009分别10/13秒完成0:0；原SDK保留。结果登记辅助脚本连续两次Slurm入口失败，标未解决，按原路径直接登记producer，不再修补或重复计算。

2026-11-12 12:59 CST：三张3090实际训练A2/S968032（node0）、A3/S513888（node6）、A4/S83648（node5）/150万，守护OBSERVING。A4已自动接上既有依赖；第0层全部完成，T1四组评价完成、余六组。主比较暂估Nov13，保持完整十组后判定。
