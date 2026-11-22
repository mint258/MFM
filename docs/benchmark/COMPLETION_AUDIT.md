# 下游授权范围完成审计

最近原生观测为2026-11-22 20:07 CST，**尚未全部完成**：必需 C1 确认配置已闭合173/175；8616在CPU11已复用原19折并新增闭合2折，达到21/25，8617保留原17折并等待串行启动；总计还缺12折。当前正常生产链为8630→8631→8632→8633。下表按[11/19指示](USER_DIRECTIVE_20261119.md)、[11/18指示](USER_DIRECTIVE_20261118.md)及[BENCHMARK_PLAN](BENCHMARK_PLAN.md)逐项对应；“已闭合”引用原生产记录及当前已发布代码/交付状态，不重跑科学计算、重算统计或数值读回。

| 要求 | 状态 | 生产记录与交付依据 |
|---|---|---|
| 授权只含B0、B1、C1及B2环境/固定100推断；全量B2、B3/B4、预训练与付费服务器不启动 | 保持 | 当前[native索引](../../workflows/benchmark_evaluation/native_jobs_20261120.json)、执行指示与PR范围；C2/C3/readout/微调属于未授权后续阶段 |
| 五个匿名暂缓终点在任何B1拟合前作完整清单校验，不公开身份 | 已闭合并保持 | B0统一入口active_evaluation_scope、严格select_active_tasks(...,verify_full_inventory=True)及各原生产binding中的完整清单证明；当前96候选 |
| 适用域使用原闭壳层/电荷/元素/3–200重原子/来源几何规则，按原因报告过滤数量 | 已闭合并保持 | [B0.DELIVERY.json](../../configs/benchmark_data/B0.DELIVERY.json)指向原domain_counts与封存manifest；不根据模型结果改变规则 |
| ExpansionRx/ASAP盲榜单保留完整TEST，域外用预先指定TRAIN均值 | 已闭合并保持 | 原盲测binding、B1_filter_impact.csv及C1首次正常统计；各模型保留实际可用特征人口及原TRAIN均值 |
| RF-ECFP4、LightGBM-RDKit2D、Chemprop v2按全集/保留/剔除部分报告 | 已闭合 | [B1_filter_impact.csv](../../results/benchmark/B1_filter_impact.csv)，原7430生产记录1140影响行；不是独立重评分 |
| B1一次筛选，冻结任务名单及角色 | 已闭合并保持 | [B1_task_screen.csv](../../results/benchmark/B1_task_screen.csv)与原SHA；7430：55 RETAIN/34 APPENDIX/6 EXCLUDE/1历史机制未决。Git文件历史确认CSV及SHA均只在92759d8一次写入 |
| B1所有必需神经第二种子确认及实际训练重做例外 | 已闭合 | 7462正常确认→7536仅格式导出；17项全部闭合，原16项显著改善中15项复现、HLM未复现，另含7338的¹H训练重做确认；冻结名单不回改 |
| B0统一入口和共享读取器，不复制数据库 | 已闭合并保持 | B0统一入口标记all_scopes_production_closed；6961 COMPLETED/0:0，双方scope最终handoff；原生产数据库/权重未复制 |
| 下游统一S′/UFF、原流程最多3个实际构象、不补足，不重建PM7优化 | 已闭合并保持 | B0 uniform_Sprime_producer、uniform_Pprime_chain与封存交付；378976实际构象，READY378636/PARTIAL340；未来QM为0 |
| P′是UFF几何上的原PM7/xTB字段，分子67字段、原子38+RDKit37；单位/原子序/掩码/缺失保留 | 已闭合并保持 | 原SharedB0Reader/PprimeReader和C1特征binding、原科学源AST证明；缺失不由D、UFF能量或其他模型几何填补 |
| 宏观pKa取最强酸/最强碱；challenge+rawdataID、完整InChIKey剔除盲测TRAIN重叠 | 已闭合 | 原pKahub绑定与清单，宏观97614/实验微观0、TRAIN完整键排除79；作者目录分类不冒充全体物理位点分类 |
| 原子pKa仅单位点，保持冻结B1历史行，新批准定义只作C1附录替换 | 已闭合 | [批准补充协议](APPROVED_PKA_ATOMIC_SUPPLEMENT_20261121.md)、7644 C0原生产；TRAIN5465/盲测9、P′4347/9；不分配多位点实验微观值、不重筛B1 |
| NMR使用作者原nmrshiftdb2-2018划分，显式H/原子序/重复谱保持 | 已闭合 | [NMR来源与划分](NMR_SPLIT_AND_LITERATURE.md)；6856完成唯一测试规模核对，7803原生原子身份/掩码恢复闭合；不重建划分、不平均重复观测 |
| NMR HOSE只引用同划分；CSTShift仅带DFT输入参考上限 | 已闭合 | 上述文献表使用作者Table3/100%覆盖；HOSE2.85/0.33ppm；不把整TEST文献数值冒充域内重跑值 |
| Joung只用scaffold/发色团外推，保留发色团与溶剂角色和gas标志 | 已闭合 | [Joung协议](JOUNG_INPUT_PROTOCOL.md)、原两组件binding及5×5外推划分；不使用随机划分主结果 |
| PPE以残差为主，C7报告绝对G4MP2与Δ目标，PPE包含Benson经典对照 | 已闭合 | 原7083正常PPE经典生产与[PPE_native_classical_baselines.csv](../../results/benchmark/PPE_native_classical_baselines.csv)、原reference任务binding |
| C1在分子端点比较D/P′/P′+D×LightGBM/TabPFN，原子仅LightGBM | 主统计已闭合，最终确认待闭合 | 8208 C0/3:41，104来源/561主行，551已报告/10原未决；最终只按批准补充替换历史原子占位 |
| 默认seed20261025，只有最终显著神经比较或实际训练重做才补seed20261026；传统ML一粒种子 | 部分闭合，仍待2配置 | 已闭合B1的17项；C1原175项固定计划/43组，当前173闭合。8616/8617只补原失败来源6/8折，保留原19/17折，无第三种子或梯度回滚重训 |
| 原官方划分按完整分子1000次配对bootstrap，无官方划分5×5 scaffold+Tukey，默认/文献超参不搜索 | 已闭合主统计，新增确认待正常生产 | 原7430/7462/8208正常生产及注册比较；8630将首次汇总所需seed26证据，不重算原primary |
| 预训练清单可得则完整InChIKey排除TEST重叠，不可得必须明确未检查 | 实现已闭合，最终表待生产 | 原8178闭合覆盖；TabPFN清单NOT_OBTAINED/未检查，LightGBM不适用；不声明不存在重叠 |
| B2独立环境/版本或commit/权重来源与许可/固定100输出维度 | 已闭合 | [BASELINE_AVAILABILITY.md](BASELINE_AVAILABILITY.md)及原SHA，5f6cf64最终写入后未改；14模型：7可用/4未决/1权重未公开/2需权限，UMA-S由用户申请 |
| 修复上限及显式未决，不把健康等待伪装未决；九格TDC/ASAP不作第三次修复 | 保持 | 原失败及可选路径manifest保留，九格capped未决继续；当前两恢复拟合有实际活跃句柄，按科学安全边界继续 |
| 后续入口真实磁盘/inode/UID配额与同行future、实际TimeLimit收尾、自有子树回收 | 部署验证已闭合，生产待运行 | CPU11模型实际准入；8629 C0/2秒、系统pidfd监督及私有/final布局原守卫startup实际通过，180秒收尾。原模块不变；shared_fs逻辑绑定未决，保留实际原共享守卫回退 |
| 新逻辑测试与合并前一次完整回归 | 已闭合当前求值库代码门 | 8580运行34模块/350例，实际私有334通过/16因缺pidfd跳过；8565系统监督同16例全过，8591核对覆盖；原版守卫7例仅执行一次；64dea938实际CI137196114740通过 |
| C1最终CSV分列种子/复现/覆盖/训练量/失败原因，正常生产唯一SHA，原字节发布 | 待闭合 | 当前8630确认→8631合并→8632首次最终CSV及唯一SHA→8633原字节发布；不能以排队或测试通过当作最终结果完成 |
| 每日一页、B1最终名单、每周一次成本、仅三个最终交付附SHA | 当前保持，最后日报待生产更新 | [日报](DAILY_20261122.md)、[B1名单日报](DAILY_20261120.md)、[W47成本](WEEKLY_COST_20261120.md)；仅B1筛选CSV、baseline availability和最终C1表附SHA，不重复周统计 |
| GitHub最终结果/代码/说明同步、PR待审、全项审计结论 | 待闭合 | 当前PR17草稿，64dea938 CI通过；只有上述正常生产及字节交付闭合后才转待审、声明目标完成 |

论文局限原句：**P 预训练模型在下游接收的是 UFF 几何。**

冻结名单证据来自Git原生文件变更历史，未读取或重算CSV数值。最终结果审计将消费正常生产端首次提供的关闭状态、行数及现有SHA，不另作数值QA或追加内容哈希。若进入下一自然周，按当时实际日期安排该周一次成本报告；本周已发布统计保持。
