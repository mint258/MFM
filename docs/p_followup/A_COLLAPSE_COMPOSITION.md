# A：表示塌缩的组成来源检验

固定5000个VAL分子（原diagnose.validation_indices，seed20261112），组成取首允许构象、构象分析取全部允许k10。第3–5层取中间输出，第6层取out_norm之后；B1在共享投影器之前。新模型训练0。

所有指标以F64计算；逐元素原子统计流式累积，原子H不落盘。只暂存各构象mean(H)的F32值，完成该条件后删除。组成基底为既有D4元素参考基底计数，加总/重原子数；CEV_size只用两种大小计数。岭回归为按分子的5外折、5内折选alpha，折内标准化并拟合截距，候选1e-3到1e3。1000次分子配对bootstrap复用固定OOF预测，不重新拟合。CVF及CVF_res限有>=2允许构象的分子；权重按其实际构象记录。

|条件|状态|第6层CEV|第6层CVF_res|
|---|---|---:|---:|
|P0-S|COMPLETE|0.63139264404515|0.03448333126178847|
|P0-P|COMPLETE|0.1437701212672422|0.048796958382248824|
|R1-B0|COMPLETE|0.8593553741824935|0.000968095505241953|
|R1-A1|COMPLETE|0.8400300609036053|0.0017093825301742567|

|预注册假设|判定|配对差值及95%CI|
|---|---|---|
|A-H1|NOT_SUPPORT|{'value': -0.48762252277790785, 'ci95': [-0.5244515064549983, -0.45211177104247935], 'valid_bootstrap_replicates': 1000, 'reason': None}|
|A-H2|NOT_SUPPORT|{'value': 0.0193253132788882, 'ci95': [0.005613805239145614, 0.034111036984102415], 'valid_bootstrap_replicates': 1000, 'reason': None}|
|A-H3|MISSING|None|
|A-H4|NOT_SUPPORT|{'value': -0.014313627120460352, 'ci95': [-0.017902798089969387, -0.01085080417451835], 'valid_bootstrap_replicates': 1000, 'reason': None}|
|A-H5|NOT_SUPPORT|{'value': -0.674594573450787, 'ci95': [-0.7144690448222102, -0.6283755810911995], 'valid_bootstrap_replicates': 1000, 'reason': None}|
|A-H6|MISSING|None|

![CEV与CVF_res](../../results/p_followup/A_collapse_composition/composition.svg)

PC1相关和目标参照仅作描述，不追加检验或阈值扫描。逐条件来源、完整CI及逐字段目标参照见summary.json。缺失条件未由其他运行替换，待指定C/D侧线完成后只补其注册条件。组成解释率不等于独立的化学准确性或迁移收益证明。
