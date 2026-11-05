# 模型 v3 实际进度 v25（2026-10-28）

本稿延续 reporting 树的 [v24报告](PRETRAINING_PREPARATION_20261028_v4.md) 及其精确来源，完整保留阶段0–7目标。新增事实是 A00 manual R1 四条 ABBA 校准及日志闭合、新几何候选独立 CPU 全套通过并公开，以及全 TRAIN 计数审计。**R1 本次无提速；head-off 固定20批已过、500步仍运行；新几何GPU48为15通过/33失败，C4 仍未通过。** 最终数据、真实架构/配方矩阵、用户确认与交接仍未完成。

本文已由 Root 审阅并核对本次实际回执。原作者草稿保留在 runs/model_v3_20261026/reporting_progress_v24_DRAFT_v1。作者仅阅读源码和指定小型 JSON/文档并作元数据 rawhash/stat；未读取 SDK、steps科学JSONL、NPZ、权重、目标或模型数组，未运行项目、Python/AST、测试、SSH、Git、API或Slurm，未修改既有v23或冻结源。新事实的path/bytes/SHA和范围见同目录 pretraining_preparation_compact_evidence_20261028_v4.json。

## A00 manual R1：完整 ABBA 校准，无提速

固定 series 为 A00_manual_R1_C35_9e16_v1，顺序 reference→candidate→candidate→reference；四父4524567/68/69/70均实际C0，使用同一C35、同一Native S数据与seed0、6层512及原方法。原a_speed_report由CPU4524571实际执行，原3976完整20+500数值门独立绑定，方法未改：

| 原报告指标 | reference pooled | candidate pooled |
| --- | ---: | ---: |
| base records/s | 151.9820945 | 150.9546401 |

candidate/reference为 **0.9932396351**，本次没有观察到提速；不声称统计显著性或其他配置的速度最优。

这里三处checkpoint实际仍均为True。reference配置的 effective_options.backbone_checkpointing=null 保留模型原有 activation_checkpointing=True；candidate解析为True，distance/head也保持True。因此这是 **A00校准**，不能作为A1关闭checkpoint、真正headOff或all-off的等价/显存/速度验收，亦不能跨seed/UUID/workload借容量资格。真正headOff已在4524580实际运行，固定20批前向/全梯度通过，500步尚待真实终态。

