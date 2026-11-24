# 已完成 R0 特征缓存清理提案（已批准执行）

16:17 CST 更新：用户已明确批准；12个精确缓存于16:13:56 CST完成unlink，实际释放3081236480B。原checkpoint、预测/读出、统计/bootstrap和3个manifest保留。已按同字节结算原闭合组件/full/joint，原GPU20 worker281103自行恢复并从1076288推进至1077344样本。[实际清理与恢复记录](../../results/d_recipe/R0_approved_cache_cleanup_and_L1_native_resume_20261124.json)。以下保留原提案内容；历史的“待批/未删除”描述仅指批准前。

2026-11-24 13:48 CST。**尚未删除任何文件。** 完整 D 任务继续，最终配方未冻结。

原 L1 任务 4539402 已在 GPU20 从原1M完整状态续接；原生配额守卫暂停在 1,076,288 样本。实际原 worker 281103 / UID1278 / start_ticks67356059 / 原job cgroup仍在，状态T；未重启、未手工发恢复信号。CPU4539403/404仍等待依赖。

拟仅删除已完成 D-R0 seed0/3M 的12个开发特征缓存文件，物理共 **3,081,236,480字节（3.081GB）**。根路径：

`/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/full/native_stage1/D-R0_seed0_3M/development_layers`

| 子目录 | 精确文件名 | 物理字节合计 |
|---|---|---:|
| expansionrx | layer3.pt、layer4.pt、layer5.pt、layer6.pt | 1197621248 |
| cyp_isoform | layer3.pt、layer4.pt、layer5.pt、layer6.pt | 313851904 |
| qm9 | layer3.pt、layer4.pt、layer5.pt、layer6.pt | 1569763328 |

完整路径、inode、设备、UID、单硬链接、mtime及字节见[精确清单](../../results/d_recipe/R0_completed_cache_cleanup_proposal_20261124.json)。清理前重新核对，只逐个unlink上述文件，不递归删除。3个manifest.json保留，并在CURRENT记录缓存已退役；不得因缺缓存重新前向。

R0主读出、层3–6读出与F64表征诊断均已完成；复用原闭合结论，没有重算。[原层读出](../../results/d_recipe/diagnostics/D-R0_seed0_3M/layer_readout_summary.json)、[原表征统计](../../results/d_recipe/diagnostics/D-R0_seed0_3M/representation_statistics.json)。保留全部checkpoint、预测、读出模型/分数、统计、bootstrap、输入和报告；原R0 3M checkpoint的文件存在性已核实。后续L1复用R1对照；最终A/B/C消费选定的冷9M终点，不使用本缓存。

本次共享盘UID余量308075278336B，原静态守卫要求309136036573B，差1060758237B。按该快照清理后，静态守卫余量约2020478243B；仅供提案估计，须由原运行守卫重新判断。先实际清理，再按实际释放字节结算已闭合R0组件/full/joint；否则peer守卫会把减少的已占空间重新算作未来增长。100GB底线、额外8GiB、5秒新鲜度、全部缓冲/活动槽及其他owner预算不变，不热改冻结运行配置。

Lustre整盘虽有约39.76TB余量，本UID只有1067335680B，低于既有守卫最小116589934592B，因此未迁移、未新增传输。

**批准依据**：TASKBOOK第3节把“需要删除本任务 scratch 以外的文件”列为必须询问的条件；第9节及HPC技能11-22也要求保留旧输出。本提案是持久缓存删除，需明确批准。未批准时保留文件和当前训练进程，等待配额恢复。
