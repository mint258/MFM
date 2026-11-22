# 开发面板完整 D3 已闭合（2026-11-23）

用户明确选择既有B6固定原坐标补H、不生成新构象；政策与完整原答复见Root `docs/d_recipe/H_POLICY_20261123.md`。旧QM9 component（10473成员）原样复用，新ExpansionRx component覆盖原5278成员；既有merge现按原15751成员顺序、ID、划分及几何引用合并，完整source人口为RAW_COMPLETE。

| 原生产步骤 | 原生结果 | 证据 |
| --- | --- | --- |
| H错误分类新2项+原相关20项测试 | CPU11/4539054，22tests/0.280秒，0:0/8秒/1CPU | 原测试日志实际reap且children=[] |
| ExpansionRx B6固定原坐标补H | CPU11/4539057，0:0/1568秒/1CPU，03:39:22 CST结束，原cursor5278 | [原component清单](../../results/data_d_descriptors/development_D3_ExpansionRx_B6_20261123.json) |
| 原完整成员合并 | CPU11/4539061，0:0/3秒/1CPU，03:39:25 CST结束，原15751成员 | [原完整清单](../../results/data_d_descriptors/development_D3_full_20261123.json) |

原NFS完整清单：`/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/development/native_D3/merged/manifest.json`。原component仍正确声明complete_source_population=false（仅ExpansionRx），原完整合并为true，policy_by_dataset为qm9/native_only、expansionrx/B6_fixed_native_H。六个分子字段PMI1/2/3、PBF、体积、总SASA原F64/uint8状态保留；逐原子SASA及源atom对应只引用，不进入分子特征向量。

固定全部原有坐标；无新构象、D20重算、D4拟合或任务标签读取。原B6明确化学失败按原错误码保留缺失，不重试/补值；未知或坐标约束错误不掩盖。原共同512MiB预算内，合并程序自身给出的component_and_merge_peak_bytes=203909476。整体联合NFS38853537501B及所有同行预留不变，所有实存保留。

原生产监督器4169297/ticks2249574973及worker4169300/ticks2249574979在CPU11实际均ABSENT，无新信号/KILL。合并原resident日志明确OWNED_TREE_REAPED(root4171120,returncode0)与RESIDENT_TERMINAL0/remaining_children=[]，并非仅以batch状态推断退出。

这里只转录原生产者和合并清单；没有读数值数组或重新计算、拟合和独立QA。reception_acceptance=pending、current_C1_complete=false仍保留；最终A/B/C等待冻结选定终点及规定9M，不将完整输入当作下游模型结果。Root两个seed1继续完成原3M及逐seed比较。