| 位置 / role | 实际GPU父 | 原W&B run | 原配置（PROJECT下） |
| --- | --- | --- | --- |
| 1 / reference | 4524567，C0/75秒 | [7prp45ox](https://wandb.ai/mint_leaf258/mfm_model_v3_development/runs/7prp45ox) | runs/model_v3_20261026/performance_manual_R1_ABBA_v1/member_1/child/configuration.json |
| 2 / candidate | 4524568，C0/76秒 | [42kaw4ai](https://wandb.ai/mint_leaf258/mfm_model_v3_development/runs/42kaw4ai) | runs/model_v3_20261026/performance_manual_R1_ABBA_v1/member_2/child/configuration.json |
| 3 / candidate | 4524569，C0/75秒 | [e1zfuz62](https://wandb.ai/mint_leaf258/mfm_model_v3_development/runs/e1zfuz62) | runs/model_v3_20261026/performance_manual_R1_ABBA_v1/member_3/child/configuration.json |
| 4 / reference | 4524570，C0/75秒 | [tekx2m3f](https://wandb.ai/mint_leaf258/mfm_model_v3_development/runs/tekx2m3f) | runs/model_v3_20261026/performance_manual_R1_ABBA_v1/member_4/child/configuration.json |

四份原配置中 /model、/data_version、/source_sha256 完整保留。共同本地执行代码为 9e16d4c5a15c558051499d3dc0c55c9bd3787734，原公开方法 [8147f44b](https://github.com/mint258/MFM/commit/8147f44baa1ea1ecc3822af7affd0a95401ed248)，seed均为0。原Native数据manifest为 /share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013/training_inputs_v1/manifest.json，SHA 2f69b672350744369b08c672b62e3d276487714abc97b766a12140ec5af59997；view SHA 138daeaccd91a627b7e80ea5f1b032721438331f28d0244f764c4e10b5f1bfaf，sampler-contract SHA ecb67948413fe6b1a507ecec8e95bc864fa439eb7be09e1f1b174e105d0da50e。这不是D5/D6最终数据权威；具体每份配置raw SHA、Root closure和实际code/data/seed绑定均在compact evidence中。v23的manual/auto R2及S10000原配置/来源链继续保留，不改写旧结果。

CPU4524571实际C0/6秒：四SDK各**22行step1–22（2warmup+20measured）**，按原single logger从保存steps投影，与原生config全字段、role、自动last-leaf summary、exit0及完整framing/EOF逐项比较，原字节前后闭合。SDK没有额外gradient_norm/input_receipt字段，也没有把3976的20+500门伪造成22行之外的history。

实际4524572和4524573各C0/20秒，明确2+2选择同步到 mint_leaf258/mfm_model_v3_development。四run均finished/22行/step1–22，原SDK与旧状态保留；远端独立读回范围是路由、state、行数和step端点，没有另行逐metric比较。已知online为**78=原74+本次4**，不是作者API全量重盘，也不自动等于这些run的集中CSV/HTML归档完成。四个独立输出holds已由Root实际释放，合计8GiB；其他entries/principals未变，原SDK/结果未删除。

## 新几何候选：源码与CPU全套闭合，GPU完整失败

显式opt-in模式 residual_expansion_fp32_v1 已在独立分支 model-v3-geometry-fp32-candidate-20261028-v1 发布：

- 本地执行候选 03e26bea6a29ef96ba5611760763329207212741；公开 [498ecbe7](https://github.com/mint258/MFM/commit/498ecbe7e88b1468067dde5692c10735fcadf2ea)；精确tree 2d3b8f17e06d73bc2bc47745ccde982625646dd0。
- GPU4524579实际FAILED1:0/64秒，全48中15通过/33失败、0errors/skip，192FP32/0FP64、512geometry/2304projection完整；Root已闭合1198current refs和资源，不采纳。
- CPU4524576实际C0/178秒，完整**116模块、2816 PASS、3项原optional SKIP、0FAIL/0ERROR**；全部runtime源码前后及当前绑定闭合。这是该独立候选分支全套，不冒充训练runtime另一代码范围的回归。
- 模式缺省仍legacy；仅显式改变encoder距离primitive，head/QKV/池化/参数/H0维度不变。TwoDiff、split-product、balanced重建和解析梯度的CPU工程检查不证明CUDA物理通过或普适正确舍入，FP32有限域/下溢限制继续保留。

原projection4550及passive4563的**12 PASS / 36 FAIL**不变；原正式C4的**21 PASS / 27 FAIL**仍单独保留，均无adoption，abs1e-5/rtol0未放宽。v23已闭合的CPU4564保存观测分析也继续保留：无新模型调用，H0/坐标局部差异不构成全模型因果排序。

## 全TRAIN计数不能代替checkpoint-off显存准入

CPU4524574实际C0/8秒，仓库检查与计数来源前后闭合；该父没有模型训练或显存实测。

| 原计数范围 | 实际值 |
| --- | ---: |
| base records | 11,104,772 |
| 每base的views | 3 |
| 全局最大native atoms/record | 712 |
| 最大singleton padded cost | 1,520,832 |
| singleton cost超过500k的records | 21 |
| 前500更新是否包含全局最大项 | 否 |

500k是原sampler目标，不是硬singleton上限，原singleton_no_discard政策未改。前500更新的可见范围不能外推全TRAIN/all-off显存安全；计数公式不是GPU内存测量。本次不削减人口、不丢大分子、不隐式扩容，也不授予all-off准入。

## 完整阶段0–7矩阵继续保留

| 原阶段/范围 | 已有证据与本次更新 | 尚未完成 |
| --- | --- | --- |
| 0 代码审阅 | 6层512/H0及兼容实现；整合训练链121模块2905PASS+3原SKIP；另有本次独立geometry116模块2816PASS+3原SKIP | 新组合仍须精确源绑定完整回归；不同分支/范围不互冒，工程通过不等于科学验收 |
| 1 性能测量 | 原短程/容量观察及本次R1完整ABBA校准 | GPU型号/批大小/工作负载完整覆盖；A00无提速，不替代真实checkpoint-off和相应容量证据 |
| 2 等价提速与bf16 | manual/auto R2的20+500和日志已闭合；本次A00 R1及四SDK闭合 | 真正checkpoint-off/A1、A5及三类卡完整覆盖；代理S的fp32/bf16各两个种子、各2万步，曲线包络及去噪RMSE差异不超过2%验收；4090的4558/原1338在v40仍PENDING |
| 3 标签、预测头与损失 | 工程实现/恢复、passive逐位控制、新geometry源码与CPU全套 | 正式C4仍21/27，projection仍12/36，新geometry GPU48为15通过/33失败，仍未达标；真实D3全字段1000分子过拟合、各卡SDP/真实标签验收 |
| 4 开发评估 | 旧S B3与Native S10000各自完整9×2及Native日志/同步闭合 | 后续预定端点/模型各自评估；单seed非seed SD，fallback不是D5选择，旧B3非Native同条件学习曲线锚点 |
| 5 架构与预测头对比 | 实现、预注册、失败诊断保留 | 真实D5的C1六次/C3四次、预测头九次/池化一次、约六次重复及seed SD、600万样本预算平台 |
| 6 训练配方 | 配置/决策及proxy/full/恢复工程入口接通 | 19项真实LR/B/WSD/SDP搜索、完整有效TRAIN preclip p99、D6 S/P至64M倍增平台/1SD/B*较大值及超过2倍报告 |
| 7 冻结与交接 | 合成6×512真实CLI更新→安全CP→新进程恢复→H0/随机/ACK链 | 真实120k/k2/1M E2E、全数据/科学验收、用户确认最终recipe/B*、最终tag/HANDOFF/PR与整合验收 |

数据线最新STATUS头部为“2026-10-28单日打包与全量继续”，日级生产持续推进；D1仍未joint-freeze，D1–D7未最终交付。模型线当前仍仅S/synthetic，不把数据线限定诊断或新进展当D3/D5接受；数据线动档也没有加入模型GPU runtime pins。

## 点时成本

历史v40采集于 **2026-10-27T22:13:43.064159+00:00**，**543父（389CPU、154GPU）**，allocated CPU **1,648,528核秒**、GPU节点作业分配时间 **80,270秒**。4574/4576已计入，4575属于数据线而非本模型任务。该v40时点模型活动仅4521338/4524558，均在compute20 PENDING，无新GPU结果。

账本不是利用率、金额或整份目标的最终成本；旧失败/重试保留，释放hold不删除历史成本。本版新增的实际发布与GPU负结果见下节及compact证据；后续真实作业/审计另计，最终recipe/B*仍未冻结。未启动学校正式预训练，未作最终冻结或交接完成声明。


历史v24方法归档在新GPU执行前完成；其原报告和原失败均保持，v25本节以后记录新实际结果。


## 新GPU4579的完整负结果与下一定位

Root已实际完成独立闭合：48例、1198个current source/control refs、18条发布证据及完整private/process cleanup均通过；实际作业仍是FAILED1:0，物理15PASS/33FAIL，不把metadata闭合升级为实验成功。终端NPZ在login仅stat，未解码或重新哈希。

两轮98份RESULT/case JSON由Root独立重哈希比较：4共同通过、11失败转通过、8通过转失败、25共同失败；1872字段×变换观测各自完整，失败73→56。新失败为extensive5、dipole34、magnitude17，其余10字段三变换全通过。两seed通过数6→13及6→2，非单调改善；不选seed或头策略。保存的失败argmax均graph row2/native32，不能排除其他行较小的超限分量。最大误差之一为2.5928020477294922e-5。

既有H0/F64头/量化诊断已核，下一必要信息仅是当前geometry同forward两独立dipole头的H0→q→center/relative/product/moment/norm端口。计划复用原被动框架，以4579全部2496终端逐bit为必要对照，保留全48和原物理门槛；按旧产物估算含16MiB余量459789432B，小于512MiB，但新捕获尚未执行。该计划针对51条dipole类失败，诊断尚未执行，另5条extensive不由该头局部实验解释。

## Head-off实际进展与本轮工作边界

4524580保持原9e16/public8147、NativeS8M/seed0，仅head_checkpointing=False，distance/backbone=True。固定20批前向/全部named-gradient gate实际pass；截至本稿源点500步仍RUNNING，无完整R2/R1提速结论。两SDK审计适配已冻结并通过Root静态检查，payload reader与exact-copy transport保留原字节；实际CPU审计、同步及新ABBA均须等待新数值门真实闭合。

最新已登记账本v41点时：2026-10-27T22:37:57.117248+00:00，546父（390CPU、156GPU），allocated CPU1651680核秒、GPU节点作业分配80458秒；其active包含4580与旧两PENDING。它是历史点时且非利用率/最终成本，后续真实C0/审计/新GPU另计。完整阶段0–7目标及D1–D7最终交付仍未完成。
