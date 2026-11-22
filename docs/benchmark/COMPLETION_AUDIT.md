# 下游授权范围完成审计

编制：2026-11-23 00:31:26 CST；正常生产发布：2026-11-23 00:14:58 CST。本次授权的B0、B1、C1及B2环境/固定100验收结论已按协议闭合。C1最终735行，175项必需确认中174有效、1项按用户两次失败上限明确未完成；九格既定primary未决保持。正常生产链8830→8831→8832→8833均实际COMPLETED/0:0，自有子树退出。未复现/未完成不改变冻结B1角色。

| 要求 | 状态 | 权威生产证据与交付依据 |
|---|---|---|
| 授权范围为B0/B1/C1及B2环境和固定100推断 | 已按范围闭合 | 11/18–19指示、当前native索引；B2验收结果含明确未完成/权限项。全量表示、B3/B4及预训练仍属后续范围。 |
| 五个匿名暂缓终点在B1前完整清单排除 | 已闭合并保持 | 6889完整清单门及 select_active_tasks(...,verify_full_inventory=True)；不公开身份，当前候选96。 |
| 原适用域与分原因过滤数量 | 已闭合并保持 | B0.DELIVERY.json 指向原domain_counts/封存清单；闭壳层、电荷、元素、3–200重原子和来源几何规则保持。 |
| ExpansionRx/ASAP保留完整盲测TEST及TRAIN均值备用 | 已闭合并保持 | 原B1绑定、B1_filter_impact.csv、8208和8830正常生产；未用缺失66条的第二种子代替完整TEST。 |
| 三基线报告全集/保留/剔除子集影响 | 已闭合 | 7430首次生产的1140影响行已交付 B1_filter_impact.csv，未重评分。 |
| B1一次筛选后名单和角色冻结 | 已闭合并保持 | B1_task_screen.csv及原SHA：55 RETAIN/34 APPENDIX/6 EXCLUDE/1历史机制未决。CSV/SHA的Git变更历史仅92759d8一次写入；后续未改。 |
| B1必需神经第二种子及实际训练重做例外 | 已闭合 | 7462统计→7536只格式导出；17项闭合，原16项显著改善15复现/HLM未复现，另含7338的¹H重做确认；不改名单。 |
| B0统一入口/共享读取器，不复制数据库 | 已闭合并保持 | 6961 C0、两scope immutable、all_scopes_production_closed；SharedB0Reader/PprimeReader原位读取。 |
| 下游统一S′/UFF，原流程最多3个实际构象、不补足 | 已闭合并保持 | 378976实际构象：READY378636/PARTIAL340；RDKit2025.09.5、ETKDGv3/UFF及0.5Å去重沿原生产；未来QM=0。 |
| P′原字段、单位、原子序、掩码和缺失保持 | 已闭合并保持 | 分子67字段，原子38+RDKit37；原科学函数/数据绑定保持，不以D或UFF能量替代、不填补失败P′。 |
| 宏观pKa最强酸/碱、挑战+rawdataID及完整键排盲测TRAIN重叠 | 已闭合 | 宏观97614/实验微观0、TRAIN完整InChIKey排除79；原pKahub和SAMPL6/7绑定。 |
| 原子pKa仅单位点；新批准定义只作C1附录替换 | 已闭合 | 7644 C0，TRAIN5465/盲测9，P′4347/9；作者目录计数TRAIN5588/18838/5546、外部9/29/6并非全局物理位点分类。不改冻结B1历史行，不分配多位点微观值。 |
| NMR原2018作者划分、显式H、原子序及重复观测 | 已闭合 | 6856只做指定测试规模核对，7803原生身份/掩码恢复；¹³C5390谱/5055 ID、¹H2554/2527，不重划分或平均重复谱。 |
| NMR HOSE同划分；CSTShift仅DFT输入参考上限 | 已闭合 | NMR_SPLIT_AND_LITERATURE.md采用作者Table3/100%覆盖的HOSE2.85/0.33ppm；CSTShift单列DFT输入上限。 |
| Joung只做scaffold/发色团外推，保留溶剂角色和gas条件 | 已闭合 | JOUNG_INPUT_PROTOCOL.md、原5×5冻结折和两组件binding；不以随机划分作为主结果。 |
| PPE残差为主、C7绝对G4MP2及Δ、Benson经典对照 | 已闭合 | 7083首次204行PPE_native_classical_baselines.csv及原任务binding；不拟合基团值或重算PM7。 |
| C1分子D/P′/P′+D×LightGBM/TabPFN，原子仅LightGBM | 已按协议闭合 | 8208 C0首次104来源/561主行；8830→8831→8832→8833正常C0。最终735行，含174个有效第二种子行；原子7644只替换既有机制占位并列附录。 |
| 默认seed20261025；只为必需比较补seed20261026，传统ML一粒 | 已按协议闭合（1项明确未完成） | 175项必需计划逐项处理：174有效、1按两次修复失败上限未完成。8616/8654仅补6/8原缺折、保留19/17旧折；8356保留24折且未再执行补折模型，无第三种子。 |
| 官方划分1000次整分子配对bootstrap；无官方5×5 scaffold+Tukey | 已闭合 | 7430/7462/8208和8830正常生产及注册比较；未重算原primary；缺失66条的8356配置未作TEST交集或伪造复现。 |
| 预训练清单可得则完整InChIKey排重，否则标未检查 | 已闭合（限制明确） | 8178原实现门及8832首次最终manifest pretraining_overlap_status_explicit=true；TabPFN NOT_OBTAINED/未检查、LightGBM不适用，不声称无重叠。 |
| B2独立环境、版本/commit、权重来源/许可与固定100输出维度 | 本次验收结论已闭合 | BASELINE_AVAILABILITY.md及原SHA：14模型，7可用/4未决/1权重未公开/2需权限；UMA-S由用户申请，未成功项未冒充推断验收成功。 |
| 两次失败/四小时上限及保守默认 | 已执行 | 九格TDC/ASAP原上限未决保持。8356一折配额写入失败；报告8655严格拒绝TEST不齐，8760只定位身份。8792/8805两次准备失败后停止，未提交第三次或任何新补折模型；详见C1_CONFIRMATION_FAILURE_CAP_20261123.md。 |
| 真实磁盘/inode/UID配额、真实TimeLimit收尾及自有子树回收 | 已闭合并保留迁移限制 | 新入口真实startup与至少180秒收尾、OS pidfd/subreaper；8616/8654及8830–8833 footer证明children_exited且原身份消失。shared_fs逻辑/share与实际/share/home仍明确未决，沿已授权的实际原共享守卫回退。最后本线写入后原版release清空自身future，保留文件。 |
| 新增逻辑测试与合并前完整回归 | 当前采用库已闭合 | 采用原已验证350例：334私有通过+相同16例系统OS通过，8591核对部署覆盖；原守卫7例仅8565执行一次。未采用的部分C0续接准备8792/8805均失败（后者355例有1项环境路由fixture失败/16跳过并摘要KeyError）；已回退原验证库，未激活补折。最终提交CI见PR17。 |
| C1最终CSV列种子/复现/覆盖/训练量/失败原因；唯一SHA和原字节交付 | 已闭合 | 8832首次FINAL_C1_RESULTS_CLOSED：561原主行+174有效第二种子=735行，175必需确认/17既有Chemprop确认；8833首次字节发布。仅复制生产端CSV、现有唯一SHA与注册比较；无额外数值QA或内容哈希。 |
| 每日一页、B1最终名单、每周一次成本、仅三个最终交付附SHA | 已闭合 | DAILY_20261123.md、B1名单DAILY_20261120.md、W47的11/20快照和新W48唯一WEEKLY_COST_20261123.md。W48本线4个分配合计0.060000核时、0 GPU时；仅B1筛选表、availability、最终C1表附SHA。 |
| GitHub结果/代码/说明同步，PR待审及逐项完成审计 | 本提交交付，审阅/CI状态见PR | 当前文件即本次完整交付内容，PR17承载最终提交与检查。最终生产/字节发布已实际C0，本审计不把旧原生C0误作缺折配置已完成；PR仅在最终检查通过后转待审。 |

[最终C1表](../../results/benchmark/C1_results.csv) · [注册比较](../../results/benchmark/C1_second_seed_registered_comparisons.csv) · [失败上限记录](C1_CONFIRMATION_FAILURE_CAP_20261123.md) · [当前日报](DAILY_20261123.md) · [W48成本](WEEKLY_COST_20261123.md) · [原生索引](../../workflows/benchmark_evaluation/native_jobs_20261120.json) · [PR17](https://github.com/mint258/MFM/pull/17)

论文局限原句：**P 预训练模型在下游接收的是 UFF 几何。**

本审计仅消费正常生产端关闭状态、原始行数与已生成SHA及原生记账/进程证明；没有重新评分、CSV数值解析、二次几何/标签读取或新增内容哈希。物理和Git的其他工作线STATUS前缀均保留；本线future在最后写入后清空，配额发布器及其他工作线保持。
